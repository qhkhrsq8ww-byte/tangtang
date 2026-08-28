"""Presentation-layer animation states. Does not change Brain interrupt policy."""
from __future__ import annotations

from dataclasses import dataclass

STATES = (
    "IDLE",
    "LISTEN",
    "HAPPY",
    "ENCOURAGE",
    "SAD",
    "WALK",
    "RUN",
    "SIT",
    "LIE",
    "SLEEP",
)

ANIM_TO_STATE = {
    "idle": "IDLE",
    "blink": "IDLE",
    "listen": "LISTEN",
    "tilt": "LISTEN",
    "happy": "HAPPY",
    "encourage": "ENCOURAGE",
    "sad": "SAD",
    "walk": "WALK",
    "run": "RUN",
    "sit": "SIT",
    "lie": "LIE",
    "sleep": "SLEEP",
}

# Ordinary / high-frequency motions cannot wake 糖糖. Wake needs priority >= this.
SLEEP_LOCK_PRIORITY = 9
MAX_FPS = 12
SLEEP_MAX_FPS = 4


@dataclass
class Transition:
    accepted: bool
    from_state: str
    to_state: str
    reason: str
    hold_previous: bool


class AnimationStateMachine:
    def __init__(self, initial: str = "IDLE") -> None:
        state = initial if initial in STATES else "IDLE"
        self.state = state
        self.priority = 0

    def request(
        self,
        state: str,
        *,
        priority: int = 0,
        interrupt: bool = True,
        force: bool = False,
    ) -> Transition:
        target = state if state in STATES else "IDLE"
        previous = self.state
        if target == previous:
            self.priority = max(self.priority, int(priority))
            return Transition(True, previous, target, "same", False)

        if not force and previous == "SLEEP" and int(priority) < SLEEP_LOCK_PRIORITY:
            return Transition(False, previous, previous, "sleep_locked", False)

        if not interrupt and int(priority) <= self.priority:
            return Transition(False, previous, previous, "no_interrupt", False)

        if int(priority) < self.priority and not interrupt:
            return Transition(False, previous, previous, "lower_priority", False)

        self.state = target
        self.priority = int(priority) if target != "IDLE" else 0
        return Transition(True, previous, target, "ok", True)
