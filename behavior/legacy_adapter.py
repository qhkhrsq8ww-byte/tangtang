"""Translate cat-brain.py events into Event + CharacterStateEngine.

EVENT_STATE in cat-brain.py is not the source of truth.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from behavior.character_state import CharacterStateEngine, CharacterStateDecision, is_quiet_hours

# Legacy event name → normalized type / scene / intent. No utterance stored.
_LEGACY = {
    "greet": {"type": "user.speak", "intent": "greet"},
    "home": {"type": "home.arrived"},
    "welcome": {"type": "home.arrived"},
    "wake": {"type": "wake"},
    "sleep": {"type": "sleep.started"},
    "sleepy": {"type": "sleepy"},
    "night": {"type": "night"},
    "rest": {"type": "screen.usage", "scene": "phone"},
    "emotion": {"type": "conversation.started", "emotion": "sad"},
    "weather": {"type": "weather", "scene": "care"},
    "water": {"type": "water", "scene": "care"},
    "play": {"type": "play"},
    "exercise": {"type": "exercise", "companion": False},
    "walking": {"type": "walking", "companion": True},
    "running": {"type": "exercise", "companion": True},
    "meal": {"type": "meal"},
    "pat": {"type": "pat"},
    "homework": {"type": "homework", "scene": "homework"},
    "tidy": {"type": "homework", "scene": "homework"},
    "say": {"type": "conversation.started"},
    "random": {"type": "idle"},
    "curious": {"type": "conversation.started", "intent": "question"},
    "accompany": {"type": "accompany"},
}


def _clock(now: datetime | None = None) -> datetime:
    if now is not None:
        return now
    raw = __import__("os").environ.get("TANGTANG_NOW", "")
    if raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.now()


def to_event(legacy_name: str, arg: str = "", *, now: datetime | None = None) -> dict[str, Any]:
    name = (legacy_name or "greet").strip().lower()
    spec = dict(_LEGACY.get(name, {"type": name}))
    spec.setdefault("type", name)
    if name == "say" and arg:
        # Intent/emotion only — never pass the raw sentence through.
        lowered = arg.lower()
        if any(tok in arg for tok in ("难过", "伤心", "考砸", "欺负")):
            spec["emotion"] = "sad"
        elif any(tok in arg for tok in ("100", "满分", "开心", "棒")):
            spec["emotion"] = "happy"
        elif "作业" in arg and any(tok in arg for tok in ("不想", "不写")):
            spec["scene"] = "homework"
            spec["intent"] = "refuse"
        elif any(tok in arg for tok in ("怎么", "为什么", "?" , "？")):
            spec["intent"] = "question"
        spec.pop("utterance", None)
        spec["_legacy_arg_used"] = True
    spec["now"] = _clock(now)
    return spec


def policy_for(event: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    tick = now or event.get("now") or datetime.now()
    if not isinstance(tick, datetime):
        tick = datetime.now()
    quiet = is_quiet_hours(tick)
    if quiet and event.get("type") not in {"wake", "user.woke", "conversation.started", "say"}:
        return {"decision": "SILENT", "quiet_hours": True}
    return {"decision": "SPEAK", "quiet_hours": quiet}


def decide_from_legacy(
    legacy_name: str,
    arg: str = "",
    *,
    now: datetime | None = None,
    identity: dict[str, Any] | None = None,
    engine: CharacterStateEngine | None = None,
) -> CharacterStateDecision:
    event = to_event(legacy_name, arg, now=now)
    policy = policy_for(event, now=now)
    ctx = {"now": event["now"]}
    return (engine or CharacterStateEngine()).decide(
        event, identity or {"member_id": "unknown"}, ctx, policy
    )
