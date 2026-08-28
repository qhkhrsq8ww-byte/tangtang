"""Turn a policy decision into a presentation-neutral response."""
from __future__ import annotations

from typing import Any, Callable


class ResponseOrchestrator:
    def __init__(self, responder: Callable[[dict[str, Any]], str] | None = None) -> None:
        self.responder = responder or (lambda context: "")

    def run(self, *, decision: str, context: dict[str, Any], action: str = "idle") -> dict[str, Any]:
        if decision != "SPEAK":
            return {"decision": decision, "text": "", "action": action,
                    "member_id": context.get("who", {}).get("member_id")}
        return {"decision": "SPEAK", "text": self.responder(context), "action": action,
                "member_id": context.get("who", {}).get("member_id")}
