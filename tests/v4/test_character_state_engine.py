"""Regression tests for the deterministic character-state layer."""
import unittest
from datetime import datetime

from behavior.character_state import VALID_STATES, CharacterStateResolver


class CharacterStateEngineTests(unittest.TestCase):
    def setUp(self):
        self.resolver = CharacterStateResolver()
        self.day = datetime(2026, 8, 29, 10, 0)

    def test_all_states_are_registered(self):
        expected = {
            "idle", "talk", "happy", "curious", "thinking", "caring",
            "encouraging", "walking", "running", "sitting", "lying", "sleepy",
            "sleeping", "welcome", "accompany", "wakeup", "night",
        }
        self.assertEqual(VALID_STATES, expected)

    def test_screen_event_does_not_force_speech(self):
        result = self.resolver.resolve({"event_type": "screen.started", "decision": "SILENT", "now": self.day})
        self.assertEqual(result.state, "idle")

    def test_negative_emotion_uses_caring(self):
        result = self.resolver.resolve({"event_type": "conversation.started", "active_conversation": True,
                                         "emotion": "sad", "now": self.day})
        self.assertEqual(result.state, "caring")

    def test_question_uses_curious(self):
        result = self.resolver.resolve({"event_type": "voice.detected", "active_conversation": True,
                                         "intent": "question", "now": self.day})
        self.assertEqual(result.state, "curious")

    def test_low_value_unknown_defaults_to_idle(self):
        result = self.resolver.resolve({"event_type": "unknown.event", "now": self.day})
        self.assertEqual(result.state, "idle")

    def test_quiet_hours_override_ordinary_activity(self):
        result = self.resolver.resolve({"event_type": "exercise.started", "now": datetime(2026, 8, 29, 23, 30)})
        self.assertEqual(result.state, "night")


if __name__ == "__main__":
    unittest.main()
