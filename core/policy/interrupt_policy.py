"""Deterministic interruption gate. LLMs must not implement or override this.

Proactive scenes (phone / sitting / no_meal / late_sleep / home / away)
must not speak on every tick. Cooldown turns a repeat into SILENT/LOG_ONLY.
Surveillance copy is not this module's job — see core.persona.copy.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, time, timedelta, timezone
from typing import Any

DECISIONS = frozenset({"SPEAK", "SILENT", "DELAY", "LOG_ONLY"})
PROACTIVE_SCENES = frozenset({"phone", "sitting", "no_meal", "late_sleep", "home", "away"})
DEFAULT_COOLDOWN = timedelta(minutes=15)

# Repeat of the same proactive scene → do not nag.
_REPEAT_DECISION = {
    "phone": "LOG_ONLY",
    "sitting": "LOG_ONLY",
    "no_meal": "DELAY",
    "late_sleep": "SILENT",
    "home": "LOG_ONLY",
    "away": "SILENT",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def infer_scene(observation: Mapping[str, Any] | None) -> str | None:
    obs = dict(observation or {})
    scene = obs.get("scene")
    if isinstance(scene, str) and scene.strip() in PROACTIVE_SCENES:
        return scene.strip()
    if obs.get("presence_home") is False and not obs.get("interactive"):
        return "away"
    if obs.get("just_arrived") or obs.get("arrived_home"):
        return "home"
    if obs.get("phone") or obs.get("on_phone") or obs.get("phone_minutes"):
        return "phone"
    if obs.get("sitting") or obs.get("sitting_minutes"):
        return "sitting"
    if obs.get("no_meal") or obs.get("missed_meal"):
        return "no_meal"
    if obs.get("late_sleep") or obs.get("past_bedtime"):
        return "late_sleep"
    return None


class InterruptPolicy:
    def __init__(
        self,
        quiet_start: time = time(22, 30),
        quiet_end: time = time(7, 0),
        clock: Callable[[], datetime] | None = None,
        cooldown: timedelta | None = None,
    ) -> None:
        self.quiet_start = quiet_start
        self.quiet_end = quiet_end
        self._clock = clock or _utc_now
        self._cooldown = cooldown or DEFAULT_COOLDOWN
        self._last_spoke: dict[tuple[str, str], datetime] = {}

    def is_quiet_hours(self, now: datetime) -> bool:
        t = now.time()
        start, end = self.quiet_start, self.quiet_end
        if start <= end:
            return start <= t < end
        return t >= start or t < end

    def _cooldown_hit(self, key: tuple[str, str], when: datetime) -> bool:
        last = self._last_spoke.get(key)
        if last is None:
            return False
        return (when - last) < self._cooldown

    def _mark_spoke(self, key: tuple[str, str], when: datetime) -> None:
        self._last_spoke[key] = when

    def decide(
        self,
        observation: Mapping[str, Any] | None = None,
        now: datetime | None = None,
        **kwargs: Any,
    ) -> str:
        obs: dict[str, Any] = dict(observation or {})
        for key, value in kwargs.items():
            if value is not None and key not in obs:
                obs[key] = value
        when = now or obs.get("now") or self._clock()
        if not isinstance(when, datetime):
            when = self._clock()

        if obs.get("emergency"):
            return "SPEAK"
        if obs.get("active_conversation"):
            return "SILENT"
        at_school = bool(obs.get("school_hours") or obs.get("at_school"))
        audience_child = bool(
            obs.get("audience_child") or obs.get("child_audience")
        )
        presence_home = obs.get("presence_home")
        if at_school and audience_child and presence_home is False:
            return "SILENT"
        interactive = bool(obs.get("interactive"))
        scene = infer_scene(obs)
        # Empty living room: never chat into the dark.
        if scene == "away" or (presence_home is False and not interactive):
            return "SILENT"
        if not interactive and self.is_quiet_hours(when):
            return "SILENT"
        if obs.get("recently_interrupted"):
            return "DELAY"
        if scene in PROACTIVE_SCENES:
            member = str(obs.get("member_id") or obs.get("audience") or "*")
            key = (member, scene)
            if self._cooldown_hit(key, when):
                return _REPEAT_DECISION.get(scene, "LOG_ONLY")
            decision = "SPEAK"
            self._mark_spoke(key, when)
            return decision
        if obs.get("importance") == "low":
            return "LOG_ONLY"
        return "SPEAK"

    def should_interrupt(
        self,
        observation: Mapping[str, Any] | None = None,
        now: datetime | None = None,
        **kwargs: Any,
    ) -> bool:
        """True = do not speak now. Inverse of a SPEAK decision."""
        return self.decide(observation, now=now, **kwargs) != "SPEAK"

    def should_interrupt(
        self,
        observation: Mapping[str, Any] | None = None,
        now: datetime | None = None,
        **kwargs: Any,
    ) -> bool:
        """True = do not speak now. Inverse of a SPEAK decision."""
        return self.decide(observation, now=now, **kwargs) != "SPEAK"
