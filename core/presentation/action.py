"""Unified PresentationAction. Core never includes MP4 paths."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

PRESENTATION_STATES = frozenset({
    "idle", "talk", "happy", "curious", "thinking", "caring",
    "encouraging", "walking", "running", "sitting", "lying", "sleepy",
    "sleeping", "welcome", "accompany", "wakeup", "night",
})

FORBIDDEN_BUSINESS = frozenset({
    "homework", "exercise", "screen", "meal", "bully", "exam",
})


@dataclass(frozen=True)
class PresentationAction:
    state: str
    transition: str = "crossfade"
    intensity: float = 0.5
    speak: bool = False
    duration_ms: int = 2000
    reason: str = ""
    text: str = ""
    speech_allowed: bool = True

    def __post_init__(self) -> None:
        state = (self.state or "idle").strip().lower()
        if state not in PRESENTATION_STATES:
            state = "idle"
        object.__setattr__(self, "state", state)
        intensity = self.intensity
        if not isinstance(intensity, (int, float)):
            intensity = 0.5
        object.__setattr__(self, "intensity", max(0.0, min(1.0, float(intensity))))
        speak = bool(self.speak) and bool(self.speech_allowed)
        object.__setattr__(self, "speak", speak)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def idle(cls, reason: str = "fallback") -> "PresentationAction":
        return cls(state="idle", speak=False, reason=reason, speech_allowed=False)
