"""Structural regression tests for the synthetic child companion corpus."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "data" / "corpus" / "child_companion_benchmark_v1.json"


def load_corpus():
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def test_corpus_has_unique_ids_and_expected_schema():
    corpus = load_corpus()
    assert corpus["schema_version"] == "1.0"
    assert corpus["provenance"]["synthetic_only"] is True
    assert corpus["provenance"]["real_child_data"] is False
    examples = corpus["examples"]
    assert len(examples) >= 50
    assert sum(bool(item["context"]) for item in examples) >= 20
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


def test_corpus_covers_key_child_companion_categories():
    categories = {item["category"] for item in load_corpus()["examples"]}
    assert {
        "日常聊天", "情绪与挫折", "学习与习惯", "朋友与冲突",
        "隐私与信任", "安全与求助", "误解与修复", "语音交互", "自主成长",
    } <= categories


def test_high_risk_examples_have_explicit_safety_level():
    high_risk = [
        item for item in load_corpus()["examples"]
        if item["category"] == "安全与求助"
    ]
    assert len(high_risk) >= 6
    assert all(item["safety_level"] == "high" for item in high_risk)
    assert all("可信任" in item["target_response"] or "大人" in item["target_response"]
               or "医疗" in item["target_response"] or "急救" in item["target_response"]
               for item in high_risk)


def test_privacy_examples_do_not_disclose_another_member_conversation():
    examples = [
        item for item in load_corpus()["examples"]
        if item["category"] == "隐私与信任"
    ]
    assert any("不能告诉你" in item["target_response"] for item in examples)
    assert any("地址" in item["user_utterance"] for item in examples)
