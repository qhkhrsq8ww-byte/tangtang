#!/usr/bin/env python3
"""Audit whether the reminder dispatcher is installed and has actually run recently."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

CAT_DIR = Path(__file__).resolve().parent
ROOT = CAT_DIR.parent if (CAT_DIR.parent / "core").is_dir() else CAT_DIR.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tangtang_paths import data_dir


def inspect(home: Path, *, now: datetime | None = None, cron_text: str | None = None) -> dict:
    current = now or datetime.now().astimezone()
    if cron_text is None:
        try:
            result = subprocess.run(["/usr/bin/crontab", "-l"], capture_output=True,
                                    text=True, timeout=8, check=False)
            cron_text = result.stdout if result.returncode == 0 else ""
            cron_error = result.returncode != 0
        except (OSError, subprocess.TimeoutExpired):
            cron_text, cron_error = "", True
    else:
        cron_error = False

    installed = any("cat-task-dispatch.py" in line and "--deliver" in line
                    and not line.lstrip().startswith("#")
                    for line in cron_text.splitlines())
    log_path = home / "tasks" / "dispatch-health.jsonl"
    last = None
    log_error = ""
    if log_path.is_file():
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines[-200:]):
                try:
                    candidate = json.loads(line)
                    if candidate.get("mode") == "deliver" and candidate.get("ts"):
                        last = candidate
                        break
                except json.JSONDecodeError:
                    continue
        except OSError:
            log_error = "health_log_unreadable"

    age_seconds = None
    if last:
        try:
            stamp = datetime.fromisoformat(last["ts"])
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=current.tzinfo)
            age_seconds = max(0, int((current - stamp.astimezone(current.tzinfo)).total_seconds()))
        except (ValueError, TypeError):
            log_error = "health_timestamp_invalid"

    task_path = home / "tasks" / "tasks.json"
    counts = {"scheduled": 0, "delivered": 0, "failed": 0, "needs_confirmation": 0, "done": 0}
    if task_path.is_file():
        try:
            data = json.loads(task_path.read_text(encoding="utf-8"))
            for task in data.get("tasks", []):
                status = task.get("status")
                if status in counts:
                    counts[status] += 1
        except (OSError, json.JSONDecodeError, AttributeError):
            log_error = log_error or "task_store_unreadable"

    issues = []
    if cron_error:
        issues.append("cannot_read_crontab")
    if not installed:
        issues.append("dispatcher_not_installed")
    if not last:
        issues.append("no_delivery_run_record")
    elif age_seconds is not None and age_seconds > 180:
        issues.append("last_delivery_run_is_stale")
    if last and last.get("outcome") not in {"ok", "skipped"}:
        issues.append("last_delivery_run_not_ok")
    if counts["failed"]:
        issues.append("failed_tasks_need_review")
    if log_error:
        issues.append(log_error)

    return {
        "checked_at": current.isoformat(timespec="seconds"),
        "cron_installed": installed,
        "last_delivery_run": last,
        "last_delivery_age_seconds": age_seconds,
        "task_counts": counts,
        "issues": issues,
        "status": "healthy" if not issues else "attention_required",
        "note": "运行记录只证明本机命令执行结果，不证明孩子实际听见提醒。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="检查糖糖定时提醒是否安装并实际运行")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    report = inspect(Path(data_dir()))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("糖糖定时提醒健康检查：" + ("正常" if report["status"] == "healthy" else "需要处理"))
        print("crontab 已安装：" + ("是" if report["cron_installed"] else "否"))
        if report["last_delivery_run"]:
            print("最近运行：" + str(report["last_delivery_run"].get("ts")))
            print("最近结果：" + str(report["last_delivery_run"].get("outcome")))
            print("距今秒数：" + str(report["last_delivery_age_seconds"]))
        else:
            print("最近运行：无记录")
        print("任务状态：" + json.dumps(report["task_counts"], ensure_ascii=False))
        for issue in report["issues"]:
            print("待处理：" + issue)
        print(report["note"])
    return 0 if report["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
