"""Low-pressure proactive gate: quiet hours, existing habit tags, and per-scene cooldown."""
from __future__ import annotations

import json
import os
from datetime import datetime, time
from pathlib import Path


def _clock(raw: str, fallback: str) -> time:
    try:
        return time.fromisoformat(raw)
    except ValueError:
        return time.fromisoformat(fallback)


def in_quiet_hours(now: datetime, start: str = "22:30", end: str = "07:00") -> bool:
    current = now.timetz().replace(tzinfo=None)
    left, right = _clock(start, "22:30"), _clock(end, "07:00")
    return left <= current < right if left <= right else current >= left or current < right


class ProactiveGate:
    """Stores only the last scene timestamp, never dialogue, prompts, or speech."""

    def __init__(self, *, home: str | Path, cooldown_minutes: int = 45):
        self.home = Path(home).expanduser().resolve()
        self.path = self.home / "proactive" / "cooldowns.json"
        self.cooldown_minutes = max(5, min(int(cooldown_minutes), 360))

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def check(self, *, event: str, member_id: str, now: datetime,
              habit_allows: bool = True, quiet_start: str = "22:30",
              quiet_end: str = "07:00") -> tuple[bool, str]:
        if in_quiet_hours(now, quiet_start, quiet_end):
            return False, "quiet_hours"
        if not habit_allows:
            return False, "habit_cooldown"
        key = f"{str(member_id or 'room')[:80]}:{str(event or 'scene')[:80]}"
        previous = self._load().get(key)
        if previous:
            try:
                last = datetime.fromisoformat(previous)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=now.tzinfo)
                if (now - last).total_seconds() < self.cooldown_minutes * 60:
                    return False, "scene_cooldown"
            except (TypeError, ValueError):
                pass
        return True, "ok"

    def record(self, *, event: str, member_id: str, now: datetime) -> None:
        key = f"{str(member_id or 'room')[:80]}:{str(event or 'scene')[:80]}"
        data = self._load()
        data[key] = now.isoformat(timespec="seconds")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
        os.chmod(self.path, 0o600)
