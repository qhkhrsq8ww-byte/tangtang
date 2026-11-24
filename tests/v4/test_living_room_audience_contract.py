from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.living_room_adapter import LivingRoomAdapter


class TestLivingRoomAudienceContract(unittest.TestCase):
    def test_proactive_event_keeps_audience_separate_from_member_identity(self):
        event = LivingRoomAdapter().to_event(
            "meal",
            member_id=None,
            privacy="PUBLIC",
            extra={"audience_id": "hanghang", "actor_kind": "system"},
        )
        self.assertIsNone(event.member_id)
        self.assertEqual(event.payload["audience_id"], "hanghang")
        self.assertEqual(event.payload["actor_kind"], "system")


if __name__ == "__main__":
    unittest.main()
