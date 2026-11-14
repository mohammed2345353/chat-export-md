# chat-export-md 🗂️

**Turn your ChatGPT, Claude and Gemini data exports into clean, searchable Markdown, and carry a conversation over to another AI when the first one hits its limit.**

[![CI](https://github.com/mohammed2345353/chat-export-md/actions/workflows/ci.yml/badge.svg)](https://github.com/mohammed2345353/chat-export-md/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

```text
$ chat-export-md chatgpt-export.zip claude-export.zip takeout.zip
✓ 1,284 conversations, 23,906 messages, ≈7,912,330 tokens → chat-archive/index.md

$ chat-export-md claude-export.zip --stats
source      conversations   messages     ≈ tokens
Claude                412      6,032    2,118,904
```

## The problem

- The official exports are big JSON files: ChatGPT's message tree, Claude's `chat_messages`, Gemini's Takeout activity log. They're hard to read and hard to search.
- When you hit a usage limit mid-conversation, there's no "continue in another assistant" button. Copying the chat by hand loses the code blocks and the structure.
- Your history is locked inside each app's own search, which is slow or missing.

## What you get

```
chat-archive/
├── index.md                                   # table: date · source · title · messages · ≈ tokens
├── 2026-11-01-claude-plan-a-trip.md           # YAML front matter + the whole conversation
├── 2026-11-01-claude-plan-a-trip.continue.md  # (with --max-tokens) paste-ready "continue here" prompt
└── 2026-11-03-chatgpt-fix-my-regex.md
```

Each file:

```markdown
---
title: "Fix my regex"
source: chatgpt
created: 2026-11-03T18:12:44+00:00
message_count: 6
est_tokens: 1840
---
# Fix my regex

### 🧑 You  ·  2026-11-03 18:12
…
```

## Install

```bash
pipx install git+https://github.com/mohammed2345353/chat-export-md
```

## Get your exports

| Service | Where |
|---|---|
| ChatGPT | Settings → Data controls → **Export data** (emailed .zip) |
| Claude.ai | Settings → Privacy → **Export data** (emailed .zip) |
| Gemini | takeout.google.com → select **My Activity → Gemini Apps** (JSON format) |

## Usage

```bash
chat-export-md export.zip                         # .zip, folder, conversations.json or MyActivity.json, auto-detected
chat-export-md a.zip b.zip -o ~/notes/ai          # several exports into one archive
chat-export-md export.zip --since 2026-10-01 --search "docker"
chat-export-md export.zip --source claude --max-tokens 6000   # + .continue.md files for moving to another AI
chat-export-md export.zip --format jsonl          # one JSON object per conversation (for RAG / scripts)
chat-export-md export.zip --stats                 # counts and ≈ tokens per source, writes nothing
```

### Move a chat to another assistant

1. Export, run with `--max-tokens 6000 --search "<chat title>"`.
2. Open `<name>.continue.md` and paste it into the next assistant. It contains the newest messages that fit and a short instruction to pick up where you left off.

## Details

- **ChatGPT**: follows `current_node` up the tree, so you get the branch you actually saw, not every edit. Code and execution output become fenced blocks, images become `[image]`, and system/hidden messages are dropped.
- **Claude**: uses the structured `content` blocks (falls back to `text`) and lists attachment names.
- **Gemini Takeout**: keeps prompts and HTML replies but **no thread ids**, so activity is grouped by day.
- Unicode-safe file names (Arabic, CJK…), collision-safe (`-2`, `-3`), and works on Windows, macOS and Linux.

## Privacy

Everything runs locally. Your exports never leave your machine. Be careful where you sync the output folder.

## Limitations

- Attachment *contents*, images and canvases aren't extracted. Only their names or placeholders are.
- Export formats change without notice. If something breaks, please open an issue with a tiny **redacted** sample.

## Roadmap

- [ ] HTML viewer with full-text search
- [ ] Obsidian-friendly tags and backlinks
- [ ] Import Gemini *Saved* chats and Copilot exports

## Related tools in this suite

Small, dependency-free tools for people fighting AI usage limits:

| Tool | What it does |
|---|---|
| [burnrate](https://github.com/mohammed2345353/burnrate) | Forecast Claude Code / Codex limits from local logs |
| [context-diet](https://github.com/mohammed2345353/context-diet) | Find the CLAUDE.md / AGENTS.md / GEMINI.md bloat you pay for on every message |
| [ai-handoff](https://github.com/mohammed2345353/ai-handoff) | Hit a limit? Move the task to another AI with a handoff file |
| [ai-error-decoder](https://github.com/mohammed2345353/ai-error-decoder) | Explain 429 / 529 / quota errors from Anthropic, OpenAI and Gemini |
| [ratelimit-retry](https://github.com/mohammed2345353/ratelimit-retry) | Retry that respects provider rate-limit headers (JS) |
| **chat-export-md** | ChatGPT / Claude / Gemini exports → Markdown |
| [mcp-token-audit](https://github.com/mohammed2345353/mcp-token-audit) | Measure how many tokens each MCP server's tools cost |
| [logslim](https://github.com/mohammed2345353/logslim) | Shrink logs and stack traces before pasting them into a chat |
| [chunkwise](https://github.com/mohammed2345353/chunkwise) | Split big files into token-budgeted chunks with continuation prompts |
| [ai-reset-clock](https://github.com/mohammed2345353/ai-reset-clock) | When does my quota reset? A countdown in your timezone |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
