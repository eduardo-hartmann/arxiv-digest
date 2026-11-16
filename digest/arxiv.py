"""Fetching from arXiv: daily RSS announcements, PDFs, and PDF -> text."""
from __future__ import annotations

import datetime as dt
import re
import time
from pathlib import Path

import feedparser
import requests

RSS_URL = "https://rss.arxiv.org/rss/{cat}"
PDF_URL = "https://arxiv.org/pdf/{aid}"
ABS_URL = "https://arxiv.org/abs/{aid}"

ID_RE = re.compile(r"(\d{4}\.\d{4,5})")
CODE_RE = re.compile(
    r"https?://(?:www\.)?(github\.com|gitlab\.com|huggingface\.co|zenodo\.org|bitbucket\.org|codeberg\.org)/[^\s\)\]\}>,;\"']+",
    re.I,
)


def _ua(contact: str) -> dict:
    ua = "personal-arxiv-digest/1.0"
    if contact:
        ua += f" (mailto:{contact})"
    return {"User-Agent": ua}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def code_links(text: str) -> list[str]:
    seen, out = set(), []
    for m in CODE_RE.finditer(text or ""):
        url = m.group(0).rstrip(".")
        if url.lower() not in seen:
            seen.add(url.lower())
            out.append(url)
    return out


def fetch_category(cat: str, contact: str = "") -> tuple[list[dict], dt.date | None]:
    """Return (papers, announcement_date) for today's announcement of `cat`."""
    r = requests.get(RSS_URL.format(cat=cat), headers=_ua(contact), timeout=60)
    r.raise_for_status()
    feed = feedparser.parse(r.content)

    ann_date = None
    pp = feed.feed.get("published_parsed") or feed.feed.get("updated_parsed")
    if pp:
        ann_date = dt.date(pp.tm_year, pp.tm_mon, pp.tm_mday)

    papers = []
    for e in feed.entries:
        m = ID_RE.search(e.get("link", "") or e.get("id", ""))
        if not m:
            continue
        aid = m.group(1)
        summary = e.get("summary", "") or e.get("description", "")
        atype = e.get("arxiv_announce_type")
        if not atype:
            mt = re.search(r"Announce Type:\s*(\S+)", summary)
            atype = mt.group(1) if mt else "new"
        abstract = re.split(r"Abstract:\s*", summary, maxsplit=1)[-1]
        authors = e.get("dc_creator") or e.get("author") or ""
        cats = [t.get("term") for t in e.get("tags", []) if t.get("term")]
        papers.append(
            {
                "id": aid,
                "title": _clean(e.get("title", "")),
                "authors": [a.strip() for a in re.split(r",\s*", _clean(authors)) if a.strip()],
                "categories": cats or [cat],
                "abstract": _clean(abstract),
                "announce_type": atype.strip().lower(),
                "link": ABS_URL.format(aid=aid),
                "pdf": PDF_URL.format(aid=aid),
                "feed": cat,
            }
        )
    return papers, ann_date


def download_pdf(aid: str, dest: Path, contact: str = "") -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{aid}.pdf"
    if path.exists() and path.stat().st_size > 10_000:
        return path
    last = None
    for attempt in range(3):
        try:
            r = requests.get(PDF_URL.format(aid=aid), headers=_ua(contact), timeout=120)
            r.raise_for_status()
            if not r.content.startswith(b"%PDF"):
                raise RuntimeError("response is not a PDF")
            path.write_bytes(r.content)
            time.sleep(3)  # be polite to arXiv
            return path
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"could not download {aid}: {last}")


_REF_HEAD = re.compile(r"^\s*(references|bibliography|references and notes)\s*$", re.I | re.M)


def pdf_to_text(path: Path, max_chars: int) -> str:
    """Text of the paper with [[PAGE n]] markers; the reference list is removed."""
    try:
        import pymupdf as fitz
    except ImportError:  # older PyMuPDF
        import fitz

    doc = fitz.open(path)
    parts = []
    for i, page in enumerate(doc, start=1):
        parts.append(f"\n\n[[PAGE {i}]]\n{page.get_text('text')}")
    text = "".join(parts)

    # Drop the bibliography (keep any appendix that follows it).
    refs = list(_REF_HEAD.finditer(text))
    if refs and refs[-1].start() > 0.4 * len(text):
        start = refs[-1].start()
        tail = text[refs[-1].end():]
        appx = re.search(r"^\s*(appendix|appendices)\b.*$", tail, re.I | re.M)
        kept = ""
        if appx:
            marks = list(re.finditer(r"\[\[PAGE \d+\]\]", tail[: appx.start()]))
            kept = (marks[-1].group(0) + "\n" if marks else "") + tail[appx.start():]
        text = text[:start] + "\n[References removed]\n" + kept

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Text truncated for length]"
    return text
