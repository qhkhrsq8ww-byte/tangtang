"""Projection sink. Core emits PresentationAction; this adapter executes it.

A projection failure must not crash Family Brain. Event stays kept.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.events.event import Event
from core.response.orchestrator import PresentationAction
from core.runtime.isolate import isolate
from core.runtime.presentation import DeliveryResult

Projector = Callable[[PresentationAction], Any]


class ProjectionAdapter:
    core_api_version = "4.0.0"

    def __init__(self, projector: Projector | None = None) -> None:
        self.projector = projector

    def deliver(self, event: Event, action: PresentationAction | None) -> DeliveryResult:
        result = DeliveryResult(event_id=event.id, event_kept=True)
        if action is None or action.sink != "projection":
            return result
        if self.projector is None:
            return result
        shown = isolate(lambda: self.projector(action))
        result.projection_ok = shown.ok
        if not shown.ok:
            result.errors.append(f"projection:{shown.error_type}")
        return result
