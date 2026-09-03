"""Long-term structured memory writes (m2) — tags/facts only for family scope.

Child raw speech must use PrivateMemory. This helper never copies utterances
into FamilyMemory / HabitTrendStore.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.errors import MemoryError
from core.memory.emotion_drift import EmotionDriftStore, mood_label
from core.memory.family import FamilyMemory, FamilySummary
from core.memory.habit_trends import HabitTrendStore
from core.memory.private import PrivateMemory
from core.memory.store import Memory
from core.policy.privacy_policy import PrivacyPolicy, raw_utterance_from


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LearningMemoryService:
    """Compose emotion + habit trends + gated long-term notes."""

    def __init__(
        self,
        *,
        home: str | Path | None = None,
        privacy: PrivacyPolicy | None = None,
        persist: bool = True,
    ) -> None:
        self._privacy = privacy or PrivacyPolicy()
        self.emotion = EmotionDriftStore(home=home, persist=persist)
        self.habits = HabitTrendStore(home=home, privacy=self._privacy, persist=persist)
        self.family = FamilyMemory(home=home, privacy=self._privacy, persist=persist)
        self.summary = FamilySummary(home=home, privacy=self._privacy, persist=persist)
        self.private = PrivateMemory(home=home, privacy=self._privacy, persist=persist)

    def on_interaction(
        self,
        *,
        member_id: str,
        event_tag: str,
        kind: str = "care",
        utterance: str = "",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        when = now or _utc_now()
        mid = str(member_id or "").strip() or "unknown"
        emotion = self.emotion.interact(kind, now=when)
        habit = self.habits.record(member_id=mid, tag=event_tag, now=when)

        private_id = None
        if utterance and self._privacy.is_child(mid):
            mem = self.private.put(member_id=mid, utterance=utterance)
            private_id = mem.memory_id
        elif utterance and not self._privacy.is_child(mid):
            # Adults: structured family note without free-form dump if policy says PRIVATE
            decision = self._privacy.classify(member_id=mid, utterance=utterance)
            if decision.privacy == "PRIVATE":
                mem = self.private.put(member_id=mid, utterance=utterance)
                private_id = mem.memory_id
            else:
                self.family.put(
                    Memory(
                        memory_id=f"lt_{uuid4().hex}",
                        member_id=mid,
                        type="interaction",
                        privacy="FAMILY",
                        data={"tag": event_tag, "mood": emotion.get("mood_label")},
                    )
                )

        # Family summary: mood + counts only (children allowed as structured, no speech)
        try:
            self.summary.add_structured(
                member_id=mid,
                mood=str(emotion.get("mood_label") or mood_label(emotion)),
                interaction_count=1,
                privacy="FAMILY",
            )
        except MemoryError:
            pass

        return {
            "member_id": mid,
            "emotion": emotion,
            "habit": habit,
            "private_memory_id": private_id,
            "mood_label": emotion.get("mood_label"),
        }

    def remember_fact(
        self,
        *,
        member_id: str,
        fact_tag: str,
        detail: Mapping[str, Any] | None = None,
    ) -> Memory:
        """Long-term family fact. Rejects utterance-like payloads."""
        mid = str(member_id or "").strip() or "unknown"
        data = {"tag": str(fact_tag)}
        if detail:
            if raw_utterance_from(dict(detail)):
                raise MemoryError("long-term family fact rejects raw utterance")
            for key in detail:
                if str(key).lower() in {
                    "text", "utterance", "transcript", "speech", "raw", "message",
                }:
                    raise MemoryError("long-term family fact rejects utterance keys")
            data.update({k: v for k, v in detail.items() if k != "tag"})
        mem = Memory(
            memory_id=f"fact_{uuid4().hex}",
            member_id=mid,
            type="long_term_fact",
            privacy="FAMILY",
            data=data,
        )
        self.family.put(mem)
        return mem
