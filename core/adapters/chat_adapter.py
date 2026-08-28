"""Wrap V3 cat-chat. New path cannot skip PrivacyPolicy.

V3 cat-chat.py still concatenates prompts from local JSON. That CLI is
left in place (opt-in TANGTANG_V4_PIPELINE=1 uses this adapter). The
adapter path is:

  STT text → Voice Observation → Identity → Event → PrivacyPolicy
  → Memory → ContextBuilder → LLM (optional) → ResponseOrchestrator → TTSAdapter

LLM only sees PrivacyPolicy-filtered context. It does not call TTS,
projection, shell, or files.
"""
from __future__ import annotations

import importlib.util
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from core.adapters.family_loader import load_members
from core.ingest import PrivacyPipeline
from core.policy.injection import InjectionGuard
from core.response.orchestrator import PresentationAction
from core.runtime.isolate import isolate

_CAT_CHAT = Path(__file__).resolve().parents[2] / "code" / "cat" / "cat-chat.py"

LLMFn = Callable[[Mapping[str, Any]], str]


def _load_cat_chat_helpers() -> tuple[Callable[[str], bool] | None, Callable[[str], str] | None]:
    """Reuse looks_risky / sanitize_output. Do not call V3 chat() (unfiltered prompt)."""
    if not _CAT_CHAT.is_file():
        return None, None
    spec = importlib.util.spec_from_file_location("tangtang_v3_chat", _CAT_CHAT)
    if spec is None or spec.loader is None:
        return None, None
    mod = importlib.util.module_from_spec(spec)
    loaded = isolate(lambda: spec.loader.exec_module(mod))  # type: ignore[union-attr]
    if not loaded.ok:
        return None, None
    risky = getattr(mod, "looks_risky", None)
    sanitize = getattr(mod, "sanitize_output", None)
    return (risky if callable(risky) else None, sanitize if callable(sanitize) else None)


def _filtered_prompt(context: Mapping[str, Any]) -> str:
    """User-facing prompt from already-filtered context. No extra family dumps."""
    utterance = str(context.get("utterance") or "")
    who = context.get("who") if isinstance(context.get("who"), Mapping) else {}
    member_id = who.get("member_id") if isinstance(who, Mapping) else None
    scope = context.get("privacy_scope") or "PRIVATE"
    family = context.get("family") if isinstance(context.get("family"), Mapping) else {}
    # Family snapshot must already be structured / non-PRIVATE.
    family_bits = []
    for key in ("mood", "interaction_count", "summary"):
        if key in family and family[key] not in (None, ""):
            family_bits.append(f"{key}={family[key]}")
    parts = [
        f"member={member_id or 'unknown'}",
        f"privacy={scope}",
    ]
    if family_bits:
        parts.append("family[" + ",".join(str(b) for b in family_bits) + "]")
    parts.append("utterance=" + utterance)
    return "\n".join(parts)


class ChatAdapter:
    """Speech → PrivacyPipeline. Optional LLM sees filtered context only."""

    core_api_version = "4.0.0"

    def __init__(
        self,
        pipeline: PrivacyPipeline | None = None,
        *,
        members: Mapping[str, object] | None = None,
        llm: LLMFn | None = None,
        sanitize: Callable[[str], str] | None = None,
        looks_risky: Callable[[str], bool] | None = None,
    ) -> None:
        roster = dict(members) if members is not None else load_members()
        self.pipeline = pipeline or PrivacyPipeline(members=roster)
        self._llm = llm
        risky, sanit = _load_cat_chat_helpers()
        self._sanitize = sanitize or sanit
        self._looks_risky = looks_risky or risky
        self._injection = InjectionGuard()

    def reply(
        self,
        utterance: str,
        observation: Mapping[str, Any] | None = None,
        *,
        viewer_id: str | None = None,
    ) -> PresentationAction:
        """New path. PrivacyPolicy runs inside ingest before Event / Memory / LLM."""
        obs = dict(observation or {})
        text = utterance or str(obs.get("utterance") or obs.get("speech") or "")
        if self._looks_risky is not None:
            risky = isolate(lambda: bool(self._looks_risky(text)), fallback=False)
            if risky.ok and risky.value:
                obs = {**obs, "safety": "risk"}
        ingested = self.pipeline.ingest(text, obs)
        who_id = viewer_id or ingested.decision.member_id
        who = {"member_id": who_id}
        if self._injection.is_injection(text):
            ctx = {
                "who": who,
                "current_event": ingested.event.to_dict(),
                "memory": [],
                "family": {},
                "utterance": text,
                "injection": True,
                "private_facts": [],
            }
            return self.pipeline.orchestrator.run(decision="SPEAK", context=ctx, action="refuse")
        scope = ingested.decision.privacy
        family_snapshot: dict[str, Any] = {}
        if ingested.decision.allow_family_summary:
            snap = isolate(lambda: self.pipeline.stores.summary.snapshot())
            if snap.ok and isinstance(snap.value, list):
                family_snapshot = {"members": snap.value}
        ctx = self.pipeline.builder.build(
            who=who,
            event=ingested.event,
            observation={**obs, "utterance": text},
            family=family_snapshot,
            privacy_scope=scope,
        )
        ctx["utterance"] = text
        ctx["scene"] = obs.get("scene")
        ctx["event_id"] = ingested.event.id
        decision = self.pipeline.interrupt.decide(obs)
        if self._llm is not None and decision == "SPEAK":
            ctx["skip_persona"] = True
            prompt_ctx = dict(ctx)
            prompt_ctx["_filtered_prompt"] = _filtered_prompt(ctx)

            def _call_llm() -> str:
                return str(self._llm(prompt_ctx))

            llm_res = isolate(_call_llm, fallback="汪汪～")
            text_out = llm_res.value if llm_res.ok and isinstance(llm_res.value, str) else "汪汪～"
            if not text_out.strip():
                text_out = "汪汪～"
            if self._sanitize is not None:
                cleaned = isolate(lambda: self._sanitize(text_out), fallback=text_out)
                if cleaned.ok and isinstance(cleaned.value, str) and cleaned.value.strip():
                    text_out = cleaned.value
            ctx["llm_text"] = text_out
            original = self.pipeline.orchestrator.responder
            self.pipeline.orchestrator.responder = lambda _c, t=text_out: t
            try:
                return self.pipeline.orchestrator.run(decision=decision, context=ctx, action="reply")
            finally:
                self.pipeline.orchestrator.responder = original
        return self.pipeline.orchestrator.run(decision=decision, context=ctx, action="reply")
