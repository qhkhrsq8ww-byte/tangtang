"""m4: cat-chat opt-out / V4-fail still goes through PrivacyPipeline."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.family_loader import load_members

MEMBERS = load_members()
BULLY = "我今天被同学欺负了。"


def _load_cat_chat():
    path = ROOT / "code" / "cat" / "cat-chat.py"
    spec = importlib.util.spec_from_file_location("cat_chat_m4", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class TestM4PrivateCliReply(unittest.TestCase):
    def test_opt_out_path_ingests_private_child(self):
        chat = _load_cat_chat()
        seen = {"n": 0}

        def llm(ctx):
            seen["n"] += 1
            self.assertIn("_filtered_prompt", ctx)
            self.assertNotIn("memory", ctx)
            return "汪汪～ 糖糖陪着你。"

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(chat, "DATA_DIR", td):
                with mock.patch.object(chat, "chat", side_effect=AssertionError("raw chat")):
                    from core.adapters.chat_adapter import ChatAdapter
                    from core.ingest import PrivacyPipeline

                    pipe = PrivacyPipeline(members=MEMBERS)
                    turn = ChatAdapter(
                        pipeline=pipe,
                        members=MEMBERS,
                        llm=llm,
                        looks_risky=chat.looks_risky,
                        sanitize=chat.sanitize_output,
                    ).turn(BULLY, {"label": "hanghang", "live": True, "interactive": True})
            self.assertEqual(turn.ingest.decision.privacy, "PRIVATE")
            self.assertTrue(turn.ingest.stored_private)
            self.assertFalse(turn.ingest.stored_family)
            self.assertFalse(pipe.stores.family.contains_text(BULLY))
            self.assertFalse(pipe.logger.contains_raw(BULLY))
            self.assertEqual(seen["n"], 1)

    def test_private_cli_risk_no_llm(self):
        chat = _load_cat_chat()
        printed = []

        def boom(_ctx):
            raise AssertionError("llm must not run on risk")

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(chat, "DATA_DIR", td):
                with mock.patch.object(chat, "_escalate_risk", return_value=None):
                    with mock.patch.object(chat, "emit_character_state"):
                        with mock.patch.object(chat, "_learn_turn"):
                            with mock.patch("builtins.print", side_effect=printed.append):
                                with mock.patch(
                                    "core.adapters.chat_adapter.ChatAdapter"
                                ) as Adapter:
                                    chat._private_cli_reply(
                                        "我不想活了",
                                        {"label": "hanghang", "live": True},
                                    )
                                    Adapter.assert_not_called()
        self.assertEqual(printed, [chat.SAFE_REPLY])

    def test_private_cli_llm_gets_filtered_not_history(self):
        chat = _load_cat_chat()
        captured = []

        def fake_chat(prompt, model=None, history=None):
            captured.append({"prompt": prompt, "history": history})
            return "汪汪～"

        with tempfile.TemporaryDirectory() as td:
            os.environ["TANGTANG_DATA_DIR"] = td
            with mock.patch.object(chat, "DATA_DIR", td):
                with mock.patch.object(chat, "chat", side_effect=fake_chat):
                    with mock.patch.object(chat, "emit_character_state"):
                        with mock.patch.object(chat, "_learn_turn"):
                            with mock.patch("builtins.print"):
                                chat._private_cli_reply(
                                    "糖糖在吗",
                                    {"label": "dad", "live": True, "interactive": True},
                                )
        self.assertTrue(captured)
        self.assertIsNone(captured[0]["history"])
        self.assertIn("utterance=", captured[0]["prompt"])


if __name__ == "__main__":
    unittest.main()
