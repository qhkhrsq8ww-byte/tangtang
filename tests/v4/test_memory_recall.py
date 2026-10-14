"""Structured-memory retrieval is bounded by owner, scope and allowlisted fields."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.chat_adapter import ChatAdapter
from core.adapters.family_loader import load_members
from core.memory.store import Memory
from core.ingest import PrivacyPipeline

MEMBERS = load_members()


class TestMemoryRecall(unittest.TestCase):
    def test_authorized_structured_fact_reaches_adult_prompt(self):
        received = []
        pipe = PrivacyPipeline(members=MEMBERS)
        pipe.stores.family.put(Memory(
            memory_id="preference-short-reply",
            member_id="dad",
            type="preference",
            privacy="FAMILY",
            data={"tag": "communication", "value": "prefer short replies"},
        ))
        # A raw utterance is stored in FamilyMemory for adults by ingest, but is never recalled.
        pipe.stores.family.put(Memory(
            memory_id="raw-utterance-row",
            member_id="dad",
            type="utterance",
            privacy="FAMILY",
            data={"speech": "PRIVATE_RAW_SHOULD_NOT_REACH_PROMPT"},
        ))
        chat = ChatAdapter(
            pipeline=pipe,
            members=MEMBERS,
            llm=lambda payload: received.append(dict(payload)) or "好，我尽量说得简短。",
        )
        turn = chat.turn("糖糖，帮我安排一下", {"label": "dad"})
        self.assertEqual(turn.action.text, "好，我尽量说得简短。")
        prompt = received[0]["_filtered_prompt"]
        self.assertIn("authorized_memory", prompt)
        self.assertIn("prefer short replies", prompt)
        self.assertNotIn("PRIVATE_RAW_SHOULD_NOT_REACH_PROMPT", prompt)
        self.assertNotIn("raw-utterance-row", prompt)

    def test_raw_utterance_is_never_recalled_even_for_owner(self):
        pipe = PrivacyPipeline(members=MEMBERS)
        pipe.stores.family.put(Memory(
            memory_id="utterance-only",
            member_id="dad",
            type="utterance",
            privacy="FAMILY",
            data={"speech": "do not repeat the transcript"},
        ))
        chat = ChatAdapter(pipeline=pipe, members=MEMBERS, llm=lambda _p: "记下了。")
        turn = chat.turn("现在开始", {"label": "dad"})
        self.assertEqual(turn.context.get("recall"), [])
        self.assertNotIn("do not repeat the transcript", str(turn.context.get("recall")))

    def test_different_viewer_does_not_receive_owners_recall(self):
        pipe = PrivacyPipeline(members=MEMBERS)
        pipe.stores.family.put(Memory(
            memory_id="dad-pref",
            member_id="dad",
            type="preference",
            privacy="FAMILY",
            data={"tag": "preference", "value": "dad-only test fact"},
        ))
        received = []
        chat = ChatAdapter(
            pipeline=pipe,
            members=MEMBERS,
            llm=lambda payload: received.append(dict(payload)) or "糖糖在呢。",
        )
        turn = chat.turn("你好", {"label": "dad"}, viewer_id="mom")
        self.assertEqual(turn.context.get("recall"), [])
        self.assertNotIn("dad-only test fact", received[0]["_filtered_prompt"])

    def test_private_raw_memory_is_not_in_structured_recall(self):
        pipe = PrivacyPipeline(members=MEMBERS)
        pipe.stores.private.put(member_id="hanghang", utterance="my private words")
        chat = ChatAdapter(pipeline=pipe, members=MEMBERS)
        turn = chat.turn("我喜欢恐龙", {"label": "hanghang"})
        self.assertEqual(turn.ingest.decision.privacy, "PRIVATE")
        self.assertNotIn("my private words", str(turn.context.get("recall")))
        self.assertTrue(all(row.get("type") != "utterance" for row in turn.context.get("recall", [])))


if __name__ == "__main__":
    unittest.main()
