"""Forbidden surveillance / toddler / lecture copy must never ship."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.persona.copy import WALK_SUGGESTION, CopyGuard, looks_surveillance
from core.response.orchestrator import ResponseOrchestrator

SURVEIL = "我知道你刚才玩了 43 分钟手机。"


class TestForbiddenSurveillance(unittest.TestCase):
    def test_direct_phrase_rewritten(self):
        guard = CopyGuard()
        out = guard.sanitize(SURVEIL, member_id="child_9", role="play")
        self.assertEqual(out, WALK_SUGGESTION)
        self.assertIn("要不要起来走一走", out)
        self.assertNotIn("43", out)
        self.assertNotIn("分钟手机", out)
        self.assertTrue(looks_surveillance(SURVEIL))
        self.assertFalse(looks_surveillance(out))

    def test_orchestrator_strips_leaky_responder(self):
        orch = ResponseOrchestrator(responder=lambda ctx: SURVEIL)
        action = orch.run(
            decision="SPEAK",
            context={"who": {"member_id": "child_9"}, "utterance": "（玩手机）"},
        )
        self.assertEqual(action.text, WALK_SUGGESTION)
        self.assertNotIn("43 分钟", action.text)
        self.assertNotIn("我知道你刚才玩了", action.text)

    def test_adult_toddler_talk_stripped(self):
        orch = ResponseOrchestrator(responder=lambda ctx: "宝宝该吃饭饭啦，觉觉时间到了")
        action = orch.run(
            decision="SPEAK",
            context={"who": {"member_id": "dad"}, "utterance": "我回来了"},
        )
        self.assertNotIn("宝宝", action.text)
        self.assertNotIn("吃饭饭", action.text)
        self.assertTrue(action.text.startswith("汪汪～"))

    def test_sister_not_toddler(self):
        orch = ResponseOrchestrator(responder=lambda ctx: "宝宝乖哦，我们去觉觉")
        action = orch.run(
            decision="SPEAK",
            context={"who": {"member_id": "child_12"}, "utterance": "好无聊"},
        )
        self.assertNotIn("宝宝", action.text)
        self.assertNotIn("觉觉", action.text)

    def test_brother_not_lecture(self):
        orch = ResponseOrchestrator(responder=lambda ctx: "作为家长我警告你立刻停止")
        action = orch.run(
            decision="SPEAK",
            context={"who": {"member_id": "child_9"}, "utterance": "我想打游戏"},
        )
        self.assertNotIn("作为家长", action.text)
        self.assertNotIn("立刻停止", action.text)


class TestForbiddenEmptyUnknown(unittest.TestCase):
    def test_empty_text(self):
        self.assertEqual(CopyGuard().sanitize("", role="adult"), "")
        self.assertFalse(looks_surveillance(""))

    def test_unknown_plain_line_kept(self):
        line = "汪汪～ 糖糖在呢。"
        self.assertEqual(CopyGuard().sanitize(line, role="adult"), line)


if __name__ == "__main__":
    unittest.main()
