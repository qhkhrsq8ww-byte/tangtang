"""Regression tests for the production voice CLI's V4 LLM bridge."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT_CHAT = ROOT / "code" / "cat" / "cat-chat.py"
SPEC = importlib.util.spec_from_file_location("tangtang_voice_cli_wiring", CAT_CHAT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load cat-chat.py for tests")
CAT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAT)


class TestVoiceCliLlmBridge(unittest.TestCase):
    def test_bridge_uses_filtered_prompt_and_never_appends_history(self):
        calls = []
        original_chat = CAT.chat

        def fake_chat(user_text, model=CAT.DEFAULT_MODEL, history=None):
            calls.append((user_text, model, history))
            return "听起来你今天有点累。要不要先歇一会儿？"

        CAT.chat = fake_chat
        try:
            bridge = CAT._runtime_llm(model="test-model")
            result = bridge({
                "_filtered_prompt": "member=dad\nprivacy=PRIVATE\nutterance=今天好累。",
                "utterance": "今天好累。",
                "history": [{"role": "user", "content": "不应发送的旧对话"}],
            })
        finally:
            CAT.chat = original_chat

        self.assertEqual(result, "听起来你今天有点累。要不要先歇一会儿？")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "member=dad\nprivacy=PRIVATE\nutterance=今天好累。")
        self.assertEqual(calls[0][1], "test-model")
        self.assertIsNone(calls[0][2])
        self.assertNotIn("不应发送的旧对话", calls[0][0])

    def test_local_risk_gate_is_before_runtime_llm_call(self):
        source = CAT_CHAT.read_text(encoding="utf-8")
        main = source[source.index("def main():"):]
        risk_gate = main.index("if looks_risky(args.text):")
        llm_call = main.index("TangTangRuntime(llm=_runtime_llm(model=args.model))")
        self.assertLess(risk_gate, llm_call)


if __name__ == "__main__":
    unittest.main()
