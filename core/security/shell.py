"""V4 core must not exec a shell from event payload or LLM text."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.errors import ShellError


def reject_event_shell(event: Any = None, text: str | None = None, command: str | None = None) -> None:
    """Always raise. There is no safe interpolation of utterance → shell."""
    payload = None
    if event is not None:
        payload = getattr(event, "payload", None)
        if payload is None and isinstance(event, Mapping):
            payload = event.get("payload")
    raise ShellError(
        "event payload / LLM text must not reach os.system or a shell "
        f"(payload_type={type(payload).__name__}, text={bool(text)}, command={bool(command)})"
    )


def guarded_system(_command: str) -> int:
    raise ShellError("os.system is forbidden in V4 core")
