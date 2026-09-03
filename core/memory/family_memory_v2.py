"""Family Memory 2.0 — today / recent / stable / family state / next accompany.

Reads existing living-room stores under one TANGTANG_HOME / TANGTANG_DATA_DIR
root (Application Support): V3 cat-habits.json, cat-habit-growth.json,
cat-turn-ledger.json, plus V4 family/ and habits/ if present.

Does not invent a third event store. The only write is a derived
family-state.json of tags and short facts — never child raw speech.

Deterministic. No LLM. PrivacyPolicy fail-closed. Speak-gate is composed
here; this module does not bypass quiet hours / school hours / privacy.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.identity.resolver import IdentityResolver
from core.memory.paths import (
    family_file,
    family_state_file,
    habit_file,
    living_room_file,
    tangtang_home,
)
from core.policy.interrupt_policy import InterruptPolicy
from core.policy.privacy_policy import PrivacyPolicy, raw_utterance_from
from core.policy.speak_gate import decide as speak_decide

OFFICIAL_IDS = ("grandpa", "grandma", "dad", "qiaqia", "hanghang")
OFFICIAL_DISPLAY = {
    "grandpa": "爷爷",
    "grandma": "奶奶",
    "dad": "爸爸",
    "qiaqia": "洽洽",
    "hanghang": "航航",
}
OFFICIAL_MEMBERS: dict[str, dict[str, Any]] = {
    "grandpa": {
        "display_name": "爷爷",
        "relation": "elder",
        "aliases": ["爷爷", "grandpa", "外公"],
    },
    "grandma": {
        "display_name": "奶奶",
        "relation": "elder",
        "aliases": ["奶奶", "grandma", "外婆"],
    },
    "dad": {
        "display_name": "爸爸",
        "profile": "adult",
        "aliases": ["爸爸", "爸", "dad"],
    },
    "qiaqia": {
        "display_name": "洽洽",
        "relation": "child",
        "age": 12,
        "aliases": ["洽洽", "qiaqia", "姐姐", "child_12"],
        "preferences": {"english_grade": 6},
    },
    "hanghang": {
        "display_name": "航航",
        "relation": "child",
        "age": 9,
        "aliases": ["航航", "hanghang", "弟弟", "child_9"],
        "preferences": {"english_grade": 2},
    },
}

# 姐姐/弟弟 are aliases only — never official snapshot ids.
_PRODUCT_CANON = {
    "child_9": "hanghang",
    "child_12": "qiaqia",
    "姐姐": "qiaqia",
    "弟弟": "hanghang",
}

KNOWN_TAGS = frozenset({
    "wake", "sleep", "meal", "water", "exercise", "screen",
    "study", "work", "outdoor", "home", "away", "chore",
    "conversation", "mood_signal",
    "english", "ask", "move", "rest", "alarm", "turn",
    "joined", "joined_soft", "oppose", "silent", "defer",
    "wont", "unclear", "stop_today", "skip",
})
MOOD_TAGS = frozenset({
    "silent", "oppose", "joined", "defer", "stop_today",
    "mood_signal", "wont", "skip",
})
FORBIDDEN_KEYS = frozenset({
    "text", "transcript", "utterance", "pcm", "audio", "words", "say",
    "stt_text", "embedding", "voiceprint", "speech", "raw",
})
RECENT_DAYS = 7
SILENT_STREAK = 2
CHILD_HOME_DEFAULT = {"hanghang": "16:00", "qiaqia": "18:00"}
SCHOOL_LEAVE_DEFAULT = "07:30"


def _env_now() -> datetime:
    raw = (os.environ.get("CAT_NOW") or os.environ.get("TANGTANG_NOW") or "").strip()
    if raw:
        raw = raw.replace("T", " ", 1)
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
    day = (os.environ.get("TANGTANG_FAKE_TODAY") or "").strip()
    hm = (os.environ.get("TANGTANG_FAKE_TIME") or "").strip()
    if day:
        t = hm or "12:00"
        if len(t) == 5:
            t = t + ":00"
        try:
            return datetime.strptime(day + " " + t, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.now().replace(microsecond=0)


def _parse_ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    if not value:
        return None
    raw = str(value).strip().replace(" ", "T")[:19]
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _iso(ts: datetime) -> str:
    return ts.replace(microsecond=0).isoformat(timespec="seconds")


def _hm(ts: datetime) -> str:
    return ts.strftime("%H:%M")


def _load_json(path: Path | None) -> Any:
    if path is None or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def strip_forbidden(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                continue
            out[key] = strip_forbidden(value)
        return out
    if isinstance(obj, list):
        return [strip_forbidden(x) for x in obj]
    return obj


def _has_forbidden_keys(obj: Any) -> bool:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                return True
            if _has_forbidden_keys(value):
                return True
    elif isinstance(obj, list):
        return any(_has_forbidden_keys(x) for x in obj)
    return False


def _tag(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text or text not in KNOWN_TAGS:
        return None
    if text == "joined_soft":
        return "joined"
    return text


@dataclass
class AccompanyDecision:
    speak: bool
    who: str
    hint: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaggedEvent:
    member_id: str
    ts: datetime
    tag: str
    source: str = "habit"
    event: str = ""
    presence: str = ""


@dataclass
class FamilyMemoryV2:
    """Compose today / recent / stable / snapshot / next_accompany from existing stores."""

    home: str | Path | None = None
    members: Mapping[str, object] | None = None
    privacy: PrivacyPolicy | None = None
    clock: Callable[[], datetime] | None = None
    persist: bool = False

    _home: Path | None = field(init=False, default=None)
    _privacy: PrivacyPolicy = field(init=False, repr=False)
    _identity: IdentityResolver = field(init=False, repr=False)
    _clock: Callable[[], datetime] = field(init=False, repr=False)
    _roster: dict[str, dict[str, Any]] = field(init=False, repr=False)
    _interrupt: InterruptPolicy = field(init=False, repr=False)

    def __post_init__(self) -> None:
        roster = dict(OFFICIAL_MEMBERS)
        if self.members:
            for mid, rec in dict(self.members).items():
                oid = self._map_official(str(mid), IdentityResolver(self.members))
                if oid and isinstance(rec, Mapping):
                    merged = dict(roster.get(oid) or {})
                    merged.update(dict(rec))
                    roster[oid] = merged
        self._roster = roster
        self._identity = IdentityResolver(roster)
        self._privacy = self.privacy or PrivacyPolicy(roster)
        self._clock = self.clock or _env_now
        self._interrupt = InterruptPolicy(clock=self._clock)
        if self.home is not None:
            self._home = Path(self.home).resolve()
        else:
            raw = os.environ.get("TANGTANG_HOME") or os.environ.get("TANGTANG_DATA_DIR")
            self._home = tangtang_home(raw) if raw else None

    def _map_official(self, raw: str | None, identity: IdentityResolver | None = None) -> str | None:
        key = (raw or "").strip()
        if not key or key.lower() in {"unknown", "访客", "guest"}:
            return None
        ident = identity or self._identity
        mapped = _PRODUCT_CANON.get(key) or _PRODUCT_CANON.get(key.lower())
        if mapped in OFFICIAL_IDS:
            return mapped
        resolved = (
            ident.resolve({"member_id": key})
            or ident.resolve({"label": key})
            or key
        )
        mapped = _PRODUCT_CANON.get(resolved) or _PRODUCT_CANON.get(str(resolved).lower())
        if mapped in OFFICIAL_IDS:
            return mapped
        if resolved in OFFICIAL_IDS:
            return resolved
        if key in OFFICIAL_IDS:
            return key
        return None

    def official_id(self, raw: str | None) -> str | None:
        return self._map_official(raw)

    def display_name(self, member_id: str) -> str:
        oid = self.official_id(member_id) or member_id
        rec = self._roster.get(oid) or {}
        return str(rec.get("display_name") or OFFICIAL_DISPLAY.get(oid) or oid)

    def _now(self, now: datetime | None) -> datetime:
        if isinstance(now, datetime):
            return now.replace(microsecond=0)
        return self._clock()

    def _is_quiet(self, now: datetime) -> bool:
        return self._interrupt.is_quiet_hours(now)

    def _is_school_day(self, now: datetime) -> bool:
        start = (os.environ.get("TANGTANG_SCHOOL_START") or "2026-09-01").strip()
        if now.strftime("%Y-%m-%d") < start:
            return False
        return now.weekday() < 5

    def _child_home_hm(self, member_id: str) -> str:
        if member_id == "qiaqia":
            return (os.environ.get("TANGTANG_HOME_QIAQIA") or CHILD_HOME_DEFAULT["qiaqia"]).strip()
        return (os.environ.get("TANGTANG_HOME_HANGHANG") or CHILD_HOME_DEFAULT["hanghang"]).strip()

    def _env_child_at_school(self, member_id: str, now: datetime) -> bool:
        if not self._privacy.is_child(member_id):
            return False
        if not self._is_school_day(now):
            return False
        leave = (os.environ.get("TANGTANG_SCHOOL_LEAVE") or SCHOOL_LEAVE_DEFAULT).strip()
        home = self._child_home_hm(member_id)
        hm = _hm(now)
        if leave <= home:
            return leave <= hm < home
        return hm >= leave or hm < home

    def _child_at_school(
        self,
        member_id: str,
        now: datetime,
        observation: Mapping[str, Any] | None,
    ) -> bool:
        if not self._privacy.is_child(member_id):
            return False
        obs = dict(observation or {})
        flagged = bool(obs.get("school_hours") or obs.get("at_school"))
        presence = obs.get("presence_home")
        obs_who = self.official_id(
            str(obs.get("member_id") or obs.get("label") or obs.get("audience") or "")
        )
        if flagged and presence is False:
            if not obs_who or obs_who == member_id or obs.get("audience_child"):
                return True
        if flagged and presence is True and (not obs_who or obs_who == member_id):
            return False
        if flagged and obs.get("audience_child") and presence is not True:
            return True
        return self._env_child_at_school(member_id, now)

    def _interactable(
        self,
        member_id: str,
        now: datetime,
        observation: Mapping[str, Any] | None,
        *,
        proactive: bool = True,
    ) -> bool:
        obs = dict(observation or {})
        if proactive and self._is_quiet(now) and not obs.get("interactive"):
            return False
        if self._child_at_school(member_id, now, obs):
            return False
        return True

    def _candidate_paths(self, *rel: tuple[str, ...]) -> list[Path]:
        home = self._home
        if home is None:
            return []
        out: list[Path] = []
        for parts in rel:
            try:
                if len(parts) == 1:
                    out.append(living_room_file(home, parts[0]))
                elif parts[0] == "family":
                    out.append(family_file(home, parts[-1]))
                elif parts[0] == "habits":
                    out.append(habit_file(home, parts[-1]))
                else:
                    out.append(living_room_file(home, parts[-1]))
            except Exception:
                continue
        return out

    def _iter_habit_events(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self._candidate_paths(("cat-habits.json",), ("habits", "cat-habits.json")):
            data = _load_json(path)
            if isinstance(data, dict):
                for row in data.get("events") or []:
                    if isinstance(row, dict):
                        rows.append(row)
                for row in data.get("logs") or []:
                    if isinstance(row, dict):
                        rows.append(row)
            elif isinstance(data, list):
                rows.extend(r for r in data if isinstance(r, dict))
        return rows

    def _iter_turns(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self._candidate_paths(("cat-turn-ledger.json",)):
            data = _load_json(path)
            if isinstance(data, dict):
                for row in data.get("turns") or []:
                    if isinstance(row, dict):
                        rows.append(row)
        return rows

    def _growth(self) -> dict[str, Any]:
        for path in self._candidate_paths(("cat-habit-growth.json",)):
            data = _load_json(path)
            if isinstance(data, dict):
                return strip_forbidden(data)
        return {"people": {}}

    def _family_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self._candidate_paths(("family", "family-memory.json"), ("family", "family-summary.json")):
            data = _load_json(path)
            if isinstance(data, list):
                rows.extend(r for r in data if isinstance(r, dict))
        return rows

    def _as_tagged(self, row: Mapping[str, Any], *, source: str) -> TaggedEvent | None:
        if raw_utterance_from(row):
            # Never lift raw speech — even adult text stays out of the ledger.
            pass
        mid = self.official_id(
            str(row.get("member_id") or row.get("who") or row.get("name") or row.get("member") or "")
        )
        if not mid:
            return None
        ts = _parse_ts(row.get("timestamp") or row.get("ts") or row.get("time") or row.get("created_at"))
        if ts is None:
            return None
        tag = (
            _tag(row.get("type"))
            or _tag(row.get("scene"))
            or _tag(row.get("result"))
            or _tag(row.get("event"))
            or _tag(row.get("tag"))
        )
        event_name = str(row.get("event") or row.get("type") or "").strip().lower()
        if event_name in KNOWN_TAGS and tag is None:
            tag = event_name
        if tag is None:
            return None
        presence = str(row.get("presence") or row.get("last_presence") or "")
        if presence not in ("home", "away", "unknown", ""):
            presence = ""
        return TaggedEvent(
            member_id=mid,
            ts=ts,
            tag=tag,
            source=source,
            event=event_name if event_name in KNOWN_TAGS else "",
            presence=presence,
        )

    def _collect(self) -> list[TaggedEvent]:
        out: list[TaggedEvent] = []
        for row in self._iter_habit_events():
            ev = self._as_tagged(row, source="habit")
            if ev:
                out.append(ev)
        for row in self._iter_turns():
            ev = self._as_tagged(row, source="turn")
            if ev:
                out.append(ev)
        for row in self._family_rows():
            data = row.get("data") if isinstance(row.get("data"), dict) else row
            if raw_utterance_from(data) and self._privacy.is_child(row.get("member_id")):
                continue
            ev = self._as_tagged({**row, **dict(data or {})}, source="family")
            if ev:
                out.append(ev)
        out.sort(key=lambda e: e.ts)
        return out

    def _growth_cells(self, member_id: str) -> list[dict[str, Any]]:
        people = (self._growth().get("people") or {})
        events = people.get(member_id) or {}
        cells: list[dict[str, Any]] = []
        if not isinstance(events, dict):
            return cells
        for kinds in events.values():
            if not isinstance(kinds, dict):
                continue
            for cell in kinds.values():
                if isinstance(cell, dict):
                    cells.append(cell)
        return cells

    def _empty_member_today(self) -> dict[str, Any]:
        return {
            "events": [],
            "counts": {},
            "last_scene": "",
            "last_event": "",
        }

    def today_ledger(self, now: datetime | None = None) -> dict[str, Any]:
        when = self._now(now)
        day = when.strftime("%Y-%m-%d")
        members: dict[str, dict[str, Any]] = {
            mid: self._empty_member_today() for mid in OFFICIAL_IDS
        }
        for ev in self._collect():
            if ev.ts.strftime("%Y-%m-%d") != day:
                continue
            block = members[ev.member_id]
            if ev.tag not in block["events"]:
                block["events"].append(ev.tag)
            block["counts"][ev.tag] = int(block["counts"].get(ev.tag) or 0) + 1
            block["last_scene"] = ev.tag
            if ev.event:
                block["last_event"] = ev.event
        for cell_mid in OFFICIAL_IDS:
            for cell in self._growth_cells(cell_mid):
                last_ts = _parse_ts(cell.get("last_ts"))
                if last_ts is None or last_ts.strftime("%Y-%m-%d") != day:
                    continue
                scene = _tag(cell.get("last_scene"))
                if not scene:
                    continue
                block = members[cell_mid]
                if scene not in block["events"]:
                    block["events"].append(scene)
                block["counts"].setdefault(scene, int((cell.get("counts") or {}).get(scene) or 0) or 1)
                if not block["last_scene"]:
                    block["last_scene"] = scene
        snap = {
            "date": day,
            "members": members,
        }
        assert not _has_forbidden_keys(snap)
        return snap

    def recent_change(self, now: datetime | None = None, *, days: int = RECENT_DAYS) -> dict[str, Any]:
        when = self._now(now)
        today = when.strftime("%Y-%m-%d")
        start = (when - timedelta(days=days)).strftime("%Y-%m-%d")
        today_counts: dict[str, dict[str, int]] = {mid: {} for mid in OFFICIAL_IDS}
        prior_counts: dict[str, dict[str, int]] = {mid: {} for mid in OFFICIAL_IDS}
        prior_days: dict[str, set[str]] = {mid: set() for mid in OFFICIAL_IDS}
        for ev in self._collect():
            day = ev.ts.strftime("%Y-%m-%d")
            if day < start:
                continue
            bucket = today_counts if day == today else prior_counts
            bucket[ev.member_id][ev.tag] = int(bucket[ev.member_id].get(ev.tag) or 0) + 1
            if day != today:
                prior_days[ev.member_id].add(day)
        members: dict[str, Any] = {}
        for mid in OFFICIAL_IDS:
            t = today_counts[mid]
            p = prior_counts[mid]
            n_prior = max(len(prior_days[mid]), 1)
            prior_avg = {k: round(v / n_prior, 2) for k, v in p.items()}
            changes: list[str] = []
            silent_today = int(t.get("silent") or 0)
            silent_avg = float(prior_avg.get("silent") or 0)
            oppose_today = int(t.get("oppose") or 0) + int(t.get("stop_today") or 0)
            streak_silent = 0
            streak_oppose = 0
            for cell in self._growth_cells(mid):
                streak_silent = max(streak_silent, int(cell.get("streak_silent") or 0))
                streak_oppose = max(streak_oppose, int(cell.get("streak_oppose") or 0))
            if silent_today >= SILENT_STREAK or streak_silent >= SILENT_STREAK:
                changes.append("silent_streak")
            if silent_today > silent_avg and silent_today >= 1:
                changes.append("more_silent")
            if oppose_today >= 1 or streak_oppose >= 1:
                changes.append("opposed_remind")
            english_today = int(t.get("english") or 0)
            skip_today = int(t.get("skip") or 0)
            joined_today = int(t.get("joined") or 0)
            if (skip_today >= 1 or silent_today >= 1) and joined_today == 0 and (
                english_today >= 1 or int(p.get("english") or 0) >= 1
            ):
                changes.append("skipped_english")
            members[mid] = {
                "changes": changes,
                "today": {k: int(v) for k, v in t.items()},
                "prior_avg": prior_avg,
                "streak_silent": streak_silent,
                "streak_oppose": streak_oppose,
            }
        snap = {"window_days": days, "date": today, "members": members}
        assert not _has_forbidden_keys(snap)
        return snap

    def stable_memory(self) -> dict[str, Any]:
        people: dict[str, Any] = {}
        growth = self._growth()
        for mid in OFFICIAL_IDS:
            rec = self._roster.get(mid) or {}
            prefs = rec.get("preferences") if isinstance(rec.get("preferences"), Mapping) else {}
            preferred = ""
            muted_until = ""
            mute_reason = ""
            presence = ""
            hour_hint = None
            for cell in self._growth_cells(mid):
                lid = str(cell.get("preferred_line_id") or "").strip()
                if lid and not preferred:
                    preferred = lid
                until = str(cell.get("muted_until") or "")
                if until and (not muted_until or until > muted_until):
                    muted_until = until
                    mute_reason = str(cell.get("mute_reason") or "")
                if cell.get("last_presence") in ("home", "away", "unknown"):
                    presence = str(cell["last_presence"])
                if cell.get("preferred_hour_hint") not in (None, ""):
                    hour_hint = cell.get("preferred_hour_hint")
            last_line = (growth.get("last_line") or {}) if isinstance(growth.get("last_line"), dict) else {}
            if not preferred:
                for key, lid in last_line.items():
                    if str(key).startswith(mid + "|") and lid:
                        preferred = str(lid)
                        break
            people[mid] = {
                "preferred_line_id": preferred,
                "muted_until": muted_until,
                "mute_reason": mute_reason,
                "english_grade": prefs.get("english_grade"),
                "presence_pattern": presence,
                "preferred_hour_hint": hour_hint,
            }
        snap = {"members": people}
        assert not _has_forbidden_keys(snap)
        return snap

    def _mood_tags(self, today_block: Mapping[str, Any], last_scene: str) -> list[str]:
        tags: list[str] = []
        for tag in today_block.get("events") or []:
            if tag in MOOD_TAGS and tag not in tags:
                tags.append(tag)
        if last_scene in MOOD_TAGS and last_scene not in tags:
            tags.append(last_scene)
        return tags

    def _hint(self, recent: Mapping[str, Any], stable: Mapping[str, Any]) -> str:
        rec_members = recent.get("members") or {}
        stab_members = stable.get("members") or {}
        for mid in ("hanghang", "qiaqia"):
            changes = list((rec_members.get(mid) or {}).get("changes") or [])
            if "opposed_remind" in changes or "silent_streak" in changes:
                return f"少提醒{self.display_name(mid)}"
        for mid in ("qiaqia", "hanghang"):
            pref = str((stab_members.get(mid) or {}).get("preferred_line_id") or "").strip()
            mute = str((stab_members.get(mid) or {}).get("mute_reason") or "")
            if pref and mute not in ("oppose", "oppose_7d", "stop_today", "silent_streak"):
                return f"{self.display_name(mid)}英语用上次那句"
        if any(
            "more_silent" in list((rec_members.get(mid) or {}).get("changes") or [])
            for mid in OFFICIAL_IDS
        ):
            for mid in OFFICIAL_IDS:
                if "more_silent" in list((rec_members.get(mid) or {}).get("changes") or []):
                    return f"少提醒{self.display_name(mid)}"
        return "安静陪伴"

    def family_state(
        self,
        now: datetime | None = None,
        *,
        observation: Mapping[str, Any] | None = None,
        persist: bool | None = None,
    ) -> dict[str, Any]:
        when = self._now(now)
        today = self.today_ledger(when)
        recent = self.recent_change(when)
        stable = self.stable_memory()
        obs = dict(observation or {})
        school = bool(obs.get("school_hours") or obs.get("at_school") or self._is_school_day(when))
        members: dict[str, Any] = {}
        for mid in OFFICIAL_IDS:
            block = today["members"][mid]
            last_scene = str(block.get("last_scene") or "")
            members[mid] = {
                "interactable": self._interactable(mid, when, obs),
                "mood_tags": self._mood_tags(block, last_scene),
                "last_scene": last_scene,
                "display_name": self.display_name(mid),
            }
        hint = self._hint(recent, stable)
        snap = {
            "date": today["date"],
            "quiet": self._is_quiet(when),
            "school": school,
            "members": members,
            "hint": hint,
            "updated_at": _iso(when),
        }
        assert not _has_forbidden_keys(snap)
        if persist if persist is not None else self.persist:
            self._write_state(snap)
        return snap

    def _write_state(self, snap: Mapping[str, Any]) -> None:
        home = self._home
        if home is None:
            return
        clean = strip_forbidden(dict(snap))
        blob = json.dumps(clean, ensure_ascii=False)
        if _has_forbidden_keys(clean):
            return
        for key in FORBIDDEN_KEYS:
            if f'"{key}"' in blob:
                return
        path = family_state_file(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)

    def _gate_reason(
        self,
        decision: str,
        now: datetime,
        observation: Mapping[str, Any] | None,
        who: str,
    ) -> str:
        obs = dict(observation or {})
        if decision != "SPEAK":
            if self._is_quiet(now) and not obs.get("interactive"):
                return "quiet_hours"
            if who and self._child_at_school(who, now, obs):
                return "school_hours"
            if obs.get("school_hours") or obs.get("at_school"):
                if obs.get("audience_child") or self._privacy.is_child(
                    self.official_id(str(obs.get("member_id") or obs.get("label") or ""))
                ):
                    return "school_hours"
            return str(decision or "SILENT").lower()
        return "ok"

    def next_accompany(
        self,
        now: datetime | None = None,
        *,
        observation: Mapping[str, Any] | None = None,
        channel: str = "remind",
    ) -> AccompanyDecision:
        """Compose speak-gate + family snapshot. No LLM. Hint is a tag, not speech."""
        when = self._now(now)
        obs = dict(observation or {})
        if "now" not in obs:
            obs["now"] = when
        snap = self.family_state(when, observation=obs)
        hint = str(snap.get("hint") or "安静陪伴")
        requested = self.official_id(
            str(obs.get("member_id") or obs.get("label") or obs.get("who") or "")
        )
        decision = speak_decide(obs, now=when, channel=channel, live=True)
        if decision != "SPEAK":
            who = requested or ""
            return AccompanyDecision(
                speak=False,
                who=who,
                hint=hint,
                reason=self._gate_reason(decision, when, obs, who),
            )
        if requested and not self._interactable(requested, when, obs):
            return AccompanyDecision(
                speak=False,
                who=requested,
                hint=hint,
                reason=self._gate_reason("SILENT", when, obs, requested) or "not_interactable",
            )
        who = ""
        if requested and snap["members"].get(requested, {}).get("interactable"):
            who = requested
        else:
            for mid in OFFICIAL_IDS:
                if snap["members"][mid]["interactable"]:
                    who = mid
                    break
        if not who:
            return AccompanyDecision(
                speak=False,
                who=requested or "",
                hint=hint,
                reason="not_interactable",
            )
        return AccompanyDecision(speak=True, who=who, hint=hint, reason="ok")


def today_ledger(now: datetime | None = None, **kwargs: Any) -> dict[str, Any]:
    return FamilyMemoryV2(**kwargs).today_ledger(now)


def recent_change(now: datetime | None = None, **kwargs: Any) -> dict[str, Any]:
    return FamilyMemoryV2(**kwargs).recent_change(now)


def stable_memory(**kwargs: Any) -> dict[str, Any]:
    return FamilyMemoryV2(**kwargs).stable_memory()


def family_state(now: datetime | None = None, **kwargs: Any) -> dict[str, Any]:
    observation = kwargs.pop("observation", None)
    persist = kwargs.pop("persist", None)
    return FamilyMemoryV2(**kwargs).family_state(now, observation=observation, persist=persist)


def next_accompany(
    now: datetime | None = None,
    *,
    observation: Mapping[str, Any] | None = None,
    channel: str = "remind",
    **kwargs: Any,
) -> dict[str, Any]:
    return FamilyMemoryV2(**kwargs).next_accompany(
        now, observation=observation, channel=channel
    ).as_dict()
