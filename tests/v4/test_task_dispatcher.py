"""Tests for durable reminder claiming and delivery outcome handling."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.tasks.dispatcher import run_due
from core.tasks.service import TaskService


class TestReminderDispatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)
        self.members = {"dad": {}, "child": {}}
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
        )

    def test_success_is_recorded_and_not_replayed(self):
        delivered = []
        result = run_due(
            self.service, member_ids=self.members,
            deliver=lambda task: delivered.append(task.task_id) or True,
            now=self.now,
        )
        self.assertEqual(result, {"claimed": 1, "succeeded": 1, "failed": 0})
        self.assertEqual(delivered, [self.task.task_id])
        self.assertEqual(self.service.get_task(self.task.task_id, viewer_id="child").status, "done")
        second = run_due(
            self.service, member_ids=self.members,
            deliver=lambda task: self.fail("completed reminder replayed"),
            now=self.now,
        )
        self.assertEqual(second["claimed"], 0)

    def test_failure_is_not_reported_as_success_and_can_be_rescheduled(self):
        result = run_due(
            self.service, member_ids=self.members, deliver=lambda task: False, now=self.now,
        )
        self.assertEqual(result["failed"], 1)
        failed = self.service.get_task(self.task.task_id, viewer_id="child")
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.result, "delivery_command_failed")
        rescheduled = self.service.reschedule(
            self.task.task_id, owner_member_id="child",
            due_at=(self.now + timedelta(minutes=5)).isoformat(),
        )
        self.assertEqual(rescheduled.status, "scheduled")

    def test_stale_running_task_is_marked_uncertain_not_replayed(self):
        claimed = self.service.claim_due(
            self.task.task_id, owner_member_id="child", now=self.now
        )
        self.assertIsNotNone(claimed)
        later = self.now + timedelta(minutes=20)
        changed = self.service.recover_stale_running(now=later)
        self.assertEqual(changed, 1)
        task = self.service.get_task(self.task.task_id, viewer_id="child")
        self.assertEqual(task.status, "failed")
        self.assertEqual(task.result, "interrupted_delivery_unknown_manual_review")
        replay = run_due(
            self.service, member_ids=self.members,
            deliver=lambda task: self.fail("uncertain delivery must not auto-replay"),
            now=later,
        )
        self.assertEqual(replay["claimed"], 0)

    def test_private_task_is_only_dispatched_for_its_owner(self):
        delivered = []
        run_due(
            self.service, member_ids=["dad"],
            deliver=lambda task: delivered.append(task.task_id) or True,
            now=self.now,
        )
        self.assertEqual(delivered, [])



    def test_delivery_exception_is_recorded_as_failure(self):
        def explode(task):
            raise RuntimeError("simulated audio command failure")

        result = run_due(
            self.service, member_ids=self.members, deliver=explode, now=self.now,
        )
        self.assertEqual(result, {"claimed": 1, "succeeded": 0, "failed": 1})
        failed = self.service.get_task(self.task.task_id, viewer_id="child")
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.result, "delivery_command_failed")
        replay = run_due(
            self.service, member_ids=self.members,
            deliver=lambda task: self.fail("failed task must not replay automatically"),
            now=self.now,
        )
        self.assertEqual(replay["claimed"], 0)

    def test_claim_and_finish_are_owner_scoped_and_state_checked(self):
        self.assertIsNone(self.service.claim_due(
            self.task.task_id, owner_member_id="dad", now=self.now,
        ))
        with self.assertRaises(PermissionError):
            self.service.finish_delivery(
                self.task.task_id, owner_member_id="dad", success=True,
            )
        claimed = self.service.claim_due(
            self.task.task_id, owner_member_id="child", now=self.now,
        )
        self.assertIsNotNone(claimed)
        with self.assertRaises(ValueError):
            self.service.finish_delivery(
                self.task.task_id, owner_member_id="child", success=True,
            ) if self.service.get_task(self.task.task_id, viewer_id="child").status != "running" else None

    def test_running_state_survives_restart_and_is_recovered_without_replay(self):
        claimed = self.service.claim_due(
            self.task.task_id, owner_member_id="child", now=self.now,
        )
        self.assertIsNotNone(claimed)

        restarted = TaskService(
            home=Path(self.tmp.name), persist=True, members=self.members,
            clock=lambda: self.now + timedelta(minutes=20),
        )
        changed = restarted.recover_stale_running(
            now=self.now + timedelta(minutes=20),
        )
        self.assertEqual(changed, 1)
        recovered = restarted.get_task(self.task.task_id, viewer_id="child")
        self.assertEqual(recovered.status, "failed")
        self.assertEqual(recovered.result, "interrupted_delivery_unknown_manual_review")
        result = run_due(
            restarted, member_ids=self.members,
            deliver=lambda task: self.fail("recovered uncertain task must not replay"),
            now=self.now + timedelta(minutes=20),
        )
        self.assertEqual(result["claimed"], 0)


if __name__ == "__main__":
    unittest.main()
