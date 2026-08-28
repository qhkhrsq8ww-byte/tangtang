"""Wrap existing voiceprint identify(). Do not rewrite the matcher.

Output: Observation {type: voice.observed, candidate_member, confidence}.
IdentityResolver maps candidate → member_id. unknown stays unknown —
never default child_9 / hanghang.
"""
from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.adapters.observation import (
    UNKNOWN_CANDIDATES,
    Observation,
    is_unknown_candidate,
    voice_observation,
)
from core.runtime.isolate import isolate

_CAT_VP = Path(__file__).resolve().parents[2] / "code" / "cat" / "cat-vp.py"

IdentifyFn = Callable[[str], Any]


def _load_identify() -> IdentifyFn | None:
    """Import identify() from the V3 voiceprint module. Never rewrite it."""
    if not _CAT_VP.is_file():
        return None
    spec = importlib.util.spec_from_file_location("tangtang_v3_voiceprint", _CAT_VP)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    loaded = isolate(lambda: spec.loader.exec_module(mod))  # type: ignore[union-attr]
    if not loaded.ok:
        return None
    fn = getattr(mod, "identify", None)
    return fn if callable(fn) else None


def _normalize_identify_result(raw: Any) -> tuple[str | None, float]:
    if raw is None:
        return None, 0.0
    if isinstance(raw, tuple) and raw:
        name, score = raw[0], raw[1] if len(raw) > 1 else 1.0
        try:
            conf = float(score)
        except (TypeError, ValueError):
            conf = 1.0
        candidate = None if is_unknown_candidate(name) else str(name).strip()
        return candidate, conf if candidate else 0.0
    text = str(raw).strip()
    if is_unknown_candidate(text) or text.lower() in UNKNOWN_CANDIDATES:
        return None, 0.0
    return text, 1.0


class VoiceAdapter:
    """Voiceprint → Observation. Identity is a later stage, not this module."""

    core_api_version = "4.0.0"

    def __init__(self, identify_fn: IdentifyFn | None = None) -> None:
        self._identify = identify_fn
        self._loaded: IdentifyFn | None | bool = False

    def _fn(self) -> IdentifyFn | None:
        if self._identify is not None:
            return self._identify
        if self._loaded is False:
            self._loaded = _load_identify()
        return self._loaded if callable(self._loaded) else None

    def observe(
        self,
        pcm_path: str | None = None,
        *,
        candidate_member: str | None = None,
        confidence: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Observation:
        """Build a voice.observed Observation.

        Tests inject candidate_member (no real mic). Production may pass pcm_path
        and reuse V3 identify(). Failures become unknown — never a child default.
        """
        candidate = candidate_member
        conf = 0.0 if confidence is None else float(confidence)
        if candidate is None and pcm_path:
            fn = self._fn()
            if fn is None:
                candidate, conf = None, 0.0
            else:
                result = isolate(lambda: fn(pcm_path), fallback="unknown")
                raw = result.value if result.ok else "unknown"
                candidate, conf = _normalize_identify_result(raw)
        if is_unknown_candidate(candidate):
            candidate, conf = None, 0.0
        # Hard rule: never invent hanghang / child_9 for unknown.
        payload = dict(extra or {})
        if pcm_path:
            payload["pcm"] = True
        return voice_observation(
            candidate_member=candidate,
            confidence=conf,
            extra=payload,
        )
