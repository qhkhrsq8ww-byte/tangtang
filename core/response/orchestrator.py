"""Presentation-neutral orchestrator.

Emits a validated PresentationAction. Does not import or call TTS,
projection, shell, or files. A text responder (optional LLM) may only
return a string; sinks are labels for a later presentation layer.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.errors import ActionError

DECISIONS = frozenset({"SPEAK", "SILENT", "DELAY", "LOG_ONLY"})
SINKS = frozenset({"none", "voice", "face", "projection"})
MAX_TEXT_BYTES = 2048


@dataclass(frozen=True)
class PresentationAction:
    decision: str
    text: str
    action: str
    member_id: str | None
    sink: str = "none"

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise ActionError("decision must be SPEAK, SILENT, DELAY, or LOG_ONLY")
        if self.sink not in SINKS:
            raise ActionError("sink must be none, voice, face, or projection")
        if not isinstance(self.text, str):
            raise ActionError("text must be a string")
        if not isinstance(self.action, str) or not self.action.strip():
            raise ActionError("action is required")
        if self.decision != "SPEAK":
            if self.text:
                raise ActionError("non-SPEAK actions must not carry speech text")
            object.__setattr__(self, "sink", "none")

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "text": self.text,
            "action": self.action,
            "member_id": self.member_id,
            "sink": self.sink,
        }


def _clip_text(text: str) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_TEXT_BYTES:
        return text
    return encoded[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")


class ResponseOrchestrator:
    def __init__(self, responder: Callable[[Mapping[str, Any]], str] | None = None) -> None:
        self.responder = responder or (lambda context: "")

    def run(
        self,
        *,
        decision: str,
        context: Mapping[str, Any] | None,
        action: str = "idle",
    ) -> PresentationAction:
        ctx = dict(context or {})
        member_id = None
        who = ctx.get("who")
        if isinstance(who, Mapping):
            member_id = who.get("member_id")
        if decision not in DECISIONS:
            raise ActionError("decision must be SPEAK, SILENT, DELAY, or LOG_ONLY")
        if decision != "SPEAK":
            return PresentationAction(
                decision=decision,
                text="",
                action=action or "idle",
                member_id=member_id,
                sink="none",
            )
        text = self.responder(ctx)
        if not isinstance(text, str):
            raise ActionError("responder must return text, not a sink callable")
        return PresentationAction(
            decision="SPEAK",
            text=_clip_text(text),
            action=action or "idle",
            member_id=member_id,
            sink="voice",
        )
