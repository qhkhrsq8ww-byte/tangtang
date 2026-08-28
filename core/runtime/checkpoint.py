"""Persist seen event ids under TANGTANG_HOME so a process restart dedupes."""
from __future__ import annotations

import json
from typing import Any

from core.memory.paths import resolve_under, tangtang_home
from core.runtime.isolate import isolate


class FileSeenStore:
    def __init__(self, home: str | None = None) -> None:
        base = tangtang_home(home) if home is not None else tangtang_home()
        self._path = resolve_under(base, "runtime", "seen-event-ids.json")
        self._ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        path = self._path
        loaded = isolate(lambda: json.loads(path.read_text(encoding="utf-8")))
        if loaded.ok and isinstance(loaded.value, list):
            self._ids = {str(x) for x in loaded.value}

    def _save(self) -> None:
        path = self._path

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(sorted(self._ids)), encoding="utf-8")
            tmp.replace(path)

        isolate(_write)

    def contains(self, event_id: str) -> bool:
        return event_id in self._ids

    def add(self, event_id: str) -> None:
        self._ids.add(event_id)
        self._save()

    def all_ids(self) -> set[str]:
        return set(self._ids)
