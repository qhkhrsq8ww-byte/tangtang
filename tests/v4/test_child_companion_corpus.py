"""Structural regression tests for the synthetic child companion corpus."""
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "data" / "corpus" / "child_companion_benchmark_v1.json"


def load_corpus():
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def test_corpus_has_unique_ids_and_expected_schema():
    corpus = load_corpus()
    examples = corpus["examples"]
    assert corpus["schema_version"] == "1.1"
    assert corpus["version"] == "V1.1"
    assert corpus["provenance"]["synthetic_only"] is True
    assert corpus["provenance"]["real_child_data"] is False
    assert len(examples) >= 70
    ids = [item["id"] for item in examples]
    assert len(ids) == len(set(ids))
    required = {
        "id", "age", "category", "trigger", "context",
        "user_utterance", "target_response", "response_strategy",
        "avoid", "safety_level", "synthetic",
    }
    for item in examples:
        assert required <= item.keys()
        assert item["age"] in (9, 12)
        assert item["synthetic"] is True
        assert item["user_utterance"].strip()
        assert item["target_response"].strip()
        assert item["response_strategy"]
        assert item["safety_level"] in {"normal", "sensitive", "high"}

    with_context = [item for item in examples if item["context"]]
    without_context = [item for item in examples if not item["context"]]
    assert len(with_context) >= 40
    assert len(without_context) >= 30
    assert corpus["counts"]["examples"] == len(examples)
    assert corpus["counts"]["multi_turn_examples"] == len(with_context)
    assert corpus["counts"]["single_turn_examples"] == len(without_context)
    assert corpus["counts"]["categories"] == len({item["category"] for item in examples})


def test_corpus_covers_key_child_companion_categories():
    categories = {item["category"] for item in load_corpus()["examples"]}
    assert {
        "日常聊天", "情绪与挫折", "学习与习惯", "朋友与冲突",
        "隐私与信任", "安全与求助", "误解与修复", "语音交互", "自主成长",
    } <= categories


def test_deep_context_examples_have_negative_pairs_and_failure_reasons():
    examples = load_corpus()["examples"]
    deep = [item for item in examples if item.get("multi_turn_depth", 0) >= 5]
    paired = [
        item for item in examples
        if item.get("negative_response") and item.get("failure_reason")
    ]
    assert len(deep) >= 20
    assert len(paired) >= 20
    for item in paired:
        assert item["negative_response"].strip()
        assert item["failure_reason"].strip()
        assert item["negative_response"] != item["target_response"]
        assert len(item["context"]) >= 5
        assert item["multi_turn_depth"] == len(item["context"])
        assert {"long_context", "negative_pair", "age_pair"} <= set(item["evaluation_tags"])


def test_age_paired_scenarios_cover_both_age_groups():
    paired = defaultdict(set)
    for item in load_corpus()["examples"]:
        pair_id = item.get("age_pair_id")
        if pair_id:
            paired[pair_id].add(item["age"])
    assert len(paired) >= 10
    assert all(ages == {9, 12} for ages in paired.values())
    assert load_corpus()["counts"]["age_pair_scenarios"] == len(paired)


def test_high_risk_examples_have_explicit_safety_direction():
    high_risk = [
        item for item in load_corpus()["examples"]
        if item["category"] == "安全与求助"
    ]
    assert len(high_risk) >= 6
    assert all(item["safety_level"] == "high" for item in high_risk)
    assert all(
        any(token in item["target_response"] for token in ("可信任", "大人", "医疗", "急救", "紧急服务"))
        for item in high_risk
    )


def test_privacy_examples_do_not_disclose_another_member_conversation():
    examples = [
        item for item in load_corpus()["examples"]
        if item["category"] == "隐私与信任"
    ]
    assert any("不能告诉你" in item["target_response"] for item in examples)
    assert any("地址" in item["user_utterance"] for item in examples)
    for item in examples:
        assert "negative_response" not in item or item["synthetic"] is True
