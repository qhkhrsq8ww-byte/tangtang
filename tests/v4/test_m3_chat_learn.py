"""m3: chat learning + FM2 habit-trends bridge."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, ROOT)

from core.memory.family_memory_v2 import FamilyMemoryV2
from core.memory.habit_trends import HabitTrendStore


def _load_cat_chat():
    path = ROOT / "code" / "cat" / "cat-chat.py"
    spec = importlib.util.spec_from_file_location("cat_chat_m3", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class TestChatLearn(unittest.TestCase):
    def test_infer_tags(self):
        chat = _load_cat_chat()
        self.assertEqual(chat._infer_learn_tag("我今天好难过"), "emotion")
        self.assertEqual(chat._infer_learn_tag("作业写不完"), "homework")
        self.assertEqual(chat._infer_learn_tag("今天天气不错"), "conversation")

    def test_learn_turn_no_raw_in_trends(self):
        chat = _load_cat_chat()
        secret = "我今天被同学欺负了"
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(chat, "DATA_DIR", td):
                with mock.patch.object(chat, "_resolve_speaker_member", return_value=("hanghang", "航航")):
                    with mock.patch.dict(os.environ, {"TANGTANG_MEMBER_ID": "hanghang"}, clear=False):
                        out = chat._learn_turn(secret, event_tag="emotion")
            self.assertIsNotNone(out)
            trends = Path(td) / "habits" / "habit-trends.json"
            self.assertTrue(trends.exists())
            blob = trends.read_text(encoding="utf-8")
            self.assertNotIn(secret, blob)
            self.assertIn("emotion", blob)


class TestFM2TrendsBridge(unittest.TestCase):
    def test_today_ledger_includes_habit_trends(self):
        with tempfile.TemporaryDirectory() as td:
            store = HabitTrendStore(home=td, persist=True)
            now = datetime(2026, 9, 3, 15, tzinfo=timezone.utc)
            store.record(member_id="hanghang", tag="water", now=now)
            eng = FamilyMemoryV2(home=td, persist=False, clock=lambda: now)
            ledger = eng.today_ledger(now)
            counts = ledger["members"]["hanghang"]["counts"]
            self.assertGreaterEqual(int(counts.get("water") or 0), 1)
            self.assertNotIn("text", json.dumps(ledger, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
