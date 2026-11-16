"""Build the static website from digests/*.md into _site/."""
from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

import markdown
import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
SITE = Path(__file__).resolve().parent

EXT = ["extra", "sane_lists", "toc", "md_in_html", "pymdownx.arithmatex"]
EXT_CFG = {"pymdownx.arithmatex": {"generic": True}}

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{title}</title>
<link rel="stylesheet" href="style.css">
<script>
window.MathJax = {{
  tex: {{inlineMath: [["\\\\(", "\\\\)"]], displayMath: [["\\\\[", "\\\\]"]], processEscapes: true}},
  options: {{ignoreHtmlClass: ".*|", processHtmlClass: "arithmatex"}}
}};
</script>
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head><body>
<header><a href="index.html" class="home">{site_title}</a><nav>{nav}</nav></header>
<main>{body}</main>
<footer>{nav}</footer>
</body></html>
"""


def md(text: str) -> str:
    return markdown.markdown(text, extensions=EXT, extension_configs=EXT_CFG)


def main():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    site_title = html.escape(cfg.get("site", {}).get("title", "arXiv digest"))
    subtitle = html.escape(cfg.get("site", {}).get("subtitle", ""))

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copy(SITE / "style.css", OUT / "style.css")
    (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    (OUT / ".nojekyll").write_text("")

    files = sorted((ROOT / "digests").glob("*.md"))
    dates = [f.stem for f in files]

    for i, f in enumerate(files):
        prev_ = f'<a href="{dates[i-1]}.html">← {dates[i-1]}</a>' if i > 0 else "<span></span>"
        next_ = f'<a href="{dates[i+1]}.html">{dates[i+1]} →</a>' if i + 1 < len(files) else "<span></span>"
        nav = f'{prev_}<a href="index.html">all</a>{next_}'
        (OUT / f"{f.stem}.html").write_text(
            PAGE.format(title=f"{site_title} · {f.stem}", site_title=site_title, nav=nav, body=md(f.read_text()))
        )

    items = []
    for d in reversed(dates):
        tops = ""
        data = ROOT / "data" / f"{d}.json"
        if data.exists():
            j = json.loads(data.read_text())
            byid = {p["id"]: p for p in j.get("ranked", [])}
            tops = "".join(
                f"<li>{md(byid[i]['title'])[3:-4]}</li>" for i in j.get("picks", []) if i in byid
            )
        items.append(f'<li class="day"><a href="{d}.html"><strong>{d}</strong></a><ul>{tops}</ul></li>')
    body = (
        f"<h1>{site_title}</h1><p class='sub'>{subtitle}</p>"
        + (f"<p><a class='latest' href='{dates[-1]}.html'>Latest digest →</a></p>" if dates else "<p>No digests yet.</p>")
        + f"<ul class='days'>{''.join(items)}</ul>"
    )
    (OUT / "index.html").write_text(PAGE.format(title=site_title, site_title=site_title, nav="", body=body))
    print(f"Built {len(files)} digest page(s) into {OUT}")


if __name__ == "__main__":
    main()
