"""In-memory memory store. Independent of Context (do not import it)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from core.errors import MemoryError

PRIVACY_SCOPES = frozenset({"PRIVATE", "FAMILY", "PUBLIC"})
SCOPE_VISIBLE = {
    "PRIVATE": frozenset({"PRIVATE"}),
    "FAMILY": frozenset({"FAMILY", "PUBLIC"}),
    "PUBLIC": frozenset({"PUBLIC"}),
}


@dataclass
class Memory:
    memory_id: str
    member_id: str
    type: str
    privacy: str
    data: dict[str, Any] = field(default_factory=dict)
    source_events: list[str] = field(default_factory=list)
    confidence: float = 1.0
    expires_at: str | None = None

    def __post_init__(self) -> None:
        if not str(self.memory_id or "").strip():
            raise MemoryError("memory_id is required")
        if not str(self.member_id or "").strip():
            raise MemoryError("member_id is required")
        if not str(self.type or "").strip():
            raise MemoryError("type is required")
        if self.privacy not in PRIVACY_SCOPES:
            raise MemoryError("invalid privacy scope")
        if not isinstance(self.data, dict):
            raise MemoryError("data must be a dict")


class MemoryStore:
    def __init__(self) -> None:
        self._items: dict[str, Memory] = {}

    def put(self, memory: Memory) -> None:
        if not isinstance(memory, Memory):
            raise MemoryError("put requires a Memory record")
        self._items[memory.memory_id] = memory

    def query(
        self,
        *,
        member_id: str,
        scope: str = "PRIVATE",
        viewer_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if scope not in SCOPE_VISIBLE:
            raise MemoryError("invalid scope")
        if not member_id:
            return []
        if scope == "PRIVATE":
            viewer = viewer_id if viewer_id is not None else member_id
            if viewer != member_id:
                return []
        visible = SCOPE_VISIBLE[scope]
        return [
            asdict(m)
            for m in self._items.values()
            if m.member_id == member_id and m.privacy in visible
        ]
