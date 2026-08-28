"""Resolve a recognized voice/person reference into a family member."""
from __future__ import annotations

from collections.abc import Mapping


class IdentityResolver:
    def __init__(self, members: Mapping[str, object] | None = None) -> None:
        self.members = dict(members or {})

    def resolve(self, candidate: str | None) -> str | None:
        if not candidate:
            return None
        return candidate if candidate in self.members else None
