"""chat-export-md command-line interface."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .parsers import load
from .render import SOURCE, conv_tokens, write_all


def _date(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chat-export-md", description="Convert ChatGPT, Claude.ai and Gemini "
                                 "(Google Takeout) exports into clean Markdown files.")
    ap.add_argument("inputs", nargs="+", help="export .zip, folder, conversations.json or MyActivity.json")
    ap.add_argument("-o", "--out", default="chat-archive", help="output folder (default ./chat-archive)")
    ap.add_argument("--format", choices=["md", "jsonl"], default="md")
    ap.add_argument("--since", type=_date, help="only conversations on/after YYYY-MM-DD")
    ap.add_argument("--until", type=_date, help="only conversations before YYYY-MM-DD")
    ap.add_argument("--search", help="only conversations whose title or text contains this (case-insensitive)")
    ap.add_argument("--source", choices=["chatgpt", "claude", "gemini"], action="append", help="filter by source")
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="also write <name>.continue.md with the newest N tokens, ready to paste into another AI")
    ap.add_argument("--stats", action="store_true", help="only print counts, write nothing")
    ap.add_argument("--version", action="version", version=f"chat-export-md {__version__}")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            try:
                s.reconfigure(encoding="utf-8")
            except Exception:
                pass

    convs = []
    for inp in a.inputs:
        p = Path(inp)
        if not p.exists():
            print(f"not found: {inp}", file=sys.stderr)
            return 1
        convs += load(p)
    if not convs:
        print("No ChatGPT, Claude or Gemini conversations found in the input.", file=sys.stderr)
        return 1

    def keep(c):
        when = c.created or c.updated
        if a.since and (not when or when < a.since):
            return False
        if a.until and (not when or when >= a.until):
            return False
        if a.source and c.source not in a.source:
            return False
        if a.search:
            q = a.search.lower()
            if q not in c.title.lower() and not any(q in m.text.lower() for m in c.messages):
                return False
        return True

    convs = [c for c in convs if keep(c)]
    if a.stats:
        by = Counter(c.source for c in convs)
        print(f"{'source':<10}{'conversations':>15}{'messages':>11}{'≈ tokens':>13}")
        for src in sorted(by):
            cs = [c for c in convs if c.source == src]
            print(f"{SOURCE[src]:<10}{len(cs):>15,}{sum(len(c.messages) for c in cs):>11,}"
                  f"{sum(conv_tokens(c) for c in cs):>13,}")
        return 0
    stats = write_all(convs, Path(a.out), a.format, a.max_tokens)
    print(f"✓ {stats['conversations']:,} conversations, {stats['messages']:,} messages, "
          f"≈{stats['tokens']:,} tokens → {Path(a.out).as_posix()}/" + ("index.md" if a.format == "md" else "conversations.jsonl"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
