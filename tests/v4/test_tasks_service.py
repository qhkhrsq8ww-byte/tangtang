"""Local task service: durable, idempotent, permission-aware lifecycle."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.family_loader import load_members
from core.tasks.service import TaskService

MEMBERS = load_members()
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


class FrozenClock:
    def __init__(self, when=NOW):
        self.when = when

    def __call__(self):
        return self.when


class TestTaskPersistence(unittest.TestCase):
    def test_task_survives_service_restart_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            first = TaskService(home=td, persist=True, members=MEMBERS, clock=FrozenClock())
            task = first.create_task(
                owner_member_id="dad",
                title="准备明天的材料",
                due_at="2026-10-15T09:00:00+08:00",
                timezone_name="Asia/Shanghai",
                kind="reminder",
                idempotency_key="tomorrow-materials",
                source_event_id="evt_abc",
            )
            duplicate = first.create_task(
                owner_member_id="dad",
                title="should not create a second task",
                due_at="2026-10-15T10:00:00+08:00",
                idempotency_key="tomorrow-materials",
            )
            self.assertEqual(task.task_id, duplicate.task_id)
            self.assertEqual(len(first.list_tasks(viewer_id="dad")), 1)

            second = TaskService(home=td, persist=True, members=MEMBERS, clock=FrozenClock())
            restored = second.get_task(task.task_id, viewer_id="dad")
            self.assertIsNotNone(restored)
            self.assertEqual(restored.title, "准备明天的材料")
            self.assertEqual(restored.timezone, "Asia/Shanghai")
            self.assertEqual(len(second.list_tasks(viewer_id="dad")), 1)

    def test_due_filter_uses_timezone_aware_instants(self):
        service = TaskService(members=MEMBERS, clock=FrozenClock())
        due = service.create_task(
            owner_member_id="dad",
            title="到期提醒",
            due_at="2026-10-14T19:00:00+08:00",
            timezone_name="Asia/Shanghai",
        )
        before = service.due_tasks(now=datetime(2026, 10, 14, 10, 59, tzinfo=timezone.utc), viewer_id="dad")
        after = service.due_tasks(now=datetime(2026, 10, 14, 11, 0, tzinfo=timezone.utc), viewer_id="dad")
        self.assertEqual(before, [])
        self.assertEqual([item.task_id for item in after], [due.task_id])

    def test_private_tasks_are_owner_only_and_family_tasks_need_registered_viewer(self):
        service = TaskService(members=MEMBERS)
        private = service.create_task(owner_member_id="dad", title="私人事项")
        family = service.create_task(owner_member_id="dad", title="家庭采购", visibility="FAMILY")
        self.assertIsNone(service.get_task(private.task_id, viewer_id="mom"))
        self.assertIsNotNone(service.get_task(family.task_id, viewer_id="mom"))
        self.assertIsNone(service.get_task(family.task_id, viewer_id="stranger"))
        self.assertEqual([t.task_id for t in service.list_tasks(viewer_id="mom")], [family.task_id])

    def test_lifecycle_complete_cancel_reschedule(self):
        service = TaskService(members=MEMBERS, clock=FrozenClock())
        task = service.create_task(owner_member_id="dad", title="待定事项")
        scheduled = service.reschedule(
            task.task_id, owner_member_id="dad", due_at="2026-10-15T09:00:00+08:00"
        )
        self.assertEqual(scheduled.status, "scheduled")
        done = service.complete(task.task_id, owner_member_id="dad", result="completed")
        self.assertEqual(done.status, "done")
        self.assertEqual(service.complete(task.task_id, owner_member_id="dad").status, "done")
        with self.assertRaises(ValueError):
            service.cancel(task.task_id, owner_member_id="dad")

        other = service.create_task(owner_member_id="dad", title="另一个事项")
        cancelled = service.cancel(other.task_id, owner_member_id="dad")
        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(service.cancel(other.task_id, owner_member_id="dad").status, "cancelled")

    def test_rejects_ambiguous_due_times_and_raw_payload_fields(self):
        service = TaskService(members=MEMBERS)
        with self.assertRaises(ValueError):
            service.create_task(owner_member_id="dad", title="时间不完整", due_at="2026-10-15T09:00:00")
        with self.assertRaises(ValueError):
            service.create_task(
                owner_member_id="dad",
                title="不要存原话",
                metadata={"transcript": "sensitive raw transcript"},
            )
        with self.assertRaises(ValueError):
            service.create_task(owner_member_id="unknown", title="invalid owner")

    def test_persisted_tasks_do_not_contain_utterance_fields(self):
        with tempfile.TemporaryDirectory() as td:
            service = TaskService(home=td, persist=True, members=MEMBERS, clock=FrozenClock())
            service.create_task(owner_member_id="dad", title="带材料", metadata={"category": "family"})
            path = Path(td) / "tasks" / "tasks.json"
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn('"transcript"', raw)
            parsed = json.loads(raw)
            self.assertEqual(parsed["version"], 1)
            self.assertEqual(len(parsed["tasks"]), 1)


if __name__ == "__main__":
    unittest.main()
