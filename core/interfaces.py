"""Explicit ports for V4 core.

Implementations live in sibling packages. This module must not import
ContextBuilder or MemoryStore (avoids Memory → Context → Memory cycles).
LLM code must not implement these ports for privacy, quiet hours, shell,
TTS, or projection — those stay deterministic.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def __call__(self) -> datetime: ...


@runtime_checkable
class EventBusPort(Protocol):
    def subscribe(self, event_type: str, handler: Callable[..., Any]) -> None: ...

    def publish(self, event: Any) -> Any: ...


@runtime_checkable
class IdentityPort(Protocol):
    def resolve(self, observation: Mapping[str, Any] | None) -> str | None: ...


@runtime_checkable
class MemoryPort(Protocol):
    def put(self, memory: Any) -> None: ...

    def query(
        self,
        *,
        member_id: str,
        scope: str = "PRIVATE",
        viewer_id: str | None = None,
    ) -> list[Mapping[str, Any]]: ...


@runtime_checkable
class PolicyPort(Protocol):
    def decide(
        self,
        observation: Mapping[str, Any] | None = None,
        now: datetime | None = None,
        **kwargs: Any,
    ) -> str: ...

    def should_interrupt(
        self,
        observation: Mapping[str, Any] | None = None,
        now: datetime | None = None,
        **kwargs: Any,
    ) -> bool: ...


@runtime_checkable
class ContextPort(Protocol):
    def build(
        self,
        *,
        who: Mapping[str, Any],
        event: Any,
        observation: Mapping[str, Any] | None = None,
        recent: list[Any] | None = None,
        family: Mapping[str, Any] | None = None,
        privacy_scope: str | None = None,
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class ResponsePort(Protocol):
    def run(
        self,
        *,
        decision: str,
        context: Mapping[str, Any],
        action: str = "idle",
    ) -> Any: ...
