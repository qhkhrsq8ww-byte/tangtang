"""TangTang V4 runtime loop.

observe → identify → event → Family Brain → decision → response → presentation

Offline (no LLM / no vendor TTS): policy, silent, basic animation, and the
event log still work. LLM down → 汪汪～. Sink failures stay local.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from core.adapters.animation import AnimationAction, AnimationController
from core.adapters.event_store import JsonlEventStore
from core.adapters.family_loader import load_members
from core.adapters.observation import Observation
from core.adapters.projection_adapter import ProjectionAdapter
from core.adapters.tts_adapter import TTSAdapter
from core.adapters.voice_adapter import VoiceAdapter
from core.events.event import Event
from core.events.event_bus import EventBus, PublishResult
from core.identity.resolver import IdentityResolver
from core.ingest import IngestResult, PrivacyPipeline
from core.logging.safe import SafeLogger
from core.response.orchestrator import PresentationAction
from core.runtime.isolate import isolate
from core.runtime.presentation import DeliveryResult, PresentationRuntime

FALLBACK = "汪汪～"


@dataclass
class RuntimeResult:
    event: Event | None
    member_id: str | None
    privacy: str | None
    decision: str
    action: PresentationAction | None
    delivery: DeliveryResult | None
    observation: dict[str, Any] = field(default_factory=dict)
    duplicate: bool = False
    event_kept: bool = True
    private_memory_id: str | None = None
    ingest: IngestResult | None = None
    context: dict[str, Any] = field(default_factory=dict)
    animation: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    publish: PublishResult | None = None

    @property
    def event_id(self) -> str | None:
        return None if self.event is None else self.event.id


class TangTangRuntime:
    """Composition root for the wired V4 path. Device sinks are injected."""

    core_api_version = "4.0.0"

    def __init__(
        self,
        *,
        members: Mapping[str, object] | None = None,
        pipeline: PrivacyPipeline | None = None,
        voice: VoiceAdapter | None = None,
        tts: TTSAdapter | None = None,
        projection: ProjectionAdapter | None = None,
        animation: AnimationController | None = None,
        bus: EventBus | None = None,
        events: JsonlEventStore | None = None,
        stt: Callable[[Any], str] | None = None,
        logger: SafeLogger | None = None,
        offline: bool = False,
    ) -> None:
        roster = dict(members) if members is not None else load_members()
        self.members = roster
        self.offline = offline
        self.logger = logger or SafeLogger()
        self.identity = IdentityResolver(roster)
        self.pipeline = pipeline or PrivacyPipeline(members=roster, logger=self.logger)
        self.voice = voice or VoiceAdapter()
        self.tts = tts or TTSAdapter()
        self.projection = projection or ProjectionAdapter()
        self.animation = animation or AnimationController()
        self.bus = bus or EventBus()
        self.events = events or JsonlEventStore()
        self.stt = stt
        self.presentation = PresentationRuntime(
            tts=self.tts.speaker,
            stt=self.stt,
            projection=self.projection.projector,
        )

    def _identify(self, observation: Mapping[str, Any]) -> str | None:
        resolved = isolate(lambda: self.identity.resolve(observation), fallback=None)
        member_id = resolved.value if resolved.ok else None
        if not member_id:
            return None
        return str(member_id)

    def _commit_event(self, event: Event) -> PublishResult:
        stored = isolate(lambda: self.events.append(event), fallback=False)
        if stored.ok and stored.value is False:
            return PublishResult(
                ok=False,
                duplicate=True,
                received_at="",
                errors=["duplicate event_id"],
                event_id=event.id,
            )
        published = isolate(lambda: self.bus.accept(event))
        if not published.ok or published.value is None:
            return PublishResult(
                ok=False,
                duplicate=False,
                received_at="",
                errors=[published.error_type or "bus"],
                event_id=event.id,
                accepted=False,
            )
        result = published.value
        if result.duplicate:
            return result
        isolate(lambda: self.logger.event(event))
        return result

    def _deliver(
        self,
        event: Event,
        action: PresentationAction | None,
        *,
        audio: Any = None,
    ) -> tuple[DeliveryResult, list[str]]:
        tts_res = isolate(lambda: self.tts.deliver(event, action))
        proj_res = isolate(lambda: self.projection.deliver(event, action))
        pres = isolate(lambda: self.presentation.deliver(event, action, audio=audio))
        delivery = DeliveryResult(event_id=event.id, event_kept=True)
        errors: list[str] = []
        for part in (tts_res, proj_res, pres):
            if not part.ok:
                errors.append(part.error_type or "sink")
                continue
            value = part.value
            if isinstance(value, DeliveryResult):
                delivery.tts_ok = delivery.tts_ok and value.tts_ok
                delivery.projection_ok = delivery.projection_ok and value.projection_ok
                delivery.stt_ok = delivery.stt_ok and value.stt_ok
                delivery.network_ok = delivery.network_ok and value.network_ok
                delivery.llm_ok = delivery.llm_ok and value.llm_ok
                errors.extend(value.errors)
                delivery.event_kept = delivery.event_kept and value.event_kept
        delivery.errors = errors
        scene = None
        if action is not None and action.decision == "SPEAK":
            clip = "眨眼"
        else:
            clip = "站立"
        frames = isolate(
            lambda: self.animation.play_safe(AnimationAction(clip)),
            fallback=["stand_0"],
        )
        anim = list(frames.value or ["stand_0"])
        return delivery, anim

    def handle_voice(
        self,
        pcm_path: str | None = None,
        *,
        audio: Any = None,
        utterance: str | None = None,
        candidate_member: str | None = None,
        confidence: float | None = None,
        observation: Mapping[str, Any] | None = None,
    ) -> RuntimeResult:
        """Mic → STT → Observation → Identity → Event → Brain → Response → TTS."""
        errors: list[str] = []
        extra = dict(observation or {})
        transcript = utterance
        if transcript is None and self.stt is not None and audio is not None:
            heard = isolate(lambda: self.stt(audio), fallback="")
            if not heard.ok:
                errors.append(f"stt:{heard.error_type}")
                transcript = ""
            else:
                transcript = str(heard.value or "")
        observed = isolate(
            lambda: self.voice.observe(
                pcm_path,
                candidate_member=candidate_member,
                confidence=confidence,
                extra=extra,
            )
        )
        if not observed.ok or not isinstance(observed.value, Observation):
            errors.append(f"voice:{observed.error_type or 'unknown'}")
            obs_map: dict[str, Any] = {"type": "voice.observed"}
        else:
            obs_map = observed.value.to_mapping()
        obs_map.update({k: v for k, v in extra.items() if k not in obs_map})
        if transcript:
            obs_map["utterance"] = transcript
        member_id = self._identify(obs_map)
        # unknown stays unknown — never default a child.
        if member_id:
            obs_map["member_id"] = member_id
            obs_map["label"] = member_id
        else:
            obs_map.pop("member_id", None)

        if transcript:
            return self._speak_path(transcript, obs_map, audio=audio, extra_errors=errors)

        event = Event.create(
            type="voice.observed",
            source="mic",
            privacy="PUBLIC",
            member_id=member_id,
            payload={"confidence": obs_map.get("confidence") or 0.0, "redacted": True},
        )
        pub = self._commit_event(event)
        if pub.duplicate:
            return RuntimeResult(
                event=event,
                member_id=member_id,
                privacy=event.privacy,
                decision="LOG_ONLY",
                action=None,
                delivery=DeliveryResult(event_id=event.id, event_kept=True),
                observation=obs_map,
                duplicate=True,
                event_kept=True,
                publish=pub,
                errors=errors,
            )
        action = PresentationAction(
            decision="LOG_ONLY",
            text="",
            action="observe",
            member_id=member_id,
            sink="none",
        )
        delivery, frames = self._deliver(event, action, audio=audio)
        return RuntimeResult(
            event=event,
            member_id=member_id,
            privacy=event.privacy,
            decision="LOG_ONLY",
            action=action,
            delivery=delivery,
            observation=obs_map,
            event_kept=delivery.event_kept,
            animation=frames,
            errors=errors + delivery.errors,
            publish=pub,
        )

    def _speak_path(
        self,
        utterance: str,
        observation: Mapping[str, Any],
        *,
        audio: Any = None,
        extra_errors: list[str] | None = None,
    ) -> RuntimeResult:
        errors = list(extra_errors or [])
        ingested = isolate(lambda: self.pipeline.ingest(utterance, observation))
        if not ingested.ok or ingested.value is None:
            errors.append(f"ingest:{ingested.error_type}")
            event = Event.create(
                type="utterance",
                source="mic",
                privacy="PUBLIC",
                payload={"redacted": True},
            )
            pub = self._commit_event(event)
            action = PresentationAction(
                decision="SILENT", text="", action="idle", member_id=None, sink="none"
            )
            delivery, frames = self._deliver(event, action, audio=audio)
            return RuntimeResult(
                event=event,
                member_id=None,
                privacy="PUBLIC",
                decision="SILENT",
                action=action,
                delivery=delivery,
                observation=dict(observation),
                event_kept=True,
                errors=errors,
                animation=frames,
                publish=pub,
            )
        result = ingested.value
        pub = self._commit_event(result.event)
        if pub.duplicate:
            return RuntimeResult(
                event=result.event,
                member_id=result.decision.member_id,
                privacy=result.decision.privacy,
                decision="LOG_ONLY",
                action=PresentationAction(
                    decision="LOG_ONLY",
                    text="",
                    action="idle",
                    member_id=result.decision.member_id,
                    sink="none",
                ),
                delivery=DeliveryResult(event_id=result.event.id, event_kept=True),
                observation=dict(observation),
                duplicate=True,
                event_kept=True,
                ingest=result,
                private_memory_id=result.private_memory_id,
                publish=pub,
                errors=errors,
            )
        who = {"member_id": result.decision.member_id}
        ctx_res = isolate(
            lambda: self.pipeline.builder.build(
                who=who,
                event=result.event,
                observation={**dict(observation), "utterance": utterance},
                privacy_scope=result.decision.privacy,
            ),
            fallback={},
        )
        context = ctx_res.value if isinstance(ctx_res.value, dict) else {}
        context["utterance"] = utterance
        context["scene"] = observation.get("scene")
        if self.pipeline.injection.is_injection(utterance):
            context["injection"] = True
            action = self.pipeline.orchestrator.run(
                decision="SPEAK", context=context, action="refuse"
            )
        else:
            decision = isolate(
                lambda: self.pipeline.interrupt.decide(observation),
                fallback="SILENT",
            )
            gate = decision.value if decision.ok and isinstance(decision.value, str) else "SILENT"
            spoken = isolate(
                lambda: self.pipeline.orchestrator.run(
                    decision=gate, context=context, action="reply"
                )
            )
            if not spoken.ok or spoken.value is None:
                errors.append(f"respond:{spoken.error_type}")
                action = PresentationAction(
                    decision="SPEAK" if gate == "SPEAK" else gate,
                    text=FALLBACK if gate == "SPEAK" else "",
                    action="reply",
                    member_id=result.decision.member_id,
                    sink="voice" if gate == "SPEAK" else "none",
                )
            else:
                action = spoken.value
        delivery, frames = self._deliver(result.event, action, audio=audio)
        return RuntimeResult(
            event=result.event,
            member_id=result.decision.member_id,
            privacy=result.decision.privacy,
            decision=action.decision,
            action=action,
            delivery=delivery,
            observation=dict(observation),
            event_kept=delivery.event_kept,
            ingest=result,
            private_memory_id=result.private_memory_id,
            context=context,
            animation=frames,
            errors=errors + delivery.errors,
            publish=pub,
        )
