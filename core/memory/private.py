"""PrivateMemory: owner-only, TTL, never mixed into family stores."""
from __future__ import annotations

import json
from collections.abc import Callable
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

    def query(self, *, member_id: str, viewer_id: str | None) -> list[dict[str, Any]]:
        if not member_id or viewer_id != member_id:
            return []
        return self._store.query(member_id=member_id, scope="PRIVATE", viewer_id=viewer_id)

    def _write_file(self, memory: Memory) -> None:
        if self._home is None:
            raise PathError("TANGTANG_HOME is required to persist PrivateMemory")
        sanitize_member_id(memory.member_id)
        path = private_file(self._home, memory.member_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: list[dict[str, Any]] = []
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    existing = loaded
            except (OSError, json.JSONDecodeError):
                existing = []
        record = {
            "memory_id": memory.memory_id,
            "member_id": memory.member_id,
            "privacy": "PRIVATE",
            "created_at": memory.created_at,
            "expires_at": memory.expires_at,
            "data": dict(memory.data),
        }
        existing = [row for row in existing if row.get("memory_id") != memory.memory_id]
        existing.append(record)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
