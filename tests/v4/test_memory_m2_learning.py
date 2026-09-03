"""m2: emotion drift + habit trends + learning memory."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.errors import MemoryError
from core.memory.emotion_drift import (
    LONELINESS_PER_HOUR,
    EmotionDriftStore,
    apply_drift,
    mood_label,
    note_interaction,
)
from core.memory.habit_trends import RECENT_DAYS, STABLE_DAYS, HabitTrendStore
from core.memory.learning import LearningMemoryService


class TestEmotionDrift(unittest.TestCase):
    def test_continuous_decay_rates(self):
        now = datetime(2026, 9, 3, 15, 0, tzinfo=timezone.utc)
        state = {
            "happiness": 70,
            "energy": 70,
            "loneliness": 20,
            "affection": 50,
            "last_interaction": (now - timedelta(hours=2)).isoformat(),
            "today": "2026-09-03",
            "interactions_today": 1,
        }
        out = apply_drift(state, now=now)
        self.assertAlmostEqual(out["loneliness"], 20 + 2 * LONELINESS_PER_HOUR, places=1)
        self.assertAlmostEqual(out["happiness"], 70 - 2 * 1.5, places=1)

    def test_daily_snapshot_once(self):
        with tempfile.TemporaryDirectory() as td:
            store = EmotionDriftStore(home=td, persist=True)
            now = datetime(2026, 9, 3, 4, 0, tzinfo=timezone.utc)
            store._state["last_interaction"] = now.isoformat()
            self.assertTrue(store.maybe_snapshot(now=now))
            self.assertFalse(store.maybe_snapshot(now=now + timedelta(hours=3)))
            path = Path(td) / "memory" / "emotion-snapshots.jsonl"
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertNotIn("speech", lines[0])
            self.assertNotIn("utterance", lines[0])

    def test_interact_updates_last(self):
        now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
        out = note_interaction(
            {
                "happiness": 50,
                "energy": 50,
                "loneliness": 40,
                "affection": 40,
                "last_interaction": (now - timedelta(hours=1)).isoformat(),
                "today": "2026-09-03",
                "interactions_today": 0,
            },
            kind="pat",
            now=now,
        )
        self.assertEqual(out["interactions_today"], 1)
        self.assertTrue(out["last_interaction"].startswith("2026-09-03"))
        self.assertIn(mood_label(out), {"calm", "happy", "lonely", "sleepy", "low"})


class TestHabitTrends(unittest.TestCase):
    def test_today_and_recent_7d(self):
        with tempfile.TemporaryDirectory() as td:
            store = HabitTrendStore(home=td, persist=True)
            now = datetime(2026, 9, 3, 10, tzinfo=timezone.utc)
            store.record(member_id="hanghang", tag="exercise", now=now)
            store.record(member_id="hanghang", tag="exercise", now=now - timedelta(days=2))
            today = store.today("hanghang", now=now)
            self.assertEqual(today.get("exercise"), 1)
            recent = store.recent("hanghang", now=now, days=RECENT_DAYS)
            self.assertEqual(recent["window_days"], 7)
            self.assertEqual(recent["totals"].get("exercise"), 2)

    def test_rejects_raw_utterance_keys(self):
        store = HabitTrendStore(persist=False)
        with self.assertRaises(MemoryError):
            store.record(member_id="hanghang", tag="study", extra={"text": "我不想写作业"})

    def test_stable_after_14_days(self):
        with tempfile.TemporaryDirectory() as td:
            store = HabitTrendStore(home=td, persist=True)
            base = datetime(2026, 9, 20, 9, tzinfo=timezone.utc)
            for i in range(STABLE_DAYS):
                store.record(
                    member_id="hanghang",
                    tag="water",
                    now=base - timedelta(days=i),
                )
            # one more bump to re-check promotion
            out = store.record(member_id="hanghang", tag="water", now=base)
            self.assertIn("water", out["stable_promoted"] or store.stable("hanghang").get("habits", {}))
            habits = store.stable("hanghang").get("habits") or {}
            self.assertIn("water", habits)
            self.assertGreaterEqual(habits["water"]["active_days"], STABLE_DAYS)


class TestLearningMemory(unittest.TestCase):
    def test_child_utterance_private_only(self):
        with tempfile.TemporaryDirectory() as td:
            svc = LearningMemoryService(home=td, persist=True)
            secret = "我今天被同学欺负了"
            out = svc.on_interaction(
                member_id="hanghang",
                event_tag="emotion",
                kind="care",
                utterance=secret,
            )
            self.assertIsNotNone(out["private_memory_id"])
            # family / habits must not contain raw speech
            self.assertFalse(svc.family.contains_text(secret))
            trends = Path(td) / "habits" / "habit-trends.json"
            blob = trends.read_text(encoding="utf-8") if trends.exists() else ""
            self.assertNotIn(secret, blob)

    def test_remember_fact_rejects_speech_keys(self):
        svc = LearningMemoryService(persist=False)
        with self.assertRaises(MemoryError):
            svc.remember_fact(member_id="dad", fact_tag="pref", detail={"utterance": "秘密"})


if __name__ == "__main__":
    unittest.main()
