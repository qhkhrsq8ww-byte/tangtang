"""In-memory memory store. Independent of Context (do not import it)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.errors import MemoryError
from core.policy.privacy_policy import PrivacyPolicy, raw_utterance_from

PRIVACY_SCOPES = frozenset({"PRIVATE", "FAMILY", "PUBLIC"})
SCOPE_VISIBLE = {
    "PRIVATE": frozenset({"PRIVATE"}),
    "FAMILY": frozenset({"FAMILY", "PUBLIC"}),
    "PUBLIC": frozenset({"PUBLIC"}),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass
class Memory:
    memory_id: str
    member_id: str
    type: str
    privacy: str
    data: dict[str, Any] = field(default_factory=dict)
    source_events: list[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: str | None = None
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
    core_api_version = "4.0.0"
    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
        privacy: PrivacyPolicy | None = None,
    ) -> None:
        self._items: dict[str, Memory] = {}
        self._clock = clock or _utc_now
        self._privacy = privacy or PrivacyPolicy()

    def put(self, memory: Memory) -> None:
        if not isinstance(memory, Memory):
            raise MemoryError("put requires a Memory record")
        raw = raw_utterance_from(memory.data)
        if raw and memory.privacy != "PRIVATE" and self._privacy.is_child(memory.member_id):
            raise MemoryError("child raw speech cannot enter family-shared stores")
        if memory.created_at is None:
            memory.created_at = self._clock().isoformat()
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
        now = self._clock()
        out: list[dict[str, Any]] = []
        for m in self._items.values():
            if m.member_id != member_id or m.privacy not in visible:
                continue
            if not self._alive(m, now):
                continue
            out.append(asdict(m))
        return out

    def _alive(self, memory: Memory, now: datetime) -> bool:
        if not memory.expires_at:
            return True
        expires = _parse_ts(memory.expires_at)
        if expires is None:
            return False
        return expires > now
