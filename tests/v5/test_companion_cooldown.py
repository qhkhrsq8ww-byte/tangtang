"""Additional V5 tests for companion anti-chatter behavior."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from core.brain.planner import CompanionPlanner


class TestCompanionCooldown(unittest.TestCase):
    def test_same_scene_is_suppressed_inside_cooldown(self):
        brain = CompanionPlanner(min_proactive_gap_minutes=20)
        t0 = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)
        first = brain.plan(member_id="child_9", observation={"now": t0, "scene": "home"}, proactive=True)
        second = brain.plan(member_id="child_9", observation={"now": t0.replace(minute=10), "scene": "home"}, proactive=True)
        self.assertEqual(first.decision, "CONSIDER")
        self.assertEqual(second.decision, "WAIT")
        self.assertEqual(second.reason, "proactive_cooldown")

    def test_same_scene_can_resume_after_cooldown(self):
        brain = CompanionPlanner(min_proactive_gap_minutes=20)
        t0 = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)
        brain.plan(member_id="child_9", observation={"now": t0, "scene": "home"}, proactive=True)
        again = brain.plan(member_id="child_9", observation={"now": t0.replace(minute=21), "scene": "home"}, proactive=True)
        self.assertEqual(again.decision, "CONSIDER")

if __name__ == "__main__":
    unittest.main()
