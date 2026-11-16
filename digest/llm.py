"""Thin wrapper around the Claude Code CLI in headless mode (`claude -p`).

Claude is used as a pure reader/writer here: all tools are disabled, the input
is passed on stdin and the answer comes back on stdout. All networking and file
writing is done by the Python code, so text inside papers (which is untrusted)
can't make the agent run commands or touch the repo.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time

DISALLOWED = ",".join(
    [
        "Bash", "Edit", "Write", "Read", "Glob", "Grep", "WebFetch", "WebSearch",
        "NotebookEdit", "Task", "TodoWrite", "MultiEdit", "LS",
    ]
)
INSTRUCTION = (
    "The task is fully described in the input you receive on stdin. "
    "Do not use any tools. Reply with only the requested output."
)


class LLMError(RuntimeError):
    pass


def ask(prompt: str, model: str, timeout: int = 900, retries: int = 1) -> str:
    if os.environ.get("DIGEST_MOCK"):
        from .mock import mock_answer

        return mock_answer(prompt)

    exe = shutil.which("claude")
    if not exe:
        raise LLMError("Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code")

    cmd = [
        exe, "-p", INSTRUCTION,
        "--model", model,
        "--output-format", "text",
        "--max-turns", "2",
        "--disallowedTools", DISALLOWED,
    ]
    last = ""
    for attempt in range(retries + 1):
        try:
            res = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            last = f"timeout after {timeout}s"
        else:
            out = (res.stdout or "").strip()
            if res.returncode == 0 and out:
                return out
            last = f"exit {res.returncode}: {(res.stderr or out)[-800:]}"
        if attempt < retries:
            time.sleep(20)
    raise LLMError(f"Claude call failed ({last})")


def extract_json(text: str):
    """Pull the first JSON array/object out of a model answer."""
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1)
    for open_c, close_c in (("[", "]"), ("{", "}")):
        i, j = text.find(open_c), text.rfind(close_c)
        if i != -1 and j > i:
            try:
                return json.loads(text[i : j + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError("no valid JSON in model answer: " + text[:300])


def ask_json(prompt: str, model: str, timeout: int = 900):
    """ask() + extract_json(), with one retry on malformed output."""
    for attempt in range(2):
        out = ask(prompt, model, timeout)
        try:
            return extract_json(out)
        except LLMError:
            if attempt == 1:
                raise
            prompt += "\n\nIMPORTANT: your previous answer was not valid JSON. Output ONLY the JSON."
