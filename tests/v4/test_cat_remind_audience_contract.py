from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestCatRemindAudienceContract(unittest.TestCase):
    def test_gate_scene_and_cooldown_use_the_same_target(self):
        source = (ROOT / "code" / "cat" / "cat-remind.sh").read_text(encoding="utf-8")
        self.assertIn('audience_id="${ARG:-${TANGTANG_MEMBER_ID:-room}}"', source)
        self.assertIn('"$EVENT" "$audience_id"', source)
        self.assertIn('"$EVENT" "$ARG"', source)
        self.assertIn('"$EVENT" "$audience_id" >/dev/null', source)

    def test_target_is_never_named_or_passed_as_authenticated_member(self):
        source = (ROOT / "code" / "cat" / "cat-remind.sh").read_text(encoding="utf-8")
        self.assertNotIn("gate_member=", source)
        self.assertNotIn("viewer_id", source)
        self.assertNotIn("speaker_id", source)


if __name__ == "__main__":
    unittest.main()
