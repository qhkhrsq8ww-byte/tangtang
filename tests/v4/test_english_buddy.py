"""弱伴读：选人、口吻、不作测验。不新建教材引擎。"""
from __future__ import annotations

import importlib.util
import os
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "code" / "cat"


def _load_english():
    path = CAT / "cat-english.py"
    spec = importlib.util.spec_from_file_location("cat_english_buddy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEnglishWho(unittest.TestCase):
    def setUp(self):
        self.en = _load_english()
        self._env = {
            k: os.environ.get(k)
            for k in ("TANGTANG_MEMBER_ID", "TANGTANG_SPEAKER", "TANGTANG_PROFILE")
        }
        for k in ("TANGTANG_MEMBER_ID", "TANGTANG_SPEAKER", "TANGTANG_PROFILE"):
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_explicit_qiaqia_not_remapped(self):
        self.assertEqual(self.en.resolve_who("qiaqia"), "qiaqia")
        self.assertEqual(self.en.resolve_who("洽洽"), "qiaqia")
        self.assertEqual(self.en.resolve_who("g6"), "qiaqia")
        os.environ["TANGTANG_PROFILE"] = "play"
        self.assertEqual(self.en.resolve_who("洽洽"), "qiaqia")

    def test_member_id_wins_empty_arg(self):
        os.environ["TANGTANG_MEMBER_ID"] = "qiaqia"
        os.environ["TANGTANG_PROFILE"] = "play"
        self.assertEqual(self.en.resolve_who(""), "qiaqia")

    def test_friend_mouth_does_not_remap_hanghang(self):
        os.environ["TANGTANG_MEMBER_ID"] = "hanghang"
        os.environ["TANGTANG_PROFILE"] = "friend"
        self.assertEqual(self.en.resolve_who(""), "hanghang")
        self.assertEqual(self.en.resolve_who("hanghang"), "hanghang")

    def test_same_day_lines_differ_by_child(self):
        when = datetime(2026, 9, 1)
        hang = self.en.pick_line("hanghang", when)
        qia = self.en.pick_line("qiaqia", when)
        self.assertTrue(hang and qia)
        self.assertNotEqual(hang, qia)


class TestEnglishTone(unittest.TestCase):
    def setUp(self):
        self.en = _load_english()

    def test_library_has_no_quiz_markers(self):
        when = datetime(2026, 9, 1)
        for who in ("hanghang", "qiaqia"):
            for _lid, item in self.en.iter_items(who, when):
                say = item.get("say") or ""
                self.assertFalse(self.en.looks_like_quiz(say), say)
                self.assertNotIn("正确", say)
                self.assertNotIn("打分", say)
                self.assertNotIn("跟我读", say)
                self.assertNotIn("repeat after me", say.lower())

    def test_quiz_line_falls_back_to_companion(self):
        quiz = "跟我读 apple，我来检查"
        self.assertTrue(self.en.looks_like_quiz(quiz))
        self.assertEqual(
            self.en.companion_line(quiz, "hanghang"),
            self.en.fallback_line("hanghang"),
        )
        self.assertIn("不学也行", self.en.fallback_line("hanghang"))


if __name__ == "__main__":
    unittest.main()
