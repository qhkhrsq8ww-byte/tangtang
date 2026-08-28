"""Presentation sinks. Failures never drop the already-accepted Event.

LLM / voice / ear / screen / network are optional injected callables.
None means the sink is not wired (unit tests). A raised exception is
recorded on the result, with event_kept=True.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.events.event import Event
from core.response.orchestrator import PresentationAction
from core.runtime.isolate import isolate


@dataclass
class DeliveryResult:
    event_id: str
    event_kept: bool
    tts_ok: bool = True
    stt_ok: bool = True
    projection_ok: bool = True
    network_ok: bool = True
    llm_ok: bool = True
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.event_kept
            and self.tts_ok
            and self.stt_ok
            and self.projection_ok
            and self.network_ok
            and self.llm_ok
        )


class PresentationRuntime:
    """Sinks are injected callables. This module does not play audio or project."""

    def __init__(
        self,
        *,
        tts: Callable[[str], Any] | None = None,
        stt: Callable[[Any], Any] | None = None,
        projection: Callable[[Any], Any] | None = None,
        network: Callable[[], Any] | None = None,
    ) -> None:
        self.tts = tts
        self.stt = stt
        self.projection = projection
        self.network = network

    def deliver(
        self,
        event: Event,
        action: PresentationAction | None = None,
        *,
        audio: Any = None,
    ) -> DeliveryResult:
        result = DeliveryResult(event_id=event.id, event_kept=True)
        if self.stt is not None and audio is not None:
            stt_res = isolate(lambda: self.stt(audio))
            result.stt_ok = stt_res.ok
            if not stt_res.ok:
                result.errors.append(f"stt:{stt_res.error_type}")
        if self.network is not None:
            net_res = isolate(self.network)
            result.network_ok = net_res.ok
            if not net_res.ok:
                result.errors.append(f"network:{net_res.error_type}")
        if action is not None and action.sink == "voice" and action.text and self.tts is not None:
            tts_res = isolate(lambda: self.tts(action.text))
            result.tts_ok = tts_res.ok
            if not tts_res.ok:
                result.errors.append(f"tts:{tts_res.error_type}")
        if action is not None and action.sink == "projection" and self.projection is not None:
            proj_res = isolate(lambda: self.projection(action))
            result.projection_ok = proj_res.ok
            if not proj_res.ok:
                result.errors.append(f"projection:{proj_res.error_type}")
        return result
