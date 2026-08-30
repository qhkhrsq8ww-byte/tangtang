"""Turn a CharacterStateDecision + optional speech into PresentationAction."""
from __future__ import annotations

from typing import Any

from core.presentation.action import PresentationAction

TRANSITION_HINTS = {
    ("idle", "talk"): "crossfade:100-150",
    ("idle", "curious"): "crossfade:100-200",
    ("talk", "caring"): "crossfade:100-200",
    ("running", "idle"): "slow-stop",
    ("sleeping", "wakeup"): "natural",
    ("night", "wakeup"): "natural",
}


class CharacterPresenter:
    def present(self, decision: Any, *, text: str = "") -> PresentationAction:
        state = getattr(decision, "presentation_state", None) or getattr(decision, "state", "idle")
        speech_allowed = bool(getattr(decision, "speech_allowed", True))
        hint = getattr(decision, "transition_hint", "") or ""
        prev = getattr(decision, "previous_state", None)
        if not hint and prev:
            hint = TRANSITION_HINTS.get((str(prev), str(state)), "crossfade")
        if not hint:
            hint = "crossfade"
        spoken = bool(text) and speech_allowed
        duration = 3000 if spoken else 2000
        if spoken:
            duration = max(3000, min(12000, len(text) * 290))
        return PresentationAction(
            state=str(state),
            transition=hint,
            intensity=float(getattr(decision, "intensity", 0.5) or 0.5),
            speak=spoken,
            duration_ms=duration,
            reason=str(getattr(decision, "reason", "") or ""),
            text=text if spoken else "",
            speech_allowed=speech_allowed,
        )
