"""Bounded model latency and deterministic timeout fallback tests."""
from __future__ import annotations

import importlib.util
import os
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT_CHAT = ROOT / "code" / "cat" / "cat-chat.py"
SPEC = importlib.util.spec_from_file_location("tangtang_voice_timeout", CAT_CHAT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load cat-chat.py for tests")
CAT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAT)


class TestVoiceLlmTimeout(unittest.TestCase):
    def test_chat_uses_bounded_timeout_and_does_not_retry_empty_reply(self):
        old_timeout = CAT.os.environ.get("TANGTANG_LLM_TIMEOUT_SECONDS")
        CAT.os.environ["TANGTANG_LLM_TIMEOUT_SECONDS"] = "7"
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = (
            b'{"choices":[{"message":{"content":""}}]}'
        )
        try:
            with mock.patch.object(CAT.urllib.request, "urlopen", return_value=response) as opened:
                result = CAT.chat("你好糖糖")
        finally:
            if old_timeout is None:
                CAT.os.environ.pop("TANGTANG_LLM_TIMEOUT_SECONDS", None)
            else:
                CAT.os.environ["TANGTANG_LLM_TIMEOUT_SECONDS"] = old_timeout

        self.assertEqual(result, CAT.FALLBACK_REPLY)
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(opened.call_args.kwargs["timeout"], 7.0)

    def test_timeout_setting_is_clamped_and_invalid_value_defaults(self):
        old_timeout = CAT.os.environ.get("TANGTANG_LLM_TIMEOUT_SECONDS")
        CAT.os.environ["TANGTANG_LLM_TIMEOUT_SECONDS"] = "999"
        try:
            self.assertEqual(CAT._llm_timeout_seconds(), 20.0)
            CAT.os.environ["TANGTANG_LLM_TIMEOUT_SECONDS"] = "invalid"
            self.assertEqual(CAT._llm_timeout_seconds(), 10.0)
        finally:
            if old_timeout is None:
                CAT.os.environ.pop("TANGTANG_LLM_TIMEOUT_SECONDS", None)
            else:
                CAT.os.environ["TANGTANG_LLM_TIMEOUT_SECONDS"] = old_timeout


if __name__ == "__main__":
    unittest.main()
