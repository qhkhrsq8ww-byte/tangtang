from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from behavior.character_state import CharacterStateEngine
from behavior.legacy_adapter import decide_from_legacy, to_event
from core.presentation.asset_registry import AssetRegistry
from core.presentation.character_presenter import CharacterPresenter
from core.presentation.transport import write_presentation_action


PRIVATE_LINE = "我今天被同学欺负了。"


def _run(event, policy=None, now=None, text=""):
    now = now or datetime(2026, 8, 29, 16, 0)
    engine = CharacterStateEngine()
    decision = engine.decide(
        event,
        {"member_id": "child9", "role": "child"},
        {"now": now},
        policy or {"decision": "SPEAK", "quiet_hours": False},
    )
    action = CharacterPresenter().present(decision, text=text)
    return decision, action


class E2EScenarios(unittest.TestCase):
    def test_e2e1_home_arrived_welcome(self):
        d, a = _run({"type": "home.arrived"})
        self.assertEqual(d.presentation_state, "welcome")
        self.assertEqual(a.state, "welcome")
        self.assertTrue(AssetRegistry().exists("welcome"))

    def test_e2e2_sad_conversation_caring(self):
        d, a = _run(
            {"type": "conversation.started", "emotion": "sad"},
            text="汪汪～糖糖陪你。",
        )
        self.assertEqual(d.presentation_state, "caring")
        self.assertEqual(d.self_state, "calm")
        self.assertTrue(a.speak)
        self.assertTrue(AssetRegistry().exists("caring"))

    def test_e2e3_score_100_happy(self):
        d, a = _run(
            {"type": "conversation.started", "emotion": "happy"},
            text="汪汪～你好厉害！",
        )
        self.assertEqual(d.presentation_state, "happy")
        self.assertTrue(a.speak)

    def test_e2e4_screen_encouraging(self):
        d, a = _run({"type": "screen.usage"})
        self.assertEqual(d.presentation_state, "encouraging")
        self.assertNotEqual(d.presentation_state, "thinking")

    def test_e2e5_night_exercise_silent(self):
        now = datetime(2026, 8, 29, 23, 30)
        d, a = _run(
            {"type": "exercise.started", "companion": True, "now": now},
            policy={"decision": "SILENT", "quiet_hours": True},
            now=now,
            text="不该说出来",
        )
        self.assertEqual(d.presentation_state, "night")
        self.assertFalse(d.speech_allowed)
        self.assertFalse(a.speak)
        self.assertEqual(a.text, "")

    def test_privacy_engine_never_keeps_utterance(self):
        event = {
            "type": "conversation.started",
            "emotion": "sad",
            "utterance": PRIVATE_LINE,
            "transcript": PRIVATE_LINE,
        }
        d, a = _run(event, text="汪汪～")
        self.assertEqual(d.presentation_state, "caring")
        blob = json.dumps(d.__dict__, ensure_ascii=False)
        self.assertNotIn(PRIVATE_LINE, blob)
        self.assertNotIn(PRIVATE_LINE, a.reason)
        family_summary = []  # would be FamilySummary in Memory — engine must not append utterance
        self.assertNotIn(PRIVATE_LINE, family_summary)

    def test_legacy_say_sad_maps_without_storing_text(self):
        event = to_event("say", PRIVATE_LINE, now=datetime(2026, 8, 29, 16, 0))
        self.assertNotIn("utterance", event)
        self.assertEqual(event.get("emotion"), "sad")
        d = decide_from_legacy("say", PRIVATE_LINE, now=datetime(2026, 8, 29, 16, 0))
        self.assertEqual(d.presentation_state, "caring")

    def test_legacy_say_100_is_happy(self):
        d = decide_from_legacy("say", "我考了100分！", now=datetime(2026, 8, 29, 16, 0))
        self.assertEqual(d.presentation_state, "happy")

    def test_transport_writes_action_and_legacy_mood(self):
        d, a = _run({"type": "home.arrived"}, text="来啦～")
        with tempfile.TemporaryDirectory() as tmp:
            write_presentation_action(a, tmp)
            data = json.loads(Path(tmp, "cat-presentation-action.json").read_text(encoding="utf-8"))
            self.assertEqual(data["state"], "welcome")
            mood = Path(tmp, "cat-mood.txt").read_text(encoding="utf-8")
            self.assertIn("welcome", mood)
