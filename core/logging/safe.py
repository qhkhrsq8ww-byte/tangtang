"""Logs must never contain PRIVATE payload or raw child utterances."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.policy.privacy_policy import UTTERANCE_KEYS, compact

_REDACTED = "[redacted]"


class SafeLogger:
    def __init__(self, sink: list[str] | None = None) -> None:
        self.lines: list[str] = sink if sink is not None else []

    def _record(self, line: str) -> None:
        self.lines.append(line)

    def event(self, event: Any) -> None:
        privacy = getattr(event, "privacy", None)
        eid = getattr(event, "id", None) or getattr(event, "event_id", None)
        etype = getattr(event, "type", None) or getattr(event, "event_type", None)
        if isinstance(event, Mapping):
            privacy = event.get("privacy", privacy)
            eid = event.get("id", event.get("event_id", eid))
            etype = event.get("type", event.get("event_type", etype))
        # Never interpolate payload / speech.
        self._record(f"event id={eid} type={etype} privacy={privacy}")

    def info(self, message: str, **fields: Any) -> None:
        parts = [message]
        for key, value in fields.items():
            if key in UTTERANCE_KEYS or key in {"payload", "speech", "utterance"}:
                parts.append(f"{key}={_REDACTED}")
                continue
            if isinstance(value, Mapping) and value.get("privacy") == "PRIVATE":
                parts.append(f"{key}={_REDACTED}")
                continue
            parts.append(f"{key}={value}")
        self._record(" ".join(str(p) for p in parts))

    def contains_raw(self, utterance: str) -> bool:
        blob = compact(utterance)
        if not blob:
            return False
        return any(blob in compact(line) for line in self.lines)
