"""Parse ChatGPT, Claude.ai and Gemini (Takeout) exports into one simple model."""
from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


@dataclass
class Message:
    role: str  # "user" | "assistant" | "tool"
    text: str
    time: Optional[datetime] = None


@dataclass
class Conversation:
    id: str
    title: str
    source: str  # chatgpt | claude | gemini
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    messages: List[Message] = field(default_factory=list)


def _ts(value) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- ChatGPT

def _chatgpt_text(content: dict) -> str:
    ctype = content.get("content_type", "text")
    if ctype in ("text", "multimodal_text"):
        parts = []
        for p in content.get("parts") or []:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                kind = p.get("content_type", "")
                if "image" in kind or "asset_pointer" in p:
                    parts.append("[image]")
                elif "audio" in kind:
                    parts.append(p.get("text") or "[audio]")
                elif p.get("text"):
                    parts.append(p["text"])
        return "\n".join(x for x in parts if x is not None).strip()
    if ctype == "code":
        lang = content.get("language") or ""
        lang = "" if lang == "unknown" else lang
        return f"```{lang}\n{content.get('text', '').rstrip()}\n```"
    if ctype == "execution_output":
        return f"```text\n{content.get('text', '').rstrip()}\n```"
    if ctype == "tether_quote":
        title = content.get("title") or content.get("url") or "quote"
        return f"> **{title}**\n> " + content.get("text", "").strip().replace("\n", "\n> ")
    if ctype in ("thoughts", "reasoning_recap", "user_editable_context", "model_editable_context",
                 "tether_browsing_display", "system_error"):
        return ""
    return str(content.get("text") or "").strip()


def parse_chatgpt(data: list) -> List[Conversation]:
    out = []
    for conv in data:
        mapping = conv.get("mapping") or {}
        node_id = conv.get("current_node")
        if node_id not in mapping:  # fall back to the deepest leaf
            leaves = [k for k, v in mapping.items() if not v.get("children")]
            node_id = leaves[-1] if leaves else None
        chain = []
        seen = set()
        while node_id and node_id in mapping and node_id not in seen:
            seen.add(node_id)
            chain.append(mapping[node_id])
            node_id = mapping[node_id].get("parent")
        msgs = []
        for node in reversed(chain):
            m = node.get("message")
            if not m:
                continue
            role = (m.get("author") or {}).get("role", "")
            meta = m.get("metadata") or {}
            if role == "system" or meta.get("is_visually_hidden_from_conversation"):
                continue
            text = _chatgpt_text(m.get("content") or {})
            if not text:
                continue
            msgs.append(Message("assistant" if role == "assistant" else "tool" if role == "tool" else "user",
                                text, _ts(m.get("create_time"))))
        out.append(Conversation(str(conv.get("id") or conv.get("conversation_id") or len(out)),
                                conv.get("title") or "Untitled", "chatgpt",
                                _ts(conv.get("create_time")), _ts(conv.get("update_time")), msgs))
    return out


# --------------------------------------------------------------------------- Claude

def parse_claude(data: list) -> List[Conversation]:
    out = []
    for conv in data:
        msgs = []
        for m in conv.get("chat_messages") or []:
            blocks = m.get("content") or []
            texts = []
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text"):
                    texts.append(b["text"])
                elif b.get("type") == "tool_use":
                    texts.append(f"[tool: {b.get('name', '?')}]")
            text = "\n\n".join(texts).strip() or str(m.get("text") or "").strip()
            files = [a.get("file_name") for a in (m.get("attachments") or []) if a.get("file_name")]
            files += [f.get("file_name") for f in (m.get("files") or []) if isinstance(f, dict) and f.get("file_name")]
            if files:
                text = (text + "\n\n" if text else "") + "📎 " + ", ".join(dict.fromkeys(files))
            if not text:
                continue
            role = "user" if m.get("sender") == "human" else "assistant"
            msgs.append(Message(role, text, _ts(m.get("created_at"))))
        out.append(Conversation(str(conv.get("uuid") or len(out)), conv.get("name") or "Untitled", "claude",
                                _ts(conv.get("created_at")), _ts(conv.get("updated_at")), msgs))
    return out


# --------------------------------------------------------------------------- Gemini Takeout

class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "pre"}

    def __init__(self):
        super().__init__()
        self.out: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag == "li":
            self.out.append("- ")

    def handle_data(self, data):
        self.out.append(data)

    def text(self):
        return re.sub(r"\n{3,}", "\n\n", "".join(self.out)).strip()


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    return p.text()


def parse_gemini(data: list) -> List[Conversation]:
    """Takeout has one activity per prompt and no thread ids, so group by local day."""
    by_day = {}
    for item in data:
        if "Gemini" not in str(item.get("header", "")) and "Bard" not in str(item.get("header", "")):
            continue
        title = str(item.get("title", ""))
        if not title.startswith("Prompted"):
            continue
        t = _ts(item.get("time"))
        prompt = title[len("Prompted"):].strip()
        reply = "\n\n".join(html_to_text(h.get("html", "")) for h in item.get("safeHtmlItem") or [] if isinstance(h, dict))
        day = t.date().isoformat() if t else "unknown"
        by_day.setdefault(day, []).append((t, prompt, reply))
    out = []
    for day, items in sorted(by_day.items()):
        items.sort(key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc))
        msgs = []
        for t, prompt, reply in items:
            msgs.append(Message("user", prompt, t))
            if reply:
                msgs.append(Message("assistant", reply, t))
        first = items[0][1].splitlines()[0][:60] if items[0][1] else "Gemini"
        out.append(Conversation(f"gemini-{day}", f"Gemini {day}: {first}", "gemini",
                                items[0][0], items[-1][0], msgs))
    return out


# --------------------------------------------------------------------------- detection / loading

def detect(data) -> Optional[str]:
    if not isinstance(data, list) or not data:
        return None
    first = next((x for x in data if isinstance(x, dict)), {})
    if "mapping" in first:
        return "chatgpt"
    if "chat_messages" in first:
        return "claude"
    if "header" in first and "time" in first:
        return "gemini"
    return None


PARSERS = {"chatgpt": parse_chatgpt, "claude": parse_claude, "gemini": parse_gemini}


def _candidates(path: Path) -> Iterable[Tuple[str, bytes]]:
    if path.is_dir():
        for p in path.rglob("*.json"):
            if p.name in ("conversations.json", "MyActivity.json"):
                yield str(p), p.read_bytes()
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                base = name.rsplit("/", 1)[-1]
                if base in ("conversations.json", "MyActivity.json"):
                    yield f"{path}!{name}", z.read(name)
                elif base.endswith(".zip"):  # nested Takeout zip
                    inner = io.BytesIO(z.read(name))
                    with zipfile.ZipFile(inner) as z2:
                        for n2 in z2.namelist():
                            if n2.rsplit("/", 1)[-1] in ("conversations.json", "MyActivity.json"):
                                yield f"{path}!{name}!{n2}", z2.read(n2)
    else:
        yield str(path), path.read_bytes()


def load(path: Path) -> List[Conversation]:
    convs: List[Conversation] = []
    for name, raw in _candidates(path):
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError):
            continue
        kind = detect(data)
        if kind:
            convs += PARSERS[kind](data)
    return convs
