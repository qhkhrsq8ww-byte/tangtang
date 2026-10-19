"""Regression tests for the local proactive companion planner."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from core.brain.planner import CompanionPlanner
from core.runtime.loop import TangTangRuntime


class TestCompanionPlanner(unittest.TestCase):
    def setUp(self):
        self.brain = CompanionPlanner()

    def test_user_initiated_turn_is_not_suppressed_by_quiet_hours(self):
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

    def test_explicit_request_for_quiet_suppresses_only_proactive_scenes(self):
        brain = CompanionPlanner()
        now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        response = brain.plan(
            member_id="child_9",
            utterance="糖糖，今天别叫我。",
            observation={"now": now},
            proactive=False,
        )
        self.assertEqual(response.decision, "RESPOND")
        self.assertEqual(response.reason, "user_requested_quiet")

        proactive = brain.plan(
            member_id="child_9",
            observation={"now": now.replace(hour=13), "scene": "home"},
            proactive=True,
        )
        self.assertEqual(proactive.decision, "WAIT")
        self.assertEqual(proactive.reason, "user_requested_quiet")

    def test_user_quiet_request_expires_after_four_hours(self):
        brain = CompanionPlanner()
        now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        brain.plan(
            member_id="child_12",
            utterance="我想安静一下",
            observation={"now": now},
            proactive=False,
        )
        after = brain.plan(
            member_id="child_12",
            observation={"now": now.replace(hour=17), "scene": "home"},
            proactive=True,
        )
        self.assertEqual(after.decision, "CONSIDER")
        self.assertEqual(after.behavior, "welcome")

    def test_same_scene_uses_cooldown(self):
        brain = CompanionPlanner(min_proactive_gap_minutes=20)
        now = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)
        first = brain.plan(member_id="child_9", observation={"now": now, "scene": "home"}, proactive=True)
        second = brain.plan(member_id="child_9", observation={"now": now.replace(minute=10), "scene": "home"}, proactive=True)
        self.assertEqual(first.decision, "CONSIDER")
        self.assertEqual(second.decision, "WAIT")
        self.assertEqual(second.reason, "proactive_cooldown")


class TestCompanionPlannerRuntime(unittest.TestCase):
    def test_runtime_records_quiet_request_without_blocking_current_turn(self):
        runtime = TangTangRuntime(offline=True)
        now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        result = runtime.handle_utterance(
            "糖糖，今天别叫我。",
            {"label": "child_9", "now": now},
        )
        self.assertEqual(result.observation["companion_plan"]["reason"], "user_requested_quiet")
        self.assertNotEqual(result.decision, "SILENT")

    def test_runtime_records_quiet_hour_plan_and_suppresses_proactive_speech(self):
        runtime = TangTangRuntime(offline=True)
        result = runtime.handle_living_room(
            "home",
            member_id="child_9",
            observation={"now": datetime(2026, 10, 15, 23, 30, tzinfo=timezone.utc)},
        )
        self.assertEqual(result.observation["companion_plan"]["reason"], "quiet_hours")
        self.assertEqual(result.decision, "SILENT")


if __name__ == "__main__":
    unittest.main()
