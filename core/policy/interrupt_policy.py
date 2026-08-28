"""Deterministic interruption gate. LLMs must not implement or override this."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, time, timezone
from typing import Any

DECISIONS = frozenset({"SPEAK", "SILENT", "DELAY", "LOG_ONLY"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InterruptPolicy:
    def __init__(
        self,
        quiet_start: time = time(22, 30),
        quiet_end: time = time(7, 0),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.quiet_start = quiet_start
        self.quiet_end = quiet_end
        self._clock = clock or _utc_now

    def is_quiet_hours(self, now: datetime) -> bool:
        t = now.time()
        start, end = self.quiet_start, self.quiet_end
        if start <= end:
            return start <= t < end
        return t >= start or t < end

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
        if not interactive and self.is_quiet_hours(when):
            return "SILENT"
        if obs.get("recently_interrupted"):
            return "DELAY"
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
