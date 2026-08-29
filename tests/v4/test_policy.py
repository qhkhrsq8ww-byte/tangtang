"""InterruptPolicy: deterministic, no LLM, school hours + quiet hours."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.compat import should_interrupt
from core.interfaces import PolicyPort
from core.policy.interrupt_policy import InterruptPolicy


def _dt(hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 8, 28, int(h), int(m), tzinfo=timezone.utc)


class TestPolicyHappy(unittest.TestCase):
    def setUp(self):
        self.p = InterruptPolicy(clock=lambda: _dt("12:00"))
        self.assertIsInstance(self.p, PolicyPort)

    def test_daytime_speak(self):
        self.assertEqual(self.p.decide({}, now=_dt("12:00")), "SPEAK")
        self.assertFalse(self.p.should_interrupt({}, now=_dt("12:00")))

    def test_emergency_overrides_quiet(self):
        self.assertEqual(
            self.p.decide({"emergency": True}, now=_dt("23:00")),
            "SPEAK",
        )


class TestPolicyQuietAndSchool(unittest.TestCase):
    def setUp(self):
        self.p = InterruptPolicy()

    def test_quiet_hours_silent(self):
        self.assertEqual(self.p.decide({}, now=_dt("22:30")), "SILENT")
        self.assertEqual(self.p.decide({}, now=_dt("06:59")), "SILENT")
        self.assertEqual(self.p.decide({}, now=_dt("07:00")), "SPEAK")

    def test_interactive_bypasses_quiet(self):
        self.assertEqual(
            self.p.decide({"interactive": True}, now=_dt("23:00")),
            "SPEAK",
        )

    def test_school_hours_child_not_home(self):
        self.assertEqual(
            self.p.decide({
                "school_hours": True,
                "audience_child": True,
                "presence_home": False,
            }, now=_dt("12:00")),
            "SILENT",
        )

    def test_active_conversation_silent(self):
        self.assertEqual(
            self.p.decide({"active_conversation": True}, now=_dt("12:00")),
            "SILENT",
        )

    def test_recently_interrupted_delay(self):
        self.assertEqual(
            self.p.decide({"recently_interrupted": True}, now=_dt("12:00")),
            "DELAY",
        )

    def test_low_importance_log_only(self):
        self.assertEqual(
            self.p.decide({"importance": "low"}, now=_dt("12:00")),
            "LOG_ONLY",
        )


class TestPolicyEmptyUnknown(unittest.TestCase):
    def test_empty_observation_daytime(self):
        p = InterruptPolicy(clock=lambda: _dt("15:00"))
        self.assertEqual(p.decide(None), "SPEAK")
        self.assertEqual(p.decide({}), "SPEAK")

    def test_unknown_flags_ignored(self):
        p = InterruptPolicy(clock=lambda: _dt("15:00"))
        self.assertEqual(p.decide({"weird_flag": "???"}), "SPEAK")


class TestPolicyNoLLMAndCompat(unittest.TestCase):
    def test_source_has_no_llm(self):
        from core.policy import interrupt_policy as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        for needle in (
            "import openai",
            "from openai",
            "chat.completions",
            "import requests",
            "from requests",
            "urllib.request",
            "http.client",
        ):
            self.assertNotIn(needle, src)

    def test_compat_should_interrupt(self):
        self.assertTrue(should_interrupt({}, now=_dt("23:00")))
        self.assertFalse(should_interrupt({"emergency": True}, now=_dt("23:00")))


if __name__ == "__main__":
    unittest.main()
