"""Deterministic privacy classifier. LLM must not decide privacy.

Every utterance path (ingest → Event → Memory → Context → prompt →
log → file → TTS) must call PrivacyPolicy. Stores fail closed: child
raw speech never enters family-shared destinations even if a caller
mis-tags privacy as FAMILY/PUBLIC.

Child (9yo 弟弟/hanghang/child_9, 12yo 姐姐/qiaqia/child_12):
  unknown utterance → PRIVATE
  bullying / hurt / secret keywords → PRIVATE

Adult similar talk (e.g. 「被同学欺负」) → FAMILY unless clearly private.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.identity.resolver import CHILD_PRODUCTS, IdentityResolver

PRIVACY_SCOPES = frozenset({"PRIVATE", "FAMILY", "PUBLIC"})

DEST_PRIVATE_MEMORY = "private_memory"
DEST_FAMILY_MEMORY = "family_memory"
DEST_FAMILY_SUMMARY = "family_summary"
DEST_PARENT_CONTEXT = "parent_context"
DEST_HABIT_STORE = "habit_store"
DEST_ORDINARY_LOG = "ordinary_log"
DEST_TTS = "tts"
DEST_PROMPT = "prompt"

FAMILY_DESTINATIONS = frozenset({
    DEST_FAMILY_MEMORY,
    DEST_FAMILY_SUMMARY,
    DEST_PARENT_CONTEXT,
    DEST_HABIT_STORE,
    DEST_ORDINARY_LOG,
})

# Child hurt / secret. Classification is still fail-closed for *any*
# child utterance; these make the PRIVATE decision explicit.
CHILD_PRIVATE_MARKERS = (
    "欺负", "霸凌", "打我", "骂我", "受伤", "好疼", "害怕",
    "秘密", "别告诉", "不要告诉", "碰我", "威胁", "不敢说",
    "同学打", "被同学", "校园暴力",
)

ADULT_PRIVATE_MARKERS = (
    "私人信息", "私人的", "我的私事", "别告诉孩子", "不要告诉孩子",
    "别告诉任何人", "不要告诉任何人", "这是秘密", "保密",
    "密码", "银行卡", "私事",
)

UTTERANCE_KEYS = ("speech", "text", "utterance", "transcript", "raw", "words")


def compact(text: str | None) -> str:
    return (text or "").replace(" ", "").replace("\n", "").replace("\t", "")


def raw_utterance_from(data: Mapping[str, Any] | None) -> str | None:
    if not isinstance(data, Mapping):
        return None
    for key in UTTERANCE_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


@dataclass(frozen=True)
class PrivacyDecision:
    privacy: str
    member_id: str | None
    is_child: bool
    allow_raw_text: bool
    allow_family_memory: bool
    allow_family_summary: bool
    allow_parent_context: bool
    allow_habit_store: bool
    allow_log_raw: bool
    reason: str

    def allows(self, destination: str) -> bool:
        if destination == DEST_PRIVATE_MEMORY:
            return self.privacy == "PRIVATE"
        if destination == DEST_FAMILY_MEMORY:
            return self.allow_family_memory
        if destination == DEST_FAMILY_SUMMARY:
            return self.allow_family_summary
        if destination == DEST_PARENT_CONTEXT:
            return self.allow_parent_context
        if destination == DEST_HABIT_STORE:
            return self.allow_habit_store
        if destination == DEST_ORDINARY_LOG:
            return self.allow_log_raw
        if destination in {DEST_TTS, DEST_PROMPT}:
            return True
        return False


class PrivacyPolicy:
    """Source of truth for PRIVATE / FAMILY / PUBLIC routing."""

    def __init__(self, members: Mapping[str, object] | None = None) -> None:
        self._identity = IdentityResolver(members)

    def canonical_member_id(self, raw: str | None) -> str | None:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return None
        return (
            self._identity.resolve({"member_id": text})
            or self._identity.resolve({"label": text})
        )

    def is_child(self, member_id: str | None) -> bool:
        if not member_id:
            return False
        if self._identity.is_child(member_id):
            return True
        canonical = self.canonical_member_id(member_id)
        return self._identity.is_child(canonical)

    def _looks_child_private(self, utterance: str | None) -> bool:
        blob = compact(utterance)
        if not blob:
            return False
        return any(marker.replace(" ", "") in blob for marker in CHILD_PRIVATE_MARKERS if marker.strip())

    def _looks_adult_private(self, utterance: str | None) -> bool:
        blob = compact(utterance)
        if not blob:
            return False
        return any(marker.replace(" ", "") in blob for marker in ADULT_PRIVATE_MARKERS)

    def classify(
        self,
        *,
        member_id: str | None = None,
        utterance: str | None = None,
        observation: Mapping[str, Any] | None = None,
    ) -> PrivacyDecision:
        obs = dict(observation or {})
        raw_id = member_id or obs.get("member_id") or obs.get("label") or obs.get("speaker")
        if raw_id is not None:
            raw_id = str(raw_id).strip() or None
        text = utterance if utterance is not None else (
            obs.get("utterance") or obs.get("speech") or obs.get("text") or ""
        )
        text = str(text) if text is not None else ""
        canonical = self.canonical_member_id(raw_id)
        child = self.is_child(raw_id) or self.is_child(canonical)

        if child:
            mid = canonical or raw_id or "unknown"
            return PrivacyDecision(
                privacy="PRIVATE",
                member_id=mid,
                is_child=True,
                allow_raw_text=True,
                allow_family_memory=False,
                allow_family_summary=False,
                allow_parent_context=False,
                allow_habit_store=False,
                allow_log_raw=False,
                reason="child-fail-closed" if not self._looks_child_private(text) else "child-private-marker",
            )

        if canonical is None and not raw_id:
            return PrivacyDecision(
                privacy="PUBLIC",
                member_id=None,
                is_child=False,
                allow_raw_text=True,
                allow_family_memory=False,
                allow_family_summary=False,
                allow_parent_context=False,
                allow_habit_store=False,
                allow_log_raw=True,
                reason="unknown-public",
            )

        mid = canonical or raw_id
        if self._looks_adult_private(text):
            return PrivacyDecision(
                privacy="PRIVATE",
                member_id=mid,
                is_child=False,
                allow_raw_text=True,
                allow_family_memory=False,
                allow_family_summary=False,
                allow_parent_context=False,
                allow_habit_store=False,
                allow_log_raw=False,
                reason="adult-clearly-private",
            )
        return PrivacyDecision(
            privacy="FAMILY",
            member_id=mid,
            is_child=False,
            allow_raw_text=True,
            allow_family_memory=True,
            allow_family_summary=True,
            allow_parent_context=True,
            allow_habit_store=True,
            allow_log_raw=True,
            reason="adult-family",
        )

    def allow_destination(
        self,
        destination: str,
        *,
        member_id: str | None = None,
        utterance: str | None = None,
        privacy: str | None = None,
    ) -> bool:
        """Fail closed: child raw speech never enters family-shared stores."""
        decision = self.classify(member_id=member_id, utterance=utterance)
        raw = bool((utterance or "").strip())
        if destination == DEST_PRIVATE_MEMORY:
            if privacy and privacy != "PRIVATE":
                return False
            return decision.privacy == "PRIVATE" or (raw and decision.is_child)
        if raw and decision.is_child:
            return False
        if (privacy or decision.privacy) == "PRIVATE":
            return destination == DEST_PRIVATE_MEMORY
        return decision.allows(destination)

    def assert_event_privacy(
        self,
        *,
        member_id: str | None,
        utterance: str | None,
        requested: str | None = None,
    ) -> PrivacyDecision:
        """Caller cannot downgrade a child utterance to FAMILY/PUBLIC."""
        decision = self.classify(member_id=member_id, utterance=utterance)
        if requested in PRIVACY_SCOPES:
            if decision.is_child and requested != "PRIVATE":
                return decision
            if decision.privacy == "PRIVATE" and requested != "PRIVATE":
                return decision
        return decision
