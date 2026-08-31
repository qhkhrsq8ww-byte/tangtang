"""One speak-or-not path for live chat / voice / remind.

Consults InterruptPolicy. Live chat/voice do not speak during quiet
hours (22:30–07:00) even if the caller marked the turn interactive.
Alarm ringing is never gated here — use channel='alarm'.

Deterministic. No LLM, TTS, files, or shell.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from core.policy.interrupt_policy import InterruptPolicy

DECISIONS = frozenset({"SPEAK", "SILENT", "DELAY", "LOG_ONLY"})
_QUIET_CHANNELS = frozenset({"chat", "voice"})


def may_call_llm(decision: str) -> bool:
    """LLM only when the unified gate says SPEAK."""
    return decision == "SPEAK"


def decide(
    observation: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    *,
    channel: str = "chat",
    policy: InterruptPolicy | None = None,
    live: bool = False,
) -> str:
    """Return SPEAK / SILENT / DELAY / LOG_ONLY.

    channel='alarm' always SPEAK (cat-alarm rings on its own path).
    channel='chat'|'voice' + (live or explicit now) → quiet hours SILENT.
    Otherwise InterruptPolicy.decide.
    """
    if channel == "alarm":
        return "SPEAK"
    obs: dict[str, Any] = dict(observation or {})
    if obs.get("emergency"):
        return "SPEAK"
    gate = policy or InterruptPolicy()
    when = now if isinstance(now, datetime) else obs.get("now")
    if not isinstance(when, datetime):
        when = None

    # Live / explicit-clock chat: no night talking. Do not wait for LLM.
    apply_quiet = bool(live or when is not None)
    if channel in _QUIET_CHANNELS and apply_quiet:
        tick = when or gate._clock()  # noqa: SLF001 — same clock as the policy
        if gate.is_quiet_hours(tick):
            return "SILENT"

    return gate.decide(obs, now=when)
