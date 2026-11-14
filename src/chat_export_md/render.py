"""Write conversations as Markdown / JSONL."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List

from .parsers import Conversation
from .tokens import estimate

ROLE = {"user": "🧑 You", "assistant": "🤖 Assistant", "tool": "🛠 Tool"}
SOURCE = {"chatgpt": "ChatGPT", "claude": "Claude", "gemini": "Gemini"}


def slugify(text: str, n: int = 60) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:n].strip("-") or "untitled"


def conv_tokens(c: Conversation) -> int:
    return sum(estimate(m.text) for m in c.messages)


def _yaml(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def to_markdown(c: Conversation) -> str:
    fm = ["---", f"title: {_yaml(c.title)}", f"source: {c.source}", f"id: {_yaml(c.id)}"]
    if c.created:
        fm.append(f"created: {c.created.isoformat()}")
    if c.updated:
        fm.append(f"updated: {c.updated.isoformat()}")
    fm += [f"message_count: {len(c.messages)}", f"est_tokens: {conv_tokens(c)}", "---", ""]
    body = [f"# {c.title}", ""]
    if c.source == "gemini":
        body += ["> Google Takeout keeps Gemini prompts and replies but not chat threads, "
                 "so this file groups one day of activity.", ""]
    for m in c.messages:
        stamp = f"  ·  {m.time.strftime('%Y-%m-%d %H:%M')}" if m.time else ""
        body += [f"### {ROLE.get(m.role, m.role)}{stamp}", "", m.text, ""]
    return "\n".join(fm + body)


def continue_prompt(c: Conversation, max_tokens: int) -> str:
    """The newest messages that fit in max_tokens, with a header for the next assistant."""
    picked, used = [], 0
    for m in reversed(c.messages):
        t = estimate(m.text) + 8
        if picked and used + t > max_tokens:
            break
        picked.append(m)
        used += t
    picked.reverse()
    skipped = len(c.messages) - len(picked)
    head = [f"I'm continuing a conversation I had with {SOURCE.get(c.source, c.source)} titled \"{c.title}\".",
            "Below is the most recent part of it" + (f" ({skipped} earlier messages omitted)." if skipped else "."),
            "Read it, briefly confirm where we left off, then continue helping me from there.", "", "---", ""]
    body = []
    for m in picked:
        body += [f"**{'Me' if m.role == 'user' else 'Assistant'}:**", m.text, ""]
    return "\n".join(head + body)


def write_all(convs: List[Conversation], out: Path, fmt: str = "md", max_tokens: int = 0) -> Dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    used_names: Dict[str, int] = {}
    index = ["# Chat archive", "", f"{len(convs)} conversations.", "",
             "| Date | Source | Title | Messages | ≈ Tokens |", "|---|---|---|---:|---:|"]
    jsonl = []
    stats = {"conversations": 0, "messages": 0, "tokens": 0}
    for c in sorted(convs, key=lambda c: (c.created or c.updated).isoformat() if (c.created or c.updated) else ""):
        date = (c.created or c.updated).strftime("%Y-%m-%d") if (c.created or c.updated) else "undated"
        base = f"{date}-{c.source}-{slugify(c.title)}"
        n = used_names.get(base, 0)
        used_names[base] = n + 1
        name = base if n == 0 else f"{base}-{n + 1}"
        tok = conv_tokens(c)
        stats["conversations"] += 1
        stats["messages"] += len(c.messages)
        stats["tokens"] += tok
        if fmt == "jsonl":
            jsonl.append(json.dumps({"id": c.id, "source": c.source, "title": c.title,
                                     "created": c.created.isoformat() if c.created else None,
                                     "messages": [{"role": m.role, "text": m.text,
                                                   "time": m.time.isoformat() if m.time else None} for m in c.messages]},
                                    ensure_ascii=False))
            continue
        (out / f"{name}.md").write_text(to_markdown(c), encoding="utf-8", newline="\n")
        if max_tokens:
            (out / f"{name}.continue.md").write_text(continue_prompt(c, max_tokens), encoding="utf-8", newline="\n")
        safe_title = c.title.replace("|", "\\|")
        index.append(f"| {date} | {SOURCE.get(c.source, c.source)} | [{safe_title}]({name}.md) | {len(c.messages)} | {tok:,} |")
    if fmt == "jsonl":
        (out / "conversations.jsonl").write_text("\n".join(jsonl) + "\n", encoding="utf-8", newline="\n")
    else:
        (out / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8", newline="\n")
    return stats
