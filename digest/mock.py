"""Fake model answers so the pipeline can be tested without Claude (DIGEST_MOCK=1)."""
from __future__ import annotations

import hashlib
import json
import re


def _h(s: str, mod: int) -> int:
    return int(hashlib.md5(s.encode()).hexdigest(), 16) % mod


def mock_answer(prompt: str) -> str:
    task = re.search(r"<!--\s*task:(\w+)\s*-->", prompt)
    task = task.group(1) if task else ""
    ids = re.findall(r"\[id:([^\]]+)\]", prompt)

    if task == "screen":
        return json.dumps([{"id": i, "score": _h(i, 11)} for i in ids if _h(i, 3) == 0])
    if task == "rank":
        return json.dumps(
            [
                {"id": i, "relevance": _h(i, 11), "field": _h(i + "f", 11),
                 "reason": "Mock reason: matches spectroscopy + ML interests."}
                for i in ids
            ]
        )
    if task == "brief":
        return json.dumps(
            [{"id": i, "summary": "Mock two-line summary of the paper's question and result.",
              "why": "Mock: related to your stellar-population work."} for i in ids]
        )
    if task == "deep":
        return (
            "**TL;DR.** Mock summary used for testing.\n\n"
            "#### Main question\nWhat sets the stellar ages of quiescent galaxies? [p. 1]\n\n"
            "#### Data & method\nDESI spectra fitted with an SPS emulator [§2, p. 3].\n\n"
            "#### Main result\nThe key result is in **Fig. 4** [p. 7]: ages correlate with $\\sigma_\\star$.\n\n"
            "#### Caveats\nThe authors note limited S/N below $10^{10}\\,M_\\odot$ [§5.1, p. 11].\n\n"
            "#### Why it matters to you\nDirectly comparable to contrastive spectral embeddings.\n"
        )
    if task == "learn":
        return "# Learned preferences\n\n## More of\n- (mock) spectroscopic SPS + ML\n\n## Less of\n- (mock) pure LLM benchmarks\n"
    return "mock"
