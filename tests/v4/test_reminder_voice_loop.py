"""Voice reminder loop tests: clarify missing time, schedule, and time-only follow-up."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.chat_adapter import ChatAdapter
from core.adapters.family_loader import load_members
from core.ingest import PrivacyPipeline
from core.tasks.reminders import parse_reminder_intent
from core.tasks.service import TaskService

MEMBERS = load_members()


class TestReminderIntent(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 15, 7, 0, tzinfo=timezone.utc)

    def test_clear_chinese_time_is_parsed(self):
        intent = parse_reminder_intent(
            "糖糖，明天晚上八点提醒我带水杯",
            now=self.now,
            timezone_name="UTC",
        )
        self.assertEqual(intent.action, "schedule")
        self.assertEqual(intent.title, "带水杯")
        self.assertEqual(intent.due_at, "2026-10-16T20:00:00+00:00")

    def test_missing_time_requires_followup(self):
        intent = parse_reminder_intent("提醒我带水杯", now=self.now, timezone_name="UTC")
        self.assertEqual(intent.action, "needs_time")
        self.assertEqual(intent.title, "带水杯")
        self.assertIsNone(intent.due_at)

    def test_time_only_followup_parses_due_time(self):
        intent = parse_reminder_intent("明天晚上八点", now=self.now, timezone_name="UTC")
        self.assertEqual(intent.action, "time_reply")
        self.assertEqual(intent.due_at, "2026-10-16T20:00:00+00:00")

    def test_hour_without_period_is_not_silently_scheduled(self):
        intent = parse_reminder_intent(
            "明天八点提醒我带水杯", now=self.now, timezone_name="UTC"
        )
        self.assertEqual(intent.action, "needs_period")
        self.assertEqual(intent.title, "带水杯")
        self.assertIsNone(intent.due_at)

    def test_explicit_period_still_schedules(self):
        intent = parse_reminder_intent(
            "明天早上八点提醒我带水杯", now=self.now, timezone_name="UTC"
        )
        self.assertEqual(intent.action, "schedule")
        self.assertEqual(intent.due_at, "2026-10-16T08:00:00+00:00")

    def test_list_cancel_and_reschedule_commands_parse(self):
        self.assertEqual(parse_reminder_intent("查看提醒").action, "list")
        cancelled = parse_reminder_intent("取消提醒：带水杯")
        self.assertEqual((cancelled.action, cancelled.title), ("cancel", "带水杯"))
        changed = parse_reminder_intent(
            "把带水杯提醒改到明天晚上八点", now=self.now, timezone_name="UTC"
        )
        self.assertEqual(changed.action, "reschedule")
        self.assertEqual(changed.title, "带水杯")
        self.assertEqual(changed.due_at, "2026-10-16T20:00:00+00:00")


class TestReminderChatLoop(unittest.TestCase):
    def make_chat(self):
        members = MEMBERS
        tasks = TaskService(members=members)
        chat = ChatAdapter(
            pipeline=PrivacyPipeline(members=members),
            members=members,
            tasks=tasks,
            llm=lambda _payload: self.fail("reminder commands must stay local"),
        )
        return tasks, chat

    def test_reminder_without_time_then_time_followup_schedules(self):
        tasks, chat = self.make_chat()
        draft = chat.turn(
            "提醒我带水杯",
            {"label": "hanghang", "interactive": True, "now": datetime(2026, 10, 15, 7, 0, tzinfo=timezone.utc), "timezone": "UTC"},
        )
        self.assertEqual(draft.action.action, "reminder_needs_time")
        self.assertIn("还没设置成功", draft.action.text)
        pending = tasks.list_tasks(viewer_id="hanghang", statuses={"needs_confirmation"}, include_family=False)
        self.assertEqual(len(pending), 1)
        self.assertIsNone(pending[0].due_at)

        scheduled = chat.turn(
            "明天晚上八点",
            {"label": "hanghang", "interactive": True, "now": datetime(2026, 10, 15, 7, 0, tzinfo=timezone.utc), "timezone": "UTC"},
        )
        self.assertEqual(scheduled.action.action, "reminder_schedule")
        self.assertIn("已经设置提醒", scheduled.action.text)
        rows = tasks.list_tasks(viewer_id="hanghang", statuses={"scheduled"}, include_family=False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "带水杯")
        self.assertEqual(rows[0].due_at, "2026-10-16T20:00:00+00:00")

    def test_clear_time_is_scheduled_without_cloud_llm(self):
        tasks, chat = self.make_chat()
        result = chat.turn(
            "明天晚上八点提醒我带水杯",
            {"label": "hanghang", "interactive": True, "now": datetime(2026, 10, 15, 7, 0, tzinfo=timezone.utc), "timezone": "UTC"},
        )
        self.assertEqual(result.action.action, "reminder_schedule")
        rows = tasks.list_tasks(viewer_id="hanghang", statuses={"scheduled"}, include_family=False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "带水杯")

    def test_reminder_can_be_queried_rescheduled_and_cancelled(self):
        tasks, chat = self.make_chat()
        obs = {"label": "hanghang", "interactive": True, "now": datetime(2026, 10, 15, 7, 0, tzinfo=timezone.utc), "timezone": "UTC"}
        chat.turn("明天晚上八点提醒我带水杯", obs)
        self.assertEqual(chat.turn("查看提醒", obs).action.action, "reminder_list")
        changed = chat.turn("把带水杯提醒改到后天晚上九点", obs)
        self.assertEqual(changed.action.action, "reminder_reschedule")
        row = tasks.list_tasks(viewer_id="hanghang", statuses={"scheduled"}, include_family=False)[0]
        self.assertEqual(row.due_at, "2026-10-17T21:00:00+00:00")
        cancelled = chat.turn("取消提醒：带水杯", obs)
        self.assertEqual(cancelled.action.action, "reminder_cancel")
        self.assertEqual(tasks.list_tasks(viewer_id="hanghang", statuses={"cancelled"}, include_family=False)[0].title, "带水杯")


if __name__ == "__main__":
    unittest.main()
