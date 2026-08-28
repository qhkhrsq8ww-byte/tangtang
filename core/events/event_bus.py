"""In-memory EventBus: inject clock, no I/O, handler faults isolated.

`publish` still requires a validated Event (Round 1). `accept` never
raises: duplicate / out-of-order / future / bad ts / huge / empty /
non-event all become PublishResult and the process continues.

Restart persistence lives in core.runtime.checkpoint (optional seen_store).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from core.errors import EventError
from core.events.event import Event
from core.runtime.isolate import isolate

Handler = Callable[[Event], Any]


class SeenStore(Protocol):
    def contains(self, event_id: str) -> bool: ...

    def add(self, event_id: str) -> None: ...

    def all_ids(self) -> set[str]: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass
class PublishResult:
    ok: bool
    duplicate: bool
    received_at: str
    results: list[Any] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    accepted: bool = True
    future_ts: bool = False
    out_of_order: bool = False
    event_id: str | None = None


class IsolationPlaceholder(Exception):
    """Stand-in for error_sink when isolate() already swallowed the exception."""


class EventBus:
    """Synchronous in-memory bus. Unit tests inject `clock` and `error_sink`."""

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
        error_sink: Callable[[str, BaseException], None] | None = None,
        seen_store: SeenStore | None = None,
    ) -> None:
        self._clock = clock or _utc_now
        self._error_sink = error_sink
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._seen_ids: set[str] = set()
        self._seen_store = seen_store
        if seen_store is not None:
            loaded = isolate(seen_store.all_ids, fallback=set())
            if loaded.ok and isinstance(loaded.value, set):
                self._seen_ids |= loaded.value
            elif isinstance(loaded.value, set):
                self._seen_ids |= loaded.value
        self._last_ts: datetime | None = None
        self._log = logging.getLogger("core.events.bus")

    def subscribe(self, event_type: str, handler: Handler) -> None:
        if not event_type or not str(event_type).strip():
            raise EventError("event_type is required to subscribe")
        if not callable(handler):
            raise EventError("handler must be callable")
        self._handlers[str(event_type).strip()].append(handler)

    def accept(self, raw: Any) -> PublishResult:
        """Never raise. Illegal payloads become ok=False, accepted=False."""
        received_at = self._clock().isoformat()
        try:
            if isinstance(raw, Event):
                event = raw
            elif isinstance(raw, Mapping):
                event = Event.from_dict(raw)
            else:
                return PublishResult(
                    ok=False,
                    duplicate=False,
                    received_at=received_at,
                    errors=["not an event"],
                    accepted=False,
                )
        except EventError as exc:
            return PublishResult(
                ok=False,
                duplicate=False,
                received_at=received_at,
                errors=[str(exc)],
                accepted=False,
            )
        except Exception as exc:  # noqa: BLE001
            return PublishResult(
                ok=False,
                duplicate=False,
                received_at=received_at,
                errors=[type(exc).__name__],
                accepted=False,
            )
        return self.publish(event)

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
                event_id=event.id,
            )
        self._seen_ids.add(event.id)
        if self._seen_store is not None:
            isolate(lambda: self._seen_store.add(event.id))
        future_ts = False
        out_of_order = False
        parsed = _parse_ts(event.ts)
        now = self._clock()
        if parsed is None and event.ts:
            out_of_order = True
        elif parsed is not None:
            if parsed - now > timedelta(minutes=5):
                future_ts = True
            if self._last_ts is not None and parsed < self._last_ts:
                out_of_order = True
            self._last_ts = parsed
        results: list[Any] = []
        errors: list[str] = []
        handlers = list(self._handlers.get(event.type, []))
        handlers.extend(self._handlers.get("*", []))
        for handler in handlers:
            wrapped = isolate(lambda h=handler: h(event))
            if wrapped.ok:
                results.append(wrapped.value)
            else:
                errors.append(wrapped.error_type or "handler")
                self._record_error_msg(event, wrapped.error_type or "Exception")
        return PublishResult(
            ok=not errors,
            duplicate=False,
            received_at=received_at,
            results=results,
            errors=errors,
            future_ts=future_ts,
            out_of_order=out_of_order,
            event_id=event.id,
        )

    def _record_error_msg(self, event: Event, kind: str) -> None:
        msg = f"handler failed event_id={event.id} type={event.type}"
        if self._error_sink is not None:
            self._error_sink(msg, IsolationPlaceholder(kind))
            return
        self._log.error("%s kind=%s", msg, kind)


InMemoryEventBus = EventBus
