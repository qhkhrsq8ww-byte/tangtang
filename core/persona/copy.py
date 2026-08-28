"""Copy rules: 糖糖 is a 比熊, not a surveillance camera.

Forbidden: 「我知道你刚才玩了 43 分钟手机。」
Preferred: 「要不要起来走一走？」
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

WALK_SUGGESTION = "汪汪～ 要不要起来走一走？"

# Minutes-on-phone / sitting surveillance. Deterministic; LLM cannot override.
FORBIDDEN_SURVEILLANCE = (
    re.compile(r"我知道你刚才玩了\s*\d+\s*分钟手机"),
    re.compile(r"我知道你刚才.{0,16}\d+\s*分钟"),
    re.compile(r"已经玩了\s*\d+\s*分钟手机"),
    re.compile(r"你刚才玩了\s*\d+\s*分钟"),
    re.compile(r"监控到你"),
    re.compile(r"糖糖看到你玩了\s*\d+"),
    re.compile(r"屏幕时间\s*\d+\s*分钟"),
)

TODDLER_TOKENS = (
    "宝宝",
    "吃饭饭",
    "觉觉",
    "抱抱哦",
    "乖哦",
    "咿呀",
    "小宝宝",
    "糖糖宝宝",
    "尿尿",
    "饭饭",
)

LECTURE_TOKENS = (
    "你必须立即",
    "立刻停止",
    "作为家长",
    "禁止你",
    "我警告你",
    "你应该感到羞耻",
    "再不听话",
    "这是命令",
)


def looks_surveillance(text: str | None) -> bool:
    blob = text or ""
    if not blob:
        return False
    return any(pat.search(blob) for pat in FORBIDDEN_SURVEILLANCE)


def has_any(text: str | None, tokens: tuple[str, ...]) -> bool:
    blob = text or ""
    return any(tok and tok in blob for tok in tokens)


class CopyGuard:
    """Last-line filter on SPEAK text. Never lets surveillance copy through."""

    def sanitize(
        self,
        text: str | None,
        *,
        member_id: str | None = None,
        role: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        raw = text if isinstance(text, str) else ""
        if looks_surveillance(raw):
            return WALK_SUGGESTION
        ctx = dict(context or {})
        role = role or str(ctx.get("role") or "")
        member_id = member_id or str((ctx.get("who") or {}).get("member_id") or "")
        if role in {"elder", "adult", "friend"} and has_any(raw, TODDLER_TOKENS):
            return "汪汪～ 糖糖在呢。"
        if role == "play" and has_any(raw, LECTURE_TOKENS):
            return "汪汪～ 可以玩一会儿，等下糖糖喊你起来动一动哦。"
        if member_id in {"grandpa", "grandma", "dad", "mom"} and has_any(raw, TODDLER_TOKENS):
            return "汪汪～ 糖糖在呢。"
        return raw
