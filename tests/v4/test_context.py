"""ContextBuilder uses Memory/Policy ports only; never opens files."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.context.builder import ContextBuilder
from core.events.event import Event
from core.interfaces import ContextPort
from core.memory.store import Memory, MemoryStore
from core.policy.interrupt_policy import InterruptPolicy
from core.security.contexts import ViewerContext


class TestContextHappy(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.put(Memory(
            memory_id="p9", member_id="child_9", type="note",
            privacy="PRIVATE", data={"speech": "secret"},
        ))
        self.store.put(Memory(
            memory_id="f9", member_id="child_9", type="note",
            privacy="FAMILY", data={"tag": "play"},
        ))
        self.policy = InterruptPolicy()
        self.builder = ContextBuilder(self.store, self.policy, max_recent=2)
        self.assertIsInstance(self.builder, ContextPort)

    def test_private_scope_loads_via_port(self):
        ev = Event.create(id="evt_c", type="greet", privacy="PRIVATE", member_id="child_9")
        ctx = self.builder.build(
            who={"member_id": "child_9"},
            event=ev,
            privacy_scope="PRIVATE",
            viewer_context=ViewerContext("child_9", "verified"),
        )
        ids = {m["memory_id"] for m in ctx["memory"]}
        self.assertEqual(ids, {"p9"})
        self.assertEqual(ctx["privacy_scope"], "PRIVATE")
        self.assertIn("policy_decision", ctx)

    def test_family_scope_drops_private(self):
        ev = Event.create(id="evt_f", type="meal", privacy="FAMILY", member_id="child_9")
        ctx = self.builder.build(
            who={"member_id": "child_9"},
            event=ev,
            privacy_scope="FAMILY",
            viewer_context=ViewerContext("child_9", "verified"),
            family={"summary": "ok", "private": "must-drop"},
        )
        ids = {m["memory_id"] for m in ctx["memory"]}
        self.assertEqual(ids, {"f9"})
        self.assertNotIn("private", ctx["family"])

    def test_public_scope(self):
        self.store.put(Memory(
            memory_id="u9", member_id="child_9", type="note",
            privacy="PUBLIC", data={"tag": "home"},
        ))
        ctx = self.builder.build(
            who={"member_id": "child_9"},
            event=Event.create(id="evt_p", type="home"),
            privacy_scope="PUBLIC",
            viewer_context=ViewerContext("child_9", "verified"),
        )
        ids = {m["memory_id"] for m in ctx["memory"]}
        self.assertEqual(ids, {"u9"})

    def test_recent_bound(self):
        ctx = self.builder.build(
            who={"member_id": "dad"},
            event={"id": "e", "type": "x"},
            recent=[1, 2, 3, 4],
            privacy_scope="PUBLIC",
        )
        self.assertEqual(ctx["recent"], [3, 4])


class TestContextViewerAuthorization(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.put(Memory(
            memory_id="private-child", member_id="child_9", type="note",
            privacy="PRIVATE", data={"tag": "private"},
        ))
        self.store.put(Memory(
            memory_id="family-child", member_id="child_9", type="note",
            privacy="FAMILY", data={"tag": "family"},
        ))
        self.builder = ContextBuilder(self.store, InterruptPolicy())

    def test_subject_and_legacy_viewer_id_do_not_authorize_reads(self):
        ctx = self.builder.build(
            who={"member_id": "child_9"},
            event=Event.create(id="evt_no_viewer", type="x", member_id="child_9"),
            privacy_scope="PRIVATE",
            viewer_id="child_9",
        )
        self.assertEqual(ctx["memory"], [])
        self.assertEqual(ctx["family"], {})

    def test_family_grant_does_not_grant_private_memory(self):
        viewer = ViewerContext("dad", "verified", frozenset({"family:read"}))
        family_ctx = self.builder.build(
            who={"member_id": "child_9"},
            event=Event.create(id="evt_family_grant", type="x"),
            privacy_scope="FAMILY",
            viewer_context=viewer,
        )
        self.assertEqual({row["memory_id"] for row in family_ctx["memory"]}, {"family-child"})
        private_ctx = self.builder.build(
            who={"member_id": "child_9"},
            event=Event.create(id="evt_private_denied", type="x"),
            privacy_scope="PRIVATE",
            viewer_context=viewer,
        )
        self.assertEqual(private_ctx["memory"], [])

    def test_private_owner_viewer_can_read_private_memory(self):
        ctx = self.builder.build(
            who={"member_id": "child_9"},
            event=Event.create(id="evt_private_owner", type="x"),
            privacy_scope="PRIVATE",
            viewer_context=ViewerContext("child_9", "verified"),
        )
        self.assertEqual({row["memory_id"] for row in ctx["memory"]}, {"private-child"})


class TestContextEmptyUnknown(unittest.TestCase):
    def test_empty_who_and_event(self):
        builder = ContextBuilder(MemoryStore(), InterruptPolicy())
        ctx = builder.build(who={}, event=None)
        self.assertEqual(ctx["memory"], [])
        self.assertEqual(ctx["who"], {})
        self.assertEqual(ctx["current_event"], {})

    def test_unknown_member_no_rows(self):
        store = MemoryStore()
        store.put(Memory(
            memory_id="p9", member_id="child_9", type="n", privacy="PRIVATE",
        ))
        ctx = ContextBuilder(store, InterruptPolicy()).build(
            who={"member_id": "stranger"},
            event=Event.create(id="e", type="x"),
            privacy_scope="PRIVATE",
        )
        self.assertEqual(ctx["memory"], [])


class TestContextNoDirectIO(unittest.TestCase):
    def test_constructor_requires_ports(self):
        with self.assertRaises(TypeError):
            ContextBuilder(None, InterruptPolicy())  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            ContextBuilder(MemoryStore(), None)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            ContextBuilder()  # type: ignore[call-arg]

    def test_source_has_no_open_or_db(self):
        from core.context import builder as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("open(", src)
        self.assertNotIn("sqlite", src.lower())
        self.assertNotIn("json.load", src)
        self.assertNotIn("Path(", src)
        self.assertIn("MemoryPort", src)
        self.assertIn("PolicyPort", src)


if __name__ == "__main__":
    unittest.main()
