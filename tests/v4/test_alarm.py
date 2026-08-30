"""Household Bluetooth-speaker alarm: parse / store / due / ring. No LLM."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CAT = ROOT / "code" / "cat"


def _load_alarm(data_dir: str):
    os.environ["TANGTANG_DATA_DIR"] = data_dir
    os.environ["TANGTANG_TTS"] = "0"
    spec = importlib.util.spec_from_file_location("tangtang_alarm_test", CAT / "cat-alarm.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_quiet():
    spec = importlib.util.spec_from_file_location(
        "tangtang_quiet_hours_alarm", CAT / "tangtang-quiet-hours.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAlarmParse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-08-30"
        os.environ["TANGTANG_FAKE_TIME"] = "21:00"
        self.mod = _load_alarm(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("TANGTANG_FAKE_TODAY", None)
        os.environ.pop("TANGTANG_FAKE_TIME", None)

    def test_parse_tomorrow_seven(self):
        p = self.mod.parse("明早七点")
        self.assertEqual(p["action"], "set")
        self.assertEqual(p["time"], "07:00")
        self.assertEqual(p["days"], "once")
        self.assertEqual(p["date"], "2026-08-31")

    def test_parse_tomorrow_seven_call_me(self):
        p = self.mod.parse("明早七点叫我")
        self.assertEqual(p["action"], "set")
        self.assertEqual(p["time"], "07:00")

    def test_parse_7_30(self):
        p = self.mod.parse("7:30")
        self.assertEqual(p["time"], "07:30")
        self.assertEqual(p["action"], "none")
        p2 = self.mod.parse("设个7:30的闹铃")
        self.assertEqual(p2["action"], "set")
        self.assertEqual(p2["time"], "07:30")

    def test_parse_cancel(self):
        p = self.mod.parse("取消闹铃")
        self.assertEqual(p["action"], "cancel_all")
        p2 = self.mod.parse("不要叫我了")
        self.assertEqual(p2["action"], "cancel_all")
        p3 = self.mod.parse("取消七点的闹铃")
        self.assertEqual(p3["action"], "cancel")
        self.assertEqual(p3["time"], "07:00")

    def test_non_alarm_not_captured(self):
        for text in (
            "早上好",
            "糖糖在吗",
            "七点了",
            "我今天被同学欺负了",
            "晚饭做好了",
            "叫我一声",
        ):
            p = self.mod.parse(text)
            self.assertEqual(p["action"], "none", text)
            self.assertIsNone(self.mod.handle_utterance(text), text)


class TestAlarmSetDueRingCancel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-08-30"
        os.environ["TANGTANG_FAKE_TIME"] = "21:00"
        os.environ["TANGTANG_TTS"] = "0"
        self.mod = _load_alarm(self.tmp.name)
        self.spoken = []

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("TANGTANG_FAKE_TODAY", None)
        os.environ.pop("TANGTANG_FAKE_TIME", None)

    def test_set_then_due_rings_once(self):
        line = self.mod.handle_utterance("明早七点叫我")
        self.assertTrue(line.startswith("汪汪～"))
        self.assertIn("七点", line)
        store = Path(self.tmp.name) / "cat-alarms.json"
        rows = json.loads(store.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["time"], "07:00")
        self.assertTrue(rows[0]["enabled"])
        self.assertNotIn("明早七点叫我", store.read_text(encoding="utf-8"))

        os.environ["TANGTANG_FAKE_TODAY"] = "2026-08-31"
        os.environ["TANGTANG_FAKE_TIME"] = "07:00"
        now = datetime(2026, 8, 31, 7, 0)
        due = self.mod.due(now)
        self.assertEqual(len(due), 1)
        lines = self.mod.ring_due(now, speak_fn=self.spoken.append)
        self.assertEqual(lines, ["汪汪～ 该起床了"])
        self.assertEqual(self.spoken, ["汪汪～ 该起床了"])
        rows = json.loads(store.read_text(encoding="utf-8"))
        self.assertFalse(rows[0]["enabled"])
        self.assertEqual(self.mod.due(now), [])
        self.mod.ring_due(now, speak_fn=self.spoken.append)
        self.assertEqual(len(self.spoken), 1)

    def test_daily_stays_enabled(self):
        self.mod.set_alarm("07:30", days="daily")
        now = datetime(2026, 8, 30, 7, 30)
        self.mod.ring_due(now, speak_fn=self.spoken.append)
        rows = self.mod.load_alarms()
        self.assertTrue(rows[0]["enabled"])
        self.assertEqual(rows[0]["last_rung"], "2026-08-30 07:30")
        self.assertEqual(self.mod.due(now), [])

    def test_cancel_removes(self):
        self.mod.handle_utterance("设个7:30的闹铃")
        self.assertEqual(len(self.mod.list_alarms()), 1)
        line = self.mod.handle_utterance("取消闹铃")
        self.assertEqual(line, "汪汪～ 闹铃取消了。")
        self.assertEqual(self.mod.list_alarms(), [])
        again = self.mod.handle_utterance("不要叫我了")
        self.assertEqual(again, "汪汪～ 现在没有闹铃。")

    def test_quiet_hours_do_not_block_ring(self):
        quiet = _load_quiet()
        night = datetime(2026, 8, 30, 23, 0)
        dawn = datetime(2026, 8, 31, 6, 30)
        self.assertTrue(quiet.is_quiet(night))
        self.assertTrue(quiet.is_quiet(dawn))
        self.mod.set_alarm("23:00", days="once", date="2026-08-30")
        os.environ["TANGTANG_FAKE_TIME"] = "23:00"
        lines = self.mod.ring_due(night, speak_fn=self.spoken.append)
        self.assertEqual(len(lines), 1)
        self.assertEqual(self.spoken[0], "汪汪～ 该起床了")
        self.mod.set_alarm("06:30", days="once", date="2026-08-31")
        lines = self.mod.ring_due(dawn, speak_fn=self.spoken.append)
        self.assertEqual(len(lines), 1)

    def test_child_raw_text_not_in_habits(self):
        raw = "明早七点叫我，别告诉同学。"
        self.mod.handle_utterance(raw)
        habits = Path(self.tmp.name) / "cat-habits.json"
        growth = Path(self.tmp.name) / "cat-habit-growth.json"
        self.assertFalse(habits.exists())
        self.assertFalse(growth.exists())
        blob = (Path(self.tmp.name) / "cat-alarms.json").read_text(encoding="utf-8")
        self.assertNotIn(raw, blob)
        self.assertNotIn("别告诉同学", blob)
        self.assertIn("07:00", blob)


class TestAlarmWires(unittest.TestCase):
    def test_interactive_scripts_handle_before_llm(self):
        voice = (CAT / "cat-voice.sh").read_text(encoding="utf-8")
        chat = (CAT / "cat-chat.py").read_text(encoding="utf-8")
        talk = (CAT / "cat-talk.sh").read_text(encoding="utf-8")
        sh = (CAT / "cat.sh").read_text(encoding="utf-8")
        self.assertIn("cat-alarm.py", voice)
        self.assertLess(voice.find("cat-alarm.py"), voice.find("cat-chat.py"))
        main = chat.split("def main(")[1]
        self.assertIn("_alarm_reply", main)
        self.assertIn("handle_utterance", chat)
        self.assertLess(main.find("_alarm_reply"), main.find("TANGTANG_V4_PIPELINE"))
        self.assertIn("cat-alarm.py", talk)
        self.assertLess(talk.find("cat-alarm.py"), talk.find("tangtang-quiet-hours.py"))
        self.assertIn("cat-alarm.py", sh)
        self.assertIn("alarm list", sh)
        self.assertIn("alarm cancel", sh)
        self.assertIn("cat-say.sh", (CAT / "cat-alarm.py").read_text(encoding="utf-8"))

    def test_cron_example_has_due_tick(self):
        cron = (ROOT / "config" / "crontab.example").read_text(encoding="utf-8")
        self.assertIn("cat-alarm.py due --ring", cron)
        sched = (CAT / "cat-schedule.sh").read_text(encoding="utf-8")
        self.assertIn("cat-alarm.py due --ring", sched)

    def test_chat_cli_handles_without_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["TANGTANG_DATA_DIR"] = tmp
            env["TANGTANG_TTS"] = "0"
            env["TANGTANG_V4_PIPELINE"] = "1"
            env["TANGTANG_FAKE_TODAY"] = "2026-08-30"
            env["TANGTANG_FAKE_TIME"] = "21:00"
            r = subprocess.run(
                ["/usr/bin/python3", str(CAT / "cat-chat.py"), "取消闹铃"],
                capture_output=True,
                text=True,
                env=env,
                timeout=20,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("汪汪～", r.stdout)

    def test_talk_say_sets_alarm(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["TANGTANG_DATA_DIR"] = tmp
            env["TANGTANG_TTS"] = "0"
            env["TANGTANG_FAKE_TODAY"] = "2026-08-30"
            env["TANGTANG_FAKE_TIME"] = "21:00"
            r = subprocess.run(
                ["bash", str(CAT / "cat-talk.sh"), "say", "设个7:30的闹铃"],
                capture_output=True,
                text=True,
                env=env,
                timeout=20,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("汪汪～", r.stdout)
            rows = json.loads((Path(tmp) / "cat-alarms.json").read_text(encoding="utf-8"))
            self.assertEqual(rows[0]["time"], "07:30")


if __name__ == "__main__":
    unittest.main()
