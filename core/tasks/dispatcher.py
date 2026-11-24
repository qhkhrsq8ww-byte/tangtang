"""Due-task dispatcher with explicit system Actor and reminder Audience."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from core.security.contexts import ActorContext
from core.tasks.service import Task, TaskService


def run_due(
    service: TaskService,
    *,
    actor: ActorContext,
    deliver: Callable[[Task], bool],
    now: datetime | None = None,
    defer_reason: Callable[[Task], str | None] | None = None,
    on_defer: Callable[[Task, str], None] | None = None,
) -> dict[str, int]:
    """Dispatch FAMILY reminders as the system actor, never by impersonating owners.

    PRIVATE reminders are deferred inside TaskService; their titles are not returned
    to the delivery adapter. The callback's success only confirms a local command,
    not that a human listener actually heard the reminder.
    """
    service._require_dispatch_actor(actor)
    counts = {"claimed": 0, "succeeded": 0, "failed": 0, "deferred": 0}
    counts["deferred"] = service.defer_private_due_for_dispatch(actor=actor, now=now)

    for candidate in service.due_tasks_for_dispatch(actor=actor, now=now):
        reason = defer_reason(candidate) if defer_reason else None
        if reason:
            service.defer_delivery(
                candidate.task_id,
                owner_member_id=candidate.owner_member_id,
                reason=reason,
                actor=actor,
            )
            counts["deferred"] += 1
            if on_defer:
                try:
                    on_defer(candidate, reason)
                except Exception:
                    pass
            continue
        claimed = service.claim_due(
            candidate.task_id,
            owner_member_id=candidate.owner_member_id,
            actor=actor,
            now=now,
        )
        if claimed is None:
            continue
        counts["claimed"] += 1
        try:
            ok = bool(deliver(claimed))
        except Exception:
            ok = False
        service.finish_delivery(
            claimed.task_id,
            owner_member_id=claimed.owner_member_id,
            actor=actor,
            success=ok,
            result="delivery_command_succeeded" if ok else "delivery_command_failed",
        )
        counts["succeeded" if ok else "failed"] += 1
    return counts
