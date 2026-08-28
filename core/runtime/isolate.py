"""Failure isolation: a broken sink/handler/LLM must not crash the process."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class IsolatedResult:
    ok: bool
    value: Any = None
    error_type: str | None = None

    @property
    def error(self) -> str | None:
        return self.error_type


def isolate(fn: Callable[[], T], fallback: T | None = None) -> IsolatedResult:
    """Run fn. Never raise. Do not log arguments (may contain speech)."""
    try:
        return IsolatedResult(ok=True, value=fn(), error_type=None)
    except Exception as exc:  # noqa: BLE001 — isolation boundary
        return IsolatedResult(ok=False, value=fallback, error_type=type(exc).__name__)
