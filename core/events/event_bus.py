"""Small synchronous event bus with explicit subscribers."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from .event import Event

Handler = Callable[[Event], Any]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> list[Any]:
        results: list[Any] = []
        for handler in self._handlers.get(event.event_type, []):
            results.append(handler(event))
        for handler in self._handlers.get("*", []):
            results.append(handler(event))
        return results
