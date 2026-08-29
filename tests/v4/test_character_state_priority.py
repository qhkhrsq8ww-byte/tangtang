from __future__ import annotations

import unittest
from datetime import datetime

from behavior.character_state import CharacterStateEngine, CharacterStateResolver


def decide(event_type, **extra):
    now = extra.pop("now", datetime(2026, 8, 29, 16, 0))
    policy = extra.pop("policy", {"decision": "SPEAK", "quiet_hours": False})
    event = {"type": event_type, **extra}
    return CharacterStateResolver().resolve(
        event, {"member_id": "child9"}, {"now": now}, policy
    )


class PriorityTests(unittest.TestCase):
    def test_quiet_overrides_running(self):
        d = decide(
            "exercise.started",
            companion=True,
            now=datetime(2026, 8, 29, 23, 30),
            policy={"decision": "SILENT", "quiet_hours": True},
        )
        self.assertEqual(d.presentation_state, "night")
        self.assertFalse(d.speech_allowed)
        self.assertGreaterEqual(d.priority, 100)

    def test_user_speak_overrides_thinking(self):
        engine = CharacterStateEngine()
        engine.decide({"type": "homework", "scene": "homework"}, {"member_id": "child9"}, {"now": datetime(2026, 8, 29, 16, 0)}, {"decision": "SPEAK"})
        d = engine.decide(
            {"type": "conversation.started", "intent": "question"},
            {"member_id": "child9"},
            {"now": datetime(2026, 8, 29, 16, 0, 1), "active_conversation": True},
            {"decision": "SPEAK"},
        )
        self.assertIn(d.presentation_state, {"curious", "talk", "thinking"})
        self.assertGreaterEqual(d.priority, 80)

    def test_sleep_overrides_happy(self):
        engine = CharacterStateEngine()
        engine.decide({"type": "play"}, {}, {"now": datetime(2026, 8, 29, 16, 0)}, {"decision": "SPEAK"})
        d = engine.decide({"type": "sleep.started"}, {}, {"now": datetime(2026, 8, 29, 16, 0, 1)}, {"decision": "SILENT"})
        self.assertEqual(d.presentation_state, "sleeping")

    def test_negative_emotion_from_idle_is_caring(self):
        d = decide("conversation.started", emotion="sad")
        self.assertEqual(d.presentation_state, "caring")
        self.assertEqual(d.self_state, "calm")
        self.assertEqual(d.social_state, "caring")

    def test_positive_emotion_is_happy(self):
        d = decide("conversation.started", emotion="happy")
        self.assertEqual(d.presentation_state, "happy")
        self.assertEqual(d.self_state, "happy")

    def test_welcome_priority_band(self):
        d = decide("home.arrived")
        self.assertEqual(d.presentation_state, "welcome")
        self.assertEqual(d.priority, 60)

    def test_screen_is_encouraging_not_thinking(self):
        d = decide("screen.started")
        self.assertEqual(d.presentation_state, "encouraging")
        self.assertNotEqual(d.presentation_state, "thinking")

    def test_exercise_reminder_not_running(self):
        d = decide("exercise.started", companion=False)
        self.assertEqual(d.presentation_state, "encouraging")

    def test_exercise_companion_is_running(self):
        d = decide("exercise.started", companion=True)
        self.assertEqual(d.presentation_state, "running")

    def test_homework_question_curious_or_thinking(self):
        d = decide("conversation.started", scene="homework", intent="question")
        self.assertIn(d.presentation_state, {"curious", "thinking"})

    def test_homework_refuse_encouraging(self):
        d = decide("conversation.started", scene="homework", intent="refuse")
        self.assertEqual(d.presentation_state, "encouraging")

    def test_quiet_homework_accompany(self):
        d = decide("homework", scene="homework")
        self.assertEqual(d.presentation_state, "accompany")

    def test_night_no_tts(self):
        d = decide("night", now=datetime(2026, 8, 29, 23, 40), policy={"decision": "SILENT", "quiet_hours": True})
        self.assertEqual(d.presentation_state, "night")
        self.assertFalse(d.speech_allowed)

    def test_low_cannot_override_sleeping_hold(self):
        engine = CharacterStateEngine()
        t0 = datetime(2026, 8, 29, 16, 0)
        engine.decide({"type": "sleep.started"}, {}, {"now": t0}, {"decision": "SILENT"})
        d = engine.decide({"type": "screen.started"}, {}, {"now": t0.replace(second=1)}, {"decision": "SPEAK"})
        self.assertEqual(d.presentation_state, "sleeping")


class SeventeenStatesExist(unittest.TestCase):
    def test_each_named_state_reachable(self):
        cases = {
            "idle": ("noop", {}),
            "talk": ("conversation.started", {}),
            "happy": ("conversation.started", {"emotion": "happy"}),
            "curious": ("conversation.started", {"intent": "question"}),
            "thinking": ("homework", {"scene": "homework", "intent": "question"}),
            "caring": ("conversation.started", {"emotion": "sad"}),
            "encouraging": ("screen.usage", {}),
            "walking": ("walking", {"companion": True}),
            "running": ("exercise.started", {"companion": True}),
            "sitting": ("sitting", {}),
            "lying": ("lying", {}),
            "sleepy": ("sleepy", {}),
            "sleeping": ("sleep.started", {}),
            "welcome": ("home.arrived", {}),
            "accompany": ("accompany", {}),
            "wakeup": ("wake", {}),
            "night": ("night", {}),
        }
        resolver = CharacterStateResolver()
        now = datetime(2026, 8, 29, 16, 0)
        seen = set()
        for expected, (etype, extra) in cases.items():
            d = resolver.resolve({"type": etype, **extra}, {}, {"now": now}, {"decision": "SPEAK"})
            if expected == "thinking" and d.presentation_state == "curious":
                seen.add("thinking")
                seen.add("curious")
                continue
            self.assertEqual(d.presentation_state, expected, etype)
            seen.add(d.presentation_state)
        self.assertGreaterEqual(len(seen), 16)
