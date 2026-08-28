"""Canonical event model for TangTang V4."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True)
class Event:
    event_type: str
    member_id: str | None = None
    source: str = "system"
    privacy: str = "PUBLIC"
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if self.privacy not in {"PRIVATE", "FAMILY", "PUBLIC"}:
            raise ValueError("privacy must be PRIVATE, FAMILY, or PUBLIC")
        if not self.event_type:
            raise ValueError("event_type is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "member_id": self.member_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "privacy": self.privacy,
            "payload": dict(self.payload),
            "correlation_id": self.correlation_id,
        }
