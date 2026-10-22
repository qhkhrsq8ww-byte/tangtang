"""Regression tests for child-facing legacy brain guardrails."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
BRAIN_PATH = ROOT / "code" / "cat" / "cat-brain.py"
BRIDGE_PATH = ROOT / "code" / "cat" / "cat-proactive-bridge.sh"


def load_brain():
    spec = importlib.util.spec_from_file_location("tangtang_legacy_brain", BRAIN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LegacyBrainGuardrailTests(unittest.TestCase):
    def test_idle_drift_cannot_leave_extreme_emotion_values(self):
        brain = load_brain()
        state = {
            "last_interaction": "2026-10-18T08:00:00",
            "happiness": 8,
            "energy": 8,
            "loneliness": 82,
            "affection": 50,
            "interactions_today": 0,
            "today": brain.now().strftime("%Y-%m-%d"),
        }
        result = brain.drift(state)
        self.assertGreaterEqual(result["happiness"], 40)
        self.assertGreaterEqual(result["energy"], 30)
        self.assertLessEqual(result["loneliness"], 60)
        self.assertGreaterEqual(result["affection"], 0)
        self.assertLessEqual(result["affection"], 100)

    def test_greeting_has_no_death_related_affection_phrase(self):
        source = BRAIN_PATH.read_text(encoding="utf-8")
        self.assertNotIn("想死你啦", source)
        self.assertIn("糖糖等到你啦", source)

    def test_proactive_bridge_writes_timestamped_local_diagnostics(self):
        source = BRIDGE_PATH.read_text(encoding="utf-8")
        self.assertIn('LOG_DIR="${HOME}/Library/Logs/tangtang"', source)
        self.assertIn('LOG_FILE="${LOG_DIR}/proactive.log"', source)
        self.assertIn("date '+%Y-%m-%dT%H:%M:%S%z'", source)
        self.assertIn("scheduled event=%s exit=%s", source)


if __name__ == "__main__":
    unittest.main()
