"""V5 companion brain behavior tests."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from core.brain.planner import CompanionPlanner


class TestCompanionPlanner(unittest.TestCase):
    def setUp(self):
        self.brain = CompanionPlanner()

    def test_user_turn_always_responds_even_at_night(self):
        plan = self.brain.plan(
            member_id="child_9",
            utterance="糖糖，你还在吗？",
            observation={"now": datetime(2026, 10, 15, 23, 30, tzinfo=timezone.utc)},
            proactive=False,
        )
        self.assertEqual(plan.decision, "RESPOND")
        self.assertEqual(plan.behavior, "conversation")

    def test_proactive_night_is_silent(self):
        plan = self.brain.plan(
            member_id="child_9",
            observation={"now": datetime(2026, 10, 15, 23, 30, tzinfo=timezone.utc), "scene": "home"},
            proactive=True,
        )
        self.assertEqual(plan.decision, "SILENT")
        self.assertEqual(plan.reason, "quiet_hours")

    def test_proactive_school_does_not_interrupt(self):
        plan = self.brain.plan(
            member_id="child_12",
            observation={"now": datetime(2026, 10, 15, 16, 0, tzinfo=timezone.utc), "at_school": True},
            proactive=True,
        )
        self.assertEqual(plan.decision, "WAIT")
        self.assertEqual(plan.reason, "do_not_interrupt")

    def test_home_has_welcome_behavior(self):
        plan = self.brain.plan(
            member_id="child_9",
            observation={"now": datetime(2026, 10, 15, 17, 0, tzinfo=timezone.utc), "scene": "home"},
            proactive=True,
        )
        self.assertEqual(plan.decision, "CONSIDER")
        self.assertEqual(plan.behavior, "welcome")
        self.assertEqual(plan.role, "play")


if __name__ == "__main__":
    unittest.main()
