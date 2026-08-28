"""Map Event + PresentationAction → AnimationAction. Presentation layer only."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

VOICE_EVENT_TYPES = frozenset(
    {"utterance", "voice.observed", "voice", "speech", "listen"}
)

ACTION_TO_ANIM = {
    "idle": "idle",
    "greet": "happy",
    "welcome": "happy",
    "happy": "happy",
    "encourage": "encourage",
    "encouraging": "encourage",
    "caring": "encourage",
    "refuse": "sad",
    "sad": "sad",
    "walk": "walk",
    "run": "run",
    "sit": "sit",
    "sitting": "sit",
    "lie": "lie",
    "lying": "lie",
    "sleep": "sleep",
    "sleeping": "sleep",
    "sleepy": "sleep",
    "listen": "listen",
    "curious": "listen",
    "tilt": "listen",
    "blink": "blink",
    "show": "idle",
    "stand": "idle",
    "站立": "idle",
    "眨眼": "blink",
    "走路": "walk",
    "跑步": "run",
    "坐下": "sit",
    "趴下": "lie",
    "睡觉": "sleep",
    "开心": "happy",
    "鼓励": "encourage",
    "难过": "sad",
    "歪头": "listen",
}

VIGOROUS = frozenset({"walk", "run", "happy"})
LOOPING = frozenset({"idle", "walk", "run", "sleep"})


@dataclass(frozen=True)
class AnimationAction:
    name: str
    loops: int = 1
    priority: int = 0
    interrupt: bool = True
    force: bool = False

    def __post_init__(self) -> None:
        raw = (self.name or "idle").strip().lower()
        mapped = ACTION_TO_ANIM.get(raw, raw if raw in ACTION_TO_ANIM.values() else "idle")
        if mapped not in {
            "idle",
            "blink",
            "listen",
            "tilt",
            "happy",
            "encourage",
            "sad",
            "walk",
            "run",
            "sit",
            "lie",
            "sleep",
        }:
            mapped = "idle"
        object.__setattr__(self, "name", mapped)
        loops = self.loops if isinstance(self.loops, int) and self.loops > 0 else 1
        object.__setattr__(self, "loops", loops)


def is_night(now: datetime | None = None) -> bool:
    """Living-room night window 22:30–07:00. Presentation-only; does not edit quiet-hours.py."""
    tick = now or datetime.now()
    mins = tick.hour * 60 + tick.minute
    return mins >= 22 * 60 + 30 or mins < 7 * 60


def soften_for_night(name: str, night: bool) -> str:
    if night and name in VIGOROUS:
        return "sit" if name in {"walk", "run"} else "idle"
    return name


def animation_from_response_action(action: Any) -> str:
    label = getattr(action, "action", None)
    if not isinstance(label, str) or not label.strip():
        return "idle"
    return AnimationAction(label).name


def event_wants_listen(event: Any) -> bool:
    etype = getattr(event, "type", None)
    if isinstance(etype, str) and etype.strip().lower() in VOICE_EVENT_TYPES:
        return True
    return False


def plan_actions(
    event: Any = None,
    response: Any = None,
    *,
    night: bool | None = None,
    now: datetime | None = None,
    specs: dict[str, dict] | None = None,
) -> list[AnimationAction]:
    """观察 → 转头 → 判断 → 动作. Never skip listen on a family voice event."""
    dark = is_night(now) if night is None else bool(night)
    steps: list[AnimationAction] = []
    if event_wants_listen(event):
        listen_pri = int((specs or {}).get("listen", {}).get("priority", 3))
        steps.append(
            AnimationAction(name="listen", loops=1, priority=listen_pri, interrupt=True)
        )
    mapped = animation_from_response_action(response) if response is not None else "idle"
    mapped = soften_for_night(mapped, dark)
    spec = (specs or {}).get(mapped, {})
    pri = int(spec.get("priority", 0) or 0)
    interruptible = bool(spec.get("interruptible", True))
    force = mapped == "idle" and event is not None and getattr(event, "type", "") == "wake"
    steps.append(
        AnimationAction(
            name=mapped,
            loops=1,
            priority=pri,
            interrupt=interruptible,
            force=force,
        )
    )
    if mapped not in LOOPING:
        idle_pri = int((specs or {}).get("idle", {}).get("priority", 0))
        steps.append(AnimationAction(name="idle", loops=1, priority=idle_pri, interrupt=True))
    return steps
