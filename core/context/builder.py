"""Bounded context. Opens no files/DB — MemoryPort + PolicyPort only."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.interfaces import MemoryPort, PolicyPort

_PRIVACY = frozenset({"PRIVATE", "FAMILY", "PUBLIC"})


class ContextBuilder:
    def __init__(
        self,
        memory: MemoryPort,
        policy: PolicyPort,
        *,
        max_recent: int = 10,
    ) -> None:
        if memory is None or policy is None:
            raise TypeError("ContextBuilder requires MemoryPort and PolicyPort")
        self._memory = memory
        self._policy = policy
        self.max_recent = max_recent

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
        memories = self._memory.query(
            member_id=str(member_id or ""),
            scope=str(scope),
            viewer_id=str(member_id) if member_id else None,
        )
        decision = self._policy.decide(obs)
        family_out = dict(family or {})
        family_out.pop("private", None)
        if hasattr(event, "to_dict"):
            event_out = event.to_dict()
        elif isinstance(event, Mapping):
            event_out = dict(event)
        else:
            event_out = {}
        recent_out = list(recent or [])[-self.max_recent :]
        return {
            "who": who_map,
            "current_event": event_out,
            "recent": recent_out,
            "memory": list(memories),
            "family": family_out,
            "privacy_scope": scope,
            "policy_decision": decision,
        }
