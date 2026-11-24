"""Per-turn responder overrides must not mutate shared orchestrator state."""
from __future__ import annotations

import unittest

from core.response.orchestrator import ResponseOrchestrator


class TestPerTurnResponder(unittest.TestCase):
    def test_override_is_local_to_one_run(self):
        base = lambda _ctx: "base response"
        orchestrator = ResponseOrchestrator(responder=base, persona=None)
        context = {"who": {"member_id": "dad"}, "utterance": "hello", "skip_persona": True}

        override_action = orchestrator.run(
            decision="SPEAK",
            context=context,
            action="reply",
            responder=lambda _ctx: "per-turn response",
        )
        default_action = orchestrator.run(
            decision="SPEAK",
            context=context,
            action="reply",
        )

        self.assertEqual(override_action.text, "per-turn response")
        self.assertEqual(default_action.text, "base response")
        self.assertIs(orchestrator.responder, base)


if __name__ == "__main__":
    unittest.main()
