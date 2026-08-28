"""Proactive scenes: phone/sitting/no_meal/late_sleep/home/away — not speak-every-event."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.policy.interrupt_policy import InterruptPolicy, infer_scene


def _dt(hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 8, 28, int(h), int(m), tzinfo=timezone.utc)


class TestProactiveScenes(unittest.TestCase):
    def setUp(self):
        self.p = InterruptPolicy(clock=lambda: _dt("16:00"))

    def test_phone_speaks_once_then_logs(self):
        first = self.p.decide({"scene": "phone", "member_id": "child_9", "phone_minutes": 43}, now=_dt("16:00"))
        second = self.p.decide({"scene": "phone", "member_id": "child_9", "phone_minutes": 44}, now=_dt("16:01"))
        third = self.p.decide({"scene": "phone", "member_id": "child_9", "phone_minutes": 45}, now=_dt("16:02"))
        self.assertEqual(first, "SPEAK")
        self.assertEqual(second, "LOG_ONLY")
        self.assertEqual(third, "LOG_ONLY")
        self.assertNotEqual(first, second)

    def test_sitting_not_every_tick(self):
        a = self.p.decide({"scene": "sitting", "member_id": "dad"}, now=_dt("16:00"))
        b = self.p.decide({"scene": "sitting", "member_id": "dad"}, now=_dt("16:00"))
        self.assertEqual(a, "SPEAK")
        self.assertEqual(b, "LOG_ONLY")

    def test_no_meal_then_delay(self):
        a = self.p.decide({"scene": "no_meal", "member_id": "child_12"}, now=_dt("12:30"))
        b = self.p.decide({"scene": "no_meal", "member_id": "child_12"}, now=_dt("12:35"))
        self.assertEqual(a, "SPEAK")
        self.assertEqual(b, "DELAY")

    def test_late_sleep_then_silent(self):
        a = self.p.decide({"scene": "late_sleep", "member_id": "child_9"}, now=_dt("21:40"))
        b = self.p.decide({"scene": "late_sleep", "member_id": "child_9"}, now=_dt("21:50"))
        self.assertEqual(a, "SPEAK")
        self.assertEqual(b, "SILENT")

    def test_home_greet_once(self):
        a = self.p.decide({"scene": "home", "member_id": "mom", "just_arrived": True}, now=_dt("18:10"))
        b = self.p.decide({"scene": "home", "member_id": "mom"}, now=_dt("18:11"))
        self.assertEqual(a, "SPEAK")
        self.assertEqual(b, "LOG_ONLY")

    def test_away_always_silent(self):
        for _ in range(3):
            self.assertEqual(
                self.p.decide({"scene": "away", "presence_home": False}, now=_dt("16:00")),
                "SILENT",
            )

    def test_empty_room_inferred_away(self):
        self.assertEqual(infer_scene({"presence_home": False}), "away")
        self.assertEqual(
            self.p.decide({"presence_home": False}, now=_dt("16:00")),
            "SILENT",
        )

    def test_interactive_overrides_away_inference(self):
        # Phone call from outside: user is talking to 糖糖.
        self.assertEqual(
            self.p.decide({"presence_home": False, "interactive": True}, now=_dt("16:00")),
            "SPEAK",
        )


class TestProactiveEmptyUnknown(unittest.TestCase):
    def test_unknown_scene_ignored(self):
        p = InterruptPolicy(clock=lambda: _dt("15:00"))
        self.assertEqual(p.decide({"scene": "unicorn"}), "SPEAK")

    def test_empty_still_daytime_speak(self):
        p = InterruptPolicy(clock=lambda: _dt("15:00"))
        self.assertEqual(p.decide({}), "SPEAK")

    def test_cooldown_expires(self):
        p = InterruptPolicy(clock=lambda: _dt("16:00"), cooldown=timedelta(minutes=1))
        self.assertEqual(p.decide({"scene": "phone", "member_id": "dad"}, now=_dt("16:00")), "SPEAK")
        self.assertEqual(p.decide({"scene": "phone", "member_id": "dad"}, now=_dt("16:00")), "LOG_ONLY")
        self.assertEqual(p.decide({"scene": "phone", "member_id": "dad"}, now=_dt("16:02")), "SPEAK")


if __name__ == "__main__":
    unittest.main()
