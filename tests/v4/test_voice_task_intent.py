"""Voice-to-task intents: explicit intent only, local persistence, privacy by default."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.tasks.intent import handle_voice_task, looks_like_task_intent, parse_due
from core.tasks.service import TaskService

MEMBERS = {
    "dad": {"member_id": "dad", "display_name": "爸爸", "profile": "adult"},
    "qiaqia": {"member_id": "qiaqia", "display_name": "洽洽", "profile": "friend"},
    "hanghang": {"member_id": "hanghang", "display_name": "航航", "profile": "play"},
}
NOW = datetime(2026, 10, 20, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


class TestVoiceTaskIntent(unittest.TestCase):
    def test_parse_explicit_chinese_time(self):
        due = parse_due("提醒我明天晚上八点做作业", now=NOW)
        self.assertEqual(due, "2026-10-21T20:00:00+08:00")
        self.assertIsNone(parse_due("提醒我做作业", now=NOW))

    def test_only_explicit_task_language_is_routed(self):
        self.assertTrue(looks_like_task_intent("提醒我明天晚上八点做作业"))
        self.assertTrue(looks_like_task_intent("我的任务"))
        self.assertFalse(looks_like_task_intent("我今天有点累"))

    def test_private_task_is_idempotent_and_raw_utterance_not_saved(self):
        with tempfile.TemporaryDirectory() as home:
            utterance = "提醒我明天晚上八点做作业"
            reply = handle_voice_task(utterance, owner_member_id="hanghang", members=MEMBERS,
                                      home=home, now=NOW)
            self.assertIn("只对你可见", reply)
            service = TaskService(home=home, persist=True, members=MEMBERS)
            rows = service.list_tasks(viewer_id="hanghang")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].title, "做作业")
            self.assertEqual(rows[0].visibility, "PRIVATE")
            self.assertNotIn("提醒我", str(rows[0].metadata))
            handle_voice_task(utterance, owner_member_id="hanghang", members=MEMBERS,
                              home=home, now=NOW)
            self.assertEqual(len(service.list_tasks(viewer_id="hanghang")), 1)
            self.assertEqual(service.list_tasks(viewer_id="qiaqia"), [])

    def test_family_visibility_requires_explicit_sharing_phrase(self):
        with tempfile.TemporaryDirectory() as home:
            handle_voice_task("提醒我明天晚上八点整理家庭作业", owner_member_id="hanghang",
                              members=MEMBERS, home=home, now=NOW)
            handle_voice_task("提醒我全家一起明天晚上八点整理客厅", owner_member_id="dad",
                              members=MEMBERS, home=home, now=NOW)
            service = TaskService(home=home, persist=True, members=MEMBERS)
            dad_rows = service.list_tasks(viewer_id="dad")
            child_rows = service.list_tasks(viewer_id="hanghang")
            self.assertEqual(dad_rows[0].visibility, "FAMILY")
            self.assertEqual(child_rows[0].visibility, "PRIVATE")
            self.assertNotIn("全家一起", dad_rows[0].title)

    def test_missing_time_asks_for_confirmation_and_unknown_identity_does_not_store(self):
        with tempfile.TemporaryDirectory() as home:
            reply = handle_voice_task("提醒我做作业", owner_member_id="hanghang",
                                      members=MEMBERS, home=home, now=NOW)
            self.assertIn("几点提醒", reply)
            service = TaskService(home=home, persist=True, members=MEMBERS)
            self.assertEqual(service.list_tasks(viewer_id="hanghang")[0].status, "proposed")
            unknown = handle_voice_task("提醒我明天晚上八点做作业", owner_member_id=None,
                                        members=MEMBERS, home=home, now=NOW)
            self.assertIn("还没认出你", unknown)
            self.assertEqual(len(service.list_tasks(viewer_id="hanghang")), 1)

    def test_list_complete_and_cancel_by_exact_title(self):
        with tempfile.TemporaryDirectory() as home:
            handle_voice_task("提醒我做作业", owner_member_id="hanghang",
                              members=MEMBERS, home=home, now=NOW)
            self.assertIn("做作业", handle_voice_task("我的任务", owner_member_id="hanghang",
                                                     members=MEMBERS, home=home, now=NOW))
            self.assertIn("标记完成", handle_voice_task("我做完了做作业", owner_member_id="hanghang",
                                                       members=MEMBERS, home=home, now=NOW))
            handle_voice_task("提醒我整理书包", owner_member_id="hanghang",
                              members=MEMBERS, home=home, now=NOW)
            self.assertIn("取消", handle_voice_task("取消任务整理书包", owner_member_id="hanghang",
                                                   members=MEMBERS, home=home, now=NOW))


if __name__ == "__main__":
    unittest.main()
