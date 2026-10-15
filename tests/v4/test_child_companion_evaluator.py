"""Unit tests for the offline corpus evaluator (no network or model calls)."""
import unittest

from scripts.evaluate_child_companion_corpus import (
    analyze_corpus,
    build_report,
    build_review_rows,
    load_corpus,
    summarize_scores,
)


class OfflineCorpusEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = load_corpus()
        cls.stats = analyze_corpus(cls.corpus)

    def test_analysis_reports_expected_coverage_without_structural_gaps(self):
        self.assertEqual(self.stats["examples"], 74)
        self.assertEqual(self.stats["context_examples"], 40)
        self.assertEqual(self.stats["deep_context_examples"], 20)
        self.assertEqual(self.stats["negative_pair_examples"], 20)
        self.assertEqual(self.stats["age_pair_scenarios"], 10)
        self.assertEqual(self.stats["duplicate_ids"], [])
        self.assertEqual(self.stats["malformed_examples"], [])
        self.assertEqual(self.stats["bad_age_pairs"], [])
        self.assertEqual(self.stats["safety_direction_gaps"], [])

    def test_blind_review_template_omits_reference_answers(self):
        rows = build_review_rows(self.corpus)
        self.assertEqual(len(rows), 74)
        self.assertIn("conversation_context", rows[0])
        self.assertIn("model_response", rows[0])
        self.assertNotIn("target_response", rows[0])
        self.assertNotIn("negative_response", rows[0])
        self.assertNotIn("failure_reason", rows[0])
        self.assertIn("context_fit_score", rows[0])
        self.assertIn("safety_privacy_score", rows[0])

    def test_score_summary_flags_zero_safety_score_for_high_risk(self):
        fields = [
            "context_fit_score", "naturalness_score", "age_fit_score",
            "autonomy_score", "safety_privacy_score",
        ]
        high = {
            "sample_id": "risk_01",
            "safety_level": "high",
            **{field: "2" for field in fields},
        }
        high["safety_privacy_score"] = "0"
        normal = {
            "sample_id": "normal_01",
            "safety_level": "normal",
            **{field: "1" for field in fields},
        }
        result = summarize_scores([high, normal])
        self.assertEqual(result["completed_rows"], 2)
        self.assertEqual(result["incomplete_rows"], 0)
        self.assertEqual(result["averages"]["safety_privacy_score"], 0.5)
        self.assertEqual(result["high_risk_safety_zero"], ["risk_01"])
        self.assertEqual(result["invalid_scores"], [])

    def test_report_states_automation_limitations(self):
        report = build_report(self.stats, label="test-run", score_summary=summarize_scores([]))
        self.assertIn("test-run", report)
        self.assertIn("不自动调用模型", report)
        self.assertIn("人工评分", report)


if __name__ == "__main__":
    unittest.main()
