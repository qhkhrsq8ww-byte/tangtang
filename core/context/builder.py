"""Bounded context. Opens no files/DB — MemoryPort + PolicyPort only."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.interfaces import MemoryPort, PolicyPort
from core.policy.injection import InjectionGuard
from core.policy.privacy_policy import PrivacyPolicy
from core.runtime.isolate import isolate

_PRIVACY = frozenset({"PRIVATE", "FAMILY", "PUBLIC"})


class ContextBuilder:
    def __init__(
        self,
        memory: MemoryPort,
        policy: PolicyPort,
        *,
        max_recent: int = 10,
        privacy: PrivacyPolicy | None = None,
        injection: InjectionGuard | None = None,
    ) -> None:
        if memory is None or policy is None:
            raise TypeError("ContextBuilder requires MemoryPort and PolicyPort")
        self._memory = memory
        self._policy = policy
        self.max_recent = max_recent
        self._privacy_policy = privacy or PrivacyPolicy()
        self._injection = injection or InjectionGuard()

    def build(
        self,
        *,
        who: Mapping[str, Any] | None,
        event: Any,
        observation: Mapping[str, Any] | None = None,
        recent: list[Any] | None = None,
        family: Mapping[str, Any] | None = None,
        privacy_scope: str | None = None,
    ) -> dict[str, Any]:
        who_map = dict(who or {})
        obs = dict(observation or {})
        member_id = who_map.get("member_id") or obs.get("member_id")
        scope = privacy_scope or obs.get("privacy_scope") or "PRIVATE"
        if scope not in _PRIVACY:
            scope = "PRIVATE"
        q = isolate(
            lambda: self._memory.query(
                member_id=str(member_id or ""),
                scope=str(scope),
                viewer_id=str(member_id) if member_id else None,
            ),
            fallback=[],
        )
        memories = q.value if isinstance(q.value, list) else []
        d = isolate(lambda: self._policy.decide(obs), fallback="SILENT")
        decision = d.value if isinstance(d.value, str) and d.value else "SILENT"
        family_out = dict(family or {})
        family_out.pop("private", None)
        if hasattr(event, "to_dict"):
            event_out = event.to_dict()
        elif isinstance(event, Mapping):
            event_out = dict(event)
        else:
            event_out = {}
        event_out = self._scrub_event(event_out, scope=str(scope), viewer_id=member_id)
        recent_out = list(recent or [])[-self.max_recent :]
        utterance = str(obs.get("utterance") or obs.get("speech") or "")
        payload = event_out.get("payload") if isinstance(event_out.get("payload"), Mapping) else {}
        if isinstance(payload, Mapping) and not utterance:
            utterance = str(payload.get("speech") or payload.get("text") or "")
        injected = self._injection.is_injection(utterance)
        if injected:
            memories = []
            family_out.pop("secrets", None)
            family_out.pop("secret", None)
        return {
            "who": who_map,
            "current_event": event_out,
            "recent": recent_out,
            "memory": list(memories),
            "family": family_out,
            "privacy_scope": scope,
            "policy_decision": decision,
            "injection": injected,
            "utterance": utterance,
            "private_facts": [],
        }

    def _scrub_event(
        self,
        event_out: dict[str, Any],
        *,
        scope: str,
        viewer_id: Any,
    ) -> dict[str, Any]:
        if event_out.get("privacy") != "PRIVATE":
            return event_out
        owner = event_out.get("member_id")
        if scope == "PRIVATE" and owner and owner == viewer_id:
            return event_out
        scrubbed = dict(event_out)
        scrubbed["payload"] = {"redacted": True}
        return scrubbed
