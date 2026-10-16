"""V5 memory lifecycle rules.

Keeps memory useful without turning every interaction into permanent memory.
This module is policy-neutral: callers still enforce privacy/consent.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

TEMPORARY_TYPES = frozenset({"task", "commitment", "goal"})
PERSISTENT_TYPES = frozenset({"preference", "important_fact", "long_term_fact"})

def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

def lifecycle_state(row: Mapping[str, Any], *, now: datetime | None = None) -> str:
    """Return active, expired, completed, or persistent."""
    now = now or datetime.now(timezone.utc)
    typ = str(row.get("type") or "")
    data = row.get("data")
    data = data if isinstance(data, Mapping) else {}
    status = str(data.get("status") or "").lower()
    if typ in TEMPORARY_TYPES:
        if status in {"done", "completed", "cancelled", "canceled", "已完成", "已取消"}:
            return "completed"
        expires = _parse(row.get("expires_at")) or _parse(data.get("due_at"))
        if expires and expires <= now:
            return "expired"
        return "active"
    if typ in PERSISTENT_TYPES:
        return "persistent"
    return "active"

def suggested_expiry(memory_type: str, *, now: datetime | None = None) -> datetime | None:
    """Default expiry for temporary memory when the caller has no explicit date."""
    now = now or datetime.now(timezone.utc)
    if memory_type == "task":
        return now + timedelta(days=14)
    if memory_type == "commitment":
        return now + timedelta(days=30)
    if memory_type == "goal":
        return now + timedelta(days=90)
    return None
