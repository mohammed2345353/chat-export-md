"""Dependency-free token estimate.

Real tokenizers differ per vendor, so this is a heuristic: ~4 chars/token for
Latin text and code, ~2.5 for Arabic/Cyrillic/Greek/Hebrew, ~1.5 for CJK.
If `tiktoken` is installed it is used instead (still only an approximation for
Claude and Gemini, but closer)."""
from __future__ import annotations

try:  # optional
    import tiktoken  # type: ignore
    _ENC = tiktoken.get_encoding("o200k_base")
except Exception:  # pragma: no cover - depends on environment
    _ENC = None


def _bucket(ch: str) -> float:
    o = ord(ch)
    if o < 0x0370:
        return 1 / 4
    if 0x0370 <= o < 0x0800:  # Greek, Cyrillic, Armenian, Hebrew, Arabic, Syriac
        return 1 / 2.5
    if 0x3000 <= o < 0xA000 or 0xAC00 <= o < 0xD7B0 or 0xF900 <= o < 0xFB00:
        return 1 / 1.5
    return 1 / 3


def estimate(text: str, exact: bool = True) -> int:
    if not text:
        return 0
    if exact and _ENC is not None:
        return len(_ENC.encode(text, disallowed_special=()))
    return max(1, round(sum(_bucket(c) for c in text)))


def method() -> str:
    return "tiktoken o200k_base" if _ENC is not None else "heuristic (≈ chars/4)"
