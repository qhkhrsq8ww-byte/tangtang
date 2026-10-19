"""PrivateMemory: owner-only, TTL, never mixed into family stores."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.errors import MemoryError, PathError
from core.memory.paths import private_file, sanitize_member_id, tangtang_home
from core.memory.store import Memory, MemoryStore
from core.policy.privacy_policy import PrivacyPolicy


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


PREFERENCE_CATEGORIES = frozenset({"likes", "dislikes", "favorite"})

class PrivateMemory:
    def __init__(
        self,
        store: MemoryStore | None = None,
        *,
        home: str | Path | None = None,
        clock: Callable[[], datetime] | None = None,
        ttl_days: int = 30,
        privacy: PrivacyPolicy | None = None,
        persist: bool = False,
    ) -> None:
        self._clock = clock or _utc_now
        self._store = store or MemoryStore(clock=self._clock, privacy=privacy)
        self._ttl_days = ttl_days
        self._privacy = privacy or PrivacyPolicy()
        self._persist = persist
        self._home: Path | None = None
        self._loaded_members: set[str] = set()
        if home is not None or persist:
            self._home = tangtang_home(home) if home is not None else tangtang_home()

    @property
    def memory_port(self) -> MemoryStore:
        return self._store

    def put(
        self,
        *,
        member_id: str,
        utterance: str,
        event_id: str | None = None,
        memory_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Memory:
        mid = str(member_id or "").strip()
        if not mid:
            raise MemoryError("member_id is required")
        if self._persist or self._home is not None:
            sanitize_member_id(mid)
        self._load_member(mid)
        decision = self._privacy.classify(member_id=mid, utterance=utterance)
        if decision.privacy != "PRIVATE":
            raise MemoryError("refusing non-PRIVATE write to PrivateMemory")
        now = self._clock()
        expires = now + timedelta(days=self._ttl_days)
        data = {"speech": utterance}
        if extra:
            data.update(extra)
        mem = Memory(
            memory_id=memory_id or f"priv_{uuid4().hex}",
            member_id=mid,
            type="utterance",
            privacy="PRIVATE",
            data=data,
            source_events=[event_id] if event_id else [],
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )
        self._store.put(mem)
        if self._persist:
            self._write_file(mem)
        return mem

    def remember_preference(
        self,
        *,
        member_id: str,
        category: str,
        value: str,
        event_id: str | None = None,
        ttl_days: int = 365,
    ) -> Memory:
        """Persist a compact, owner-only preference explicitly requested by the member."""
        mid = str(member_id or "").strip()
        clean = " ".join(str(value or "").split()).strip(" ，,。.!！?？:：")
        if not mid or category not in PREFERENCE_CATEGORIES:
            raise MemoryError("member_id/category is invalid")
        if not clean or len(clean) > 80:
            raise MemoryError("preference value must contain 1–80 characters")
        if self._persist or self._home is not None:
            sanitize_member_id(mid)
        self._load_member(mid)
        # Explicit memory is owner-only even when an adult's ordinary conversation is FAMILY.
        if self._privacy.canonical_member_id(mid) is None:
            raise MemoryError("preference owner must be a registered family member")
        digest = hashlib.sha256(f"{category}:{clean.casefold()}".encode("utf-8")).hexdigest()[:16]
        memory = Memory(
            memory_id=f"pref_{sanitize_member_id(mid)}_{digest}",
            member_id=mid,
            type="preference",
            privacy="PRIVATE",
            data={"tag": category, "value": clean},
            source_events=[event_id] if event_id else [],
            created_at=self._clock().isoformat(),
            expires_at=(self._clock() + timedelta(days=max(1, ttl_days))).isoformat(),
        )
        self._store.put(memory)
        if self._persist:
            self._write_file(memory)
        return memory

    def forget_preference(
        self,
        *,
        member_id: str,
        category: str,
        value: str,
    ) -> int:
        """Forget only an exact owner preference; never broad-delete other memory."""
        mid = str(member_id or "").strip()
        clean = " ".join(str(value or "").split()).strip(" ，,。.!！?？:：")
        if not mid or category not in PREFERENCE_CATEGORIES or not clean:
            return 0
        if self._privacy.canonical_member_id(mid) is None:
            return 0
        self._load_member(mid)
        removed: list[str] = []
        for row in self._store.query(member_id=mid, scope="PRIVATE", viewer_id=mid):
            data = row.get("data") if isinstance(row.get("data"), Mapping) else {}
            if (
                row.get("type") == "preference"
                and data.get("tag") == category
                and str(data.get("value") or "").casefold() == clean.casefold()
            ):
                removed.append(str(row.get("memory_id") or ""))
        for memory_id in removed:
            self._store._items.pop(memory_id, None)
        if removed and self._persist:
            self._write_member_file(mid)
        return len(removed)

    def query(self, *, member_id: str, viewer_id: str | None) -> list[dict[str, Any]]:
        if not member_id or viewer_id != member_id:
            return []
        self._load_member(member_id)
        return self._store.query(member_id=member_id, scope="PRIVATE", viewer_id=viewer_id)

    def _load_member(self, member_id: str) -> None:
        """Load the owner-only file once per process and discard expired/invalid rows."""
        if not self._persist or self._home is None or member_id in self._loaded_members:
            return
        mid = sanitize_member_id(member_id)
        self._loaded_members.add(mid)
        path = private_file(self._home, mid)
        if not path.is_file():
            return
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        rows = parsed if isinstance(parsed, list) else []
        now = self._clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        valid_rows: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, Mapping) or row.get("member_id") != mid or row.get("privacy") != "PRIVATE":
                continue
            data = row.get("data")
            if not isinstance(data, Mapping):
                continue
            record_type = str(row.get("type") or "utterance")
            speech = data.get("speech")
            if record_type == "preference" and not speech:
                if (
                    set(data.keys()) != {"tag", "value"}
                    or data.get("tag") not in PREFERENCE_CATEGORIES
                    or not isinstance(data.get("value"), str)
                    or not str(data.get("value")).strip()
                    or len(str(data.get("value"))) > 80
                ):
                    continue
            elif not isinstance(speech, str) or not speech.strip():
                continue
            expires_raw = row.get("expires_at")
            try:
                expires = datetime.fromisoformat(str(expires_raw))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
            if expires <= now:
                continue
            if record_type != "preference":
                decision = self._privacy.classify(member_id=mid, utterance=speech)
                if decision.privacy != "PRIVATE":
                    continue
            try:
                memory = Memory(
                    memory_id=str(row.get("memory_id") or ""),
                    member_id=mid,
                    type=record_type,
                    privacy="PRIVATE",
                    data=dict(data),
                    source_events=list(row.get("source_events") or []),
                    confidence=float(row.get("confidence", 1.0)),
                    created_at=str(row.get("created_at") or ""),
                    expires_at=expires.isoformat(),
                )
                self._store.put(memory)
                valid_rows.append(dict(row))
            except Exception:
                continue
        # Persist cleanup so expired rows are not retained indefinitely on disk.
        if len(valid_rows) != len(rows):
            # Expired/corrupt rows should be removed when possible, but a read-only
            # data home must not turn a safe memory read into a runtime failure.
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(path.suffix + ".tmp")
                tmp.write_text(json.dumps(valid_rows, ensure_ascii=False, indent=2), encoding="utf-8")
                tmp.replace(path)
            except OSError:
                # Invalid/expired rows are still filtered from this in-memory load.
                # Cleanup can be retried on a later run with writable storage.
                pass

    def _write_member_file(self, member_id: str) -> None:
        """Atomically rewrite only one owner's private records after deletion."""
        if self._home is None:
            raise PathError("TANGTANG_HOME is required to persist PrivateMemory")
        mid = sanitize_member_id(member_id)
        path = private_file(self._home, mid)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self._store.query(member_id=mid, scope="PRIVATE", viewer_id=mid)
        payload = [{
            "memory_id": row["memory_id"],
            "member_id": row["member_id"],
            "type": row["type"],
            "privacy": "PRIVATE",
            "created_at": row.get("created_at"),
            "expires_at": row.get("expires_at"),
            "source_events": row.get("source_events") or [],
            "confidence": row.get("confidence", 1.0),
            "data": row.get("data") or {},
        } for row in rows]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _write_file(self, memory: Memory) -> None:
        if self._home is None:
            raise PathError("TANGTANG_HOME is required to persist PrivateMemory")
        sanitize_member_id(memory.member_id)
        path = private_file(self._home, memory.member_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._store.query(
            member_id=memory.member_id,
            scope="PRIVATE",
            viewer_id=memory.member_id,
        )
        record = {
            "memory_id": memory.memory_id,
            "member_id": memory.member_id,
            "type": memory.type,
            "privacy": "PRIVATE",
            "created_at": memory.created_at,
            "expires_at": memory.expires_at,
            "source_events": list(memory.source_events),
            "confidence": memory.confidence,
            "data": dict(memory.data),
        }
        existing = [row for row in existing if row.get("memory_id") != memory.memory_id]
        existing.append(record)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
