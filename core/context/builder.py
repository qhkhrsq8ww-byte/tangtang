"""Build a bounded context instead of exposing raw storage to the model."""
from __future__ import annotations

from typing import Any


class ContextBuilder:
    def __init__(self, max_recent: int = 10) -> None:
        self.max_recent = max_recent

    def build(self, *, who: dict[str, Any], event: dict[str, Any],
              recent: list[dict[str, Any]] | None = None,
              memories: list[dict[str, Any]] | None = None,
              family: dict[str, Any] | None = None,
              privacy_scope: str = "PRIVATE") -> dict[str, Any]:
        memories = memories or []
        if privacy_scope == "FAMILY":
            memories = [m for m in memories if m.get("privacy") in {"FAMILY", "PUBLIC"}]
        elif privacy_scope == "PUBLIC":
            memories = [m for m in memories if m.get("privacy") == "PUBLIC"]
        return {
            "who": who,
            "current_event": event,
            "recent": (recent or [])[-self.max_recent:],
            "memory": memories,
            "family": family or {},
            "privacy_scope": privacy_scope,
        }
