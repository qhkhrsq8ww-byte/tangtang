"""Daily plan and lightweight reflection built from coarse labels, never raw dialogue."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.tasks.service import TaskService

FEEDBACK = frozenset({"completed", "partial", "skipped", "not_applicable"})
HABIT_LABELS = frozenset({"joined", "oppose", "silent", "defer", "wont", "unclear", "stop_today", "skip"})


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class DailyPlanService:
    """Small local-only plan store. It accepts structured items and coarse feedback only."""

    def __init__(self, *, home: str | Path, members: dict[str, Any],
                 task_service: TaskService | None = None):
        self.home = Path(home).expanduser().resolve()
        self.members = {str(k) for k in members}
        self.task_service = task_service or TaskService(
            home=self.home, persist=True, members=members
        )
        self.path = self.home / "daily-plan" / "daily-plan.json"
        self._rows: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            rows = data.get("plans", []) if isinstance(data, dict) else []
            if isinstance(rows, list):
                self._rows = [r for r in rows if isinstance(r, dict)
                              and r.get("member_id") in self.members
                              and r.get("feedback") in FEEDBACK | {None}]
        except (OSError, json.JSONDecodeError):
            self._rows = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "plans": self._rows[-2000:]},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
        os.chmod(self.path, 0o600)

    def add(self, *, member_id: str, plan_date: str, title: str,
            category: str = "daily_life", due_time: str | None = None) -> dict[str, Any]:
        member = str(member_id or "").strip()
        if member not in self.members:
            raise ValueError("unknown family member")
        date.fromisoformat(plan_date)
        title = str(title or "").strip()
        if not title or len(title) > 160:
            raise ValueError("title must contain 1–160 characters")
        if due_time is not None:
            try:
                datetime.strptime(due_time, "%H:%M")
            except ValueError as exc:
                raise ValueError("due_time must be HH:MM") from exc
        category = str(category or "daily_life").strip()
        if category not in {"study", "habit", "daily_life", "family", "rest"}:
            raise ValueError("unsupported plan category")
        row = {"plan_id": "plan_" + uuid4().hex, "member_id": member,
               "plan_date": plan_date, "title": title, "category": category,
               "due_time": due_time, "task_id": None, "feedback": None, "habit_label": None,
               "created_at": _stamp(), "updated_at": _stamp()}
        if due_time:
            due_at = datetime.fromisoformat(f"{plan_date}T{due_time}:00").replace(
                tzinfo=ZoneInfo("Asia/Shanghai")
            ).isoformat()
            task = self.task_service.create_task(
                owner_member_id=member, title=title, due_at=due_at,
                timezone_name="Asia/Shanghai", kind="task", visibility="PRIVATE",
                idempotency_key=f"daily-plan:{row['plan_id']}",
                metadata={"source": "daily_plan", "plan_id": row["plan_id"], "category": category},
            )
            row["task_id"] = task.task_id
        self._rows.append(row)
        self._save()
        return dict(row)

    def feedback(self, plan_id: str, *, member_id: str, result: str,
                 habit_label: str | None = None) -> dict[str, Any]:
        if result not in FEEDBACK:
            raise ValueError("invalid feedback")
        if habit_label is not None and habit_label not in HABIT_LABELS:
            raise ValueError("only coarse habit labels are allowed")
        for row in self._rows:
            if row["plan_id"] == plan_id and row["member_id"] == str(member_id):
                row["feedback"] = result
                row["habit_label"] = habit_label
                row["updated_at"] = _stamp()
                if result == "completed" and row.get("task_id"):
                    try:
                        self.task_service.complete(row["task_id"], owner_member_id=str(member_id),
                                                   result="daily_plan_feedback_completed")
                        row.pop("task_sync_error", None)
                    except (ValueError, PermissionError):
                        # Keep the child's feedback, but surface the mismatch instead of hiding it.
                        row["task_sync_error"] = "task_completion_sync_failed"
                self._save()
                return dict(row)
        raise PermissionError("plan item not found for this member")

    def today(self, *, member_id: str, plan_date: str | None = None) -> dict[str, Any]:
        member = str(member_id or "")
        if member not in self.members:
            return {"items": [], "summary": {"total": 0, "completed": 0, "open": 0}}
        day = plan_date or datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        items = [dict(r) for r in self._rows if r["member_id"] == member and r["plan_date"] == day]
        completed = sum(r.get("feedback") == "completed" for r in items)
        return {"items": sorted(items, key=lambda r: (r.get("due_time") or "99:99", r["created_at"])),
                "summary": {"total": len(items), "completed": completed,
                            "open": sum(r.get("feedback") is None for r in items)}}

    def reflection(self, *, member_id: str, plan_date: str | None = None) -> dict[str, Any]:
        snapshot = self.today(member_id=member_id, plan_date=plan_date)
        items = snapshot["items"]
        labels: dict[str, int] = {}
        for item in items:
            label = item.get("habit_label")
            if label in HABIT_LABELS:
                labels[label] = labels.get(label, 0) + 1
        return {"date": plan_date or datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(), "summary": snapshot["summary"],
                "habit_labels": labels,
                "prompt": "今天哪件事做起来比较顺？明天只挑一件最重要的事就好。"
                if items else "今天还没有计划。想先安排一件小事吗？"}
