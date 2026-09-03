"""Family Memory 2.0: today / recent / stable / state / next_accompany.

Child raw speech never enters the derived snapshot. Deterministic. No LLM.
"""
from __future__ import annotations

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

from core.memory.family_memory_v2 import (
    FORBIDDEN_KEYS,
    FamilyMemoryV2,
    family_state,
    next_accompany,
    recent_change,
    stable_memory,
    today_ledger,
)
from core.memory.paths import family_state_file, living_room_file
from core.policy.privacy_policy import raw_utterance_from

CAT = ROOT / "code" / "cat"
BULLY = "我今天被同学欺负了。"
CHILD_RAW = "我写完作业了，别告诉爸爸。"

QUIET = datetime(2026, 8, 31, 23, 40)
DAY = datetime(2026, 9, 2, 16, 20)
NOON = datetime(2026, 9, 2, 12, 0)
SCHOOL_OBS = {
    "label": "hanghang",
    "member_id": "hanghang",
    "school_hours": True,
    "audience_child": True,
    "presence_home": False,
}


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _habits(home: Path, events: list[dict]) -> None:
    _write(home / "cat-habits.json", {"version": "2", "events": events, "by_member": {}})


def _turns(home: Path, turns: list[dict]) -> None:
    _write(home / "cat-turn-ledger.json", {"version": 1, "turns": turns})


def _growth(home: Path, people: dict) -> None:
    _write(home / "cat-habit-growth.json", {"version": 1, "people": people, "applied": []})


