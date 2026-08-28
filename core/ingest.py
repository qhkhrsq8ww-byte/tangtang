"""Utterance ingest: Identity → PrivacyPolicy → Event → stores.

This is the only supported speech path. Callers cannot skip PrivacyPolicy
or dump child raw speech into FamilyMemory / habits / parent context / logs.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.errors import PrivacyError
from core.events.event import Event
from core.identity.resolver import IdentityResolver
from core.logging.safe import SafeLogger
from core.memory.family import FamilyMemory, FamilySummary, HabitStore, ParentContext
from core.memory.private import PrivateMemory
from core.memory.store import Memory
from core.policy.injection import InjectionGuard
from core.policy.interrupt_policy import InterruptPolicy
from core.policy.privacy_policy import PrivacyDecision, PrivacyPolicy
from core.response.orchestrator import PresentationAction, ResponseOrchestrator
from core.context.builder import ContextBuilder


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class IngestResult:
    event: Event
    decision: PrivacyDecision
    stored_private: bool = False
    stored_family: bool = False
    stored_summary: bool = False
    stored_parent: bool = False
    stored_habit: bool = False
    private_memory_id: str | None = None


@dataclass
class Stores:
    private: PrivateMemory = field(default_factory=PrivateMemory)
    family: FamilyMemory = field(default_factory=FamilyMemory)
    summary: FamilySummary = field(default_factory=FamilySummary)
    parent: ParentContext = field(default_factory=ParentContext)
    habits: HabitStore = field(default_factory=HabitStore)


class PrivacyPipeline:
    """Composition root. LLM cannot access stores, files, shell, TTS."""

    def __init__(
        self,
        *,
        members: Mapping[str, object] | None = None,
        identity: IdentityResolver | None = None,
        privacy: PrivacyPolicy | None = None,
        stores: Stores | None = None,
        logger: SafeLogger | None = None,
        interrupt: InterruptPolicy | None = None,
        injection: InjectionGuard | None = None,
        responder: Callable[[Mapping[str, Any]], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.identity = identity or IdentityResolver(members)
        self.privacy = privacy or PrivacyPolicy(members)
        self.clock = clock or _utc_now
        if stores is None:
            stores = Stores(
                private=PrivateMemory(privacy=self.privacy, clock=self.clock),
                family=FamilyMemory(privacy=self.privacy, clock=self.clock),
                summary=FamilySummary(privacy=self.privacy, clock=self.clock),
                parent=ParentContext(privacy=self.privacy, clock=self.clock),
                habits=HabitStore(privacy=self.privacy),
            )
        self.stores = stores
        self.logger = logger or SafeLogger()
        self.interrupt = interrupt or InterruptPolicy(clock=self.clock)
        self.injection = injection or InjectionGuard()
        self.builder = ContextBuilder(
            self.stores.private.memory_port,
            self.interrupt,
            privacy=self.privacy,
            injection=self.injection,
        )
        self.orchestrator = ResponseOrchestrator(responder=responder, injection=self.injection)

    def ingest(
        self,
        utterance: str,
        observation: Mapping[str, Any] | None = None,
        *,
        source: str = "mic",
    ) -> IngestResult:
        obs = dict(observation or {})
        member_id = self.identity.resolve(obs) or obs.get("member_id") or obs.get("label")
        if member_id is not None:
            member_id = str(member_id).strip() or None
        decision = self.privacy.assert_event_privacy(
            member_id=member_id,
            utterance=utterance,
            requested=obs.get("privacy"),
        )
        if not decision.member_id and decision.privacy == "PRIVATE":
            raise PrivacyError("PRIVATE ingest requires member_id")
        event = Event.create(
            type="utterance",
            source=source,
            privacy=decision.privacy,
            member_id=decision.member_id,
            payload={"redacted": True} if decision.privacy == "PRIVATE" else {"speech": utterance},
            clock=self.clock,
        )
        self.logger.event(event)
        if self.logger.contains_raw(utterance) and decision.privacy == "PRIVATE":
            raise PrivacyError("SafeLogger leaked PRIVATE utterance")

        result = IngestResult(event=event, decision=decision)
        if decision.privacy == "PRIVATE" and decision.member_id:
            mem = self.stores.private.put(
                member_id=decision.member_id,
                utterance=utterance,
                event_id=event.id,
            )
            result.stored_private = True
            result.private_memory_id = mem.memory_id
        elif decision.allow_family_memory and decision.member_id:
            self.stores.family.put(Memory(
                memory_id=f"fam_{event.id}",
                member_id=decision.member_id,
                type="utterance",
                privacy="FAMILY",
                data={"speech": utterance},
                source_events=[event.id],
            ))
            result.stored_family = True
            if decision.allow_family_summary:
                self.stores.summary.add(member_id=decision.member_id, summary="family-note")
                result.stored_summary = True
            if decision.allow_habit_store:
                self.stores.habits.put(member_id=decision.member_id, utterance=utterance)
                result.stored_habit = True
            if decision.allow_parent_context:
                self.stores.parent.put(Memory(
                    memory_id=f"par_{event.id}",
                    member_id=decision.member_id,
                    type="note",
                    privacy="FAMILY",
                    data={"tag": "family-event"},
                    source_events=[event.id],
                ))
                result.stored_parent = True
        return result

    def respond(
        self,
        utterance: str,
        observation: Mapping[str, Any] | None = None,
        *,
        viewer_id: str | None = None,
    ) -> PresentationAction:
        obs = dict(observation or {})
        ingested = self.ingest(utterance, obs)
        who_id = viewer_id or ingested.decision.member_id
        who = {"member_id": who_id}
        if self.injection.is_injection(utterance):
            ctx = {
                "who": who,
                "current_event": ingested.event.to_dict(),
                "memory": [],
                "family": {},
                "utterance": utterance,
                "injection": True,
                "private_facts": [],
            }
            return self.orchestrator.run(decision="SPEAK", context=ctx, action="refuse")
        scope = ingested.decision.privacy
        ctx = self.builder.build(
            who=who,
            event=ingested.event,
            observation={**obs, "utterance": utterance},
            privacy_scope=scope,
        )
        ctx["utterance"] = utterance
        decision = self.interrupt.decide(obs)
        return self.orchestrator.run(decision=decision, context=ctx, action="reply")
