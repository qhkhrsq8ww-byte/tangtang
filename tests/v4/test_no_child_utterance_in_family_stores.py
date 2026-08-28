"""Child raw utterance must not enter family-shared stores or ordinary logs."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.errors import MemoryError
from core.ingest import PrivacyPipeline
from core.logging.safe import SafeLogger
from core.memory.family import FamilyMemory, FamilySummary, HabitStore, ParentContext
from core.memory.store import Memory, MemoryStore

V4_MEMBERS = {
    "grandpa": {"display_name": "爷爷", "relation": "elder"},
    "grandma": {"display_name": "奶奶", "relation": "elder"},
    "dad": {"display_name": "爸爸", "profile": "adult"},
    "mom": {"display_name": "妈妈", "profile": "adult"},
    "child_12": {"display_name": "姐姐", "relation": "child", "age": 12, "aliases": ["qiaqia"]},
    "child_9": {"display_name": "弟弟", "relation": "child", "age": 9, "aliases": ["hanghang"]},
}

BULLY = "我今天被同学欺负了。"


class TestNoChildUtteranceInFamilyStores(unittest.TestCase):
    def setUp(self):
        self.logger = SafeLogger()
        self.pipe = PrivacyPipeline(members=V4_MEMBERS, logger=self.logger)
        self.result = self.pipe.ingest(BULLY, {"label": "hanghang"})

    def test_ingest_routes_private_only(self):
        self.assertEqual(self.result.decision.privacy, "PRIVATE")
        self.assertTrue(self.result.stored_private)
        self.assertFalse(self.result.stored_family)
        self.assertFalse(self.result.stored_summary)
        self.assertFalse(self.result.stored_parent)
        self.assertFalse(self.result.stored_habit)

    def test_family_memory_empty_of_bully(self):
        self.assertFalse(self.pipe.stores.family.contains_text(BULLY))
        self.assertFalse(self.pipe.stores.summary.contains_text(BULLY))
        self.assertFalse(self.pipe.stores.parent.contains_text(BULLY))
        self.assertFalse(self.pipe.stores.habits.contains_text(BULLY))

    def test_logger_has_no_raw_sentence(self):
        self.assertFalse(self.logger.contains_raw(BULLY))
        joined = "\n".join(self.logger.lines)
        self.assertNotIn(BULLY, joined)
        self.assertNotIn("被同学欺负", joined)

    def test_direct_family_put_rejected(self):
        mem = Memory(
            memory_id="bad",
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

    def test_memory_store_fail_closed_on_misclassified_child(self):
        store = MemoryStore()
        with self.assertRaises(MemoryError):
            store.put(Memory(
                memory_id="mis",
                member_id="child_9",
                type="utterance",
                privacy="PUBLIC",
                data={"utterance": BULLY},
            ))

    def test_parent_context_build_omits_raw(self):
        parent = ParentContext()
        text = parent.build(members=V4_MEMBERS)
        self.assertNotIn(BULLY, text)
        self.assertIn("child_9", text)

    def test_habit_file_on_disk_has_no_bully(self):
        with tempfile.TemporaryDirectory() as tmp:
            habits = HabitStore(home=tmp, persist=True)
            with self.assertRaises(MemoryError):
                habits.put(member_id="hanghang", utterance=BULLY)
            path = Path(tmp) / "habits" / "cat-habits.json"
            if path.exists():
                raw = path.read_text(encoding="utf-8")
                self.assertNotIn(BULLY, raw)
                self.assertNotIn("被同学欺负", json.dumps(json.loads(raw), ensure_ascii=False))


class TestAdultFamilyMayStore(unittest.TestCase):
    def test_dad_family_talk_can_enter_family_memory(self):
        pipe = PrivacyPipeline(members=V4_MEMBERS)
        result = pipe.ingest("晚饭做好了", {"label": "dad"})
        self.assertEqual(result.decision.privacy, "FAMILY")
        self.assertTrue(result.stored_family)
        self.assertTrue(pipe.stores.family.contains_text("晚饭做好了"))


if __name__ == "__main__":
    unittest.main()
