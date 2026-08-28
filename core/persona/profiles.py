"""Six-member personas. 糖糖 is a 比熊 playmate (汪汪～), not a supervisor.

Adults must not get baby-talk. 姐姐 (12 / qiaqia) is a friend, not a toddler.
弟弟 (9 / hanghang) is a playmate, not a lecture target.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.identity.resolver import CHILD_PRODUCTS, IdentityResolver
from core.persona.copy import CopyGuard, LECTURE_TOKENS, TODDLER_TOKENS, WALK_SUGGESTION

# Canonical product ids. family.json still uses child_12 / child_9;
# living-room names qiaqia / hanghang are aliases only.
PERSONAS: dict[str, dict[str, Any]] = {
    "grandpa": {
        "role": "elder",
        "display": "爷爷",
        "tone": "adult-respectful",
        "forbid": TODDLER_TOKENS,
    },
    "grandma": {
        "role": "elder",
        "display": "奶奶",
        "tone": "adult-warm",
        "forbid": TODDLER_TOKENS,
    },
    "dad": {
        "role": "adult",
        "display": "爸爸",
        "tone": "adult-concise",
        "forbid": TODDLER_TOKENS,
    },
    "mom": {
        "role": "adult",
        "display": "妈妈",
        "tone": "adult-caring",
        "forbid": TODDLER_TOKENS,
    },
    "child_12": {
        "role": "friend",
        "display": "姐姐",
        "product": "qiaqia",
        "age": 12,
        "tone": "peer-friend",
        "forbid": TODDLER_TOKENS,
    },
    "child_9": {
        "role": "play",
        "display": "弟弟",
        "product": "hanghang",
        "age": 9,
        "tone": "playmate",
        "forbid": LECTURE_TOKENS,
    },
}

# Six living-room utterances used as the Round 3 acceptance matrix.
SIX_UTTERANCES: tuple[tuple[str, str, str], ...] = (
    ("grandpa", "糖糖，帮我看看明天天气。", "汪汪～ 爷爷，明天可能有雨，出门记得带伞。"),
    ("grandma", "糖糖陪奶奶说说话。", "汪汪～ 奶奶，糖糖在呢，想聊什么都行。"),
    ("dad", "糖糖，我加班回来了。", "汪汪～ 爸爸回来啦，要不要先歇一会儿。"),
    ("mom", "孩子们作业写完了吗？", "汪汪～ 妈妈，糖糖还没看到作业都收好，要不要轻轻提醒一下。"),
    ("child_12", "好无聊，不想写作业。", "汪汪～ 先歇两分钟也行，等一下再挑最容易的一题？"),
    ("child_9", "我想打游戏！", "汪汪～ 可以玩一会儿，等下糖糖喊你起来动一动哦。"),
)

_ALIAS_TO_CANONICAL = {
    "爷爷": "grandpa",
    "奶奶": "grandma",
    "爸爸": "dad",
    "妈妈": "mom",
    "姐姐": "child_12",
    "qiaqia": "child_12",
    "洽洽": "child_12",
    "12岁姐姐": "child_12",
    "弟弟": "child_9",
    "hanghang": "child_9",
    "航航": "child_9",
    "9岁弟弟": "child_9",
}


def profile_for(member_id: str | None, members: Mapping[str, object] | None = None) -> str | None:
    if not member_id:
        return None
    ident = IdentityResolver(members)
    canonical = ident.resolve({"member_id": member_id}) or ident.resolve({"label": member_id}) or member_id
    canonical = _ALIAS_TO_CANONICAL.get(canonical, canonical)
    if canonical in PERSONAS:
        return str(PERSONAS[canonical]["role"])
    if canonical in CHILD_PRODUCTS:
        return "friend" if canonical in {"child_12", "qiaqia"} else "play"
    return "adult"


@dataclass(frozen=True)
class PersonaReply:
    member_id: str
    role: str
    text: str


class PersonaRenderer:
    """Deterministic copy. LLM may suggest; this module still filters tone."""

    def __init__(
        self,
        members: Mapping[str, object] | None = None,
        copy_guard: CopyGuard | None = None,
    ) -> None:
        self._identity = IdentityResolver(members)
        self._copy = copy_guard or CopyGuard()
        self._exact = {(mid, utt): reply for mid, utt, reply in SIX_UTTERANCES}

    def canonical(self, member_id: str | None) -> str | None:
        if not member_id:
            return None
        found = (
            self._identity.resolve({"member_id": member_id})
            or self._identity.resolve({"label": member_id})
            or member_id
        )
        return _ALIAS_TO_CANONICAL.get(found, found)

    def reply(
        self,
        *,
        member_id: str | None,
        utterance: str | None = None,
        scene: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> PersonaReply:
        ctx = dict(context or {})
        mid_raw = member_id or (ctx.get("who") or {}).get("member_id") if isinstance(ctx.get("who"), Mapping) else member_id
        mid = self.canonical(str(mid_raw) if mid_raw else None) or "unknown"
        text_in = utterance if utterance is not None else str(ctx.get("utterance") or "")
        scene = scene or ctx.get("scene")
        spec = PERSONAS.get(mid, {"role": "adult", "forbid": TODDLER_TOKENS})
        role = str(spec.get("role") or "adult")

        exact = self._exact.get((mid, text_in))
        if exact:
            out = exact
        elif scene in {"phone", "sitting"}:
            out = WALK_SUGGESTION
        elif role == "elder":
            name = spec.get("display") or "您"
            out = f"汪汪～ {name}，糖糖在呢。"
        elif role == "adult":
            out = "汪汪～ 糖糖在，需要帮忙就说一声。"
        elif role == "friend":
            out = "汪汪～ 嗯，糖糖听着呢。想歇一下还是先做一件小的？"
        elif role == "play":
            out = "汪汪～ 糖糖陪你！我们一会儿再动一动好不好。"
        else:
            out = "汪汪～"

        out = self._copy.sanitize(out, member_id=mid, role=role)
        return PersonaReply(member_id=mid, role=role, text=out)

    def reply_text(self, **kwargs: Any) -> str:
        return self.reply(**kwargs).text
