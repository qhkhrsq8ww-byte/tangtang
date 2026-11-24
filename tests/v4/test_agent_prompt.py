"""Regression tests for the Hermes system prompt structure."""
from __future__ import annotations

import unittest

from core.persona.agent_prompt import build_agent_system_prompt


class TestAgentSystemPrompt(unittest.TestCase):
    def test_sections_are_separated_by_real_newlines(self):
        prompt = build_agent_system_prompt("child_9")
        self.assertEqual(prompt.count("\n"), 7)
        self.assertNotIn("\\n", prompt)
        self.assertIn("\n安全与隐私规则：", prompt)
        self.assertIn("\n不要声称监视或追踪孩子", prompt)

    def test_child_profiles_receive_distinct_audience_guidance(self):
        younger = build_agent_system_prompt("child_9")
        older = build_agent_system_prompt("child_12")
        self.assertIn("儿童玩伴模式", younger)
        self.assertIn("平等、尊重边界的朋友", older)
        self.assertNotEqual(younger, older)

    def test_unknown_identity_does_not_assume_family_member(self):
        prompt = build_agent_system_prompt(None)
        self.assertIn("当前说话人身份未知", prompt)
        self.assertIn("不提及任何家庭成员的私人信息", prompt)


if __name__ == "__main__":
    unittest.main()
