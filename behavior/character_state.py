"""Deterministic character-state resolver for TangTang.

Keeps presentation choices out of the LLM. The resolver consumes normalized
context and returns a safe, presentation-neutral character state plus reason.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

VALID_STATES = frozenset({
    "idle", "talk", "happy", "curious", "thinking", "caring",
    "encouraging", "walking", "running", "sitting", "lying", "sleepy",
    "sleeping", "welcome", "accompany", "wakeup", "night",
})


@dataclass(frozen=True)
class CharacterState:
    state: str
    reason: str
    priority: int

    def __post_init__(self) -> None:
        if self.state not in VALID_STATES:
            raise ValueError(f"unknown character state: {self.state}")


class CharacterStateResolver:
    """Map context into one of the 17 supported presentation states."""

    def resolve(self, context: Mapping[str, Any]) -> CharacterState:
        event_type = str(context.get("event_type") or "").lower()
        explicit_intent = str(context.get("intent") or "").lower()
        emotion = str(context.get("emotion") or "").lower()
        decision = str(context.get("decision") or "").upper()
        active = bool(context.get("active_conversation"))
        now = context.get("now") or datetime.now()

        # Hard presentation boundaries first: sleep/night should not be
        # overridden by ordinary low-priority events.
        if isinstance(now, datetime) and (now.hour >= 23 or now.hour < 6):
            if not active and event_type not in {"user.woke", "voice.wake", "wake"}:
                return CharacterState("night", "nighttime", 100)

        if event_type in {"sleep.started", "sleep", "bedtime"}:
            return CharacterState("sleeping", "sleep event", 100)
        if event_type in {"sleepy", "fatigue"}:
            return CharacterState("sleepy", "fatigue", 90)
        if event_type in {"wake", "user.woke", "voice.wake"}:
            return CharacterState("wakeup", "wake event", 90)
        if event_type in {"home.arrived", "home", "welcome"}:
            return CharacterState("welcome", "arrival", 80)

        if decision == "SILENT" and not active:
            return CharacterState("idle", "policy silent", 70)
        if active or event_type in {"voice.detected", "conversation.started", "user.speaking"}:
            if explicit_intent in {"ask", "question", "listen"} or emotion == "curious":
                return CharacterState("curious", "listening to user", 75)
            if emotion in {"sad", "low", "upset", "worried", "tired"}:
                return CharacterState("caring", "supportive conversation", 76)
            if explicit_intent in {"encourage", "motivate"}:
                return CharacterState("encouraging", "encouragement", 76)
            return CharacterState("talk", "active conversation", 74)

        if event_type in {"exercise.started", "exercise", "running"}:
            return CharacterState("running", "exercise", 65)
        if event_type in {"walking", "walk"}:
            return CharacterState("walking", "walking", 60)
        if event_type in {"meal", "meal.started", "pat", "play", "fun"}:
            return CharacterState("happy", "positive event", 55)
        if event_type in {"homework", "study", "task.started"}:
            return CharacterState("thinking", "focus task", 50)
        if event_type in {"rest", "emotion", "weather", "water", "comfort"}:
            return CharacterState("caring", "care event", 50)
        if event_type in {"sitting", "sit"}:
            return CharacterState("sitting", "sitting", 40)
        if event_type in {"lying", "lie", "resting"}:
            return CharacterState("lying", "resting", 40)
        if event_type in {"accompany", "quiet_company"}:
            return CharacterState("accompany", "companionship", 35)
        if event_type in {"night"}:
            return CharacterState("night", "night event", 90)

        return CharacterState("idle", "default", 10)
