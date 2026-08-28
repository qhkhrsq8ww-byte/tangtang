"""Family-shared stores. PRIVATE and child raw speech are rejected here."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.errors import MemoryError
from core.memory.paths import family_file, habit_file, tangtang_home
from core.memory.store import Memory, MemoryStore
from core.policy.privacy_policy import (
    DEST_FAMILY_MEMORY,
    DEST_FAMILY_SUMMARY,
    DEST_HABIT_STORE,
    DEST_PARENT_CONTEXT,
    PrivacyPolicy,
    raw_utterance_from,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _GatedStore:
    destination = DEST_FAMILY_MEMORY

    def __init__(
        self,
        store: MemoryStore | None = None,
        *,
        privacy: PrivacyPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        home: str | Path | None = None,
        persist: bool = False,
        filename: str = "family-memory.json",
    ) -> None:
        self._privacy = privacy or PrivacyPolicy()
        self._clock = clock or _utc_now
        self._store = store or MemoryStore(clock=self._clock, privacy=self._privacy)
        self._persist = persist
        self._filename = filename
        self._home: Path | None = Path(home).resolve() if home else None

    def _reject(self, memory: Memory) -> None:
        raw = raw_utterance_from(memory.data)
        if memory.privacy == "PRIVATE":
            raise MemoryError(f"PRIVATE cannot enter {self.destination}")
        if raw and self._privacy.is_child(memory.member_id):
            raise MemoryError(f"child raw speech cannot enter {self.destination}")
        if not self._privacy.allow_destination(
            self.destination,
            member_id=memory.member_id,
            utterance=raw,
            privacy=memory.privacy,
        ):
            raise MemoryError(f"{self.destination} rejected by PrivacyPolicy")

    def put(self, memory: Memory) -> None:
        if not isinstance(memory, Memory):
            raise MemoryError("put requires a Memory record")
        self._reject(memory)
        if memory.created_at is None:
            memory.created_at = self._clock().isoformat()
        self._store.put(memory)
        if self._persist:
            self._write(memory)

    def query(self, *, member_id: str, viewer_id: str | None = None) -> list[dict[str, Any]]:
        return self._store.query(member_id=member_id, scope="FAMILY", viewer_id=viewer_id)

    def all_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for mem in self._store._items.values():
            if mem.privacy == "PRIVATE":
                continue
            rows.append({
                "memory_id": mem.memory_id,
                "member_id": mem.member_id,
                "privacy": mem.privacy,
                "data": dict(mem.data),
            })
        return rows

    def contains_text(self, needle: str) -> bool:
        blob = needle or ""
        if not blob:
            return False
        for mem in self._store._items.values():
            raw = json.dumps(mem.data, ensure_ascii=False)
            if blob in raw:
                return True
        return False

    def _write(self, memory: Memory) -> None:
        home = self._home or tangtang_home()
        path = family_file(home, self._filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "memory_id": memory.memory_id,
            "member_id": memory.member_id,
            "privacy": memory.privacy,
            "created_at": memory.created_at,
            "data": dict(memory.data),
        }
        existing: list[Any] = []
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    existing = loaded
            except (OSError, json.JSONDecodeError):
                existing = []
        existing.append(payload)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


class FamilyMemory(_GatedStore):
    destination = DEST_FAMILY_MEMORY


class FamilySummary(_GatedStore):
    destination = DEST_FAMILY_SUMMARY

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("filename", "family-summary.json")
        super().__init__(**kwargs)

    def add(self, *, member_id: str, summary: str, privacy: str = "FAMILY") -> Memory:
        mem = Memory(
            memory_id=f"sum_{uuid4().hex}",
            member_id=member_id,
            type="summary",
            privacy=privacy,
            data={"summary": summary},
        )
        self.put(mem)
        return mem

    def add_structured(
        self,
        *,
        member_id: str,
        mood: str | None = None,
        interaction_count: int = 0,
        privacy: str = "FAMILY",
    ) -> Memory:
        """{mood, interaction_count} only. put() still rejects PRIVATE / child raw."""
        mem = Memory(
            memory_id=f"sum_{uuid4().hex}",
            member_id=member_id,
            type="summary",
            privacy=privacy,
            data={
                "mood": mood,
                "interaction_count": int(interaction_count),
            },
        )
        self.put(mem)
        return mem

    def snapshot(self) -> list[dict[str, Any]]:
        """Structured family view. Children and PRIVATE rows are omitted."""
        rows: list[dict[str, Any]] = []
        for mem in self._store._items.values():
            if mem.privacy == "PRIVATE" or self._privacy.is_child(mem.member_id):
                continue
            raw = raw_utterance_from(mem.data)
            if raw:
                continue
            rows.append({
                "member_id": mem.member_id,
                "mood": mem.data.get("mood"),
                "interaction_count": mem.data.get("interaction_count", 1),
            })
        return rows


class ParentContext(_GatedStore):
    destination = DEST_PARENT_CONTEXT

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("filename", "parent-context.json")
        super().__init__(**kwargs)

    def build(self, members: Mapping[str, Mapping[str, Any]] | None = None) -> str:
        """Structured parent view: no raw child speech."""
        lines: list[str] = []
        for mem in self._store._items.values():
            if mem.privacy == "PRIVATE" or self._privacy.is_child(mem.member_id):
                continue
            raw = raw_utterance_from(mem.data)
            if raw and self._privacy.is_child(mem.member_id):
                continue
            tag = mem.data.get("tag") or mem.data.get("summary") or mem.type
            lines.append(f"{mem.member_id}: {tag}")
        for mid, rec in dict(members or {}).items():
            if self._privacy.is_child(mid):
                lines.append(f"{mid}: 互动数据受隐私保护，不展示原话")
            else:
                lines.append(f"{mid}: relation={rec.get('relation', '')}")
        return "\n".join(lines)


class HabitStore:
    """V4 gate in front of cat-habits.json. Does not import the living-room cat stack."""

    destination = DEST_HABIT_STORE

    def __init__(
        self,
        *,
        home: str | Path | None = None,
        privacy: PrivacyPolicy | None = None,
        persist: bool = False,
    ) -> None:
        self._privacy = privacy or PrivacyPolicy()
        self._persist = persist
        self._home = Path(home).resolve() if home else None
        self._rows: list[dict[str, Any]] = []

    def put(self, *, member_id: str, utterance: str = "", extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not self._privacy.allow_destination(
            DEST_HABIT_STORE, member_id=member_id, utterance=utterance
        ):
            raise MemoryError("habit store rejected by PrivacyPolicy")
        if utterance and self._privacy.is_child(member_id):
            raise MemoryError("child raw speech cannot enter cat-habits.json")
        row = {
            "member_id": member_id,
            "text": utterance if self._privacy.allow_destination(
                DEST_HABIT_STORE, member_id=member_id, utterance=utterance
            ) else "",
            "privacy": self._privacy.classify(member_id=member_id, utterance=utterance).privacy,
        }
        if extra:
            row.update(dict(extra))
        self._rows.append(row)
        if self._persist:
            self._write()
        return row

    def contains_text(self, needle: str) -> bool:
        if not needle:
            return False
        return any(needle in json.dumps(row, ensure_ascii=False) for row in self._rows)

    def rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def _write(self) -> None:
        home = self._home or tangtang_home()
        path = habit_file(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps({"logs": self._rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
