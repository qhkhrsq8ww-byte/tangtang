#!/usr/bin/env python3
"""糖糖本地任务入口：任务内容只写本机，默认 PRIVATE，不保存语音原话。"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

CAT_DIR = Path(__file__).resolve().parent
ROOT = CAT_DIR.parent if (CAT_DIR.parent / "core").is_dir() else CAT_DIR.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(CAT_DIR) not in sys.path:
    sys.path.insert(0, str(CAT_DIR))

from tangtang_paths import data_dir
from core.adapters.family_loader import load_members
from core.tasks.intent import handle_voice_task
from core.tasks.service import TaskService


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="糖糖本地任务与提醒")
    parser.add_argument("--owner", default=os.environ.get("TANGTANG_MEMBER_ID") or os.environ.get("TANGTANG_SPEAKER") or "")
    parser.add_argument("--timezone", default=os.environ.get("TANGTANG_TIMEZONE", "Asia/Shanghai"))
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="列出当前成员可见的待办")
    add = sub.add_parser("add", help="添加任务")
    add.add_argument("title")
    add.add_argument("--due", help="ISO 8601，必须包含时区偏移")
    add.add_argument("--visibility", choices=("PRIVATE", "FAMILY"), default="PRIVATE")
    done = sub.add_parser("done", help="完成任务")
    done.add_argument("task_id")
    cancel = sub.add_parser("cancel", help="取消任务")
    cancel.add_argument("task_id")
    voice = sub.add_parser("voice", help="按自然语言处理任务意图")
    voice.add_argument("utterance")
    args = parser.parse_args(argv)

    home = data_dir()
    os.environ.setdefault("TANGTANG_HOME", home)
    os.environ.setdefault("TANGTANG_DATA_DIR", home)
    members = load_members()
    owner = str(args.owner or "").strip()
    if not owner or owner not in members:
        print("无法确认当前家庭成员。请设置 --owner 或 TANGTANG_MEMBER_ID；未修改任务。", file=sys.stderr)
        return 2

    if args.action == "voice":
        response = handle_voice_task(args.utterance, owner_member_id=owner, members=members,
                                     home=home, timezone_name=args.timezone)
        print(response or "这句话不是任务或提醒指令。")
        return 0

    service = TaskService(home=home, persist=True, members=members)
    if args.action == "list":
        tasks = service.list_tasks(viewer_id=owner, statuses={"proposed", "needs_confirmation", "scheduled", "failed"})
        if not tasks:
            print("没有待办任务。")
            return 0
        for task in tasks:
            due = task.due_at or "时间待定"
            print(f"{task.status}\t{task.visibility}\t{task.title}\t{due}\t{task.task_id}")
        return 0
    if args.action == "add":
        task = service.create_task(owner_member_id=owner, title=args.title, due_at=args.due,
                                   timezone_name=args.timezone, visibility=args.visibility,
                                   kind="reminder" if args.due else "task",
                                   metadata={"source": "local_cli", "category": "daily_life"})
        print(f"已保存：{task.title}；状态={task.status}；可见范围={task.visibility}；ID={task.task_id}")
        if task.due_at and task.visibility == "PRIVATE":
            print("安全提示：私人任务不会在公共客厅音箱自动播报。")
        return 0
    if args.action == "done":
        task = service.complete(args.task_id, owner_member_id=owner)
        print(f"已完成：{task.title}")
        return 0
    if args.action == "cancel":
        task = service.cancel(args.task_id, owner_member_id=owner)
        print(f"已取消：{task.title}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
