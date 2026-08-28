"""Explicit ports for V4 core.

Implementations live in sibling packages. This module must not import
ContextBuilder or MemoryStore (avoids Memory → Context → Memory cycles).
LLM code must not implement these ports for privacy, quiet hours, shell,
TTS, or projection — those stay deterministic.

CORE_API_VERSION is frozen at 4.x. A V5 port must bump the major and
will be rejected by require_v4() so it cannot silently smash V4.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from core.errors import CompatibilityError

CORE_API_VERSION = "4.0.0"
CORE_API_MAJOR = 4


def require_v4(port: object, name: str = "port") -> None:
    """Fail closed: missing or non-4.x version cannot enter the pipeline."""
    ver = getattr(port, "core_api_version", None)
    if ver is None:
        raise CompatibilityError(
            f"{name} missing core_api_version; unversioned ports cannot replace V4"
        )
    major = str(ver).split(".", 1)[0]
    if major != str(CORE_API_MAJOR):
        raise CompatibilityError(
            f"{name} core_api_version={ver} is not V4; V5 must not silently smash V4"
        )


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
class PrivacyPolicyPort(Protocol):
    """Deterministic classifier. LLM must not implement this port."""

    def classify(
        self,
        *,
        member_id: str | None = None,
        utterance: str | None = None,
        observation: Mapping[str, Any] | None = None,
    ) -> Any: ...

    def allow_destination(
        self,
        destination: str,
        *,
        member_id: str | None = None,
        utterance: str | None = None,
        privacy: str | None = None,
    ) -> bool: ...

    def is_child(self, member_id: str | None) -> bool: ...


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
