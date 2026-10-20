#!/usr/bin/env python3
"""Manage a local daily plan using only structured tasks and coarse habit feedback."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

CAT_DIR = Path(__file__).resolve().parent
ROOT = CAT_DIR.parent if (CAT_DIR.parent / "core").is_dir() else CAT_DIR.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.adapters.family_loader import load_members
from core.companion.daily_plan import DailyPlanService
from tangtang_paths import data_dir

LABEL_FOR_RESULT = {
    "completed": "joined",
    "partial": "defer",
    "skipped": "silent",
    "not_applicable": "skip",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="糖糖每日计划")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="新增计划")
    add.add_argument("--member", required=True)
    add.add_argument("--date", required=True, dest="plan_date")
    add.add_argument("--title", required=True)
    add.add_argument("--category", default="daily_life",
                     choices=["study", "habit", "daily_life", "family", "rest"])
    add.add_argument("--time", dest="due_time", help="可选，24小时制 HH:MM")
    listing = sub.add_parser("list", help="查看当天计划")
    listing.add_argument("--member", required=True)
    listing.add_argument("--date", dest="plan_date")
    feedback = sub.add_parser("feedback", help="记录完成反馈，不记录孩子原话")
    feedback.add_argument("plan_id")
    feedback.add_argument("--member", required=True)
    feedback.add_argument("--result", required=True,
                          choices=["completed", "partial", "skipped", "not_applicable"])
    reflection = sub.add_parser("reflection", help="轻量复盘")
    reflection.add_argument("--member", required=True)
    reflection.add_argument("--date", dest="plan_date")
    args = parser.parse_args()

    members = load_members()
    if not members:
        print("未读取到家庭成员配置。", file=sys.stderr)
        return 2
    service = DailyPlanService(home=Path(data_dir()), members=members)
    try:
        if args.command == "add":
            item = service.add(member_id=args.member, plan_date=args.plan_date,
                               title=args.title, category=args.category, due_time=args.due_time)
            print(json.dumps(item, ensure_ascii=False))
        elif args.command == "list":
            print(json.dumps(service.today(member_id=args.member, plan_date=args.plan_date),
                             ensure_ascii=False, indent=2))
        elif args.command == "reflection":
            print(json.dumps(service.reflection(member_id=args.member, plan_date=args.plan_date),
                             ensure_ascii=False, indent=2))
        elif args.command == "feedback":
            label = LABEL_FOR_RESULT[args.result]
            item = service.feedback(args.plan_id, member_id=args.member,
                                    result=args.result, habit_label=label)
            # Feed the existing habit-label system only a coarse label; never pass a transcript.
            habits = CAT_DIR / "cat-habits.py"
            if habits.is_file():
                subprocess.run(["/usr/bin/python3", str(habits), "observe",
                                args.member, "daily_plan", label, "-", "1", "home"],
                               capture_output=True, text=True, timeout=8, check=False)
            print(json.dumps(item, ensure_ascii=False))
    except (ValueError, PermissionError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
