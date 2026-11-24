"""System-owned reminder dispatch: Audience is not a Viewer or listener."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.security.contexts import ActorContext
from core.tasks.dispatcher import run_due
from core.tasks.service import TaskService


class TestReminderDispatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)
        self.members = {"dad": {}, "child": {}}
        self.actor = ActorContext(
            None, "system", "system", frozenset({"tasks:dispatch"})
        )
        self.service = TaskService(
            home=Path(self.tmp.name), persist=True, members=self.members,
            clock=lambda: self.now,
        )
        self.task = self.service.create_task(
            owner_member_id="child",
            title="带水杯",
            due_at=(self.now - timedelta(minutes=1)).isoformat(),
            timezone_name="UTC",
            idempotency_key="water-1",
            visibility="FAMILY",
        )

    def dispatch(self, **kwargs):
        return run_due(self.service, actor=self.actor, now=self.now, **kwargs)

    def test_success_is_recorded_and_not_replayed(self):
        delivered = []
        result = self.dispatch(deliver=lambda task: delivered.append(task.task_id) or True)
        self.assertEqual(result, {"claimed": 1, "succeeded": 1, "failed": 0, "deferred": 0})
        self.assertEqual(delivered, [self.task.task_id])
        self.assertEqual(self.service.get_task(self.task.task_id, viewer_id="child").status, "delivered")
        second = self.dispatch(deliver=lambda task: self.fail("completed reminder replayed"))
        self.assertEqual(second["claimed"], 0)

    def test_failure_is_not_reported_as_success(self):
        result = self.dispatch(deliver=lambda task: False)
        self.assertEqual(result["failed"], 1)
        failed = self.service.get_task(self.task.task_id, viewer_id="child")
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.result, "delivery_command_failed")

    def test_private_due_task_is_deferred_inside_core_without_exposing_title(self):
        private = self.service.create_task(
            owner_member_id="child",
            title="私人提醒：收拾书包",
            due_at=(self.now - timedelta(minutes=1)).isoformat(),
            timezone_name="UTC",
            visibility="PRIVATE",
        )
        delivered = []
        result = self.dispatch(deliver=lambda task: delivered.append(task.title) or True)
        self.assertEqual(delivered, ["带水杯"])
        self.assertEqual(result["deferred"], 1)
        stored = self.service.get_task(private.task_id, viewer_id="child")
        self.assertEqual(stored.status, "needs_confirmation")
        self.assertEqual(stored.result, "private_reminder_requires_private_channel")

    def test_family_reminder_can_be_deferred_by_quiet_hours_policy(self):
        result = self.dispatch(
            deliver=lambda task: self.fail("quiet-hours task must not be spoken"),
            defer_reason=lambda task: "quiet_hours",
        )
        self.assertEqual(result["deferred"], 1)
        stored = self.service.get_task(self.task.task_id, viewer_id="child")
        self.assertEqual(stored.status, "needs_confirmation")
        self.assertEqual(stored.result, "quiet_hours")

    def test_dispatcher_uses_system_actor_and_keeps_owner_as_audience(self):
        delivered = []
        self.dispatch(
            deliver=lambda task: delivered.append(
                {"task_id": task.task_id, "audience_id": task.owner_member_id}
            ) or True
        )
        self.assertEqual(delivered, [{"task_id": self.task.task_id, "audience_id": "child"}])

    def test_member_or_unprivileged_actor_cannot_dispatch(self):
        member_actor = ActorContext("dad", "member", "verified")
        with self.assertRaises(PermissionError):
            run_due(self.service, actor=member_actor, deliver=lambda task: True, now=self.now)
        unprivileged_system = ActorContext(None, "system", "system")
        with self.assertRaises(PermissionError):
            self.service.due_tasks_for_dispatch(actor=unprivileged_system, now=self.now)

    def test_claim_and_finish_require_system_capability_and_owner_scope(self):
        self.assertIsNone(self.service.claim_due(
            self.task.task_id, owner_member_id="dad", actor=self.actor, now=self.now
        ))
        with self.assertRaises(PermissionError):
            self.service.finish_delivery(
                self.task.task_id, owner_member_id="dad", actor=self.actor, success=True
            )
        claimed = self.service.claim_due(
            self.task.task_id, owner_member_id="child", actor=self.actor, now=self.now
        )
        self.assertIsNotNone(claimed)
        delivered = self.service.finish_delivery(
            self.task.task_id, owner_member_id="child", actor=self.actor, success=True
        )
        self.assertEqual(delivered.status, "delivered")
        self.assertIsNone(delivered.completed_at)
        with self.assertRaises(ValueError):
            self.service.finish_delivery(
                self.task.task_id, owner_member_id="child", actor=self.actor, success=True
            )

    def test_running_task_is_recovered_without_automatic_replay(self):
        self.service.claim_due(
            self.task.task_id, owner_member_id="child", actor=self.actor, now=self.now
        )
        later = self.now + timedelta(minutes=20)
        self.assertEqual(self.service.recover_stale_running(now=later), 1)
        task = self.service.get_task(self.task.task_id, viewer_id="child")
        self.assertEqual(task.status, "failed")
        self.assertEqual(task.result, "interrupted_delivery_unknown_manual_review")
        replay = run_due(
            self.service, actor=self.actor,
            deliver=lambda item: self.fail("uncertain delivery must not auto-replay"),
            now=later,
        )
        self.assertEqual(replay["claimed"], 0)

    def test_running_state_survives_restart(self):
        self.service.claim_due(
            self.task.task_id, owner_member_id="child", actor=self.actor, now=self.now
        )
        restarted = TaskService(
            home=Path(self.tmp.name), persist=True, members=self.members,
            clock=lambda: self.now + timedelta(minutes=20),
        )
        self.assertEqual(restarted.recover_stale_running(
            now=self.now + timedelta(minutes=20)
        ), 1)
        recovered = restarted.get_task(self.task.task_id, viewer_id="child")
        self.assertEqual(recovered.status, "failed")
        self.assertEqual(recovered.result, "interrupted_delivery_unknown_manual_review")


if __name__ == "__main__":
    unittest.main()
