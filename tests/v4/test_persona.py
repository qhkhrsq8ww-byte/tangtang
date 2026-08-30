"""Six family utterances map to the right 糖糖 persona (not a supervisor)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.persona.copy import LECTURE_TOKENS, TODDLER_TOKENS
from core.persona.profiles import PERSONAS, SIX_UTTERANCES, PersonaRenderer, profile_for

V4_MEMBERS = {
    "grandpa": {"display_name": "爷爷", "relation": "elder", "aliases": ["爷爷"]},
    "grandma": {"display_name": "奶奶", "relation": "elder", "aliases": ["奶奶"]},
    "dad": {"display_name": "爸爸", "profile": "adult", "aliases": ["爸爸"]},
    "mom": {"display_name": "妈妈", "profile": "adult", "aliases": ["妈妈"]},
    "child_12": {
        "display_name": "姐姐",
        "relation": "child",
        "age": 12,
        "aliases": ["姐姐", "qiaqia", "洽洽"],
    },
    "child_9": {
        "display_name": "弟弟",
        "relation": "child",
        "age": 9,
        "aliases": ["弟弟", "hanghang", "航航"],
    },
}


class TestPersonaSixUtterances(unittest.TestCase):
    def setUp(self):
        self.r = PersonaRenderer(V4_MEMBERS)

    def test_six_members_get_correct_role_and_tone(self):
        expected_role = {
            "grandpa": "elder",
            "grandma": "elder",
            "dad": "adult",
            "mom": "adult",
            "child_12": "friend",
            "child_9": "play",
        }
        for member_id, utterance, _expected in SIX_UTTERANCES:
            reply = self.r.reply(member_id=member_id, utterance=utterance)
            self.assertEqual(reply.role, expected_role[member_id], member_id)
            self.assertTrue(reply.text.startswith("汪汪～"), reply.text)
            if expected_role[member_id] in {"elder", "adult"}:
                for tok in TODDLER_TOKENS:
                    self.assertNotIn(tok, reply.text, f"{member_id} childish {tok}")
            if member_id == "child_12":
                for tok in TODDLER_TOKENS:
                    self.assertNotIn(tok, reply.text, f"姐姐 toddler {tok}")
            if member_id == "child_9":
                for tok in LECTURE_TOKENS:
                    self.assertNotIn(tok, reply.text, f"弟弟 lecture {tok}")

    def test_exact_six_lines(self):
        for member_id, utterance, expected in SIX_UTTERANCES:
            self.assertEqual(
                self.r.reply_text(member_id=member_id, utterance=utterance),
                expected,
                member_id,
            )

    def test_sister_alias_qiaqia_not_toddler(self):
        text = self.r.reply_text(member_id="qiaqia", utterance="好无聊，不想写作业。")
        self.assertTrue(text.startswith("汪汪～"))
        self.assertNotIn("宝宝", text)
        self.assertNotIn("吃饭饭", text)
        self.assertEqual(profile_for("姐姐", V4_MEMBERS), "friend")

    def test_brother_alias_hanghang_not_lecture(self):
        text = self.r.reply_text(member_id="hanghang", utterance="我想打游戏！")
        self.assertTrue(text.startswith("汪汪～"))
        self.assertNotIn("作为家长", text)
        self.assertNotIn("立刻停止", text)
        self.assertEqual(profile_for("弟弟", V4_MEMBERS), "play")


class TestPersonaEmptyUnknown(unittest.TestCase):
    def test_empty_member_falls_back(self):
        r = PersonaRenderer()
        reply = r.reply(member_id=None, utterance="")
        self.assertEqual(reply.member_id, "unknown")
        self.assertTrue(reply.text.startswith("汪汪～"))

    def test_unknown_visitor(self):
        r = PersonaRenderer(V4_MEMBERS)
        reply = r.reply(member_id="邻居", utterance="你好")
        self.assertIn("汪汪～", reply.text)
        self.assertNotIn("宝宝", reply.text)

    def test_personas_cover_six(self):
        self.assertEqual(
            set(PERSONAS),
            {"grandpa", "grandma", "dad", "mom", "child_12", "child_9"},
        )


if __name__ == "__main__":
    unittest.main()
