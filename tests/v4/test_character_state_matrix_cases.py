"""One assertion per event/context/policy cell — real resolver, no video mocks."""
from __future__ import annotations

import unittest
from datetime import datetime

from behavior.character_state import CharacterStateResolver

NOW = datetime(2026, 8, 29, 16, 0)
NIGHT = datetime(2026, 8, 29, 23, 30)


def R(event, ctx=None, policy=None, now=NOW):
    return CharacterStateResolver().resolve(
        event,
        {"member_id": "child9"},
        {"now": now, **(ctx or {})},
        policy or {"decision": "SPEAK", "quiet_hours": False},
    )


class MatrixCases(unittest.TestCase):
    def _eq(self, event, state, **kwargs):
        d = R(event, kwargs.get("ctx"), kwargs.get("policy"), kwargs.get("now", NOW))
        self.assertEqual(d.presentation_state, state, event)

    def test_home(self):
        self._eq({"type": "home.arrived"}, "welcome")

    def test_home_alias(self):
        self._eq({"type": "home"}, "welcome")

    def test_family_arrived(self):
        self._eq({"type": "family.arrived"}, "welcome")

    def test_sad(self):
        self._eq({"type": "conversation.started", "emotion": "sad"}, "caring")

    def test_low(self):
        self._eq({"type": "conversation.started", "emotion": "low"}, "caring")

    def test_upset(self):
        self._eq({"type": "conversation.started", "emotion": "upset"}, "caring")

    def test_happy_talk(self):
        self._eq({"type": "conversation.started", "emotion": "happy"}, "happy")

    def test_proud(self):
        self._eq({"type": "conversation.started", "emotion": "proud"}, "happy")

    def test_question(self):
        self._eq({"type": "conversation.started", "intent": "question"}, "curious")

    def test_ask(self):
        self._eq({"type": "conversation.started", "intent": "ask"}, "curious")

    def test_neutral_talk(self):
        self._eq({"type": "conversation.started"}, "talk")

    def test_user_speaking(self):
        self._eq({"type": "user.speaking"}, "talk")

    def test_say(self):
        self._eq({"type": "say"}, "talk")

    def test_screen_started(self):
        self._eq({"type": "screen.started"}, "encouraging")

    def test_screen_usage(self):
        self._eq({"type": "screen.usage"}, "encouraging")

    def test_phone(self):
        self._eq({"type": "phone.usage"}, "encouraging")

    def test_exercise_alone(self):
        self._eq({"type": "exercise"}, "encouraging")

    def test_exercise_companion(self):
        self._eq({"type": "exercise.started", "companion": True}, "running")

    def test_walk_companion(self):
        self._eq({"type": "walking", "companion": True}, "walking")

    def test_sleep(self):
        self._eq({"type": "sleep.started"}, "sleeping")

    def test_bedtime(self):
        self._eq({"type": "bedtime"}, "sleeping")

    def test_night_event(self):
        self._eq({"type": "night"}, "night")

    def test_wake(self):
        self._eq({"type": "wake"}, "wakeup")

    def test_pat(self):
        self._eq({"type": "pat"}, "happy")

    def test_meal(self):
        self._eq({"type": "meal"}, "happy")

    def test_water(self):
        self._eq({"type": "water"}, "caring")

    def test_sit(self):
        self._eq({"type": "sitting"}, "sitting")

    def test_lie(self):
        self._eq({"type": "lying"}, "lying")

    def test_accompany(self):
        self._eq({"type": "accompany"}, "accompany")

    def test_sleepy(self):
        self._eq({"type": "sleepy"}, "sleepy")

    def test_homework_quiet(self):
        self._eq({"type": "homework", "scene": "homework"}, "accompany")

    def test_homework_q(self):
        self._eq({"type": "homework", "scene": "homework", "intent": "question"}, "thinking")

    def test_homework_no(self):
        self._eq({"type": "homework", "scene": "homework", "intent": "refuse"}, "encouraging")

    def test_silent_idle(self):
        d = R({"type": "random"}, policy={"decision": "SILENT", "quiet_hours": False})
        self.assertEqual(d.presentation_state, "idle")
        self.assertFalse(d.speech_allowed)

    def test_night_screen(self):
        d = R(
            {"type": "screen.started"},
            policy={"decision": "SILENT", "quiet_hours": True},
            now=NIGHT,
        )
        self.assertEqual(d.presentation_state, "night")
        self.assertFalse(d.speech_allowed)

    def test_night_exercise(self):
        d = R(
            {"type": "exercise.started", "companion": True},
            policy={"decision": "SILENT", "quiet_hours": True},
            now=NIGHT,
        )
        self.assertEqual(d.presentation_state, "night")
