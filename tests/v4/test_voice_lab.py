"""Tests for the local TangTang blind voice audition utility."""
from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB_PATH = ROOT / "code" / "cat" / "cat-voice-lab.py"
EDGE_PATH = ROOT / "code" / "cat" / "cat-tts-edge.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LAB = load_module("tangtang_voice_lab_test", LAB_PATH)
EDGE = load_module("tangtang_edge_tts_test", EDGE_PATH)


class TestVoiceLab(unittest.TestCase):
    def test_choose_voices_keeps_production_voice_and_preferred_alternatives(self):
        available = [
            {"ShortName": "zh-CN-XiaoxiaoNeural", "Locale": "zh-CN", "Gender": "Female"},
            {"ShortName": "zh-CN-XiaoyiNeural", "Locale": "zh-CN", "Gender": "Female"},
            {"ShortName": "zh-CN-XiaohanNeural", "Locale": "zh-CN", "Gender": "Female"},
            {"ShortName": "zh-CN-YunxiNeural", "Locale": "zh-CN", "Gender": "Male"},
            {"ShortName": "en-US-JennyNeural", "Locale": "en-US", "Gender": "Female"},
            {"ShortName": "zh-CN-XiaochenMultilingualNeural", "Locale": "zh-CN", "Gender": "Female"},
        ]
        chosen = LAB.choose_voices(available, limit=3)
        self.assertEqual(
            [v["ShortName"] for v in chosen],
            ["zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural", "zh-CN-XiaohanNeural"],
        )

    def test_rejects_too_small_limit_and_insufficient_available_voices(self):
        with self.assertRaises(ValueError):
            LAB.choose_voices([], limit=1)
        with self.assertRaises(RuntimeError):
            LAB.choose_voices(
                [{"ShortName": "zh-CN-XiaoxiaoNeural", "Locale": "zh-CN", "Gender": "Female"}],
                limit=6,
            )

    def test_default_voice_can_be_overridden_without_changing_default(self):
        self.assertEqual(EDGE.DEFAULT_VOICE, "zh-CN-XiaoxiaoNeural")
        old = os.environ.get("TANGTANG_TTS_VOICE")
        try:
            os.environ.pop("TANGTANG_TTS_VOICE", None)
            self.assertEqual(EDGE.selected_voice(), "zh-CN-XiaoxiaoNeural")
            os.environ["TANGTANG_TTS_VOICE"] = "zh-CN-XiaoyiNeural"
            self.assertEqual(EDGE.selected_voice(), "zh-CN-XiaoyiNeural")
            os.environ["TANGTANG_TTS_VOICE"] = "   "
            self.assertEqual(EDGE.selected_voice(), "zh-CN-XiaoxiaoNeural")
        finally:
            if old is None:
                os.environ.pop("TANGTANG_TTS_VOICE", None)
            else:
                os.environ["TANGTANG_TTS_VOICE"] = old


if __name__ == "__main__":
    unittest.main()
