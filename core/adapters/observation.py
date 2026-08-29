"""Observation records produced by adapters. IdentityResolver maps them."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

VOICE_OBSERVED = "voice.observed"
UNKNOWN_CANDIDATES = frozenset({
    "unknown", "访客", "guest", "stranger", "none", "null", "",
})


def is_unknown_candidate(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    return text.lower() in UNKNOWN_CANDIDATES


@dataclass(frozen=True)
class Observation:
    type: str
    candidate_member: str | None = None
    confidence: float = 0.0
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, Any]:
        candidate = self.candidate_member
        if is_unknown_candidate(candidate):
            candidate = None
        out: dict[str, Any] = {
            "type": self.type,
            "candidate_member": candidate,
            "confidence": float(self.confidence),
        }
        out.update(dict(self.payload or {}))
        if candidate:
            # IdentityResolver reads label / member_id / speaker / candidate_member.
            out.setdefault("label", candidate)
        return out


def voice_observation(
    *,
    candidate_member: str | None,
    confidence: float = 0.0,
    extra: Mapping[str, Any] | None = None,
) -> Observation:
    candidate = None if is_unknown_candidate(candidate_member) else str(candidate_member).strip()
    payload = dict(extra or {})
    payload["type"] = VOICE_OBSERVED
    return Observation(
        type=VOICE_OBSERVED,
        candidate_member=candidate,
        confidence=0.0 if candidate is None else float(confidence),
        payload=payload,
    )
