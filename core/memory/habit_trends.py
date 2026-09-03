"""Habit trends — day ledger + 7d rollup + 14d stable (m2).

Never stores child raw speech. Only event tags / counts.
Stable habits require >= 14 distinct active days with enough samples.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.errors import MemoryError
from core.memory.paths import habit_trends_file, tangtang_home
from core.policy.privacy_policy import PrivacyPolicy, raw_utterance_from

RECENT_DAYS = 7
STABLE_DAYS = 14
STABLE_MIN_EVENTS = 5

# Allowed tags only — reject free text masquerading as tags.
ALLOWED_TAGS = frozenset({
    "wake", "sleep", "meal", "water", "exercise", "screen",
    "study", "work", "outdoor", "home", "away", "chore",
    "conversation", "mood_signal",
    "english", "ask", "move", "rest", "alarm", "turn",
    "joined", "joined_soft", "oppose", "silent", "defer",
    "wont", "unclear", "stop_today", "skip",
    "greet", "pat", "play", "homework", "tidy", "emotion",
    "caring", "encouraging", "happy", "curious",
})

FORBIDDEN_KEYS = frozenset({
    "text", "transcript", "utterance", "pcm", "audio", "words", "say",
    "stt_text", "embedding", "voiceprint", "speech", "raw", "message",
})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _day_key(when: datetime) -> str:
    local = when.astimezone() if when.tzinfo else when
    return local.strftime("%Y-%m-%d")


class HabitTrendStore:
    """Persist tag counts by member/day. Promote stable after 14 active days."""

    def __init__(
        self,
        *,
        home: str | Path | None = None,
        privacy: PrivacyPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        persist: bool = True,
    ) -> None:
        self._privacy = privacy or PrivacyPolicy()
        self._clock = clock or _utc_now
        self._persist = persist
        self._home = Path(home).resolve() if home else None
        # {member_id: {YYYY-MM-DD: {tag: count}}}
        self._days: dict[str, dict[str, dict[str, int]]] = {}
        self._stable: dict[str, dict[str, Any]] = {}
        if self._persist:
            self._load()

    def _root(self) -> Path:
        return self._home or tangtang_home()

    def _load(self) -> None:
        path = habit_trends_file(self._root())
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        days = data.get("days") or {}
        if isinstance(days, dict):
            self._days = {
                str(mid): {
                    str(day): {str(t): int(c) for t, c in (tags or {}).items() if str(t) in ALLOWED_TAGS}
                    for day, tags in (member or {}).items()
                }
                for mid, member in days.items()
            }
        stable = data.get("stable") or {}
        if isinstance(stable, dict):
            self._stable = {str(k): dict(v) for k, v in stable.items() if isinstance(v, dict)}

    def save(self) -> None:
        if not self._persist:
            return
        path = habit_trends_file(self._root())
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "recent_days": RECENT_DAYS,
            "stable_days": STABLE_DAYS,
            "days": self._days,
            "stable": self._stable,
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def record(
        self,
        *,
        member_id: str,
        tag: str,
        now: datetime | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        mid = str(member_id or "").strip() or "unknown"
        clean_tag = str(tag or "").strip().lower()
        if clean_tag not in ALLOWED_TAGS:
            raise MemoryError(f"unknown habit tag: {tag!r}")
        if extra:
            for key in extra:
                if str(key).lower() in FORBIDDEN_KEYS:
                    raise MemoryError("habit trends reject utterance-like keys")
            raw = raw_utterance_from(dict(extra))
            if raw:
                raise MemoryError("habit trends reject raw utterance")
            if self._privacy.is_child(mid) and raw_utterance_from(dict(extra)):
                raise MemoryError("child raw speech cannot enter habit trends")

        when = now or self._clock()
        day = _day_key(when)
        bucket = self._days.setdefault(mid, {}).setdefault(day, {})
        bucket[clean_tag] = int(bucket.get(clean_tag) or 0) + 1
        promoted = self._maybe_promote_stable(mid, when)
        if self._persist:
            self.save()
        return {
            "member_id": mid,
            "date": day,
            "tag": clean_tag,
            "count": bucket[clean_tag],
            "stable_promoted": promoted,
        }

    def today(self, member_id: str, *, now: datetime | None = None) -> dict[str, int]:
        mid = str(member_id or "").strip() or "unknown"
        day = _day_key(now or self._clock())
        return dict(self._days.get(mid, {}).get(day) or {})

    def recent(
        self,
        member_id: str,
        *,
        now: datetime | None = None,
        days: int = RECENT_DAYS,
    ) -> dict[str, Any]:
        mid = str(member_id or "").strip() or "unknown"
        when = now or self._clock()
        totals: dict[str, int] = {}
        active_days = 0
        for i in range(max(1, days)):
            day = _day_key(when - timedelta(days=i))
            tags = self._days.get(mid, {}).get(day) or {}
            if tags:
                active_days += 1
            for tag, count in tags.items():
                totals[tag] = int(totals.get(tag) or 0) + int(count)
        return {
            "member_id": mid,
            "window_days": days,
            "active_days": active_days,
            "totals": totals,
        }

    def stable(self, member_id: str) -> dict[str, Any]:
        mid = str(member_id or "").strip() or "unknown"
        return dict(self._stable.get(mid) or {"member_id": mid, "habits": {}})

    def _maybe_promote_stable(self, member_id: str, when: datetime) -> list[str]:
        """Promote tags seen on >= STABLE_DAYS distinct days with enough events."""
        promoted: list[str] = []
        member_days = self._days.get(member_id) or {}
        tag_days: dict[str, int] = {}
        tag_events: dict[str, int] = {}
        for tags in member_days.values():
            for tag, count in tags.items():
                tag_days[tag] = int(tag_days.get(tag) or 0) + 1
                tag_events[tag] = int(tag_events.get(tag) or 0) + int(count)

        habits = dict((self._stable.get(member_id) or {}).get("habits") or {})
        for tag, dcount in tag_days.items():
            if dcount >= STABLE_DAYS and tag_events.get(tag, 0) >= STABLE_MIN_EVENTS:
                if tag not in habits:
                    promoted.append(tag)
                habits[tag] = {
                    "active_days": dcount,
                    "events": tag_events[tag],
                    "promoted_at": when.isoformat(timespec="seconds"),
                }
        if habits:
            self._stable[member_id] = {
                "member_id": member_id,
                "habits": habits,
                "updated_at": when.isoformat(timespec="seconds"),
            }
        return promoted