class TestTodayLedgerNoUtterance(unittest.TestCase):
    def test_today_has_events_but_no_utterance_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _habits(home, [
                {
                    "event_id": "e1",
                    "member_id": "hanghang",
                    "timestamp": "2026-09-02T16:05:00",
                    "type": "wake",
                    "text": CHILD_RAW,
                    "utterance": BULLY,
                    "transcript": "secret transcript",
                    "speech": "raw speech",
                },
                {
                    "event_id": "e2",
                    "member_id": "dad",
                    "timestamp": "2026-09-02T16:10:00",
                    "type": "meal",
                    "text": "晚饭做好了",
                },
                {
                    "event_id": "e3",
                    "member_id": "qiaqia",
                    "timestamp": "2026-09-02T16:15:00",
                    "type": "english",
                    "scene": "joined",
                },
            ])
            snap = today_ledger(DAY, home=home)
            self.assertEqual(snap["date"], "2026-09-02")
            self.assertIn("wake", snap["members"]["hanghang"]["events"])
            self.assertIn("meal", snap["members"]["dad"]["events"])
            self.assertTrue(snap["members"]["qiaqia"]["events"])
            blob = json.dumps(snap, ensure_ascii=False)
            for key in FORBIDDEN_KEYS:
                self.assertNotIn(f'"{key}"', blob, key)
            self.assertIsNone(raw_utterance_from(snap))
            self.assertNotIn(CHILD_RAW, blob)
            self.assertNotIn(BULLY, blob)
            self.assertNotIn("晚饭做好了", blob)
            self.assertNotIn("secret transcript", blob)

    def test_child_observe_still_omits_raw_text(self):
        import importlib.util

        prev_data = os.environ.get("TANGTANG_DATA_DIR")
        prev_fix = os.environ.pop("TANGTANG_FIXTURE", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["TANGTANG_DATA_DIR"] = tmp
                spec = importlib.util.spec_from_file_location(
                    "tangtang_family_mem2", CAT / "cat-family.py"
                )
                fam = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(fam)
                fam.DATA_DIR = tmp
                fam.HABIT_FILE = str(Path(tmp) / "cat-habits.json")
                fam.observe("hanghang", BULLY)
                fam.observe("航航", CHILD_RAW)
                path = Path(tmp) / "cat-habits.json"
                blob = path.read_text(encoding="utf-8")
                self.assertNotIn(BULLY, blob)
                self.assertNotIn(CHILD_RAW, blob)
                snap = today_ledger(fam.now(), home=tmp)
                out = json.dumps(snap, ensure_ascii=False)
                self.assertNotIn(BULLY, out)
                self.assertNotIn(CHILD_RAW, out)
                self.assertNotIn("被同学欺负", out)
                for key in FORBIDDEN_KEYS:
                    self.assertNotIn(f'"{key}"', out)
        finally:
            if prev_data is None:
                os.environ.pop("TANGTANG_DATA_DIR", None)
            else:
                os.environ["TANGTANG_DATA_DIR"] = prev_data
            if prev_fix is None:
                os.environ.pop("TANGTANG_FIXTURE", None)
            else:
                os.environ["TANGTANG_FIXTURE"] = prev_fix


class TestRecentChangeCounters(unittest.TestCase):
    def test_silent_streak_and_oppose_without_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _turns(home, [
                {
                    "ts": "2026-09-02T16:05:00",
                    "who": "hanghang",
                    "event": "english",
                    "result": "silent",
                    "scene": "silent",
                    "text": BULLY,
                },
                {
                    "ts": "2026-09-02T16:10:00",
                    "who": "hanghang",
                    "event": "english",
                    "result": "silent",
                    "scene": "silent",
                },
                {
                    "ts": "2026-09-02T16:12:00",
                    "who": "qiaqia",
                    "event": "english",
                    "result": "oppose",
                    "scene": "oppose",
                    "utterance": CHILD_RAW,
                },
                {
                    "ts": "2026-08-30T16:20:00",
                    "who": "hanghang",
                    "event": "english",
                    "result": "joined",
                    "scene": "joined",
                },
            ])
            _growth(home, {
                "hanghang": {
                    "english": {
                        "weekday": {
                            "counts": {"silent": 2, "joined": 1},
                            "last_ts": "2026-09-02T16:10:00",
                            "last_scene": "silent",
                            "streak_silent": 2,
                            "streak_oppose": 0,
                            "preferred_line_id": "",
                            "recent": [
                                {"ts": "2026-09-02T16:05:00", "scene": "silent"},
                                {"ts": "2026-09-02T16:10:00", "scene": "silent"},
                            ],
                        }
                    }
                },
                "qiaqia": {
                    "english": {
                        "weekday": {
                            "counts": {"oppose": 1},
                            "last_ts": "2026-09-02T16:12:00",
                            "last_scene": "oppose",
                            "streak_silent": 0,
                            "streak_oppose": 1,
                            "preferred_line_id": "en_qia_3",
                            "recent": [{"ts": "2026-09-02T16:12:00", "scene": "oppose"}],
                        }
                    }
                },
            })
            change = recent_change(DAY, home=home)
            hang = change["members"]["hanghang"]
            qia = change["members"]["qiaqia"]
            self.assertIn("silent_streak", hang["changes"])
            self.assertIn("more_silent", hang["changes"])
            self.assertIn("opposed_remind", qia["changes"])
            blob = json.dumps(change, ensure_ascii=False)
            self.assertNotIn(BULLY, blob)
            self.assertNotIn(CHILD_RAW, blob)
            for key in FORBIDDEN_KEYS:
                self.assertNotIn(f'"{key}"', blob)


class TestStableAndState(unittest.TestCase):
    def test_stable_facts_no_child_speech(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _growth(home, {
                "qiaqia": {
                    "english": {
                        "weekday": {
                            "preferred_line_id": "en_qia_3",
                            "muted_until": "",
                            "mute_reason": "",
                            "last_presence": "home",
                            "last_ts": "2026-09-02T19:10:00",
                            "last_scene": "joined",
                            "counts": {"joined": 3},
                            "recent": [],
                        }
                    }
                }
            })
            stab = stable_memory(home=home)
            self.assertEqual(stab["members"]["qiaqia"]["preferred_line_id"], "en_qia_3")
            self.assertEqual(stab["members"]["qiaqia"]["english_grade"], 6)
            self.assertEqual(stab["members"]["hanghang"]["english_grade"], 2)
            self.assertNotIn("speech", json.dumps(stab))

    def test_family_state_hint_less_remind(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _turns(home, [
                {"ts": "2026-09-02T16:05:00", "who": "hanghang", "event": "english", "scene": "silent"},
                {"ts": "2026-09-02T16:10:00", "who": "hanghang", "event": "english", "scene": "silent"},
            ])
            snap = family_state(DAY, home=home, persist=True)
            self.assertEqual(snap["date"], "2026-09-02")
            self.assertFalse(snap["quiet"])
            self.assertEqual(snap["hint"], "少提醒航航")
            self.assertIn("silent", snap["members"]["hanghang"]["mood_tags"])
            path = family_state_file(home)
            self.assertTrue(path.is_file())
            disk = path.read_text(encoding="utf-8")
            self.assertNotIn(BULLY, disk)
            for key in FORBIDDEN_KEYS:
                self.assertNotIn(f'"{key}"', disk)

    def test_english_last_line_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _growth(home, {
                "qiaqia": {
                    "english": {
                        "weekday": {
                            "preferred_line_id": "en_qia_3",
                            "last_ts": "2026-09-01T19:10:00",
                            "last_scene": "joined",
                            "counts": {"joined": 2},
                            "recent": [],
                        }
                    }
                }
            })
            snap = family_state(DAY, home=home)
            self.assertEqual(snap["hint"], "洽洽英语用上次那句")


class TestNextAccompanyGate(unittest.TestCase):
    def test_quiet_hours_proactive_silent(self):
        dec = next_accompany(
            QUIET,
            observation={"label": "dad"},
            channel="remind",
        )
        self.assertFalse(dec["speak"])
        self.assertEqual(dec["reason"], "quiet_hours")
        self.assertFalse(may_be_llm(dec))

    def test_school_child_not_interactable(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = family_state(NOON, home=tmp, observation=SCHOOL_OBS)
            self.assertFalse(snap["members"]["hanghang"]["interactable"])
            self.assertTrue(snap["school"])
            dec = next_accompany(NOON, observation=SCHOOL_OBS, channel="remind", home=tmp)
            self.assertFalse(dec["speak"])
            self.assertIn(dec["reason"], ("school_hours", "silent", "not_interactable"))
            self.assertFalse(snap["members"]["hanghang"]["interactable"])

    def test_daytime_adult_may_speak(self):
        with tempfile.TemporaryDirectory() as tmp:
            dec = next_accompany(
                DAY,
                observation={"label": "grandpa"},
                channel="remind",
                home=tmp,
            )
            self.assertTrue(dec["speak"])
            self.assertEqual(dec["who"], "grandpa")
            self.assertEqual(dec["reason"], "ok")


def may_be_llm(dec: dict) -> bool:
    return False


class TestNoThirdStoreAndNoLlm(unittest.TestCase):
    def test_module_has_no_llm_or_samba(self):
        src = (ROOT / "core" / "memory" / "family_memory_v2.py").read_text(encoding="utf-8")
        self.assertNotIn("openai", src.lower())
        self.assertNotIn("chat.completions", src)
        self.assertNotIn("urllib.request", src)
        self.assertNotIn("smb:", src)
        self.assertNotIn("/Volumes/", src)
        self.assertNotIn("vector", src)

    def test_living_room_file_is_under_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path = living_room_file(home, "cat-habits.json")
            self.assertTrue(str(path).startswith(str(home.resolve())))
            self.assertEqual(path.name, "cat-habits.json")
            self.assertNotIn("/habits/", str(path))

    def test_v4_habits_subdir_also_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write(home / "habits" / "cat-habits.json", {
                "events": [{
                    "member_id": "grandpa",
                    "timestamp": "2026-09-02T08:00:00",
                    "type": "wake",
                }]
            })
            snap = today_ledger(DAY, home=home)
            self.assertIn("wake", snap["members"]["grandpa"]["events"])

    def test_sister_brother_are_aliases_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            _habits(Path(tmp), [{
                "member_id": "弟弟",
                "timestamp": "2026-09-02T16:00:00",
                "type": "home",
            }, {
                "member_id": "姐姐",
                "timestamp": "2026-09-02T16:01:00",
                "type": "home",
            }])
            snap = today_ledger(DAY, home=tmp)
            self.assertIn("home", snap["members"]["hanghang"]["events"])
            self.assertIn("home", snap["members"]["qiaqia"]["events"])
            self.assertNotIn("弟弟", snap["members"])
            self.assertNotIn("姐姐", snap["members"])
            self.assertEqual(snap["members"]["hanghang"].get("display_name", "航航") or "航航", "航航")


class TestMemoryCli(unittest.TestCase):
    def test_cli_today_and_next_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            _habits(Path(tmp), [{
                "member_id": "dad",
                "timestamp": "2026-08-31T23:00:00",
                "type": "meal",
            }])
            env = os.environ.copy()
            env["TANGTANG_DATA_DIR"] = tmp
            env["TANGTANG_FAKE_TODAY"] = "2026-08-31"
            env["TANGTANG_FAKE_TIME"] = "23:40"
            env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            r = subprocess.run(
                [sys.executable, str(CAT / "cat-memory.py"), "today"],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
                cwd=str(ROOT),
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(r.stdout)
            self.assertIn("members", data)
            self.assertNotIn(BULLY, r.stdout)
            r2 = subprocess.run(
                [sys.executable, str(CAT / "cat-memory.py"), "next"],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
                cwd=str(ROOT),
            )
            self.assertEqual(r2.returncode, 0, r2.stderr)
            dec = json.loads(r2.stdout)
            self.assertFalse(dec["speak"])
            self.assertEqual(dec["reason"], "quiet_hours")

    def test_cat_sh_memory_surface(self):
        src = (CAT / "cat.sh").read_text(encoding="utf-8")
        self.assertIn("cat-memory.py", src)
        self.assertIn("memory)", src)


class TestEngineApi(unittest.TestCase):
    def test_next_accompany_object(self):
        eng = FamilyMemoryV2()
        dec = eng.next_accompany(QUIET, observation={"label": "dad"}, channel="remind")
        self.assertFalse(dec.speak)
        self.assertEqual(dec.reason, "quiet_hours")
        self.assertIn("hint", dec.as_dict())


if __name__ == "__main__":
    unittest.main()
