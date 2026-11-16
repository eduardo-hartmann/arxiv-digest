"""Assemble the daily digest as Markdown (renders on GitHub and on the site)."""
from __future__ import annotations

import datetime as dt

from .feedback import issue_link


def _authors(p: dict, n: int = 6) -> str:
    a = p.get("authors") or []
    return ", ".join(a[:n]) + (" et al." if len(a) > n else "")


def _meta(p: dict) -> str:
    bits = [f"*{_authors(p)}*", " · ".join(f"`{c}`" for c in p.get("categories", [])[:4])]
    bits.append(f"[arXiv]({p['link']}) · [PDF]({p['pdf']})")
    if p.get("code"):
        bits.append(" · ".join(f"[💻 code/data]({u})" for u in p["code"][:2]))
    if p.get("announce_type") and p["announce_type"] != "new":
        bits.append(f"_{p['announce_type']}_")
    return " · ".join(b for b in bits if b)


def _scores(p: dict) -> str:
    return f"score **{p['score']:.1f}** (you {p['relevance']}/10 · field {p['field']}/10)"


def _fb(repo: str | None, p: dict) -> str:
    if not repo:
        return ""
    return (
        f"<small>[👍 more like this]({issue_link(repo, '+1', p)}) · "
        f"[👎 not for me]({issue_link(repo, '-1', p)})</small>"
    )


def build(date: dt.date, stats: dict, picks, runners, highlights, rest, repo: str | None) -> str:
    L = []
    L.append(f"# arXiv digest — {date:%A %d %B %Y}\n")
    L.append(
        f"{stats['total']} papers announced in your categories · "
        f"{stats['ranked']} ranked on abstracts "
        f"({stats['full']} from {', '.join(stats['full_cats'])}, "
        f"{stats['promoted']} promoted from {stats['screened']} titles in {', '.join(stats['screened_cats'])}).\n"
    )
    if repo:
        L.append(f"<small>[💬 Leave a note for the agent]({issue_link(repo, 'note')})</small>\n")

    L.append("## Top picks\n")
    for i, p in enumerate(picks, 1):
        L.append(f"### {i}. {p['title']}\n")
        L.append(_meta(p) + "\n")
        L.append(f"> **Why it was picked:** {p['reason']} — {_scores(p)}\n")
        L.append(p.get("deep", "_Summary unavailable._").strip() + "\n")
        L.append(_fb(repo, p) + "\n")
        L.append("---\n")

    if runners:
        L.append("## Also worth a look\n")
        for i, p in enumerate(runners, len(picks) + 1):
            L.append(f"### {i}. {p['title']}\n")
            L.append(_meta(p) + "\n")
            L.append(f"{p.get('summary', '')}\n")
            why = p.get("why") or p["reason"]
            L.append(f"**Why you might care:** {why} <small>({_scores(p)})</small>\n")
            L.append(f"<details><summary>Abstract</summary>\n\n{p['abstract']}\n\n</details>\n")
            L.append(_fb(repo, p) + "\n")

    if highlights:
        L.append("## Big for the field, outside your core interests\n")
        for p in highlights:
            L.append(f"- **[{p['title']}]({p['link']})** — {p['reason']} <small>(field {p['field']}/10)</small> {_fb(repo, p)}")
        L.append("")

    if rest:
        L.append("## Everything else that was ranked\n")
        L.append(f"<details><summary>{len(rest)} more papers, by score</summary>\n")
        for p in rest:
            L.append(f"- {p['score']:.1f} · [{p['title']}]({p['link']}) — {p['reason']}")
        L.append("\n</details>\n")

    L.append(f"\n<small>Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC by Claude. "
             "Summaries can contain mistakes: check the cited pages before relying on a claim.</small>\n")
    return "\n".join(L)
