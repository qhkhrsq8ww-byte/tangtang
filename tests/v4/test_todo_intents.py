"""Natural-language todo commands reuse the shared local TaskService."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.chat_adapter import ChatAdapter
from core.adapters.family_loader import load_members
from core.ingest import PrivacyPipeline
from core.tasks.intents import parse_task_intent
from core.tasks.service import TaskService
from tangtang_runtime import TangTangRuntime

MEMBERS = load_members()


class TestTodoIntentParser(unittest.TestCase):
    def test_create_list_complete_cancel(self):
        self.assertEqual(
            parse_task_intent("糖糖，记个待办：给糖糖买狗粮。").__dict__,
            {"action": "create", "title": "给糖糖买狗粮"},
        )
        self.assertEqual(
            parse_task_intent("我的待办有哪些？").__dict__,
            {"action": "list", "title": None},
        )
        self.assertEqual(
            parse_task_intent("完成待办：给糖糖买狗粮").__dict__,
            {"action": "complete", "title": "给糖糖买狗粮"},
        )
        self.assertEqual(
            parse_task_intent("取消待办：给糖糖买狗粮").__dict__,
            {"action": "cancel", "title": "给糖糖买狗粮"},
        )

    def test_ambiguous_reminders_are_not_todo_commands(self):
        self.assertIsNone(parse_task_intent("明天上午九点提醒我带伞"))
        self.assertIsNone(parse_task_intent("我有件事要做"))
        self.assertIsNone(parse_task_intent("记住今天要开心"))


class TestTodoChatFlow(unittest.TestCase):
    def make_chat(self):
        pipe = PrivacyPipeline(members=MEMBERS)
        tasks = TaskService(members=MEMBERS)
        chat = ChatAdapter(
            pipeline=pipe,
            members=MEMBERS,
            tasks=tasks,
            llm=lambda _payload: self.fail("explicit todo command must not call LLM"),
        )
        return pipe, tasks, chat

    def test_create_list_complete_and_cancel_are_local(self):
        pipe, tasks, chat = self.make_chat()
        created = chat.turn("糖糖，记个待办：给糖糖买狗粮。", {"label": "hanghang"})
        self.assertEqual(created.action.action, "task_create")
        self.assertIn("给糖糖买狗粮", created.action.text)
        self.assertIn("没有设置提醒时间", created.action.text)
        self.assertEqual(created.ingest.decision.privacy, "PRIVATE")
        self.assertEqual(created.ingest.event.payload, {"redacted": True})
        self.assertFalse(created.ingest.stored_private)
        self.assertFalse(pipe.stores.family.contains_text("给糖糖买狗粮"))

        rows = tasks.list_tasks(viewer_id="hanghang", statuses={"proposed"}, include_family=False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "给糖糖买狗粮")
        listing = chat.turn("我的待办有哪些", {"label": "hanghang"})
        self.assertEqual(listing.action.action, "task_list")
        self.assertIn("买狗粮", listing.action.text)

        completed = chat.turn("完成待办：给糖糖买狗粮", {"label": "hanghang"})
        self.assertEqual(completed.action.action, "task_complete")
        self.assertIn("标记完成", completed.action.text)
        self.assertEqual(tasks.list_tasks(viewer_id="hanghang", statuses={"done"}, include_family=False)[0].title, "给糖糖买狗粮")

        chat.turn("记个待办：给爷爷打电话", {"label": "hanghang"})
        cancelled = chat.turn("取消待办：给爷爷打电话", {"label": "hanghang"})
        self.assertEqual(cancelled.action.action, "task_cancel")
        self.assertEqual(tasks.list_tasks(viewer_id="hanghang", statuses={"cancelled"}, include_family=False)[0].title, "给爷爷打电话")

    def test_unknown_speaker_cannot_create_a_todo(self):
        calls = []
        tasks = TaskService(members=MEMBERS)
        chat = ChatAdapter(
            members=MEMBERS,
            tasks=tasks,
            llm=lambda payload: calls.append(dict(payload)) or "不应该走云端",
        )
        turn = chat.turn("记个待办：买狗粮", {"label": "unknown"})
        self.assertIsNone(turn.ingest.decision.member_id)
        self.assertEqual(turn.ingest.event.payload, {"redacted": True})
        self.assertEqual(tasks.list_tasks(viewer_id="unknown"), [])
        self.assertEqual(calls, [])
        self.assertNotEqual(turn.action.action, "task_create")

    def test_runtime_shares_and_persists_the_task_service(self):
        with tempfile.TemporaryDirectory() as td:
            first_runtime = TangTangRuntime(
                members=MEMBERS,
                home=td,
                persist=True,
                llm=lambda _payload: self.fail("todo should stay local"),
            )
            result = first_runtime.handle_utterance(
                "记个待办：明天整理文件",
                {"label": "dad", "interactive": True},
            )
            self.assertEqual(result.action.action, "task_create")
            self.assertEqual(result.ingest.event.payload, {"redacted": True})
            saved = first_runtime.tasks.list_tasks(
                viewer_id="dad", statuses={"proposed"}, include_family=False
            )
            self.assertEqual([task.title for task in saved], ["明天整理文件"])

            second_runtime = TangTangRuntime(members=MEMBERS, home=td, persist=True)
            restored = second_runtime.tasks.list_tasks(
                viewer_id="dad", statuses={"proposed"}, include_family=False
            )
            self.assertEqual([task.title for task in restored], ["明天整理文件"])


if __name__ == "__main__":
    unittest.main()
