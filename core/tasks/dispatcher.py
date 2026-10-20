"""Due-task dispatcher with explicit delivery adapter and outcome recording."""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable

from core.tasks.service import Task, TaskService


def run_due(
    service: TaskService,
    *,
    member_ids: Iterable[str],
    deliver: Callable[[Task], bool],
    now: datetime | None = None,
    defer_reason: Callable[[Task], str | None] | None = None,
    on_defer: Callable[[Task, str], None] | None = None,
) -> dict[str, int]:
    """Deliver due tasks once per service instance and record adapter outcomes.

    The callback returns True only when its delivery command completed successfully.
    It cannot prove a human heard the reminder; callers should phrase status honestly.
    """
    counts = {"claimed": 0, "succeeded": 0, "failed": 0, "deferred": 0}
    seen: set[str] = set()
    for viewer_id in member_ids:
        for candidate in service.due_tasks(now=now, viewer_id=viewer_id):
            if candidate.task_id in seen or candidate.owner_member_id != viewer_id:
                continue
            seen.add(candidate.task_id)
            reason = "private_reminder_requires_private_channel" if candidate.visibility != "FAMILY" else (
                defer_reason(candidate) if defer_reason else None
            )
            if reason:
                service.defer_delivery(
                    candidate.task_id,
                    owner_member_id=candidate.owner_member_id,
                    reason=reason,
                )
                counts["deferred"] += 1
                if on_defer:
                    try:
                        on_defer(candidate, reason)
                    except Exception:
                        pass
                continue
            claimed = service.claim_due(
                candidate.task_id, owner_member_id=candidate.owner_member_id, now=now
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
                success=ok,
                result="delivery_command_succeeded" if ok else "delivery_command_failed",
            )
            counts["succeeded" if ok else "failed"] += 1
    return counts
