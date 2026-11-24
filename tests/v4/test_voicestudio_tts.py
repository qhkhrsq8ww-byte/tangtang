"""VoiceStudio TTS adapter tests; no network or child audio is used."""
from __future__ import annotations

import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "code" / "cat" / "cat-tts-voicestudio.py"
SPEC = importlib.util.spec_from_file_location("tangtang_voicestudio_tts", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load VoiceStudio TTS client")
TTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TTS)


class TestVoiceStudioRequest(unittest.TestCase):
    def test_openai_compatible_request_and_bearer_auth(self):
        with mock.patch.dict(os.environ, {
            "TANGTANG_VOICESTUDIO_URL": "https://voice.example/v1/audio/speech",
            "TANGTANG_VOICESTUDIO_API_KEY": "test-secret",
            "TANGTANG_VOICESTUDIO_VOICE": "default",
        }, clear=False):
            url, body, headers = TTS.make_request("你好糖糖", "-10")
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(url, "https://voice.example/v1/audio/speech")
        self.assertEqual(payload["input"], "你好糖糖")
        self.assertEqual(payload["response_format"], "mp3")
        self.assertEqual(payload["speed"], 0.9)
        self.assertEqual(headers["Authorization"], "Bearer test-secret")

    def test_speed_is_clamped(self):
        self.assertEqual(TTS._speed("-200"), 0.25)
        self.assertEqual(TTS._speed("999"), 4.0)
        self.assertEqual(TTS._speed("invalid"), 0.9)

    def test_rejects_empty_or_overlong_text(self):
        with self.assertRaises(ValueError):
            TTS.make_request("")
        with self.assertRaises(ValueError):
            TTS.make_request("糖" * 4097)

    def test_loopback_default_needs_no_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            url, _body, headers = TTS.make_request("你好")
        self.assertEqual(url, TTS.DEFAULT_URL)
        self.assertNotIn("Authorization", headers)

    def test_voice_style_is_optional(self):
        with mock.patch.dict(os.environ, {
            "TANGTANG_VOICESTUDIO_INSTRUCTIONS": "温柔、自然、亲切",
        }, clear=False):
            _url, body, _headers = TTS.make_request("你好")
        self.assertEqual(json.loads(body.decode("utf-8"))["instructions"], "温柔、自然、亲切")


if __name__ == "__main__":
    unittest.main()
