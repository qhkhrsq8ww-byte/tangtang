"""MemoryStore: independent of Context; privacy scopes; empty/illegal."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.errors import MemoryError
from core.interfaces import MemoryPort
from core.memory.store import Memory, MemoryStore


def _mem(mid, member, privacy, data=None):
    return Memory(
        memory_id=mid,
        member_id=member,
        type="note",
        privacy=privacy,
        data=data or {"k": mid},
        source_events=["evt_1"],
    )


class TestMemoryHappy(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.assertIsInstance(self.store, MemoryPort)
        self.store.put(_mem("p9", "child_9", "PRIVATE", {"mood": "secret"}))
        self.store.put(_mem("f9", "child_9", "FAMILY", {"tag": "play"}))
        self.store.put(_mem("u9", "child_9", "PUBLIC", {"tag": "home"}))
        self.store.put(_mem("p12", "child_12", "PRIVATE", {"mood": "other-child"}))

    def test_private_self(self):
        rows = self.store.query(member_id="child_9", scope="PRIVATE", viewer_id="child_9")
        self.assertEqual({r["memory_id"] for r in rows}, {"p9"})
        self.assertEqual(rows[0]["data"]["mood"], "secret")

    def test_family_excludes_private(self):
        rows = self.store.query(member_id="child_9", scope="FAMILY", viewer_id="dad")
        ids = {r["memory_id"] for r in rows}
        self.assertEqual(ids, {"f9", "u9"})
        self.assertNotIn("p9", ids)

    def test_public_only(self):
        rows = self.store.query(member_id="child_9", scope="PUBLIC", viewer_id="grandpa")
        self.assertEqual({r["memory_id"] for r in rows}, {"u9"})


class TestMemoryEmptyUnknown(unittest.TestCase):
    def test_empty_store(self):
        store = MemoryStore()
        self.assertEqual(store.query(member_id="child_9", scope="PRIVATE"), [])

    def test_unknown_member(self):
        store = MemoryStore()
        store.put(_mem("p9", "child_9", "PRIVATE"))
        self.assertEqual(store.query(member_id="stranger", scope="PRIVATE"), [])

    def test_empty_member_id(self):
        store = MemoryStore()
        store.put(_mem("p9", "child_9", "PRIVATE"))
        self.assertEqual(store.query(member_id="", scope="PRIVATE"), [])


class TestMemoryIllegalAndLeak(unittest.TestCase):
    def test_bad_privacy_on_put(self):
        with self.assertRaises(MemoryError):
            Memory(memory_id="x", member_id="a", type="n", privacy="SECRET")

    def test_bad_scope_on_query(self):
        store = MemoryStore()
        with self.assertRaises(MemoryError):
            store.query(member_id="child_9", scope="ALL")

    def test_missing_ids_illegal(self):
        with self.assertRaises(MemoryError):
            Memory(memory_id="", member_id="a", type="n", privacy="PUBLIC")

    def test_cross_child_private_denied(self):
        store = MemoryStore()
        store.put(_mem("p9", "child_9", "PRIVATE", {"speech": "被同学欺负"}))
        leaked = store.query(member_id="child_9", scope="PRIVATE", viewer_id="child_12")
        self.assertEqual(leaked, [])
        dad = store.query(member_id="child_9", scope="PRIVATE", viewer_id="dad")
        self.assertEqual(dad, [])


class TestMemoryNoContextImport(unittest.TestCase):
    def test_source_independent(self):
        from core.memory import store as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("context", src.lower())
        self.assertNotIn("ContextBuilder", src)


if __name__ == "__main__":
    unittest.main()
