"""Proactive speech should respect quiet hours, habit feedback, and cooldowns."""
from __future__ import annotations
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.companion.proactive import ProactiveGate, in_quiet_hours
from core.security.contexts import ActorContext, AudienceContext


class TestProactiveGate(unittest.TestCase):
    def test_quiet_hours_cross_midnight(self):
        self.assertTrue(in_quiet_hours(datetime.fromisoformat("2026-10-21T23:00:00"), "22:30", "07:00"))
        self.assertTrue(in_quiet_hours(datetime.fromisoformat("2026-10-21T06:30:00"), "22:30", "07:00"))
        self.assertFalse(in_quiet_hours(datetime.fromisoformat("2026-10-21T08:00:00"), "22:30", "07:00"))

    def test_same_scene_is_cooled_down_but_other_scene_is_not(self):
        with tempfile.TemporaryDirectory() as td:
            gate = ProactiveGate(home=td, cooldown_minutes=45)
            first = datetime.fromisoformat("2026-10-21T10:00:00+08:00")
            self.assertEqual(gate.check(event="water", audience_id="child", now=first), (True, "ok"))
            gate.record(event="water", member_id="child", now=first)
            self.assertEqual(gate.check(event="water", member_id="child",
                                        now=datetime.fromisoformat("2026-10-21T10:30:00+08:00")),
                             (False, "scene_cooldown"))
            self.assertTrue(gate.check(event="meal", member_id="child",
                                       now=datetime.fromisoformat("2026-10-21T10:30:00+08:00"))[0])

    def test_habit_feedback_can_suppress_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            gate = ProactiveGate(home=td)
            ok, reason = gate.check(event="english", member_id="child",
                                    now=datetime.fromisoformat("2026-10-21T10:00:00+08:00"),
                                    habit_allows=False)
            self.assertFalse(ok)
            self.assertEqual(reason, "habit_cooldown")


if __name__ == "__main__":
    unittest.main()

    def test_record_persists_system_actor_and_separate_audience(self):
        with tempfile.TemporaryDirectory() as td:
            gate = ProactiveGate(home=td)
            gate.record(
                event="meal",
                audience=AudienceContext("child", "proactive_scene"),
                actor=ActorContext(None, "system", "system", frozenset({"proactive:record"})),
                now=datetime.fromisoformat("2026-10-21T10:00:00+08:00"),
            )
            import json
            saved = json.loads(gate.path.read_text(encoding="utf-8"))
            row = saved["child:meal"]
            self.assertEqual(row["actor_kind"], "system")
            self.assertIsNone(row["actor_id"])
            self.assertEqual(row["audience_id"], "child")

    def test_member_actor_cannot_write_system_proactive_record(self):
        with tempfile.TemporaryDirectory() as td:
            gate = ProactiveGate(home=td)
            with self.assertRaises(PermissionError):
                gate.record(
                    event="meal",
                    audience=AudienceContext("child", "proactive_scene"),
                    actor=ActorContext("child", "member", "verified"),
                    now=datetime.fromisoformat("2026-10-21T10:00:00+08:00"),
                )
