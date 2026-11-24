"""Validated metadata contract for identity/perception observations.

Adapters should attach this metadata to every sensor-derived claim. This
module deliberately does not infer identity or turn low-confidence signals
into family permissions.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class PerceptionEvidence:
    source: str
    observed_at: datetime
    confidence: float
    expires_at: datetime
    verification_status: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PerceptionEvidence | None":
        if not isinstance(value, Mapping):
            return None
        source = value.get("source")
        status = value.get("verification_status")
        confidence = value.get("confidence")
        observed_at = _parse_datetime(value.get("observed_at"))
        expires_at = _parse_datetime(value.get("expires_at"))
        if not isinstance(source, str) or not source.strip():
            return None
        if not isinstance(status, str) or not status.strip():
            return None
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            return None
        confidence = float(confidence)
        if not 0.0 <= confidence <= 1.0:
            return None
        if observed_at is None or expires_at is None or expires_at <= observed_at:
            return None
        return cls(
            source=source.strip(),
            observed_at=observed_at,
            confidence=confidence,
            expires_at=expires_at,
            verification_status=status.strip().lower(),
        )

    def is_usable(
        self,
        *,
        now: datetime | None = None,
        min_confidence: float = 0.85,
        max_age: timedelta = timedelta(minutes=2),
    ) -> bool:
        tick = now or datetime.now(timezone.utc)
        if tick.tzinfo is None:
            tick = tick.replace(tzinfo=timezone.utc)
        observed = _aware(self.observed_at)
        expires = _aware(self.expires_at)
        return (
            self.verification_status == "verified"
            and self.confidence >= min_confidence
            and observed <= tick + timedelta(seconds=5)
            and tick - observed <= max_age
            and tick < expires
        )


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _aware(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _aware(datetime.fromisoformat(value.strip().replace("Z", "+00:00")))
    except ValueError:
        return None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def evidence_is_usable(
    observation: Mapping[str, Any],
    field: str,
    *,
    now: datetime | None = None,
    min_confidence: float = 0.85,
    max_age: timedelta = timedelta(minutes=2),
) -> bool:
    """Validate observation['evidence'][field] for a sensor-derived claim."""
    all_evidence = observation.get("evidence")
    if not isinstance(all_evidence, Mapping):
        return False
    raw = all_evidence.get(field)
    parsed = PerceptionEvidence.from_mapping(raw) if isinstance(raw, Mapping) else None
    return bool(parsed and parsed.is_usable(
        now=now,
        min_confidence=min_confidence,
        max_age=max_age,
    ))
