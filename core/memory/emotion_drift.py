"""Emotion drift + daily snapshot (m2).

Rhythm (product decision 2026-09-03):
- Continuous decay by hours since last interaction
  loneliness += 5/h, happiness -= 1.5/h (same as cat-brain.drift)
- Persist a daily snapshot at most once per calendar day (local date)
- Never stores child utterances
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.memory.paths import emotion_snapshot_file, emotion_state_file, tangtang_home

LONELINESS_PER_HOUR = 5.0
HAPPINESS_DECAY_PER_HOUR = 1.5
DEFAULT_STATE = {
    "happiness": 70.0,
    "energy": 70.0,
    "loneliness": 20.0,
    "affection": 50.0,
    "last_interaction": None,
    "interactions_today": 0,
    "today": None,
    "mood_label": "calm",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def mood_label(state: Mapping[str, Any]) -> str:
    loneliness = float(state.get("loneliness") or 0)
    energy = float(state.get("energy") or 0)
    happiness = float(state.get("happiness") or 0)
    if loneliness >= 65:
        return "lonely"
    if energy <= 30:
        return "sleepy"
    if happiness >= 75:
        return "happy"
    if happiness <= 35:
        return "low"
    return "calm"


def apply_drift(
    state: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a new state with continuous time drift applied."""
    when = now or _utc_now()
    out = deepcopy(dict(state or DEFAULT_STATE))
    for key, default in DEFAULT_STATE.items():
        out.setdefault(key, default)

    last = _parse_ts(out.get("last_interaction")) or when
    hours = max(0.0, (when - last).total_seconds() / 3600.0)
    out["loneliness"] = min(100.0, round(float(out["loneliness"]) + hours * LONELINESS_PER_HOUR, 1))
    out["happiness"] = max(0.0, round(float(out["happiness"]) - hours * HAPPINESS_DECAY_PER_HOUR, 1))

    hour = when.astimezone().hour if when.tzinfo else when.hour
    if hour >= 23 or hour < 6:
        out["energy"] = min(60.0, float(out["energy"]))

    day = when.astimezone().strftime("%Y-%m-%d") if when.tzinfo else when.strftime("%Y-%m-%d")
    if out.get("today") != day:
        out["today"] = day
        out["interactions_today"] = 0

    out["mood_label"] = mood_label(out)
    out["drift_hours"] = round(hours, 3)
    return out


def note_interaction(
    state: Mapping[str, Any] | None,
    *,
    kind: str = "care",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply a light interaction bump after drift (no utterance stored)."""
    when = now or _utc_now()
    out = apply_drift(state, now=when)
    bumps = {
        "greet": (8, -18, 3, -2),
        "pat": (12, -12, 5, 0),
        "home": (15, -30, 5, 0),
        "care": (4, -6, 1, -1),
    }
    dh, dl, da, de = bumps.get(kind, bumps["care"])
    out["happiness"] = min(100.0, round(float(out["happiness"]) + dh, 1))
    out["loneliness"] = max(0.0, round(float(out["loneliness"]) + dl, 1))
    out["affection"] = min(100.0, round(float(out["affection"]) + da, 1))
    out["energy"] = max(0.0, min(100.0, round(float(out["energy"]) + de, 1)))
    out["last_interaction"] = when.isoformat(timespec="seconds")
    out["interactions_today"] = int(out.get("interactions_today") or 0) + 1
    out["mood_label"] = mood_label(out)
    return out


class EmotionDriftStore:
    """Persist live emotion state + at most one snapshot per local day."""

    def __init__(
        self,
        *,
        home: str | Path | None = None,
        clock: Callable[[], datetime] | None = None,
        persist: bool = True,
    ) -> None:
        self._clock = clock or _utc_now
        self._persist = persist
        self._home = Path(home).resolve() if home else None
        self._state: dict[str, Any] = dict(DEFAULT_STATE)
        if self._persist:
            self._load()

    def _root(self) -> Path:
        return self._home or tangtang_home()

    def _load(self) -> None:
        path = emotion_state_file(self._root())
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._state.update(data)
        except (OSError, json.JSONDecodeError):
            return

    def current(self, *, now: datetime | None = None) -> dict[str, Any]:
        when = now or self._clock()
        self._state = apply_drift(self._state, now=when)
        return dict(self._state)

    def interact(self, kind: str = "care", *, now: datetime | None = None) -> dict[str, Any]:
        when = now or self._clock()
        self._state = note_interaction(self._state, kind=kind, now=when)
        if self._persist:
            self.save(now=when)
        return dict(self._state)

    def save(self, *, now: datetime | None = None) -> dict[str, Any]:
        when = now or self._clock()
        self._state = apply_drift(self._state, now=when)
        if not self._persist:
            return dict(self._state)
        root = self._root()
        path = emotion_state_file(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        self.maybe_snapshot(now=when)
        return dict(self._state)

    def maybe_snapshot(self, *, now: datetime | None = None) -> bool:
        """Append one JSONL snapshot per local calendar day. Returns True if written."""
        if not self._persist:
            return False
        when = now or self._clock()
        local = when.astimezone() if when.tzinfo else when
        day = local.strftime("%Y-%m-%d")
        if self._state.get("snapshot_day") == day:
            return False
        root = self._root()
        path = emotion_snapshot_file(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "date": day,
            "ts": when.isoformat(timespec="seconds"),
            "happiness": float(self._state.get("happiness") or 0),
            "energy": float(self._state.get("energy") or 0),
            "loneliness": float(self._state.get("loneliness") or 0),
            "affection": float(self._state.get("affection") or 0),
            "mood_label": mood_label(self._state),
            "interactions_today": int(self._state.get("interactions_today") or 0),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._state["snapshot_day"] = day
        # rewrite state so snapshot_day sticks
        state_path = emotion_state_file(root)
        tmp = state_path.with_suffix(state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(state_path)
        return True
