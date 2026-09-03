"""Resolve speaker → member_id. Does not open voiceprint files by itself."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.identity.resolver import IdentityResolver as _CoreResolver


class IdentityResolver(_CoreResolver):
    """V3 facade: voiceprint label is optional hint, never auto-bind unknown."""

    def resolve_from_voice_label(
        self,
        label: str | None,
        *,
        confidence: float = 0.0,
        threshold: float = 0.995,
        observation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        obs = dict(observation or {})
        if label and str(label).strip() and str(label).strip().lower() not in {
            "unknown",
            "访客",
            "guest",
            "none",
        }:
            obs.setdefault("label", label)
            obs.setdefault("speaker", label)
        if confidence:
            obs.setdefault("identity_confidence", float(confidence))
        # Low confidence → force unknown path via empty hint
        if confidence and confidence < threshold:
            obs.pop("label", None)
            obs.pop("speaker", None)
            obs.pop("candidate_member", None)
            obs["identity_confidence"] = float(confidence)
        member_id = self.resolve(obs)
        return {
            "member_id": member_id or "unknown",
            "identity_confidence": float(obs.get("identity_confidence") or confidence or 0.0),
            "bound": bool(member_id and member_id != "unknown"),
        }
