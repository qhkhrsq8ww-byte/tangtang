"""Acceptance regressions for memory lifecycle and storage failure isolation."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.adapters.family_loader import load_members
from core.memory.paths import private_file
from core.memory.private import PrivateMemory
from core.policy.privacy_policy import PrivacyPolicy


class FrozenClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class TestPrivateMemoryLifecycle(unittest.TestCase):
    def test_explicit_preference_can_be_forgotten_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            privacy = PrivacyPolicy(load_members())
            first = PrivateMemory(home=tmp, persist=True, privacy=privacy)
            first.remember_preference(
                member_id="dad", category="likes", value="青苹果", ttl_days=365
            )
            self.assertEqual(
                len(first.query(member_id="dad", viewer_id="dad")), 1
            )
            self.assertEqual(
                first.forget_preference(
                    member_id="dad", category="likes", value="青苹果"
                ),
                1,
            )
            restarted = PrivateMemory(home=tmp, persist=True, privacy=privacy)
            self.assertEqual(restarted.query(member_id="dad", viewer_id="dad"), [])

    def test_expired_memory_cleanup_failure_does_not_break_read(self):
        now = datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = private_file(tmp, "child_9")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps([{
                "memory_id": "expired-row",
                "member_id": "child_9",
                "type": "utterance",
                "privacy": "PRIVATE",
                "data": {"speech": "fixture only"},
                "source_events": [],
                "created_at": "2026-10-01T00:00:00+00:00",
                "expires_at": "2026-10-02T00:00:00+00:00",
            }]), encoding="utf-8")
            memory = PrivateMemory(
                home=tmp,
                persist=True,
                privacy=PrivacyPolicy(load_members()),
                clock=FrozenClock(now),
            )
            # Simulate a read-only / unavailable storage volume during best-effort cleanup.
            with patch.object(Path, "write_text", side_effect=OSError("read-only fixture")):
                self.assertEqual(
                    memory.query(member_id="child_9", viewer_id="child_9"), []
                )

    def test_private_memory_never_crosses_member_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = PrivateMemory(
                home=tmp, persist=True, privacy=PrivacyPolicy(load_members())
            )
            memory.remember_preference(
                member_id="child_9", category="favorite", value="恐龙"
            )
            self.assertEqual(memory.query(member_id="child_9", viewer_id="child_12"), [])
            self.assertEqual(memory.query(member_id="child_12", viewer_id="child_12"), [])


if __name__ == "__main__":
    unittest.main()
