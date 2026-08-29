"""Character State Engine — unique production decision for 糖糖's body.

Does not store utterances. Does not read video files. Does not call TTS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Mapping

VALID_STATES = frozenset({
    "idle", "talk", "happy", "curious", "thinking", "caring",
    "encouraging", "walking", "running", "sitting", "lying", "sleepy",
    "sleeping", "welcome", "accompany", "wakeup", "night",
})

PRIORITY = {
    "sleep_night": 100,
    "user": 90,
    "conversation": 80,
    "emotion": 70,
    "welcome": 60,
    "activity": 50,
    "routine": 30,
    "idle": 10,
}

MIN_DURATION = {
    "sleeping": 8.0,
    "night": 6.0,
    "welcome": 3.0,
    "caring": 3.0,
    "running": 4.0,
    "talk": 2.0,
    "idle": 2.0,
}

NEGATIVE = frozenset({"sad", "low", "upset", "worried", "hurt", "scared"})
POSITIVE = frozenset({"happy", "proud", "excited", "joy"})
QUESTION = frozenset({"ask", "question", "how", "help_homework"})


def _now(value: Any) -> datetime:
    return value if isinstance(value, datetime) else datetime.now()


def is_quiet_hours(now: datetime) -> bool:
    mins = now.hour * 60 + now.minute
    return mins >= 22 * 60 + 30 or mins < 7 * 60


def _get(mapping: Mapping[str, Any] | None, *keys: str, default: Any = "") -> Any:
    if not mapping:
        return default
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


@dataclass
class CharacterStateDecision:
    state: str
    priority: int
    intensity: float
    reason: str
    interruptible: bool
    speech_allowed: bool
    transition_hint: str
    self_state: str
    social_state: str
    presentation_state: str
    previous_state: str | None = None

    def __post_init__(self) -> None:
        if self.state not in VALID_STATES:
            self.state = "idle"
        if self.presentation_state not in VALID_STATES:
            self.presentation_state = self.state
        self.intensity = max(0.0, min(1.0, float(self.intensity)))


@dataclass
class _Hold:
    state: str
    priority: int
    until: datetime
    last_key: str = ""


class CharacterStateResolver:
    """Map Event + Identity + Context + Policy → CharacterStateDecision."""

    def resolve(
        self,
        event: Mapping[str, Any] | None = None,
        identity: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
        policy_result: Mapping[str, Any] | None = None,
    ) -> CharacterStateDecision:
        event = event or {}
        context = context or {}
        policy_result = policy_result or {}
        identity = identity or {}

        # Privacy: never read utterance / raw speech.
        if "utterance" in event or "transcript" in event or "text" in event:
            event = {k: v for k, v in event.items() if k not in {"utterance", "transcript", "text", "stt"}}

        event_type = str(_get(event, "type", "event_type", default="")).lower()
        emotion = str(_get(event, "emotion", default=_get(context, "emotion"))).lower()
        intent = str(_get(event, "intent", default=_get(context, "intent"))).lower()
        scene = str(_get(event, "scene", default=_get(context, "scene"))).lower()
        companion = bool(_get(event, "companion", default=_get(context, "companion", default=False)))
        decision = str(_get(policy_result, "decision", default=_get(context, "decision"))).upper()
        now = _now(_get(context, "now", default=_get(event, "now", default=None)))
        quiet = bool(_get(policy_result, "quiet_hours", default=is_quiet_hours(now)))
        if decision == "SILENT" or quiet:
            speech = False
        else:
            speech = decision != "LOG_ONLY"

        # --- 100: sleep / night / quiet hours ---
        if event_type in {"sleep.started", "sleep", "bedtime"}:
            return self._out("sleeping", "calm", "accompany", 100, "sleep event", speech and False, now)
        if quiet and event_type in {"exercise.started", "exercise", "running", "walking", "screen.started", "screen.usage"}:
            return self._out("night", "calm", "caring", 100, "quiet hours override", False, now, intensity=0.4)
        if quiet and event_type not in {"user.woke", "voice.wake", "wake", "wakeup", "conversation.started", "user.speak"}:
            if not _get(context, "active_conversation", default=False):
                return self._out("night", "sleepy", "caring", 100, "quiet hours", False, now, intensity=0.3)

        # --- 90: explicit user interaction ---
        if event_type in {"wake", "user.woke", "voice.wake", "wakeup"}:
            return self._out("wakeup", "happy", "welcome", 90, "wake event", speech, now)
        if event_type in {"pat", "user.pat", "greet.click"}:
            return self._out("happy", "happy", "happy", 90, "explicit interaction", speech, now, intensity=0.8)

        # --- 80: conversation ---
        talking = event_type in {
            "conversation.started", "user.speaking", "user.speak", "voice.detected", "say",
        } or bool(_get(context, "active_conversation", default=False))
        if talking:
            return self._conversation(emotion, intent, scene, speech, now)

        # --- 70: emotion (non-conversation event carrying emotion) ---
        if emotion in NEGATIVE:
            return self._out("caring", "calm", "caring", 70, "negative emotion", speech, now, intensity=0.7)
        if emotion in POSITIVE:
            return self._out("happy", "happy", "happy", 70, "positive emotion", speech, now, intensity=0.8)

        # --- 60: welcome / arrival ---
        if event_type in {"home.arrived", "home", "welcome", "family.arrived"}:
            return self._out("welcome", "happy", "welcome", 60, "arrival", speech, now, intensity=0.8)

        # --- 50: activity ---
        if event_type in {"screen.started", "screen.usage", "phone.usage"}:
            return self._out("encouraging", "calm", "encouraging", 50, "screen reminder", speech, now)
        if event_type in {"exercise.started", "exercise", "running"}:
            if companion:
                return self._out("running", "happy", "encouraging", 50, "companion exercise", speech, now)
            return self._out("encouraging", "calm", "encouraging", 50, "exercise reminder", speech, now)
        if event_type in {"walk", "walking"} and companion:
            return self._out("walking", "happy", "encouraging", 50, "companion walk", speech, now)
        if scene == "homework" or event_type in {"homework", "study"}:
            if intent in QUESTION:
                return self._out("thinking", "calm", "curious", 50, "homework question", speech, now)
            if intent in {"refuse", "avoid"}:
                return self._out("encouraging", "calm", "encouraging", 50, "homework avoid", speech, now)
            return self._out("accompany", "calm", "accompany", 50, "quiet homework", speech, now)

        # --- 30: routine ---
        if event_type in {"meal", "meal.started", "pat", "play", "fun"}:
            return self._out("happy", "happy", "happy", 30, "routine positive", speech, now)
        if event_type in {"water", "weather", "rest", "comfort"}:
            return self._out("caring", "calm", "caring", 30, "care routine", speech, now)
        if event_type in {"sitting", "sit"}:
            return self._out("sitting", "calm", "accompany", 30, "sitting", speech, now)
        if event_type in {"lying", "lie", "resting"}:
            return self._out("lying", "calm", "accompany", 30, "lying", speech, now)
        if event_type in {"accompany", "quiet_company"}:
            return self._out("accompany", "calm", "accompany", 30, "companionship", speech, now)
        if event_type in {"sleepy", "fatigue"}:
            return self._out("sleepy", "sleepy", "caring", 90, "fatigue", speech, now)
        if event_type in {"night"}:
            return self._out("night", "sleepy", "caring", 100, "night event", False, now)

        if decision == "SILENT":
            return self._out("idle", "calm", "accompany", 10, "policy silent", False, now)

        return self._out("idle", "calm", "idle", 10, "default", speech, now, intensity=0.2)

    def _conversation(
        self, emotion: str, intent: str, scene: str, speech: bool, now: datetime
    ) -> CharacterStateDecision:
        if emotion in NEGATIVE:
            return self._out("caring", "calm", "caring", 80, "supportive conversation", speech, now, intensity=0.7)
        if emotion in POSITIVE:
            return self._out("happy", "happy", "happy", 80, "celebrate conversation", speech, now, intensity=0.85)
        if intent in QUESTION or scene == "homework" and intent in QUESTION:
            return self._out("curious", "calm", "curious", 80, "question", speech, now)
        if intent in {"refuse", "avoid"} and scene == "homework":
            return self._out("encouraging", "calm", "encouraging", 80, "homework encouragement", speech, now)
        if intent in {"encourage", "motivate"}:
            return self._out("encouraging", "calm", "encouraging", 80, "encouragement", speech, now)
        return self._out("talk", "calm", "talk", 80, "active conversation", speech, now)

    def _out(
        self,
        presentation: str,
        self_state: str,
        social: str,
        priority: int,
        reason: str,
        speech: bool,
        now: datetime,
        intensity: float = 0.6,
    ) -> CharacterStateDecision:
        interruptible = priority < 90
        hint = "crossfade"
        if presentation == "running":
            hint = "crossfade"
        if presentation in {"wakeup"}:
            hint = "natural"
        return CharacterStateDecision(
            state=presentation,
            priority=priority,
            intensity=intensity,
            reason=reason,
            interruptible=interruptible,
            speech_allowed=bool(speech),
            transition_hint=hint,
            self_state=self_state,
            social_state=social,
            presentation_state=presentation,
        )


class CharacterStateEngine:
    """Resolver + debounce + priority hold. Unique production entry."""

    def __init__(self, resolver: CharacterStateResolver | None = None) -> None:
        self.resolver = resolver or CharacterStateResolver()
        self._hold: _Hold | None = None

    def decide(
        self,
        event: Mapping[str, Any] | None = None,
        identity: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
        policy_result: Mapping[str, Any] | None = None,
    ) -> CharacterStateDecision:
        incoming = self.resolver.resolve(event, identity, context, policy_result)
        now = _now(_get(context, "now", default=_get(event or {}, "now", default=None)))
        key = str((event or {}).get("type") or "")
        if self._hold and now < self._hold.until and incoming.priority <= self._hold.priority:
            return CharacterStateDecision(
                state=self._hold.state,
                priority=self._hold.priority,
                intensity=incoming.intensity,
                reason="debounce hold",
                interruptible=incoming.priority < self._hold.priority,
                speech_allowed=False if incoming.priority < 90 else incoming.speech_allowed,
                transition_hint="hold",
                self_state=incoming.self_state,
                social_state=incoming.social_state,
                presentation_state=self._hold.state,
                previous_state=self._hold.state,
            )
        min_s = MIN_DURATION.get(incoming.state, 2.0)
        previous = self._hold.state if self._hold else None
        self._hold = _Hold(
            state=incoming.state,
            priority=incoming.priority,
            until=now + timedelta(seconds=min_s),
            last_key=key,
        )
        incoming.previous_state = previous
        return incoming


# Back-compat name used by the first engine draft.
CharacterState = CharacterStateDecision
