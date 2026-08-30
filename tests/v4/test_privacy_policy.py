"""PrivacyPolicy: child fail-closed PRIVATE; adult FAMILY unless clearly private."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.interfaces import PrivacyPolicyPort
from core.policy.privacy_policy import (
    DEST_FAMILY_MEMORY,
    DEST_FAMILY_SUMMARY,
    DEST_HABIT_STORE,
    DEST_ORDINARY_LOG,
    DEST_PARENT_CONTEXT,
    DEST_PRIVATE_MEMORY,
    PrivacyPolicy,
)

V4_MEMBERS = {
    "grandpa": {"display_name": "爷爷", "relation": "elder", "aliases": ["爷爷"]},
    "grandma": {"display_name": "奶奶", "relation": "elder", "aliases": ["奶奶"]},
    "dad": {"display_name": "爸爸", "profile": "adult", "aliases": ["爸爸"]},
    "mom": {"display_name": "妈妈", "profile": "adult", "aliases": ["妈妈", "妈"]},
    "child_12": {
        "display_name": "姐姐",
        "relation": "child",
        "age": 12,
        "aliases": ["姐姐", "12岁女孩"],
    },
    "child_9": {
        "display_name": "弟弟",
        "relation": "child",
        "age": 9,
        "aliases": ["弟弟", "9岁男孩"],
    },
}

BULLY = "我今天被同学欺负了。"


class TestPrivacyPolicyHappy(unittest.TestCase):
    def setUp(self):
        self.p = PrivacyPolicy(V4_MEMBERS)
        self.assertIsInstance(self.p, PrivacyPolicyPort)

    def test_child_bully_is_private(self):
        for label in ("child_9", "hanghang", "弟弟", "航航", "9岁弟弟"):
            decision = self.p.classify(member_id=label, utterance=BULLY)
            self.assertEqual(decision.privacy, "PRIVATE", label)
            self.assertTrue(decision.is_child, label)
            self.assertEqual(decision.member_id, "child_9", label)

    def test_sister_unknown_utterance_fail_closed(self):
        decision = self.p.classify(member_id="qiaqia", utterance="今天天气真好")
        self.assertEqual(decision.privacy, "PRIVATE")
        self.assertTrue(decision.is_child)
        self.assertEqual(decision.member_id, "child_12")

    def test_adult_similar_talk_is_family(self):
        decision = self.p.classify(member_id="dad", utterance=BULLY)
        self.assertEqual(decision.privacy, "FAMILY")
        self.assertFalse(decision.is_child)
        self.assertTrue(decision.allow_family_memory)

    def test_adult_clearly_private(self):
        decision = self.p.classify(member_id="dad", utterance="这是我的私人信息，别告诉孩子")
        self.assertEqual(decision.privacy, "PRIVATE")
        self.assertFalse(decision.allow_family_memory)

    def test_unknown_visitor_public(self):
        decision = self.p.classify(member_id=None, utterance="你好糖糖")
        self.assertEqual(decision.privacy, "PUBLIC")


class TestPrivacyPolicyRouting(unittest.TestCase):
    def setUp(self):
        self.p = PrivacyPolicy(V4_MEMBERS)

    def test_child_raw_blocked_from_family_destinations(self):
        for dest in (
            DEST_FAMILY_MEMORY,
            DEST_FAMILY_SUMMARY,
            DEST_PARENT_CONTEXT,
            DEST_HABIT_STORE,
            DEST_ORDINARY_LOG,
        ):
            self.assertFalse(
                self.p.allow_destination(dest, member_id="hanghang", utterance=BULLY),
                dest,
            )
        self.assertTrue(
            self.p.allow_destination(
                DEST_PRIVATE_MEMORY, member_id="child_9", utterance=BULLY, privacy="PRIVATE"
            )
        )

    def test_cannot_downgrade_child_to_family(self):
        decision = self.p.assert_event_privacy(
            member_id="child_9", utterance=BULLY, requested="FAMILY"
        )
        self.assertEqual(decision.privacy, "PRIVATE")

    def test_adult_family_allowed(self):
        self.assertTrue(
            self.p.allow_destination(
                DEST_FAMILY_MEMORY, member_id="mom", utterance="晚饭做好了"
            )
        )


class TestPrivacyPolicyEmptyUnknown(unittest.TestCase):
    def test_empty_utterance_child_still_private(self):
        p = PrivacyPolicy(V4_MEMBERS)
        decision = p.classify(member_id="弟弟", utterance="")
        self.assertEqual(decision.privacy, "PRIVATE")

    def test_unknown_label(self):
        p = PrivacyPolicy(V4_MEMBERS)
        self.assertFalse(p.is_child("邻居"))
        decision = p.classify(member_id="邻居小孩", utterance="你好")
        self.assertEqual(decision.privacy, "FAMILY")
        self.assertIsNone(p.canonical_member_id("邻居小孩"))


if __name__ == "__main__":
    unittest.main()
