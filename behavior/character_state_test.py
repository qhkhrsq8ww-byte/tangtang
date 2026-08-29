import unittest
from datetime import datetime

from behavior.character_state import CharacterStateResolver


class CharacterStateResolverTest(unittest.TestCase):
    def setUp(self):
        self.r = CharacterStateResolver()

    def test_arrival_is_welcome(self):
        self.assertEqual(self.r.resolve({"event_type": "home.arrived", "now": datetime(2026, 8, 29, 10)}).state, "welcome")

    def test_supportive_conversation_is_caring(self):
        result = self.r.resolve({"event_type": "conversation.started", "active_conversation": True,
                                 "emotion": "sad", "now": datetime(2026, 8, 29, 10)})
        self.assertEqual(result.state, "caring")

    def test_question_is_curious(self):
        result = self.r.resolve({"event_type": "conversation.started", "active_conversation": True,
                                 "intent": "question", "now": datetime(2026, 8, 29, 10)})
        self.assertEqual(result.state, "curious")

    def test_quiet_hours_are_night(self):
        result = self.r.resolve({"event_type": "screen.started", "now": datetime(2026, 8, 29, 23, 30)})
        self.assertEqual(result.state, "night")

    def test_silent_policy_is_idle(self):
        result = self.r.resolve({"event_type": "screen.started", "decision": "SILENT",
                                 "now": datetime(2026, 8, 29, 10)})
        self.assertEqual(result.state, "idle")

    def test_exercise_is_running(self):
        self.assertEqual(self.r.resolve({"event_type": "exercise.started", "now": datetime(2026, 8, 29, 10)}).state, "running")

    def test_unknown_defaults_to_idle(self):
        self.assertEqual(self.r.resolve({"event_type": "something.unknown", "now": datetime(2026, 8, 29, 10)}).state, "idle")


if __name__ == "__main__":
    unittest.main()
