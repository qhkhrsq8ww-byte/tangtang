"""Convert living-room scenes to V4 events. Do not dump-merge that branch.

手机/久坐/吃饭/运动/睡觉/回家/离家 →
  phone.usage / activity.sedentary / meal.missed / exercise.missing /
  sleep.late / family.arrived / family.left

Then Brain → InterruptPolicy (SPEAK|SILENT|DELAY|LOG_ONLY) → Response.

Sleeping → SILENT; just reminded → DELAY; low value → LOG_ONLY.
This adapter only builds the Event + observation flags. Policy decides.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.events.event import Event
from core.policy.interrupt_policy import infer_scene

KIND_TO_TYPE: dict[str, str] = {
    "手机": "phone.usage",
    "phone": "phone.usage",
    "玩手机": "phone.usage",
    "screen": "phone.usage",
    "久坐": "activity.sedentary",
    "sitting": "activity.sedentary",
    "sedentary": "activity.sedentary",
    "吃饭": "meal.missed",
    "meal": "meal.missed",
    "no_meal": "meal.missed",
    "运动": "exercise.missing",
    "exercise": "exercise.missing",
    "睡觉": "sleep.late",
    "sleep": "sleep.late",
    "late_sleep": "sleep.late",
    "回家": "family.arrived",
    "home": "family.arrived",
    "arrived": "family.arrived",
    "离家": "family.left",
    "away": "family.left",
    "left": "family.left",
}

TYPE_TO_SCENE: dict[str, str] = {
    "phone.usage": "phone",
    "activity.sedentary": "sitting",
    "meal.missed": "no_meal",
    "exercise.missing": "exercise",
    "sleep.late": "late_sleep",
    "family.arrived": "home",
    "family.left": "away",
}

LIVING_ROOM_EVENT_TYPES = frozenset(TYPE_TO_SCENE)


def normalize_kind(kind: str | None) -> str | None:
    if not kind:
        return None
    text = str(kind).strip()
    if text in LIVING_ROOM_EVENT_TYPES:
        return text
    return KIND_TO_TYPE.get(text) or KIND_TO_TYPE.get(text.lower())


class LivingRoomAdapter:
    """Living-room scene → Event. Does not speak, project, or call an LLM."""

    core_api_version = "4.0.0"

    def event_type_for(self, kind: str | None) -> str | None:
        return normalize_kind(kind)

    def observation_for(
        self,
        kind: str | None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        obs = dict(extra or {})
        event_type = normalize_kind(kind) or str(kind or "").strip() or None
        if event_type:
            obs["event_type"] = event_type
            scene = TYPE_TO_SCENE.get(event_type)
            if scene:
                obs.setdefault("scene", scene)
        if event_type == "phone.usage":
            obs.setdefault("phone", True)
        elif event_type == "activity.sedentary":
            obs.setdefault("sitting", True)
        elif event_type == "meal.missed":
            obs.setdefault("no_meal", True)
        elif event_type == "exercise.missing":
            obs.setdefault("exercise", True)
        elif event_type == "sleep.late":
            obs.setdefault("late_sleep", True)
        elif event_type == "family.arrived":
            obs.setdefault("just_arrived", True)
            obs.setdefault("presence_home", True)
        elif event_type == "family.left":
            obs.setdefault("presence_home", False)
        if obs.get("sleeping") or obs.get("asleep"):
            obs["sleeping"] = True
        return obs

    def to_event(
        self,
        kind: str | None,
        *,
        member_id: str | None = None,
        privacy: str = "PUBLIC",
        extra: Mapping[str, Any] | None = None,
        event_id: str | None = None,
        source: str = "living-room",
    ) -> Event:
        obs = self.observation_for(kind, extra)
        event_type = str(obs.get("event_type") or normalize_kind(kind) or "living.unknown")
        payload = {
            "scene": obs.get("scene") or infer_scene(obs),
            "event_type": event_type,
        }
        if obs.get("sleeping"):
            payload["sleeping"] = True
        return Event.create(
            id=event_id,
            type=event_type[:64],
            source=source,
            privacy=privacy if privacy in {"PRIVATE", "FAMILY", "PUBLIC"} else "PUBLIC",
            member_id=member_id,
            payload=payload,
        )
