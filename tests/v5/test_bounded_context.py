"""V5 bounded context tests."""
from __future__ import annotations
import unittest
from core.context.builder import ContextBuilder

class Memory:
    def query(self, **kwargs): return []
class Policy:
    def decide(self, obs): return "RESPOND"

class TestBoundedConversationContext(unittest.TestCase):
    def test_recent_is_member_scoped_and_secrets_removed(self):
        b=ContextBuilder(Memory(), Policy(), max_recent=5)
        out=b.build(
            who={"member_id":"child_9"},
            event={},
            observation={"utterance":"你好"},
            recent=[
                {"member_id":"child_9","text":"我的作业还没写","secrets":["x"]},
                {"member_id":"child_12","text":"姐姐的私事"},
            ],
            privacy_scope="PRIVATE",
            viewer_id="child_9",
        )
        self.assertEqual(len(out["conversation_context"]),1)
        self.assertEqual(out["conversation_context"][0]["text"],"我的作业还没写")
        self.assertNotIn("secrets",out["conversation_context"][0])

if __name__=="__main__":
    unittest.main()
