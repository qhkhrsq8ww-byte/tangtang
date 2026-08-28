"""PrivateMemory: bully sentence stays owner-only with expires_at."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.ingest import PrivacyPipeline
from core.memory.private import PrivateMemory

V4_MEMBERS = {
    "grandpa": {"display_name": "爷爷", "relation": "elder", "aliases": ["爷爷"]},
    "grandma": {"display_name": "奶奶", "relation": "elder", "aliases": ["奶奶"]},
    "dad": {"display_name": "爸爸", "profile": "adult", "aliases": ["爸爸"]},
    "mom": {"display_name": "妈妈", "profile": "adult", "aliases": ["妈妈"]},
    "child_12": {
        "display_name": "姐姐",
        "relation": "child",
        "age": 12,
        "aliases": ["姐姐", "qiaqia", "洽洽"],
    },
    "child_9": {
        "display_name": "弟弟",
        "relation": "child",
        "age": 9,
        "aliases": ["弟弟", "hanghang", "航航"],
    },
}

BULLY = "我今天被同学欺负了。"
OTHERS = ("grandpa", "grandma", "dad", "mom", "child_12", "qiaqia")


class FrozenClock:
    def __init__(self, when: datetime) -> None:
        self.when = when

    def __call__(self) -> datetime:
        return self.when


class TestPrivateMemoryBully(unittest.TestCase):
    def setUp(self):
        self.when = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        self.pipe = PrivacyPipeline(members=V4_MEMBERS, clock=FrozenClock(self.when))

    def test_bully_sentence_is_private_with_ttl(self):
        result = self.pipe.ingest(BULLY, {"label": "弟弟"})
        self.assertEqual(result.decision.privacy, "PRIVATE")
        self.assertEqual(result.event.privacy, "PRIVATE")
        self.assertEqual(result.event.member_id, "child_9")
        self.assertTrue(result.stored_private)
        self.assertFalse(result.stored_family)
        self.assertFalse(result.stored_habit)
        rows = self.pipe.stores.private.query(member_id="child_9", viewer_id="child_9")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["member_id"], "child_9")
        self.assertEqual(row["privacy"], "PRIVATE")
        self.assertTrue(row.get("created_at"))
        self.assertTrue(row.get("expires_at"))
        expires = datetime.fromisoformat(row["expires_at"])
        created = datetime.fromisoformat(row["created_at"])
        self.assertGreater(expires, created)
        self.assertEqual(row["data"]["speech"], BULLY)
        self.assertNotIn(BULLY, str(result.event.payload))

    def test_hanghang_alias(self):
        result = self.pipe.ingest(BULLY, {"label": "hanghang"})
        self.assertEqual(result.event.member_id, "child_9")
        self.assertEqual(result.decision.privacy, "PRIVATE")

    def test_others_cannot_read(self):
        self.pipe.ingest(BULLY, {"member_id": "child_9"})
        private = self.pipe.stores.private
        for viewer in OTHERS:
            leaked = private.query(member_id="child_9", viewer_id=viewer)
            self.assertEqual(leaked, [], viewer)

    def test_expired_hidden(self):
        clock = FrozenClock(self.when)
        store = PrivateMemory(clock=clock, ttl_days=1, privacy=self.pipe.privacy)
        store.put(member_id="child_9", utterance=BULLY, event_id="evt_x")
        clock.when = self.when + timedelta(days=2)
        self.assertEqual(store.query(member_id="child_9", viewer_id="child_9"), [])


class TestPrivateMemoryEmptyUnknown(unittest.TestCase):
    def test_empty_viewer_denied(self):
        mem = PrivateMemory()
        mem.put(member_id="child_9", utterance=BULLY)
        self.assertEqual(mem.query(member_id="child_9", viewer_id=None), [])
        self.assertEqual(mem.query(member_id="child_9", viewer_id=""), [])

    def test_unknown_member_empty(self):
        mem = PrivateMemory()
        self.assertEqual(mem.query(member_id="stranger", viewer_id="stranger"), [])


if __name__ == "__main__":
    unittest.main()
