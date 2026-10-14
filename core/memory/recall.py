"""Policy-bounded retrieval of structured personal memory for a single turn.

Raw utterances and arbitrary blobs are intentionally never injected into a model prompt.
Only explicit structured facts for the same member can be recalled.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.memory.family import FamilyMemory
from core.memory.private import PrivateMemory

RECALLABLE_TYPES = frozenset({
    "preference", "long_term_fact", "commitment", "goal", "task", "important_fact",
})
SAFE_FIELDS = frozenset({
    "tag", "value", "label", "category", "preference", "goal",
    "title", "status", "due_at",
})
FORBIDDEN_FIELDS = frozenset({
    "speech", "text", "utterance", "transcript", "raw", "message",
    "audio", "pcm", "voiceprint", "embedding",
})


def _safe_projection(row: Mapping[str, Any]) -> dict[str, Any] | None:
    if str(row.get("type") or "") not in RECALLABLE_TYPES:
        return None
    data = row.get("data")
    if not isinstance(data, Mapping):
        return None
    if any(str(key).lower() in FORBIDDEN_FIELDS for key in data):
        return None
    safe: dict[str, Any] = {}
    for key in SAFE_FIELDS:
        value = data.get(key)
        if isinstance(value, (str, int, float, bool)) and str(value).strip():
            # Bound prompt size; memory is supporting context, not authority.
            safe[key] = str(value).strip()[:180]
    if not safe:
        return None
    return {
        "memory_id": str(row.get("memory_id") or ""),
        "type": str(row.get("type") or ""),
        "privacy": str(row.get("privacy") or ""),
        "data": safe,
        "created_at": str(row.get("created_at") or "")[:40],
    }


def retrieve_structured_memories(
    *,
    member_id: str | None,
    viewer_id: str | None,
    privacy_scope: str,
    private_store: PrivateMemory,
    family_store: FamilyMemory,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Read only the current owner's structured memories allowed in this scope."""
    if not member_id or not viewer_id or member_id != viewer_id or limit <= 0:
        return []
    if privacy_scope == "PRIVATE":
        rows = private_store.query(member_id=member_id, viewer_id=viewer_id)
    elif privacy_scope in {"FAMILY", "PUBLIC"}:
        rows = family_store.query(member_id=member_id, viewer_id=viewer_id)
    else:
        return []
    projected = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        item = _safe_projection(row)
        if item:
            projected.append(item)
    projected.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return projected[: min(limit, 8)]
