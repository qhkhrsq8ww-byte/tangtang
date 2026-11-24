"""Privacy regression tests for the legacy voiceprint interaction log."""
from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[2] / "code" / "cat" / "cat-vp.py"
SPEC = importlib.util.spec_from_file_location("tangtang_cat_vp_privacy", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load cat-vp.py")
VP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VP)


class TestVoiceLogPrivacy(unittest.TestCase):
    def test_log_never_persists_raw_utterance(self):
        secret = "这是孩子不希望被保存的私人原话"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with mock.patch.object(VP, "HABIT_FILE", str(base / "cat-habits.json")):
                with mock.patch.object(VP, "VP_FILE", str(base / "cat-voiceprints.json")):
                    VP.log("child_1", secret)
                    saved = (base / "cat-habits.json").read_text(encoding="utf-8")
                    self.assertNotIn(secret, saved)
                    parsed = json.loads(saved)
                    self.assertNotIn("text", parsed["logs"][-1])

    def test_summary_never_prints_historical_raw_utterance(self):
        secret = "历史遗留的孩子私人原话"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cat-habits.json"
            path.write_text(json.dumps({"logs": [{"name": "child_1", "text": secret, "time": "2026-11-24 08:00:00", "hour": 8}]}), encoding="utf-8")
            with mock.patch.object(VP, "HABIT_FILE", str(path)):
                output = io.StringIO()
                with redirect_stdout(output):
                    VP.summary(7)
                self.assertNotIn(secret, output.getvalue())


if __name__ == "__main__":
    unittest.main()
