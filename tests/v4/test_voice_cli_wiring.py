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
                "privacy_scope": "FAMILY",
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

    def test_private_bridge_does_not_call_gateway_without_opt_in(self):
        calls = []
        original_chat = CAT.chat
        original_flag = CAT.os.environ.get("TANGTANG_ALLOW_PRIVATE_LLM")
        def fake_chat(*args, **kwargs):
            calls.append(args)
            return "这句话不该被调用"
        CAT.chat = fake_chat
        CAT.os.environ.pop("TANGTANG_ALLOW_PRIVATE_LLM", None)
        try:
            response = CAT._runtime_llm(model="test-model")({
                "_filtered_prompt": "member=hanghang\\nprivacy=PRIVATE\\nutterance=我的私事",
                "utterance": "我的私事",
                "privacy_scope": "PRIVATE",
            })
        finally:
            CAT.chat = original_chat
            if original_flag is not None:
                CAT.os.environ["TANGTANG_ALLOW_PRIVATE_LLM"] = original_flag
            else:
                CAT.os.environ.pop("TANGTANG_ALLOW_PRIVATE_LLM", None)
        self.assertEqual(response, CAT.FALLBACK_REPLY)
        self.assertEqual(calls, [])

    def test_risky_turn_uses_local_safe_reply_without_model_call(self):
        names = ("looks_risky", "_escalate_risk", "emit_character_state", "_learn_turn")
        originals = {name: getattr(CAT, name) for name in names}
        calls = []
        try:
            CAT.looks_risky = lambda _text: True
            CAT._escalate_risk = lambda text: calls.append(("escalate", text))
            CAT.emit_character_state = lambda text, reply: calls.append(("state", reply))
            CAT._learn_turn = lambda text, **kwargs: calls.append(("learn", kwargs.get("event_tag")))
            self.assertEqual(CAT._local_safety_reply("risk-signal"), CAT.SAFE_REPLY)
        finally:
            for name, original in originals.items():
                setattr(CAT, name, original)
        self.assertEqual(calls[0], ("escalate", "risk-signal"))
        self.assertEqual(calls[1], ("state", CAT.SAFE_REPLY))
        self.assertEqual(calls[2], ("learn", "emotion"))

    def test_local_risk_gate_is_before_runtime_llm_call(self):
        source = CAT_CHAT.read_text(encoding="utf-8")
        main = source[source.index("def main():"):]
        risk_gate = main.index("risk_reply = _local_safety_reply(args.text)")
        alarm_gate = main.index("alarm_line = _alarm_reply(args.text)")
        observation_gate = main.index("obs = _live_obs()")
        speak_gate = main.index("if not _may_speak_now(obs):")
        llm_call = main.index("TangTangRuntime(llm=_runtime_llm(model=args.model), allow_private_llm=_allow_private_llm())")
        self.assertLess(risk_gate, alarm_gate)
        self.assertLess(risk_gate, observation_gate)
        self.assertLess(risk_gate, speak_gate)
        self.assertLess(risk_gate, llm_call)


if __name__ == "__main__":
    unittest.main()
