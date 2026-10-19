"""Deterministic V5 companion planner.

This is the missing layer between raw observations and persona/response:
"what should TangTang do now?"  It is deliberately small and local-first.

The planner never generates speech and never overrides an explicit user turn.
For proactive scenes it applies timing/attention rules and produces a
structured plan that downstream Persona/LLM layers can use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Mapping

from core.persona.profiles import profile_for

QUIET_START = 22
QUIET_END = 7
USER_QUIET_HOURS = 4
_USER_QUIET_MARKERS = (
    "今天别叫我", "别打扰我", "不想说话", "让我自己待会", "让我自己待一会",
    "先别提醒我", "不要再提醒我", "别再提醒我", "我想安静一下",
)

_BEHAVIOR_BY_SCENE = {
    "home": "welcome",
    "phone": "check_in",
    "sitting": "check_in",
    "exercise": "encourage_movement",
    "no_meal": "meal_check",
    "late_sleep": "wind_down",
}

@dataclass(frozen=True)
class CompanionPlan:
    """A decision record, not a response."""

    decision: str
    behavior: str
    reason: str
    role: str | None = None
    proactive: bool = False
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "behavior": self.behavior,
            "reason": self.reason,
            "role": self.role,
            "proactive": self.proactive,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }


class CompanionPlanner:
    """Small deterministic policy for natural companion behavior."""

    def __init__(self, *, min_proactive_gap_minutes: int = 20) -> None:
        self.min_proactive_gap_minutes = max(1, int(min_proactive_gap_minutes))
        # Runtime-local anti-chatter state. No speech/content is persisted here.
        self._last_proactive: dict[str, datetime] = {}
        self._last_behavior: dict[str, str] = {}
        self._quiet_until: dict[str, datetime] = {}

    @staticmethod
    def _hour(observation: Mapping[str, Any]) -> int | None:
        now = observation.get("now")
        if isinstance(now, datetime):
            return now.hour
        return None

    @staticmethod
    def _is_quiet(observation: Mapping[str, Any]) -> bool:
        hour = CompanionPlanner._hour(observation)
        return hour is not None and (hour >= QUIET_START or hour < QUIET_END)

    def _role(self, member_id: str | None) -> str | None:
        try:
            return profile_for(member_id)
        except Exception:
            return None

    def plan(
        self,
        *,
        member_id: str | None,
        observation: Mapping[str, Any] | None = None,
        utterance: str | None = None,
        proactive: bool = False,
    ) -> CompanionPlan:
        obs = dict(observation or {})
        role = self._role(member_id)
        scene = str(obs.get("scene") or "").strip()
        text = str(utterance or obs.get("utterance") or "").strip()

        # Explicit user speech always gets to the normal response pipeline.
        # A clear request for quiet is remembered for proactive scenes only.
        if text and not proactive:
            quiet_request = any(marker in text.replace(" ", "") for marker in _USER_QUIET_MARKERS)
            now = obs.get("now")
            if quiet_request and member_id and isinstance(now, datetime):
                key = str(member_id)
                self._quiet_until[key] = now + timedelta(hours=USER_QUIET_HOURS)
                return CompanionPlan(
                    decision="RESPOND",
                    behavior="respect_boundary",
                    reason="user_requested_quiet",
                    role=role,
                    proactive=False,
                    metadata={"quiet_hours": USER_QUIET_HOURS},
                )
            return CompanionPlan(
                decision="RESPOND",
                behavior="conversation",
                reason="user_initiated",
                role=role,
                proactive=False,
                metadata={"scene": scene} if scene else {},
            )

        if not proactive:
            return CompanionPlan(
                decision="WAIT",
                behavior="idle",
                reason="no_user_turn",
                role=role,
                proactive=False,
            )

        if self._is_quiet(obs) and not bool(obs.get("emergency")):
            return CompanionPlan(
                decision="SILENT",
                behavior="quiet",
                reason="quiet_hours",
                role=role,
                proactive=True,
            )

        if obs.get("at_school") or obs.get("sleeping") or obs.get("asleep"):
            return CompanionPlan(
                decision="WAIT",
                behavior="quiet",
                reason="do_not_interrupt",
                role=role,
                proactive=True,
            )

        now = obs.get("now")
        quiet_until = self._quiet_until.get(str(member_id or ""))
        if isinstance(now, datetime) and isinstance(quiet_until, datetime):
            comparable_now = now if now.tzinfo is not None else now.replace(tzinfo=quiet_until.tzinfo)
            comparable_until = quiet_until if quiet_until.tzinfo is not None else quiet_until.replace(tzinfo=comparable_now.tzinfo)
            if comparable_now < comparable_until:
                return CompanionPlan(
                    decision="WAIT",
                    behavior="quiet",
                    reason="user_requested_quiet",
                    role=role,
                    proactive=True,
                    metadata={"quiet_until": comparable_until.isoformat()},
                )
            self._quiet_until.pop(str(member_id or ""), None)

        behavior = _BEHAVIOR_BY_SCENE.get(scene)
        if behavior:
            key = str(member_id or "unknown")
            now = obs.get("now")
            last = self._last_proactive.get(key)
            if isinstance(now, datetime) and isinstance(last, datetime):
                elapsed = (now - last).total_seconds() / 60.0
                if elapsed < self.min_proactive_gap_minutes and self._last_behavior.get(key) == behavior:
                    return CompanionPlan(
                        decision="WAIT",
                        behavior="quiet",
                        reason="proactive_cooldown",
                        role=role,
                        proactive=True,
                        metadata={"scene": scene, "cooldown_minutes": self.min_proactive_gap_minutes},
                    )
            if isinstance(now, datetime):
                self._last_proactive[key] = now
                self._last_behavior[key] = behavior
            return CompanionPlan(
                decision="CONSIDER",
                behavior=behavior,
                reason=f"scene:{scene}",
                role=role,
                proactive=True,
                metadata={"scene": scene},
            )

        return CompanionPlan(
            decision="WAIT",
            behavior="idle",
            reason="no_relevant_trigger",
            role=role,
            proactive=True,
        )
