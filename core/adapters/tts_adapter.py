"""TTS sink adapter. Core never calls a vendor speak binary.

Failures are recorded on DeliveryResult. The Event stays kept.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.events.event import Event
from core.response.orchestrator import PresentationAction
from core.runtime.isolate import isolate
from core.runtime.presentation import DeliveryResult

Speaker = Callable[[str], Any]


class TTSAdapter:
    """Execute PresentationAction.sink == voice via an injected speaker."""

    core_api_version = "4.0.0"

    def __init__(self, speaker: Speaker | None = None) -> None:
        self.speaker = speaker

    def deliver(self, event: Event, action: PresentationAction | None) -> DeliveryResult:
        result = DeliveryResult(event_id=event.id, event_kept=True)
        if action is None or action.decision != "SPEAK" or action.sink != "voice":
            return result
        if not action.text:
            return result
        if self.speaker is None:
            # Offline / unwired: still a presentation no-op, Event kept.
            return result
        spoken = isolate(lambda: self.speaker(action.text))
        result.tts_ok = spoken.ok
        if not spoken.ok:
            result.errors.append(f"tts:{spoken.error_type}")
        return result
