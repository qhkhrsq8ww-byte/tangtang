"""Daily plan is local-first and stores only structured plans/coarse feedback."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.companion.daily_plan import DailyPlanService


class TestDailyPlan(unittest.TestCase):
    def test_plan_feedback_and_reflection_survive_restart(self):
        with tempfile.TemporaryDirectory() as td:
            svc = DailyPlanService(home=td, members={"dad": {}, "child": {}})
            item = svc.add(member_id="child", plan_date="2026-10-21", title="读英语 10 分钟",
                           category="habit", due_time="19:30")
            svc.feedback(item["plan_id"], member_id="child", result="completed", habit_label="joined")
            again = DailyPlanService(home=td, members={"dad": {}, "child": {}})
            data = again.reflection(member_id="child", plan_date="2026-10-21")
            self.assertEqual(data["summary"]["completed"], 1)
            self.assertEqual(data["habit_labels"], {"joined": 1})
            self.assertEqual(again.today(member_id="dad", plan_date="2026-10-21")["summary"]["total"], 0)

    def test_rejects_raw_dialogue_fields_and_unknown_labels(self):
        with tempfile.TemporaryDirectory() as td:
            svc = DailyPlanService(home=td, members={"child": {}})
            item = svc.add(member_id="child", plan_date="2026-10-21", title="整理书包")
            with self.assertRaises(ValueError):
                svc.feedback(item["plan_id"], member_id="child", result="completed",
                             habit_label="原始对话内容")
            svc.feedback(item["plan_id"], member_id="child", result="partial", habit_label="defer")
            raw = svc.path.read_text(encoding="utf-8")
            self.assertNotIn("transcript", raw.lower())
            self.assertNotIn("utterance", raw.lower())

    def test_timed_plan_links_to_task_service_and_completion_feedback_closes_it(self):
        with tempfile.TemporaryDirectory() as td:
            svc = DailyPlanService(home=td, members={"child": {}})
            item = svc.add(member_id="child", plan_date="2026-10-21",
                           title="整理书包", category="habit", due_time="19:30")
            self.assertIsNotNone(item["task_id"])
            task = svc.task_service.get_task(item["task_id"], viewer_id="child")
            self.assertEqual(task.status, "scheduled")
            self.assertEqual(task.visibility, "PRIVATE")
            svc.feedback(item["plan_id"], member_id="child", result="completed",
                         habit_label="joined")
            closed = svc.task_service.get_task(item["task_id"], viewer_id="child")
            self.assertEqual(closed.status, "done")

    def test_member_cannot_update_another_members_plan(self):
        with tempfile.TemporaryDirectory() as td:
            svc = DailyPlanService(home=td, members={"child1": {}, "child2": {}})
            item = svc.add(member_id="child1", plan_date="2026-10-21", title="读书")
            with self.assertRaises(PermissionError):
                svc.feedback(item["plan_id"], member_id="child2", result="completed")


if __name__ == "__main__":
    unittest.main()
