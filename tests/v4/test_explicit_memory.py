"""Explicit preference memory commands stay local, structured and owner-only."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.chat_adapter import ChatAdapter
from core.adapters.family_loader import load_members
from core.memory.explicit_intents import parse_memory_intent
from core.memory.private import PrivateMemory
from core.memory.store import Memory
from core.ingest import PrivacyPipeline
from core.policy.privacy_policy import PrivacyPolicy

MEMBERS = load_members()


class TestExplicitIntentParser(unittest.TestCase):
    def test_parse_remember_forget_and_recall(self):
        self.assertEqual(
            parse_memory_intent("糖糖，记住我喜欢恐龙。").__dict__,
            {"action": "remember", "category": "likes", "value": "恐龙"},
        )
        self.assertEqual(
            parse_memory_intent("记住我最喜欢海豚") .__dict__,
            {"action": "remember", "category": "favorite", "value": "海豚"},
        )
        self.assertEqual(
            parse_memory_intent("忘记我不喜欢香菜").__dict__,
            {"action": "forget", "category": "dislikes", "value": "香菜"},
        )
        self.assertEqual(
            parse_memory_intent("你记得我喜欢什么吗？").__dict__,
            {"action": "recall", "category": None, "value": None},
        )
        self.assertEqual(
            parse_memory_intent("我不喜欢什么？").__dict__,
            {"action": "recall", "category": "dislikes", "value": None},
        )

    def test_ambiguous_sentences_do_not_create_memory_intents(self):
        self.assertIsNone(parse_memory_intent("我喜欢恐龙"))
        self.assertIsNone(parse_memory_intent("记住今天很开心"))
        self.assertIsNone(parse_memory_intent("记住我喜欢" + "恐龙" * 50))


class TestExplicitMemoryChat(unittest.TestCase):
    def test_child_remember_is_structured_local_and_does_not_store_command(self):
        calls = []
        pipe = PrivacyPipeline(members=MEMBERS)
        chat = ChatAdapter(
            pipeline=pipe,
            members=MEMBERS,
            llm=lambda payload: calls.append(dict(payload)) or "不应该调用云端",
        )
        turn = chat.turn("糖糖，记住我喜欢恐龙。", {"label": "hanghang"})
        self.assertEqual(turn.action.action, "memory_remember")
        self.assertIn("恐龙", turn.action.text)
        self.assertEqual(turn.ingest.decision.privacy, "PRIVATE")
        self.assertEqual(turn.ingest.event.payload, {"redacted": True})
        self.assertFalse(turn.ingest.stored_private)
        self.assertEqual(calls, [])

        rows = pipe.stores.private.query(member_id="child_9", viewer_id="child_9")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "preference")
        self.assertEqual(rows[0]["data"], {"tag": "likes", "value": "恐龙"})
        self.assertNotIn("speech", rows[0]["data"])
        self.assertFalse(pipe.logger.contains_raw("糖糖，记住我喜欢恐龙。"))

    def test_recall_and_forget_use_only_current_members_private_preferences(self):
        pipe = PrivacyPipeline(members=MEMBERS)
        chat = ChatAdapter(pipeline=pipe, members=MEMBERS, llm=lambda _p: self.fail("LLM should not run"))
        saved = chat.turn("记住我喜欢恐龙", {"label": "hanghang"})
        recalled = chat.turn("糖糖，你还记得我喜欢什么吗？", {"label": "hanghang"})
        self.assertEqual(saved.action.action, "memory_remember")
        self.assertEqual(recalled.action.action, "memory_recall")
        self.assertIn("恐龙", recalled.action.text)
        self.assertEqual(recalled.ingest.event.payload, {"redacted": True})
        self.assertFalse(recalled.ingest.stored_private)

        forgotten = chat.turn("忘记我喜欢恐龙", {"label": "hanghang"})
        self.assertEqual(forgotten.action.action, "memory_forget")
        self.assertIn("忘", forgotten.action.text)
        after = chat.turn("我喜欢什么？", {"label": "hanghang"})
        self.assertNotIn("恐龙", after.action.text)

    def test_adult_explicit_preference_is_private_not_family_shared(self):
        pipe = PrivacyPipeline(members=MEMBERS)
        chat = ChatAdapter(pipeline=pipe, members=MEMBERS, llm=lambda _p: self.fail("LLM should not run"))
        turn = chat.turn("记住我喜欢短一点的回答", {"label": "dad"})
        self.assertEqual(turn.ingest.decision.privacy, "PRIVATE")
        self.assertEqual(turn.ingest.event.payload, {"redacted": True})
        self.assertFalse(turn.ingest.stored_family)
        self.assertFalse(pipe.stores.family.contains_text("短一点的回答"))
        rows = pipe.stores.private.query(member_id="dad", viewer_id="dad")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "preference")

    def test_unknown_speaker_cannot_save_or_read_personal_memory(self):
        calls = []
        chat = ChatAdapter(
            members=MEMBERS,
            llm=lambda payload: calls.append(dict(payload)) or "云端不应该被调用",
        )
        turn = chat.turn("记住我喜欢恐龙", {"label": "unknown"})
        self.assertIsNone(turn.ingest.decision.member_id)
        self.assertEqual(turn.ingest.event.payload, {"redacted": True})
        self.assertEqual(calls, [])
        self.assertNotEqual(turn.action.action, "memory_remember")


class TestStructuredPrivatePreferencePersistence(unittest.TestCase):
    def test_preference_survives_restart_and_forget_rewrites_file(self):
        with tempfile.TemporaryDirectory() as td:
            privacy = PrivacyPolicy(MEMBERS)
            first = PrivateMemory(home=td, persist=True, privacy=privacy)
            first.remember_preference(member_id="child_9", category="likes", value="恐龙")
            path = Path(td) / "private" / "child_9" / "memories.json"
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved), 1)
            self.assertNotIn("speech", saved[0]["data"])

            second = PrivateMemory(home=td, persist=True, privacy=privacy)
            rows = second.query(member_id="child_9", viewer_id="child_9")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["data"]["value"], "恐龙")
            self.assertEqual(second.query(member_id="child_9", viewer_id="dad"), [])
            self.assertEqual(second.forget_preference(member_id="child_9", category="likes", value="恐龙"), 1)
            third = PrivateMemory(home=td, persist=True, privacy=privacy)
            self.assertEqual(third.query(member_id="child_9", viewer_id="child_9"), [])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()
