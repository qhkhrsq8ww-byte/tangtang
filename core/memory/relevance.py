"""V5 memory relevance scoring.

Scores structured memories for the current turn without reading raw speech.
This is ranking only: privacy and allowed-field projection remain authoritative.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

_TYPE_WEIGHT = {
    "commitment": 1.00,
    "task": 0.95,
    "goal": 0.90,
    "important_fact": 0.88,
    "preference": 0.72,
    "long_term_fact": 0.68,
}

def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d

def relevance_score(row: Mapping[str, Any], *, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    typ = str(row.get("type") or "")
    score = _TYPE_WEIGHT.get(typ, 0.30)
    try:
        score *= 0.65 + 0.35 * max(0.0, min(1.0, float(row.get("confidence", 1.0))))
    except (TypeError, ValueError):
        pass
    created = _parse(row.get("created_at"))
    if created:
        age_days = max(0.0, (now - created).total_seconds() / 86400)
        score *= 0.5 + 0.5 * (0.5 ** (age_days / 180.0))
    data = row.get("data")
    if isinstance(data, Mapping):
        status = str(data.get("status") or "").lower()
        if typ in {"task", "commitment", "goal"} and status in {"open", "pending", "todo", "active", "未完成", "进行中"}:
            score += 0.18
        if data.get("due_at"):
            due = _parse(data.get("due_at"))
            if due:
                days = (due - now).total_seconds() / 86400
                if -1 <= days <= 7:
                    score += 0.22
    return round(min(1.5, score), 4)
