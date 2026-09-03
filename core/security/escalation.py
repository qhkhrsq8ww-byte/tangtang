"""Deterministic escalation for high-risk child content (V4 core).

Privacy rule: a safety alert never contains the raw child utterance. It
records only the risk category, timestamp, and an optional member_id /
event_id. The child's raw speech stays inside owner-only PrivateMemory and
never enters this parent-visible local log.

This module is deterministic and does not call LLM, TTS, projection, or a
shell. The macOS notification push is the caller's job (see cat-chat.py).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.memory.paths import resolve_under

RISK_CATEGORY_MARKERS: dict[str, tuple[str, ...]] = {
    "self_harm": ("不想活", "自杀", "杀死自己", "伤害自己", "想死", "去死", "割腕", "跳楼"),
    "violence": ("打死", "杀人", "霸凌", "校园暴力"),
    "unsafe_contact": ("有人碰我身体",),
    "secret_keep": ("不要告诉爸", "不要告诉妈", "不要告诉大人"),
}

ALERT_FILENAME = "safety-alerts.jsonl"
LATEST_FILENAME = "latest-alert.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def classify_risk(text: str | None) -> str | None:
    """Return the first matched risk category, or None. Never stores text."""
    blob = (text or "").replace(" ", "").replace("\n", "").replace("\t", "")
    if not blob:
        return None
    for category, markers in RISK_CATEGORY_MARKERS.items():
        if any(marker in blob for marker in markers):
            return category
    return None


def record_safety_alert(
    category: str,
    *,
    member_id: str | None = None,
    event_id: str | None = None,
    when: datetime | None = None,
    home: str | Path | None = None,
) -> dict[str, Any] | None:
    """Append a structured alert (no raw text) and refresh latest-alert.json.

    Returns the recorded row, or None when there is nothing to record.
    """
    if category not in RISK_CATEGORY_MARKERS:
        return None
    if home is None:
        home = os.environ.get("TANGTANG_DATA_DIR") or os.environ.get("TANGTANG_HOME")
    if home is None:
        return None
    base = Path(home)
    if not str(base).strip():
        return None
    row: dict[str, Any] = {
        "ts": (when or _utc_now()).isoformat(),
        "category": category,
        "member_id": (member_id or "").strip() or None,
        "event_id": event_id,
    }
    try:
        jsonl = resolve_under(str(base), "safety", ALERT_FILENAME)
        latest = resolve_under(str(base), "safety", LATEST_FILENAME)
        jsonl.parent.mkdir(parents=True, exist_ok=True)
        with jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        tmp = latest.with_suffix(latest.suffix + ".tmp")
        tmp.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
        tmp.replace(latest)
    except (OSError, ValueError):
        return None
    return row