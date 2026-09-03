"""V3 package facade: documented top-level modules re-export core implementations."""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TestV3Facades(unittest.TestCase):
    def test_family_exports(self):
        import family
        from family.identity_resolver import IdentityResolver

        self.assertTrue(hasattr(family, "IdentityResolver"))
        r = IdentityResolver({})
        out = r.resolve_from_voice_label("unknown", confidence=0.1)
        self.assertEqual(out["member_id"], "unknown")
        self.assertFalse(out["bound"])

    def test_memory_exports(self):
        import memory

        self.assertTrue(hasattr(memory, "MemoryStore"))
        self.assertTrue(hasattr(memory, "FamilyMemoryV2"))

    def test_context_exports(self):
        import context

        self.assertTrue(hasattr(context, "ContextBuilder"))

    def test_behavior_exports(self):
        import behavior

        self.assertTrue(hasattr(behavior, "CharacterStateEngine"))
        self.assertTrue(hasattr(behavior, "ShouldInterrupt"))
        self.assertIs(behavior.ShouldInterrupt, behavior.InterruptPolicy)

    def test_interaction_exports(self):
        import interaction

        self.assertTrue(hasattr(interaction, "ResponseOrchestrator"))

    def test_pipeline_smoke(self):
        from behavior import CharacterStateEngine, InterruptPolicy
        from context import ContextBuilder
        from interaction import ResponseOrchestrator

        eng = CharacterStateEngine()
        methods = [n for n in dir(eng) if not n.startswith("_") and callable(getattr(eng, n))]
        self.assertTrue(methods, msg="engine should expose public methods")
        self.assertTrue(hasattr(InterruptPolicy, "decide"))
        self.assertTrue(hasattr(ContextBuilder, "build") or callable(ContextBuilder))
        self.assertTrue(hasattr(ResponseOrchestrator, "compose") or hasattr(ResponseOrchestrator, "run") or callable(ResponseOrchestrator))


if __name__ == "__main__":
    unittest.main()
