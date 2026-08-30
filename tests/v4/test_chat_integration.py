"""Chat adapter: new path cannot skip PrivacyPolicy. PRIVATE bully stays private."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.chat_adapter import ChatAdapter
from core.adapters.family_loader import load_members
from core.errors import MemoryError
from core.memory.family import FamilySummary
from tangtang_runtime import TangTangRuntime

MEMBERS = load_members()
BULLY = "我今天被同学欺负了。"
CHAT_SRC = (ROOT / "core" / "adapters" / "chat_adapter.py").read_text(encoding="utf-8")


class TestChatPrivacyGate(unittest.TestCase):
    def test_adapter_source_goes_through_ingest(self):
        self.assertIn("pipeline.ingest", CHAT_SRC)
        self.assertNotIn("chat(", CHAT_SRC.split("def turn")[1][:800] if "def turn" in CHAT_SRC else "")

    def test_bully_chain_private_not_in_family_or_logs(self):
        calls = {"n": 0}
        from core.policy.privacy_policy import PrivacyPolicy

        real = PrivacyPolicy(MEMBERS)

        class Spy(PrivacyPolicy):
            core_api_version = "4.0.0"

            def assert_event_privacy(self, **kwargs):
                calls["n"] += 1
                return real.assert_event_privacy(**kwargs)

        from core.ingest import PrivacyPipeline

        pipe = PrivacyPipeline(members=MEMBERS, privacy=Spy())
        chat = ChatAdapter(pipeline=pipe, members=MEMBERS)
        turn = chat.turn(BULLY, {"label": "hanghang"})
        self.assertGreaterEqual(calls["n"], 1)
        self.assertEqual(turn.ingest.decision.privacy, "PRIVATE")
        self.assertEqual(turn.ingest.decision.member_id, "hanghang")
        self.assertTrue(turn.ingest.stored_private)
        self.assertFalse(turn.ingest.stored_family)
        self.assertFalse(turn.ingest.stored_summary)
        self.assertFalse(pipe.stores.family.contains_text(BULLY))
        self.assertFalse(pipe.stores.summary.contains_text(BULLY))
        self.assertFalse(pipe.logger.contains_raw(BULLY))
        # Other member context
        dad_ctx = pipe.builder.build(
            who={"member_id": "dad"},
            event=turn.ingest.event,
            privacy_scope="FAMILY",
        )
        self.assertNotIn(BULLY, str(dad_ctx))
        self.assertNotIn("被同学欺负", str(dad_ctx.get("family") or {}))

    def test_structured_summary_does_not_bypass_private(self):
        summary = FamilySummary(privacy=__import__(
            "core.policy.privacy_policy", fromlist=["PrivacyPolicy"]
        ).PrivacyPolicy(MEMBERS))
        with self.assertRaises(MemoryError):
            summary.add_structured(member_id="child_9", mood="sad", interaction_count=1)
        with self.assertRaises(MemoryError):
            summary.add(member_id="hanghang", summary=BULLY)


class TestChatMembers(unittest.TestCase):
    def test_qiaqia_private(self):
        chat = ChatAdapter(members=MEMBERS)
        turn = chat.turn("今天有点累", {"label": "qiaqia"})
        self.assertEqual(turn.ingest.decision.privacy, "PRIVATE")
        self.assertEqual(turn.ingest.decision.member_id, "qiaqia")

    def test_dad_family(self):
        chat = ChatAdapter(members=MEMBERS)
        turn = chat.turn("晚饭做好了", {"label": "dad"})
        self.assertEqual(turn.ingest.decision.privacy, "FAMILY")
        self.assertTrue(turn.ingest.stored_family)

    def test_grandpa_family(self):
        chat = ChatAdapter(members=MEMBERS)
        turn = chat.turn("糖糖，帮我看看明天天气。", {"label": "grandpa"})
        self.assertEqual(turn.ingest.decision.privacy, "FAMILY")
        self.assertEqual(turn.action.decision, "SPEAK")

    def test_unknown_public(self):
        chat = ChatAdapter(members=MEMBERS)
        turn = chat.turn("你好糖糖", {"label": "unknown"})
        self.assertEqual(turn.ingest.decision.privacy, "PUBLIC")
        self.assertIsNone(turn.ingest.decision.member_id)


class TestChatLlmFailure(unittest.TestCase):
    def test_llm_down_falls_back_wangwang(self):
        def boom(_ctx):
            raise ConnectionError("llm down")

        rt = TangTangRuntime(members=MEMBERS, llm=boom)
        result = rt.handle_utterance("糖糖在吗", {"label": "dad"})
        self.assertEqual(result.action.text, "汪汪～")
        self.assertTrue(result.event_kept)
        self.assertEqual(result.decision, "SPEAK")

    def test_llm_only_sees_filtered_prompt(self):
        seen: list[str] = []

        def llm(ctx):
            seen.append(str(ctx.get("_filtered_prompt") or ctx))
            return "汪汪～ 爸爸，糖糖在。"

        rt = TangTangRuntime(members=MEMBERS, llm=llm)
        # First store child private
        rt.handle_utterance(BULLY, {"label": "child_9"})
        result = rt.handle_utterance("晚饭好了吗", {"label": "dad"})
        self.assertTrue(result.event_kept)
        self.assertNotIn(BULLY, seen[-1] if seen else "")


class TestChatV3NotDeleted(unittest.TestCase):
    def test_cat_chat_file_still_exists(self):
        path = ROOT / "code" / "cat" / "cat-chat.py"
        self.assertTrue(path.is_file())
        src = path.read_text(encoding="utf-8")
        self.assertIn("TANGTANG_V4_PIPELINE", src)
        self.assertIn("def chat(", src)


if __name__ == "__main__":
    unittest.main()
