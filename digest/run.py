"""Daily pipeline: feedback -> fetch -> screen -> rank -> deep-read -> brief -> render.

Usage:
    python -m digest.run                 # normal daily run
    python -m digest.run --force         # regenerate even if today's digest exists
    python -m digest.run --fixture f.json --date 2026-11-17   # offline test input
    DIGEST_MOCK=1 python -m digest.run --fixture ...         # no Claude calls at all
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import yaml

from . import arxiv, feedback, llm, render

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
DIGESTS = ROOT / "digests"
DATA = ROOT / "data"
WORK = ROOT / "work"


def log(msg: str):
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}] {msg}", flush=True)


def fill(name: str, **kw) -> str:
    tpl = (PROMPTS / f"{name}.md").read_text()
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(kw.get(m.group(1), m.group(0))), tpl)


def fmt_paper(p: dict, abstract: bool = True) -> str:
    if not abstract:
        return f"[id:{p['id']}] {p['title']}"
    authors = ", ".join(p["authors"][:8]) + (" et al." if len(p["authors"]) > 8 else "")
    return (
        f"[id:{p['id']}] {p['title']}\n"
        f"Authors: {authors}\nCategories: {', '.join(p['categories'])}\n"
        f"Abstract: {p['abstract']}\n"
    )


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def fmt_feedback(entries: list[dict], n: int) -> str:
    if not entries:
        return "(no feedback yet)"
    lines = []
    for e in entries[-n:]:
        if e["verdict"] == "note":
            lines.append(f"- NOTE ({e['date']}): {e['comment']}")
        else:
            c = f" — comment: {e['comment']}" if e.get("comment") else ""
            lines.append(f"- {e['verdict']} \"{e.get('title') or e.get('id')}\"{c}")
    return "\n".join(lines)


def lookup_factory():
    cache = {}

    def lookup(aid):
        if not cache:
            for f in sorted(DATA.glob("*.json"))[-60:]:
                try:
                    for p in json.loads(f.read_text()).get("ranked", []):
                        cache[p["id"]] = p
                except Exception:  # noqa: BLE001
                    pass
        return cache.get(aid)

    return lookup


# ---------------------------------------------------------------------------


def fetch(cfg, fixture: str | None):
    if fixture:
        papers = json.loads(Path(fixture).read_text())
        for p in papers:
            p.setdefault("link", arxiv.ABS_URL.format(aid=p["id"]))
            p.setdefault("pdf", arxiv.PDF_URL.format(aid=p["id"]))
            p.setdefault("announce_type", "new")
        return papers, None

    allp, dates = {}, []
    full = set(cfg["full_categories"])
    for cat in cfg["full_categories"] + cfg["screened_categories"]:
        try:
            ps, d = arxiv.fetch_category(cat, cfg.get("contact_email", ""))
        except Exception as exc:  # noqa: BLE001
            log(f"WARNING: could not fetch {cat}: {exc}")
            continue
        if d:
            dates.append(d)
        log(f"{cat}: {len(ps)} entries")
        for p in ps:
            if p["announce_type"] not in cfg["announce_types"]:
                continue
            p["full"] = bool(full.intersection(p["categories"])) or p["feed"] in full
            if p["id"] in allp:
                allp[p["id"]]["full"] |= p["full"]
            else:
                allp[p["id"]] = p
    return list(allp.values()), (max(dates) if dates else None)


def screen(cfg, papers, ctx) -> list[dict]:
    if not papers:
        return []
    scored = {}
    for ch in chunks(papers, cfg["screen_chunk_size"]):
        prompt = fill(
            "screen",
            max=cfg["screen_max_forward"],
            interests=ctx["interests"],
            learned=ctx["learned"],
            papers="\n".join(fmt_paper(p, abstract=False) for p in ch),
        )
        try:
            for r in llm.ask_json(prompt, cfg["models"]["screen"], cfg["claude_timeout_s"]):
                scored[str(r["id"])] = float(r.get("score", 5))
        except Exception as exc:  # noqa: BLE001
            log(f"WARNING: screening chunk failed: {exc}")
    keep = sorted(scored, key=scored.get, reverse=True)[: cfg["screen_max_forward"]]
    byid = {p["id"]: p for p in papers}
    return [byid[i] for i in keep if i in byid]


def rank(cfg, cands, ctx) -> list[dict]:
    scores = {}
    for ch in chunks(cands, cfg["rank_chunk_size"]):
        prompt = fill(
            "rank",
            interests=ctx["interests"],
            learned=ctx["learned"],
            feedback=ctx["feedback"],
            papers="\n".join(fmt_paper(p) for p in ch),
        )
        try:
            for r in llm.ask_json(prompt, cfg["models"]["rank"], cfg["claude_timeout_s"]):
                scores[str(r["id"])] = r
        except Exception as exc:  # noqa: BLE001
            log(f"WARNING: ranking chunk failed: {exc}")
    w = cfg["weights"]
    out = []
    for p in cands:
        r = scores.get(p["id"], {})
        p["relevance"] = int(round(float(r.get("relevance", 0))))
        p["field"] = int(round(float(r.get("field", 0))))
        p["reason"] = (r.get("reason") or "Not scored.").strip()
        p["score"] = w["relevance"] * p["relevance"] + w["field"] * p["field"]
        out.append(p)
    out.sort(key=lambda p: (p["score"], p["relevance"]), reverse=True)
    return out


def deep_read(cfg, p, ctx):
    note = ""
    text = ""
    try:
        if os.environ.get("DIGEST_MOCK"):
            raise RuntimeError("mock mode: PDF download skipped")
        pdf = arxiv.download_pdf(p["id"], WORK / "pdf", cfg.get("contact_email", ""))
        text = arxiv.pdf_to_text(pdf, cfg["pdf_max_chars"])
    except Exception as exc:  # noqa: BLE001
        log(f"WARNING: no PDF text for {p['id']}: {exc}")
    if not text:
        note = ("\nNOTE: the PDF could not be retrieved; only the abstract is available. "
                "Say so at the top, keep it short, and cite [abstract] instead of pages.")
        text = "Abstract: " + p["abstract"]
    p["code"] = list(dict.fromkeys(p.get("code", []) + arxiv.code_links(text)))[:3]
    prompt = fill(
        "deep",
        interests=ctx["interests"],
        title=p["title"],
        authors=", ".join(p["authors"][:15]),
        id=p["id"],
        categories=", ".join(p["categories"]),
        text=text,
        pdf_note=note,
    )
    try:
        return llm.ask(prompt, cfg["models"]["summary"], cfg["claude_timeout_s"])
    except Exception as exc:  # noqa: BLE001
        log(f"WARNING: deep summary failed for {p['id']}: {exc}")
        return f"_Summary failed today ({exc.__class__.__name__}). Abstract:_\n\n{p['abstract']}"


def brief(cfg, runners, ctx):
    if not runners:
        return
    prompt = fill("brief", interests=ctx["interests"], papers="\n".join(fmt_paper(p) for p in runners))
    try:
        res = {str(r["id"]): r for r in llm.ask_json(prompt, cfg["models"]["brief"], cfg["claude_timeout_s"])}
    except Exception as exc:  # noqa: BLE001
        log(f"WARNING: briefs failed: {exc}")
        res = {}
    for p in runners:
        r = res.get(p["id"], {})
        p["summary"] = r.get("summary") or ""
        p["why"] = r.get("why") or ""


def learn(cfg, ctx, entries):
    prompt = fill(
        "learn",
        interests=ctx["interests"],
        learned=ctx["learned"],
        feedback=fmt_feedback(entries, 200),
    )
    try:
        new = llm.ask(prompt, cfg["models"]["learn"], cfg["claude_timeout_s"]).strip()
    except Exception as exc:  # noqa: BLE001
        log(f"WARNING: could not update learned preferences: {exc}")
        return
    if new.startswith("```"):
        new = re.sub(r"^```\w*\n|\n```$", "", new)
    if "# Learned preferences" in new:
        (ROOT / "interests_learned.md").write_text(new + "\n")
        ctx["learned"] = new
        log("Updated interests_learned.md")


def pick(cfg, ranked):
    d = cfg["deep_dive"]
    picks = [p for i, p in enumerate(ranked[: d["max"]]) if i < d["min"] or p["score"] >= d["min_score"]]
    n = len(picks)
    runners = ranked[n : n + cfg["runner_ups"]]
    shown = {p["id"] for p in picks + runners}
    rest = [p for p in ranked if p["id"] not in shown]
    highlights = sorted([p for p in rest if p["field"] >= 8], key=lambda p: p["field"], reverse=True)
    highlights = highlights[: cfg["field_highlights"]]
    hl = {p["id"] for p in highlights}
    rest = [p for p in rest if p["id"] not in hl]
    return picks, runners, highlights, rest


# ---------------------------------------------------------------------------


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--fixture", help="JSON list of papers to use instead of arXiv RSS")
    ap.add_argument("--date", help="YYYY-MM-DD (defaults to arXiv announcement date / today UTC)")
    args = ap.parse_args(argv)

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    WORK.mkdir(exist_ok=True)
    repo = os.environ.get("GITHUB_REPOSITORY")

    ctx = {
        "interests": (ROOT / "interests.md").read_text(),
        "learned": (ROOT / "interests_learned.md").read_text(),
    }

    # 1. feedback ---------------------------------------------------------
    try:
        new_fb = feedback.collect(lookup_factory())
    except Exception as exc:  # noqa: BLE001
        log(f"WARNING: feedback sync failed: {exc}")
        new_fb = []
    entries = feedback.read_log()
    if new_fb:
        learn(cfg, ctx, entries)
    ctx["feedback"] = fmt_feedback(entries, cfg["recent_feedback_in_prompt"])

    # 2. fetch ------------------------------------------------------------
    papers, ann_date = fetch(cfg, args.fixture)
    date = dt.date.fromisoformat(args.date) if args.date else (ann_date or dt.datetime.now(dt.timezone.utc).date())
    if not papers:
        log("No new papers today (weekend/holiday?). Nothing to do.")
        return 0
    out_md = DIGESTS / f"{date.isoformat()}.md"
    if out_md.exists() and not args.force:
        log(f"{out_md.name} already exists; use --force to regenerate.")
        return 0

    for p in papers:
        p["code"] = arxiv.code_links(p["abstract"])
    full = [p for p in papers if p.get("full", True)]
    others = [p for p in papers if not p.get("full", True)]
    log(f"{len(papers)} papers: {len(full)} full-ranked, {len(others)} to screen")

    # 3. screen + rank ----------------------------------------------------
    promoted = screen(cfg, others, ctx)
    log(f"Promoted {len(promoted)} from screening")
    ranked = rank(cfg, full + promoted, ctx)
    if not ranked or all(p["reason"] == "Not scored." for p in ranked):
        log("ERROR: ranking failed completely")
        return 1

    picks, runners, highlights, rest = pick(cfg, ranked)

    # 4. deep reads + briefs ---------------------------------------------
    for p in picks:
        log(f"Deep read {p['id']}: {p['title'][:70]}")
        p["deep"] = deep_read(cfg, p, ctx)
    log(f"Briefing {len(runners)} runner-ups")
    brief(cfg, runners, ctx)

    # 5. write ------------------------------------------------------------
    stats = {
        "total": len(papers),
        "ranked": len(ranked),
        "full": len(full),
        "full_cats": cfg["full_categories"],
        "screened": len(others),
        "screened_cats": cfg["screened_categories"],
        "promoted": len(promoted),
    }
    DIGESTS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    out_md.write_text(render.build(date, stats, picks, runners, highlights, rest, repo))
    keep = ("id", "title", "authors", "categories", "abstract", "link", "pdf", "announce_type",
            "relevance", "field", "score", "reason", "code", "summary", "why")
    (DATA / f"{date.isoformat()}.json").write_text(json.dumps({
        "date": date.isoformat(),
        "stats": stats,
        "picks": [p["id"] for p in picks],
        "runners": [p["id"] for p in runners],
        "ranked": [{k: p.get(k) for k in keep} for p in ranked],
    }, ensure_ascii=False, indent=1))
    log(f"Wrote {out_md.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
