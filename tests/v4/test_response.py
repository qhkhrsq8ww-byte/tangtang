"""ResponseOrchestrator emits validated actions; never calls TTS/projection."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.errors import ActionError
from core.interfaces import ResponsePort
from core.response.orchestrator import PresentationAction, ResponseOrchestrator


class TestResponseHappy(unittest.TestCase):
    def test_speak_emits_voice_sink_label_not_call(self):
        orch = ResponseOrchestrator(responder=lambda ctx: "汪汪～")
        self.assertIsInstance(orch, ResponsePort)
        action = orch.run(
            decision="SPEAK",
            context={"who": {"member_id": "child_9"}},
            action="greet",
        )
        self.assertIsInstance(action, PresentationAction)
        self.assertEqual(action.decision, "SPEAK")
        self.assertEqual(action.text, "汪汪～")
        self.assertEqual(action.sink, "voice")
        self.assertEqual(action.member_id, "child_9")

    def test_silent_empty_text(self):
        orch = ResponseOrchestrator(responder=lambda ctx: "should-not-appear")
        action = orch.run(decision="SILENT", context={"who": {"member_id": "dad"}}, action="idle")
        self.assertEqual(action.text, "")
        self.assertEqual(action.sink, "none")
        self.assertEqual(action.decision, "SILENT")


class TestResponseEmptyUnknownIllegal(unittest.TestCase):
    def test_empty_context(self):
        orch = ResponseOrchestrator()
        action = orch.run(decision="LOG_ONLY", context=None)
        self.assertEqual(action.text, "")
        self.assertIsNone(action.member_id)

    def test_unknown_decision_illegal(self):
        orch = ResponseOrchestrator()
        with self.assertRaises(ActionError):
            orch.run(decision="YELL", context={})

    def test_non_speak_cannot_carry_text_on_action(self):
        with self.assertRaises(ActionError):
            PresentationAction(
                decision="SILENT",
                text="nope",
                action="idle",
                member_id=None,
            )

    def test_responder_must_return_str(self):
        orch = ResponseOrchestrator(responder=lambda ctx: {"tts": True})  # type: ignore[arg-type]
        with self.assertRaises(ActionError):
            orch.run(decision="SPEAK", context={})

    def test_delay_and_log_only(self):
        orch = ResponseOrchestrator()
        self.assertEqual(orch.run(decision="DELAY", context={}).sink, "none")
        self.assertEqual(orch.run(decision="LOG_ONLY", context={}).decision, "LOG_ONLY")


class TestResponseNoSinks(unittest.TestCase):
    def test_source_does_not_call_tts_or_projection(self):
        from core.response import orchestrator as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        lower = src.lower()
        self.assertNotIn("cat-tts", lower)
        self.assertNotIn("subprocess", lower)
        self.assertNotIn("import tts", lower)
        self.assertNotIn("cat-screen", lower)
        # sink names may appear as labels; calling APIs must not
        self.assertNotIn("play_audio", lower)
        self.assertNotIn("project_to", lower)


if __name__ == "__main__":
    unittest.main()
