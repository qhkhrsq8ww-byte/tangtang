"""Persistence contract: runtime and memories must survive process-style re-instantiation."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.family_loader import load_members
from core.memory.family import FamilyMemory
from core.memory.private import PrivateMemory
from core.memory.store import Memory
from core.policy.privacy_policy import PrivacyPolicy
from tangtang_runtime import TangTangRuntime

MEMBERS = load_members()
PRIVATE_TEXT = "我喜欢恐龙"


class FrozenClock:
    def __init__(self, when: datetime) -> None:
        self.when = when

    def __call__(self) -> datetime:
        return self.when


class TestPrivateMemoryPersistence(unittest.TestCase):
    def test_private_memory_survives_new_instance_but_remains_owner_only(self):
        with tempfile.TemporaryDirectory() as td:
            privacy = PrivacyPolicy(MEMBERS)
            first = PrivateMemory(home=td, persist=True, privacy=privacy)
            first.put(member_id="hanghang", utterance=PRIVATE_TEXT)

            second = PrivateMemory(home=td, persist=True, privacy=privacy)
            self.assertEqual(second.query(member_id="hanghang", viewer_id="dad"), [])
            rows = second.query(member_id="hanghang", viewer_id="hanghang")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["data"]["speech"], PRIVATE_TEXT)

    def test_expired_disk_memory_is_removed_when_reloaded(self):
        start = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            privacy = PrivacyPolicy(MEMBERS)
            first = PrivateMemory(
                home=td, persist=True, privacy=privacy,
                clock=FrozenClock(start), ttl_days=1,
            )
            first.put(member_id="hanghang", utterance=PRIVATE_TEXT)
            path = Path(td) / "private" / "hanghang" / "memories.json"
            self.assertTrue(path.is_file())

            later = PrivateMemory(
                home=td, persist=True, privacy=privacy,
                clock=FrozenClock(start + timedelta(days=2)), ttl_days=1,
            )
            self.assertEqual(later.query(member_id="hanghang", viewer_id="hanghang"), [])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [])


class TestFamilyMemoryPersistence(unittest.TestCase):
    def test_family_memory_restores_after_reinstantiation(self):
        with tempfile.TemporaryDirectory() as td:
            privacy = PrivacyPolicy(MEMBERS)
            first = FamilyMemory(home=td, persist=True, privacy=privacy)
            first.put(Memory(
                memory_id="family_pref_1",
                member_id="dad",
                type="preference",
                privacy="FAMILY",
                data={"tag": "communication", "value": "short replies"},
            ))

            second = FamilyMemory(home=td, persist=True, privacy=privacy)
            rows = second.query(member_id="dad", viewer_id="dad")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["data"]["value"], "short replies")


class TestRuntimePersistence(unittest.TestCase):
    def test_runtime_events_and_private_memory_survive_new_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            first = TangTangRuntime(members=MEMBERS, home=td, persist=True)
            result = first.handle_utterance(
                PRIVATE_TEXT,
                {"label": "hanghang", "interactive": True},
            )
            self.assertTrue(result.event_kept)
            self.assertTrue(result.ingest and result.ingest.stored_private)

            second = TangTangRuntime(members=MEMBERS, home=td, persist=True)
            event_rows = second.events.query(event_id=result.event_id)
            self.assertEqual(len(event_rows), 1)
            self.assertEqual(event_rows[0]["payload"], {"redacted": True})

            memories = second.pipeline.stores.private.query(
                member_id="hanghang", viewer_id="hanghang"
            )
            self.assertTrue(any(row["data"].get("speech") == PRIVATE_TEXT for row in memories))
            self.assertEqual(
                second.pipeline.stores.private.query(member_id="hanghang", viewer_id="dad"),
                [],
            )


if __name__ == "__main__":
    unittest.main()
