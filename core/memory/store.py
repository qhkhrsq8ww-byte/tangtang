"""Minimal auditable memory store with mandatory privacy boundaries."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Memory:
    memory_id: str
    member_id: str
    type: str
    privacy: str
    data: dict[str, Any]
    source_events: list[str]
    confidence: float = 1.0
    expires_at: str | None = None


class MemoryStore:
    def __init__(self) -> None:
        self._items: dict[str, Memory] = {}

    def put(self, memory: Memory) -> None:
        if memory.privacy not in {"PRIVATE", "FAMILY", "PUBLIC"}:
            raise ValueError("invalid privacy scope")
        self._items[memory.memory_id] = memory

    def query(self, *, member_id: str, scope: str = "PRIVATE") -> list[dict[str, Any]]:
        allowed = {"PRIVATE": {"PRIVATE"}, "FAMILY": {"FAMILY", "PUBLIC"}, "PUBLIC": {"PUBLIC"}}
        if scope not in allowed:
            raise ValueError("invalid scope")
        return [asdict(m) for m in self._items.values()
                if m.member_id == member_id and m.privacy in allowed[scope]]
