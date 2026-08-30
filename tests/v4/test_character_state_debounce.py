from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from behavior.character_state import CharacterStateEngine


class DebounceTests(unittest.TestCase):
    def test_repeated_screen_does_not_jitter(self):
        engine = CharacterStateEngine()
        t0 = datetime(2026, 8, 29, 16, 0, 0)
        states = []
        for i in range(4):
            d = engine.decide(
                {"type": "screen.started"},
                {"member_id": "child9"},
                {"now": t0 + timedelta(seconds=i * 2)},
                {"decision": "SPEAK"},
            )
            states.append(d.presentation_state)
        self.assertEqual(set(states), {"encouraging"})
        self.assertNotIn("idle", states)
        self.assertNotIn("thinking", states)

    def test_min_duration_two_seconds(self):
        engine = CharacterStateEngine()
        t0 = datetime(2026, 8, 29, 16, 0, 0)
        engine.decide({"type": "welcome", "type": "home.arrived"}, {}, {"now": t0}, {"decision": "SPEAK"})
        d = engine.decide({"type": "idle"}, {}, {"now": t0 + timedelta(seconds=1)}, {"decision": "SPEAK"})
        self.assertEqual(d.presentation_state, "welcome")
        self.assertEqual(d.reason, "debounce hold")

    def test_higher_priority_breaks_hold(self):
        engine = CharacterStateEngine()
        t0 = datetime(2026, 8, 29, 16, 0, 0)
        engine.decide({"type": "screen.started"}, {}, {"now": t0}, {"decision": "SPEAK"})
        d = engine.decide({"type": "sleep.started"}, {}, {"now": t0 + timedelta(seconds=1)}, {"decision": "SILENT"})
        self.assertEqual(d.presentation_state, "sleeping")

    def test_after_min_duration_can_change(self):
        engine = CharacterStateEngine()
        t0 = datetime(2026, 8, 29, 16, 0, 0)
        engine.decide({"type": "home.arrived"}, {}, {"now": t0}, {"decision": "SPEAK"})
        d = engine.decide({"type": "accompany"}, {}, {"now": t0 + timedelta(seconds=5)}, {"decision": "SPEAK"})
        self.assertEqual(d.presentation_state, "accompany")
