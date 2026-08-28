"""PrivacyPolicy is the single speech gate. Tests fail if it is skipped."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.errors import CompatibilityError, MemoryError
from core.ingest import PrivacyPipeline
from core.memory.family import FamilyMemory, FamilySummary, HabitStore, ParentContext
from core.memory.store import Memory, MemoryStore
from core.policy.privacy_policy import PrivacyDecision, PrivacyPolicy

BULLY = "我今天被同学欺负了。"
INGEST_SRC = (ROOT / "core" / "ingest.py").read_text(encoding="utf-8")
FAMILY_SRC = (ROOT / "core" / "memory" / "family.py").read_text(encoding="utf-8")
STORE_SRC = (ROOT / "core" / "memory" / "store.py").read_text(encoding="utf-8")
PRIVATE_SRC = (ROOT / "core" / "memory" / "private.py").read_text(encoding="utf-8")


class TestSinglePrivacyGate(unittest.TestCase):
    def test_ingest_calls_privacy_before_event_create(self):
        self.assertIn("assert_event_privacy", INGEST_SRC)
        self.assertIn("Event.create", INGEST_SRC)
        self.assertLess(
            INGEST_SRC.index("assert_event_privacy"),
            INGEST_SRC.index("Event.create"),
            "PrivacyPolicy must run before Event.create; skipping the gate fails this test",
        )

    def test_ingest_invokes_classify_or_assert(self):
        calls = {"n": 0}
        real = PrivacyPolicy()

        class Spy(PrivacyPolicy):
            core_api_version = "4.0.0"

            def classify(self, **kwargs):
                calls["n"] += 1
                return real.classify(**kwargs)

            def assert_event_privacy(self, **kwargs):
                calls["n"] += 1
                return real.assert_event_privacy(**kwargs)

        pipe = PrivacyPipeline(privacy=Spy())
        result = pipe.ingest(BULLY, {"label": "hanghang"})
        self.assertGreaterEqual(calls["n"], 1)
        self.assertEqual(result.decision.privacy, "PRIVATE")
        self.assertFalse(pipe.stores.family.contains_text(BULLY))

    def test_bypass_ingest_family_put_still_rejected(self):
        mem = Memory(
            memory_id="bypass",
            member_id="child_9",
            type="utterance",
            privacy="FAMILY",
            data={"speech": BULLY},
        )
        with self.assertRaises(MemoryError):
            FamilyMemory().put(mem)
        with self.assertRaises(MemoryError):
            FamilySummary().put(mem)
        with self.assertRaises(MemoryError):
            ParentContext().put(mem)
        with self.assertRaises(MemoryError):
            HabitStore().put(member_id="child_9", utterance=BULLY)
        with self.assertRaises(MemoryError):
            MemoryStore().put(Memory(
                memory_id="bypass2",
                member_id="hanghang",
                type="utterance",
                privacy="PUBLIC",
                data={"utterance": BULLY},
            ))

    def test_stores_source_consults_privacy_policy(self):
        self.assertIn("allow_destination", FAMILY_SRC)
        self.assertIn("is_child", STORE_SRC)
        self.assertIn("classify", PRIVATE_SRC)

    def test_leaky_v5_policy_rejected(self):
        class V5Leak:
            core_api_version = "5.0.0"

            def classify(self, **kwargs):
                return PrivacyDecision(
                    privacy="PUBLIC",
                    member_id="child_9",
                    is_child=False,
                    allow_raw_text=True,
                    allow_family_memory=True,
                    allow_family_summary=True,
                    allow_parent_context=True,
                    allow_habit_store=True,
                    allow_log_raw=True,
                    reason="v5-leak",
                )

            def assert_event_privacy(self, **kwargs):
                return self.classify(**kwargs)

            def is_child(self, member_id=None):
                return False

        with self.assertRaises(CompatibilityError):
            PrivacyPipeline(privacy=V5Leak())  # type: ignore[arg-type]

    def test_unversioned_policy_rejected(self):
        class Unversioned:
            def classify(self, **kwargs):
                return PrivacyPolicy().classify(**kwargs)

            def assert_event_privacy(self, **kwargs):
                return PrivacyPolicy().assert_event_privacy(**kwargs)

        with self.assertRaises(CompatibilityError):
            PrivacyPipeline(privacy=Unversioned())  # type: ignore[arg-type]


class TestPrivacyGateEmptyUnknown(unittest.TestCase):
    def test_empty_ingest_still_goes_through_gate(self):
        pipe = PrivacyPipeline()
        result = pipe.ingest("", {"label": "dad"})
        self.assertIn(result.decision.privacy, {"FAMILY", "PUBLIC", "PRIVATE"})

    def test_unknown_member_does_not_skip_gate(self):
        pipe = PrivacyPipeline()
        result = pipe.ingest("你好", {"label": "邻居"})
        self.assertTrue(result.event.id)


if __name__ == "__main__":
    unittest.main()
