"""Deterministic interruption gate; LLMs must not override this layer."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any


class InterruptPolicy:
    def __init__(self, quiet_start: time = time(22, 30), quiet_end: time = time(7, 0)) -> None:
        self.quiet_start = quiet_start
        self.quiet_end = quiet_end

    def is_quiet_hours(self, now: datetime) -> bool:
        t = now.time()
        return t >= self.quiet_start or t < self.quiet_end

    def decide(self, *, now: datetime, active_conversation: bool = False,
               emergency: bool = False, recently_interrupted: bool = False,
               importance: str = "normal") -> str:
        if emergency:
            return "SPEAK"
        if active_conversation:
            return "SILENT"
        if self.is_quiet_hours(now):
            return "SILENT"
        if recently_interrupted:
            return "DELAY"
        if importance == "low":
            return "LOG_ONLY"
        return "SPEAK"
