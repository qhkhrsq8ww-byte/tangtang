"""Speak gate: quiet hours / school hours / SILENT never call LLM."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.chat_adapter import ChatAdapter
from core.adapters.family_loader import load_members
from core.compat import may_speak, should_interrupt
from core.ingest import PrivacyPipeline
from core.policy.interrupt_policy import InterruptPolicy
from core.policy.speak_gate import decide, may_call_llm
from tangtang_runtime import TangTangRuntime

MEMBERS = load_members()
CAT = ROOT / "code" / "cat"


def _dt(hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 8, 31, int(h), int(m), tzinfo=timezone.utc)


def _boom(_ctx):
    raise AssertionError("LLM must not be called when the speak gate is closed")


class TestSpeakGateDecide(unittest.TestCase):
    def test_alarm_always_speak(self):
        self.assertEqual(decide({}, now=_dt("23:00"), channel="alarm"), "SPEAK")
        self.assertTrue(may_speak({}, now=_dt("23:00"), channel="alarm"))

    def test_chat_quiet_hours_silent_when_not_interactive(self):
        self.assertEqual(
            decide({"interactive": False, "label": "dad"}, now=_dt("23:00"), channel="chat"),
            "SILENT",
        )
        self.assertEqual(
            decide({"label": "dad"}, now=_dt("23:00"), channel="remind"),
            "SILENT",
        )
        self.assertFalse(may_call_llm("SILENT"))
        self.assertFalse(may_call_llm("LOG_ONLY"))
        self.assertTrue(may_call_llm("SPEAK"))

    def test_chat_quiet_hours_interactive_may_speak(self):
        self.assertEqual(
            decide({"interactive": True, "label": "dad"}, now=_dt("23:00"), channel="chat"),
            "SPEAK",
        )

    def test_without_now_does_not_use_wall_clock_quiet(self):
        # Existing handle_utterance tests stay SPEAK when interactive.
        self.assertEqual(
            decide({"interactive": True, "label": "dad"}, channel="chat"),
            "SPEAK",
        )

    def test_school_hours_child_silent(self):
        self.assertEqual(
            decide({
                "label": "hanghang",
                "school_hours": True,
                "audience_child": True,
                "presence_home": False,
                "interactive": True,
            }, now=_dt("12:00"), channel="chat"),
            "SILENT",
        )

    def test_interrupt_policy_interactive_bypass_unchanged(self):
        p = InterruptPolicy()
        self.assertEqual(p.decide({"interactive": True}, now=_dt("23:00")), "SPEAK")
        self.assertTrue(should_interrupt({}, now=_dt("23:00")))


class TestNoLlmWhenSilent(unittest.TestCase):
    def test_quiet_hours_handle_utterance_does_not_call_llm(self):
        rt = TangTangRuntime(members=MEMBERS, llm=_boom)
        result = rt.handle_utterance(
            "糖糖在吗",
            {"label": "dad", "now": _dt("23:00"), "interactive": False},
        )
        self.assertEqual(result.decision, "SILENT")
        self.assertEqual((result.action.text if result.action else ""), "")

    def test_school_hours_handle_utterance_does_not_call_llm(self):
        rt = TangTangRuntime(members=MEMBERS, llm=_boom)
        result = rt.handle_utterance(
            "糖糖在吗",
            {
                "label": "hanghang",
                "school_hours": True,
                "audience_child": True,
                "presence_home": False,
            },
        )
        self.assertEqual(result.decision, "SILENT")
        self.assertEqual((result.action.text if result.action else ""), "")

    def test_log_only_does_not_call_llm(self):
        rt = TangTangRuntime(members=MEMBERS, llm=_boom)
        result = rt.handle_utterance(
            "糖糖在吗",
            {"label": "dad", "importance": "low"},
        )
        self.assertEqual(result.decision, "LOG_ONLY")
        self.assertEqual((result.action.text if result.action else ""), "")

    def test_chat_adapter_quiet_skips_llm(self):
        chat = ChatAdapter(members=MEMBERS, llm=_boom)
        turn = chat.turn(
            "你好",
            {"label": "dad", "now": _dt("23:10"), "live": True, "interactive": False},
        )
        self.assertEqual(turn.action.decision, "SILENT")
        self.assertEqual(turn.action.text, "")

    def test_handle_voice_skips_stt_when_school(self):
        def stt_boom(_a):
            raise AssertionError("STT must not run when already silent")

        rt = TangTangRuntime(members=MEMBERS, llm=_boom, stt=stt_boom)
        result = rt.handle_voice(
            audio=b"x",
            observation={
                "label": "hanghang",
                "school_hours": True,
                "audience_child": True,
                "presence_home": False,
            },
        )
        self.assertEqual(result.decision, "SILENT")


class TestV4NoDoubleBrain(unittest.TestCase):
    def test_v4_block_does_not_call_v3_chat(self):
        src = (CAT / "cat-chat.py").read_text(encoding="utf-8")
        main = src.split("def main(")[1]
        v4 = main.split("TANGTANG_V4_PIPELINE")[1].split("_private_cli_reply")[0]
        self.assertNotIn("chat(args", v4)
        self.assertNotIn("build_persona()", v4)
        self.assertNotIn("cat-chat-history", v4)
        self.assertLess(main.find("_alarm_reply"), main.find("TANGTANG_V4_PIPELINE"))
        self.assertLess(main.find("_may_speak_now"), main.find("TANGTANG_V4_PIPELINE"))

    def test_m4_fallback_uses_chat_adapter_not_history(self):
        src = (CAT / "cat-chat.py").read_text(encoding="utf-8")
        priv = src.split("def _private_cli_reply")[1].split("def main(")[0]
        self.assertIn("ChatAdapter", priv)
        self.assertIn("history=None", priv)
        self.assertNotIn("json.dump", priv)
        self.assertIn("looks_risky", priv)
        main = src.split("def main(")[1]
        self.assertIn("_private_cli_reply", main)
        # main must not dump history files anymore
        self.assertNotIn("cat-chat-history-", main)
    def test_v4_cli_school_child_prints_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["TANGTANG_DATA_DIR"] = tmp
            env["TANGTANG_V4_PIPELINE"] = "1"
            env["TANGTANG_MEMBER_ID"] = "hanghang"
            env["TANGTANG_SPEAKER"] = "hanghang"
            env["TANGTANG_SCHOOL_START"] = "2026-09-01"
            env["TANGTANG_FAKE_TODAY"] = "2026-09-02"
            env["TANGTANG_FAKE_TIME"] = "12:00"
            env["TANGTANG_TTS"] = "0"
            env.pop("TANGTANG_HOST_HANGHANG", None)
            env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            r = subprocess.run(
                [sys.executable, str(CAT / "cat-chat.py"), "糖糖在吗"],
                capture_output=True,
                text=True,
                env=env,
                timeout=20,
                cwd=str(ROOT),
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "")

    def test_llm_payload_has_no_memory_history(self):
        seen: list[dict] = []

        def llm(ctx):
            seen.append(dict(ctx))
            return "汪汪～"

        day = _dt("12:00")
        pipe = PrivacyPipeline(
            members=MEMBERS,
            interrupt=InterruptPolicy(clock=lambda: day),
        )
        rt = TangTangRuntime(members=MEMBERS, pipeline=pipe, llm=llm)
        rt.handle_utterance("糖糖在吗", {"label": "dad", "now": day})
        self.assertTrue(seen)
        self.assertNotIn("memory", seen[-1])
        self.assertNotIn("recent", seen[-1])
        self.assertIn("_filtered_prompt", seen[-1])


class TestLiveWrappersUseGate(unittest.TestCase):
    def test_voice_checks_gate_before_listen(self):
        src = (CAT / "cat-voice.sh").read_text(encoding="utf-8")
        self.assertIn("tangtang-speak-gate.py", src)
        self.assertLess(src.find("tangtang-speak-gate.py"), src.find("cat-listen.sh"))
        self.assertLess(src.find("tangtang-speak-gate.py"), src.find("cat-stt-baidu.sh"))
        self.assertNotIn("再说一次", src)
        self.assertNotIn("再聊聊", src)

    def test_cat_sh_chat_uses_gate(self):
        src = (CAT / "cat.sh").read_text(encoding="utf-8")
        self.assertIn("tangtang-speak-gate.py", src)

    def test_turn_never_calls_cloud_chat(self):
        turn = (CAT / "cat-turn.py").read_text(encoding="utf-8")
        self.assertNotIn("cat-chat.py", turn)
        self.assertNotIn("chat.completions", turn)
        self.assertNotIn("urllib.request", turn)
        self.assertIn("TANGTANG_TURN_LLM is ignored", turn)

    def test_speak_gate_cli_quiet(self):
        env = os.environ.copy()
        env["TANGTANG_FAKE_TODAY"] = "2026-08-31"
        env["TANGTANG_FAKE_TIME"] = "23:40"
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        r = subprocess.run(
            [sys.executable, str(CAT / "tangtang-speak-gate.py"), "--channel", "remind"],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
            cwd=str(ROOT),
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "silent")

    def test_speak_gate_cli_chat_night_is_interactive(self):
        env = os.environ.copy()
        env["TANGTANG_FAKE_TODAY"] = "2026-08-31"
        env["TANGTANG_FAKE_TIME"] = "23:40"
        env["TANGTANG_MEMBER_ID"] = "dad"
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        r = subprocess.run(
            [sys.executable, str(CAT / "tangtang-speak-gate.py"), "--channel", "chat", "--member", "dad"],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
            cwd=str(ROOT),
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "speak")

    def test_speak_gate_cli_alarm_speak(self):
        env = os.environ.copy()
        env["TANGTANG_FAKE_TODAY"] = "2026-08-31"
        env["TANGTANG_FAKE_TIME"] = "23:40"
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        r = subprocess.run(
            [sys.executable, str(CAT / "tangtang-speak-gate.py"), "--channel", "alarm"],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
            cwd=str(ROOT),
        )
        self.assertEqual(r.stdout.strip(), "speak")


if __name__ == "__main__":
    unittest.main()
