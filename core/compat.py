"""Compat shim: cat-* may later call should_interrupt without deleting cat-brain.

Existing runtime (this parent): code/cat/cat-brain.py::should_speak (cooldown).
Living-room (not merged this round): cat-brain + cat-turn + habits + school hours.

Later wiring (do not delete cat-brain):

    from core.compat import should_interrupt
    if should_interrupt(observation):
        # skip proactive speech
        ...

This wraps InterruptPolicy only. Deterministic. No LLM, files, TTS, or shell.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from core.policy.interrupt_policy import InterruptPolicy
from core.policy.speak_gate import decide as decide_speak, may_call_llm

_DEFAULT = InterruptPolicy()


def should_interrupt(
    observation: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    policy: InterruptPolicy | None = None,
    **kwargs: Any,
) -> bool:
    gate = policy or _DEFAULT
    return gate.should_interrupt(observation, now=now, **kwargs)


def may_speak(
    observation: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    *,
    channel: str = "chat",
    policy: InterruptPolicy | None = None,
    live: bool = False,
    **kwargs: Any,
) -> bool:
    """True when live chat/voice/remind may speak / call LLM."""
    obs = dict(observation or {})
    for key, value in kwargs.items():
        if value is not None and key not in obs:
            obs[key] = value
    return decide_speak(
        obs, now=now, channel=channel, policy=policy, live=live
    ) == "SPEAK"


__all__ = ["should_interrupt", "may_speak", "decide_speak", "may_call_llm"]
