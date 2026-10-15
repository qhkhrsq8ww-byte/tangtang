"""Structural regression tests for the synthetic child companion corpus."""
import json
import unittest
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "data" / "corpus" / "child_companion_benchmark_v1.json"


def load_corpus():
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


class ChildCompanionCorpusTests(unittest.TestCase):
    def test_corpus_has_unique_ids_and_expected_schema(self):
        corpus = load_corpus()
        examples = corpus["examples"]
        self.assertEqual(corpus["schema_version"], "1.1")
        self.assertEqual(corpus["version"], "V1.1")
        self.assertTrue(corpus["provenance"]["synthetic_only"])
        self.assertFalse(corpus["provenance"]["real_child_data"])
        self.assertGreaterEqual(len(examples), 70)

        ids = [item["id"] for item in examples]
        self.assertEqual(len(ids), len(set(ids)))
        required = {
            "id", "age", "category", "trigger", "context",
            "user_utterance", "target_response", "response_strategy",
            "avoid", "safety_level", "synthetic",
        }
        for item in examples:
            self.assertTrue(required <= item.keys(), item["id"])
            self.assertIn(item["age"], (9, 12), item["id"])
            self.assertTrue(item["synthetic"], item["id"])
            self.assertTrue(item["user_utterance"].strip(), item["id"])
            self.assertTrue(item["target_response"].strip(), item["id"])
            self.assertTrue(item["response_strategy"], item["id"])
            self.assertIn(item["safety_level"], {"normal", "sensitive", "high"})

        with_context = [item for item in examples if item["context"]]
        without_context = [item for item in examples if not item["context"]]
        self.assertGreaterEqual(len(with_context), 40)
        self.assertGreaterEqual(len(without_context), 30)
        self.assertEqual(corpus["counts"]["examples"], len(examples))
        self.assertEqual(corpus["counts"]["multi_turn_examples"], len(with_context))
        self.assertEqual(corpus["counts"]["single_turn_examples"], len(without_context))
        self.assertEqual(corpus["counts"]["categories"], len({item["category"] for item in examples}))

    def test_corpus_covers_key_child_companion_categories(self):
        categories = {item["category"] for item in load_corpus()["examples"]}
        self.assertTrue({
            "日常聊天", "情绪与挫折", "学习与习惯", "朋友与冲突",
            "隐私与信任", "安全与求助", "误解与修复", "语音交互", "自主成长",
        } <= categories)

    def test_deep_context_examples_have_negative_pairs_and_failure_reasons(self):
        examples = load_corpus()["examples"]
        deep = [item for item in examples if item.get("multi_turn_depth", 0) >= 5]
        paired = [
            item for item in examples
            if item.get("negative_response") and item.get("failure_reason")
        ]
        self.assertGreaterEqual(len(deep), 20)
        self.assertGreaterEqual(len(paired), 20)
        for item in paired:
            self.assertTrue(item["negative_response"].strip(), item["id"])
            self.assertTrue(item["failure_reason"].strip(), item["id"])
            self.assertNotEqual(item["negative_response"], item["target_response"])
            self.assertGreaterEqual(len(item["context"]), 5)
            self.assertEqual(item["multi_turn_depth"], len(item["context"]))
            self.assertTrue({"long_context", "negative_pair", "age_pair"} <= set(item["evaluation_tags"]))

    def test_age_paired_scenarios_cover_both_age_groups(self):
        paired = defaultdict(set)
        for item in load_corpus()["examples"]:
            pair_id = item.get("age_pair_id")
            if pair_id:
                paired[pair_id].add(item["age"])
        self.assertGreaterEqual(len(paired), 10)
        self.assertTrue(all(ages == {9, 12} for ages in paired.values()))
        self.assertEqual(load_corpus()["counts"]["age_pair_scenarios"], len(paired))

    def test_high_risk_examples_have_explicit_safety_direction(self):
        high_risk = [
            item for item in load_corpus()["examples"]
            if item["category"] == "安全与求助"
        ]
        self.assertGreaterEqual(len(high_risk), 6)
        self.assertTrue(all(item["safety_level"] == "high" for item in high_risk))
        self.assertTrue(all(
            any(token in item["target_response"] for token in ("可信任", "大人", "医疗", "急救", "紧急服务"))
            for item in high_risk
        ))

    def test_privacy_examples_do_not_disclose_another_member_conversation(self):
        examples = [
            item for item in load_corpus()["examples"]
            if item["category"] == "隐私与信任"
        ]
        self.assertTrue(any("不能告诉你" in item["target_response"] for item in examples))
        self.assertTrue(any("地址" in item["user_utterance"] for item in examples))


if __name__ == "__main__":
    unittest.main()
