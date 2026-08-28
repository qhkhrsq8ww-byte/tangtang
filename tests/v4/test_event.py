"""Event schema, constructors, illegal payloads."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.errors import EventError
from core.events.event import Event, MAX_PAYLOAD_BYTES, PRIVACY_SCOPES


class TestEventHappy(unittest.TestCase):
    def test_create_public_minimal(self):
        ev = Event.create(type="wake", source="schedule", privacy="PUBLIC")
        self.assertTrue(ev.id.startswith("evt_"))
        self.assertEqual(ev.type, "wake")
        self.assertEqual(ev.source, "schedule")
        self.assertEqual(ev.privacy, "PUBLIC")
        self.assertIsNone(ev.member_id)
        self.assertEqual(dict(ev.payload), {})
        self.assertEqual(ev.event_id, ev.id)
        self.assertEqual(ev.event_type, ev.type)
        self.assertEqual(ev.timestamp, ev.ts)

    def test_from_dict_canonical_fields(self):
        ev = Event.from_dict({
            "id": "evt_1",
            "type": "greet",
            "ts": "2026-08-28T00:00:00+00:00",
            "source": "mic",
            "privacy": "FAMILY",
            "member_id": "dad",
            "payload": {"kind": "hi"},
        })
        self.assertEqual(ev.id, "evt_1")
        self.assertEqual(ev.to_dict()["payload"], {"kind": "hi"})

    def test_privacy_enum_all_three(self):
        self.assertEqual(PRIVACY_SCOPES, frozenset({"PRIVATE", "FAMILY", "PUBLIC"}))
        Event.create(type="n", privacy="PUBLIC")
        Event.create(type="n", privacy="FAMILY", member_id="dad")
        Event.create(type="n", privacy="PRIVATE", member_id="child_9")


class TestEventEmpty(unittest.TestCase):
    def test_empty_payload_ok(self):
        ev = Event.create(type="status", payload={})
        self.assertEqual(dict(ev.payload), {})

    def test_empty_member_id_public_ok(self):
        ev = Event.create(type="tick", member_id="")
        self.assertIsNone(ev.member_id)


class TestEventIllegal(unittest.TestCase):
    def test_missing_id_from_dict(self):
        with self.assertRaises(EventError):
            Event.from_dict({
                "type": "wake",
                "ts": "t",
                "source": "s",
                "privacy": "PUBLIC",
            })

    def test_blank_id(self):
        with self.assertRaises(EventError):
            Event(
                id="  ",
                type="wake",
                ts="t",
                source="s",
                privacy="PUBLIC",
            )

    def test_missing_type(self):
        with self.assertRaises(EventError):
            Event.from_dict({
                "id": "evt_x",
                "ts": "t",
                "source": "s",
                "privacy": "PUBLIC",
            })

    def test_bad_privacy_enum(self):
        with self.assertRaises(EventError):
            Event.create(type="wake", privacy="SECRET")
        with self.assertRaises(EventError):
            Event.create(type="wake", privacy="private")

    def test_private_without_member(self):
        with self.assertRaises(EventError):
            Event.create(type="speech", privacy="PRIVATE")

    def test_huge_payload(self):
        blob = {"text": "x" * (MAX_PAYLOAD_BYTES + 10)}
        with self.assertRaises(EventError):
            Event.create(type="speech", privacy="PRIVATE", member_id="child_9", payload=blob)

    def test_non_mapping_payload(self):
        with self.assertRaises(EventError):
            Event.create(type="wake", payload=["nope"])  # type: ignore[arg-type]

    def test_non_serializable_payload(self):
        with self.assertRaises(EventError):
            Event.create(type="wake", payload={"fn": lambda: 1})

    def test_payload_not_mutated_after_create(self):
        raw = {"k": "v"}
        ev = Event.create(type="wake", payload=raw)
        raw["k"] = "changed"
        self.assertEqual(ev.payload["k"], "v")
        with self.assertRaises(TypeError):
            ev.payload["k"] = "no"  # type: ignore[index]


class TestEventUnknown(unittest.TestCase):
    def test_unknown_type_is_allowed_as_data(self):
        ev = Event.create(type="not_a_known_scene", source="unknown")
        self.assertEqual(ev.type, "not_a_known_scene")


class TestEventNoResolverEmbed(unittest.TestCase):
    def test_event_module_does_not_import_identity(self):
        from core.events import event as event_mod
        src = Path(event_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("identity", src.lower())
        self.assertFalse(hasattr(Event.create(type="x"), "resolver"))


if __name__ == "__main__":
    unittest.main()
