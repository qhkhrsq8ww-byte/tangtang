"""Minimal Event Store: JSONL under TANGTANG_HOME. Unique event_id, append, query, dedupe.

SQLite is intentionally unused (core must not grow a DB client).
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.events.event import Event
from core.memory.paths import resolve_under, tangtang_home
from core.runtime.isolate import isolate


class JsonlEventStore:
    """Append-only event log. Duplicate event_id is a no-op, not a second behavior."""

    core_api_version = "4.0.0"

    def __init__(
        self,
        home: str | Path | None = None,
        *,
        persist: bool = False,
        filename: str = "events.jsonl",
    ) -> None:
        self._rows: list[dict[str, Any]] = []
        self._ids: set[str] = set()
        self._persist = persist
        self._path: Path | None = None
        if persist or home is not None:
            base = tangtang_home(home) if home is not None else tangtang_home()
            self._path = resolve_under(base, "events", filename)
            self._load()

    def _load(self) -> None:
        path = self._path
        if path is None or not path.is_file():
            return

        def _read() -> list[str]:
            return path.read_text(encoding="utf-8").splitlines()

        loaded = isolate(_read, fallback=[])
        lines = loaded.value if isinstance(loaded.value, list) else []
        for line in lines:
            if not str(line).strip():
                continue
            parsed = isolate(lambda raw=line: json.loads(raw))
            if not parsed.ok or not isinstance(parsed.value, Mapping):
                continue
            row = dict(parsed.value)
            eid = str(row.get("id") or row.get("event_id") or "")
            if not eid or eid in self._ids:
                continue
            self._ids.add(eid)
            self._rows.append(row)

    def contains(self, event_id: str) -> bool:
        return str(event_id) in self._ids

    def append(self, event: Event | Mapping[str, Any]) -> bool:
        """Return True if stored. False if duplicate or illegal — never raises."""
        try:
            if isinstance(event, Event):
                row = event.to_dict()
            elif isinstance(event, Mapping):
                row = Event.from_dict(event).to_dict()
            else:
                return False
        except Exception:
            return False
        eid = str(row.get("id") or "")
        if not eid or eid in self._ids:
            return False
        self._ids.add(eid)
        self._rows.append(row)
        if self._persist and self._path is not None:
            path = self._path

            def _write() -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")

            isolate(_write)
        return True

    def query(
        self,
        *,
        event_id: str | None = None,
        event_type: str | None = None,
        member_id: str | None = None,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in self._rows:
            if event_id and row.get("id") != event_id:
                continue
            if event_type and row.get("type") != event_type:
                continue
            if member_id and row.get("member_id") != member_id:
                continue
            out.append(dict(row))
        return out

    def all_ids(self) -> set[str]:
        return set(self._ids)
