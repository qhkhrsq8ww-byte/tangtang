#!/usr/bin/env python3
"""Dispatch due local reminders. Use --deliver to enable audible output."""
from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.family_loader import load_members
from tangtang_paths import data_dir
from core.tasks.dispatcher import run_due
from core.tasks.service import TaskService

SAY = ROOT / "code" / "cat" / "cat-say.sh"


@contextmanager
def dispatch_lock(home: Path):
    """Prevent overlapping instances of this dispatcher on the same Mac."""
    lock_path = home / "tasks" / "task-dispatch.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("糖糖提醒派发器已经在运行；本次跳过，避免重复播放")
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def main() -> int:
    parser = argparse.ArgumentParser(description="糖糖本地到期提醒派发器")
    parser.add_argument("--deliver", action="store_true", help="实际调用本机语音播放；默认仅预览")
    args = parser.parse_args()
    home = Path(data_dir())
    os.environ.setdefault("TANGTANG_HOME", str(home))
    os.environ.setdefault("TANGTANG_DATA_DIR", str(home))
    members = load_members()
    if not members:
        print("未读取到家庭成员配置；未执行提醒。", file=sys.stderr)
        return 2
    service = TaskService(home=home, persist=True, members=members)

    if not args.deliver:
        due = []
        seen = set()
        for viewer_id in members:
            for task in service.due_tasks(viewer_id=viewer_id):
                if task.owner_member_id == viewer_id and task.task_id not in seen:
                    seen.add(task.task_id)
                    due.append(task)
        for task in due:
            print(f"[预览] {task.owner_member_id}: {task.title} ({task.task_id})")
        print(f"到期任务 {len(due)} 项；预览模式未更改任务状态。实际播放请加 --deliver。")
        return 0

    def deliver(task):
        if sys.platform != "darwin":
            print("当前不是 macOS；未执行真实语音播放，提醒保留失败状态。", file=sys.stderr)
            return False
        if os.environ.get("TANGTANG_TTS", "1").strip().lower() in {"0", "dry"}:
            print("当前 TANGTANG_TTS 为静音/干运行模式；不将提醒记为已投递。", file=sys.stderr)
            return False
        if not SAY.is_file():
            print("未找到 cat-say.sh；提醒未播放。", file=sys.stderr)
            return False
        result = subprocess.run(
            ["/bin/bash", str(SAY), task.title, "soft"],
            check=False,
            timeout=90,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"语音命令失败：{task.task_id}", file=sys.stderr)
            return False
        print(f"[播放命令成功，未验证实际听见] {task.task_id}")
        return True

    try:
        with dispatch_lock(home):
            recovered = service.recover_stale_running()
            if recovered:
                print(f"有 {recovered} 项中断提醒结果不确定，已标记待人工核查；不会自动重播。")
            stats = run_due(service, member_ids=members.keys(), deliver=deliver)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 0
    print("糖糖提醒派发结果：" + ", ".join(f"{key}={value}" for key, value in stats.items()))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
