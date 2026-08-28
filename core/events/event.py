"""Canonical, validated event model for TangTang V4.

Illegal construction is rejected here. IdentityResolver is not a field
and must not be imported — Event stays a dumb, bounded record.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping
from uuid import uuid4

from core.errors import EventError

PRIVACY_SCOPES = frozenset({"PRIVATE", "FAMILY", "PUBLIC"})
MAX_PAYLOAD_BYTES = 8192
MAX_ID_LEN = 128
MAX_TYPE_LEN = 64
MAX_SOURCE_LEN = 64


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_size(payload: Mapping[str, Any]) -> int:
    try:
        raw = json.dumps(payload, ensure_ascii=False, default=None)
    except (TypeError, ValueError) as exc:
        raise EventError("payload must be JSON-serializable") from exc
    return len(raw.encode("utf-8"))


def _require_text(value: Any, name: str, max_len: int) -> str:
    if value is None or not isinstance(value, str):
        raise EventError(f"{name} is required")
    text = value.strip()
    if not text:
        raise EventError(f"{name} is required")
    if len(text) > max_len:
        raise EventError(f"{name} exceeds {max_len} characters")
    return text


@dataclass(frozen=True)
class Event:
    id: str
    type: str
    ts: str
    source: str
    privacy: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    member_id: str | None = None
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_text(self.id, "id", MAX_ID_LEN))
        object.__setattr__(self, "type", _require_text(self.type, "type", MAX_TYPE_LEN))
        object.__setattr__(self, "ts", _require_text(self.ts, "ts", MAX_ID_LEN))
        object.__setattr__(self, "source", _require_text(self.source, "source", MAX_SOURCE_LEN))
        if self.privacy not in PRIVACY_SCOPES:
            raise EventError("privacy must be PRIVATE, FAMILY, or PUBLIC")
        member = self.member_id.strip() if isinstance(self.member_id, str) else self.member_id
        if member == "":
            member = None
        object.__setattr__(self, "member_id", member)
        if self.privacy == "PRIVATE" and not member:
            raise EventError("PRIVATE events require member_id")
        if self.payload is None:
            payload: dict[str, Any] = {}
        elif not isinstance(self.payload, Mapping):
            raise EventError("payload must be a mapping")
        else:
            payload = dict(self.payload)
        if _json_size(payload) > MAX_PAYLOAD_BYTES:
            raise EventError(f"payload exceeds {MAX_PAYLOAD_BYTES} bytes")
        object.__setattr__(self, "payload", MappingProxyType(payload))
        if self.correlation_id is not None and not isinstance(self.correlation_id, str):
            raise EventError("correlation_id must be a string or None")

    @property
    def event_id(self) -> str:
        return self.id

    @property
    def event_type(self) -> str:
        return self.type

    @property
    def timestamp(self) -> str:
        return self.ts

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "ts": self.ts,
            "source": self.source,
            "privacy": self.privacy,
            "payload": dict(self.payload),
            "member_id": self.member_id,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Event:
        if not isinstance(data, Mapping):
            raise EventError("event must be a mapping")
        eid = data.get("id", data.get("event_id"))
        if eid is None or (isinstance(eid, str) and not eid.strip()):
            raise EventError("id is required")
        etype = data.get("type", data.get("event_type"))
        ts = data.get("ts", data.get("timestamp"))
        source = data.get("source")
        privacy = data.get("privacy", "PUBLIC")
        return cls(
            id=str(eid) if eid is not None else "",
            type=str(etype) if etype is not None else "",
            ts=str(ts) if ts is not None else "",
            source=str(source) if source is not None else "",
            privacy=str(privacy) if privacy is not None else "",
            payload=data.get("payload") or {},
            member_id=data.get("member_id"),
            correlation_id=data.get("correlation_id"),
        )

    @classmethod
    def create(
        cls,
        *,
        type: str,
        source: str = "system",
        privacy: str = "PUBLIC",
        payload: Mapping[str, Any] | None = None,
        member_id: str | None = None,
        id: str | None = None,
        ts: str | None = None,
        correlation_id: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> Event:
        """Happy-path factory: generates id/ts when omitted. Still validates."""
        tick = clock or _utc_now
        return cls(
            id=id or f"evt_{uuid4().hex}",
            type=type,
            ts=ts or tick().isoformat(),
            source=source,
            privacy=privacy,
            payload=payload or {},
            member_id=member_id,
            correlation_id=correlation_id,
        )
