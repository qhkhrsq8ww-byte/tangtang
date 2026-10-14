"""Deterministic, consent-explicit local memory intent parsing."""
from __future__ import annotations

import re
from dataclasses import dataclass

_CATEGORY = {
    "最喜欢": "favorite",
    "喜欢": "likes",
    "不喜欢": "dislikes",
    "讨厌": "dislikes",
}
_CATEGORY_TEXT = {
    "favorite": "最喜欢",
    "likes": "喜欢",
    "dislikes": "不喜欢",
}
_REMEMBER = re.compile(
    r"^(?:糖糖[，, ]*)?(?:请)?(?:帮我)?记住(?:一下)?[，,：:\\s]*"
    r"(?:我)?(最喜欢|喜欢|不喜欢|讨厌)(.{1,80})$"
)
_FORGET = re.compile(
    r"^(?:糖糖[，, ]*)?(?:请)?忘记[，,：:\\s]*"
    r"(?:我)?(最喜欢|喜欢|不喜欢|讨厌)(.{1,80})$"
)
_RECALL = re.compile(
    r"^(?:糖糖[，, ]*)?(?:(?:你)?(?:还)?记得(?:我)?"
    r"(最喜欢|喜欢|不喜欢|讨厌)(?:什么|哪种|哪些)(?:吗)?"
    r"|(?:我)?(最喜欢|喜欢|不喜欢|讨厌)(?:什么|哪种|哪些))$"
)
_RECALL_ALL = re.compile(
    r"^(?:糖糖[，, ]*)?(?:你)?(?:还)?记得(?:我)?喜欢什么(?:吗)?$"
)


@dataclass(frozen=True)
class MemoryIntent:
    action: str
    category: str | None = None
    value: str | None = None


def parse_memory_intent(text: str | None) -> MemoryIntent | None:
    """Recognize only clear remember/forget/recall commands; no model is involved."""
    raw = " ".join(str(text or "").strip().split()).strip(" ，,。.!！?？:：")
    if not raw or len(raw) > 120:
        return None

    match = _FORGET.fullmatch(raw)
    if match:
        value = match.group(2).strip(" ，,。.!！?？:：")
        if value:
            return MemoryIntent("forget", _CATEGORY[match.group(1)], value[:80])

    match = _REMEMBER.fullmatch(raw)
    if match:
        value = match.group(2).strip(" ，,。.!！?？:：")
        if value:
            return MemoryIntent("remember", _CATEGORY[match.group(1)], value[:80])

    if _RECALL_ALL.fullmatch(raw):
        return MemoryIntent("recall")

    match = _RECALL.fullmatch(raw)
    if match:
        category_text = match.group(1) or match.group(2)
        return MemoryIntent("recall", _CATEGORY[category_text] if category_text else None)

    return None


def category_text(category: str) -> str:
    return _CATEGORY_TEXT.get(category, "喜欢")
