"""In-memory EventBus: inject clock, no I/O, handler faults isolated."""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.errors import EventError
from core.events.event import Event

Handler = Callable[[Event], Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PublishResult:
    ok: bool
    duplicate: bool
    received_at: str
    results: list[Any] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class EventBus:
    """Synchronous in-memory bus. Unit tests inject `clock` and `error_sink`."""

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
        error_sink: Callable[[str, BaseException], None] | None = None,
    ) -> None:
        self._clock = clock or _utc_now
        self._error_sink = error_sink
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._seen_ids: set[str] = set()
        self._log = logging.getLogger("core.events.bus")

    def subscribe(self, event_type: str, handler: Handler) -> None:
        if not event_type or not str(event_type).strip():
            raise EventError("event_type is required to subscribe")
        if not callable(handler):
            raise EventError("handler must be callable")
        self._handlers[str(event_type).strip()].append(handler)

    def publish(self, event: Event) -> PublishResult:
        if not isinstance(event, Event):
            raise EventError("EventBus.publish requires a validated Event")
        received_at = self._clock().isoformat()
        if event.id in self._seen_ids:
            return PublishResult(
                ok=False,
                duplicate=True,
                received_at=received_at,
                results=[],
                errors=["duplicate event_id"],
            )
        self._seen_ids.add(event.id)
        results: list[Any] = []
        errors: list[str] = []
        handlers = list(self._handlers.get(event.type, []))
        handlers.extend(self._handlers.get("*", []))
        for handler in handlers:
            try:
                results.append(handler(event))
            except Exception as exc:  # noqa: BLE001 — isolate, continue
                errors.append(f"{type(exc).__name__}: {exc}")
                self._record_error(event, exc)
        return PublishResult(
            ok=not errors,
            duplicate=False,
            received_at=received_at,
            results=results,
            errors=errors,
        )

    def _record_error(self, event: Event, exc: BaseException) -> None:
        # Never log payload / member speech. id + type only.
        msg = f"handler failed event_id={event.id} type={event.type}"
        if self._error_sink is not None:
            self._error_sink(msg, exc)
            return
        self._log.exception("%s", msg)


InMemoryEventBus = EventBus
