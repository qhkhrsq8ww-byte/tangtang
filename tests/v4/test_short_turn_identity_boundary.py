from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "code" / "cat" / "cat-turn.py"
spec = importlib.util.spec_from_file_location("tangtang_cat_turn_identity_test", SCRIPT)
cat_turn = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(cat_turn)


class TestShortTurnIdentityBoundary(unittest.TestCase):
    def test_scheduled_child_is_audience_not_verified_speaker(self):
        with tempfile.TemporaryDirectory() as td:
            row = cat_turn.append_turn(
                event="english",
                who="hanghang",
                result="joined",
                stt=False,
                presence="home",
                seconds=5,
                rms=800,
                root=td,
                ts="2026-11-24T10:00:00+08:00",
                speak=False,
            )
            self.assertEqual(row["actor_kind"], "system")
            self.assertEqual(row["audience_id"], "hanghang")
            self.assertEqual(row["speaker_identity_status"], "unverified")
            self.assertIsNone(row["speaker_member_id"])
            data = json.loads((Path(td) / "cat-turn-ledger.json").read_text(encoding="utf-8"))
            saved = data["turns"][-1]
            self.assertEqual(saved["audience_id"], "hanghang")
            self.assertEqual(saved["speaker_identity_status"], "unverified")

    def test_unverified_short_turn_does_not_update_member_habits(self):
        row = {
            "who": "hanghang",
            "audience_id": "hanghang",
            "actor_kind": "system",
            "speaker_identity_status": "unverified",
            "speaker_member_id": None,
            "result": "joined",
        }
        cat_turn._notify_habits(row)
        self.assertEqual(row["speaker_identity_status"], "unverified")


if __name__ == "__main__":
    unittest.main()
