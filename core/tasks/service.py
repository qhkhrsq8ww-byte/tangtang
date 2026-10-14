"""Small local-first task/commitment store for reminders and follow-up.

This module manages durable task state only. A scheduler/tool adapter is responsible
for delivery; callers must not claim a reminder was delivered just because it was
created or returned by due_tasks().
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from core.memory.paths import resolve_under, tangtang_home

STATUSES = frozenset({
    "proposed", "needs_confirmation", "scheduled", "running",
    "done", "failed", "cancelled",
})
KINDS = frozenset({"reminder", "follow_up", "commitment", "task"})
VISIBILITIES = frozenset({"PRIVATE", "FAMILY"})
FORBIDDEN_KEYS = frozenset({
    "speech", "text", "utterance", "transcript", "raw", "message",
    "audio", "pcm", "voiceprint", "embedding", "prompt",
})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now(clock) -> str:
    value = clock()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parse_aware(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("时间必须是 ISO 8601 格式") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("时间必须带时区偏移，例如 2026-10-15T09:00:00+08:00")
    return parsed


def _reject_raw_metadata(value: Any, trail: str = "metadata") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"{trail} contains forbidden raw-data field: {key}")
            _reject_raw_metadata(child, f"{trail}.{key}")
    elif isinstance(value, (list, tuple)):
        for i, child in enumerate(value):
            _reject_raw_metadata(child, f"{trail}[{i}]")
    elif not isinstance(value, (str, int, float, bool, type(None))):
        raise ValueError(f"{trail} must contain JSON-compatible values")


@dataclass
class Task:
    task_id: str
    owner_member_id: str
    kind: str
    title: str
    due_at: str | None
    timezone: str
    status: str
    visibility: str
    source_event_id: str | None
    idempotency_key: str | None
    created_at: str
    updated_at: str
    metadata: dict[str, Any]
    completed_at: str | None = None
    cancelled_at: str | None = None
    last_attempt_at: str | None = None
    result: str | None = None


class TaskService:
    """Local task repository with restart recovery, permissions and idempotency."""

    core_api_version = "4.0.0"

    def __init__(
        self,
        *,
        home: str | Path | None = None,
        persist: bool = False,
        members: Mapping[str, object] | None = None,
        clock=_now,
    ) -> None:
        self._clock = clock
        self._persist = bool(persist)
        self._home = tangtang_home(home) if self._persist else (
            Path(home).expanduser().resolve() if home is not None else None
        )
        self._member_ids = {str(key) for key in (members or {})}
        self._tasks: dict[str, Task] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        if self._persist:
            self._load()

    @property
    def path(self) -> Path | None:
        if self._home is None:
            return None
        return resolve_under(self._home, "tasks", "tasks.json")

    def _load(self) -> None:
        path = self.path
        if path is None or not path.is_file():
            return
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        rows = parsed.get("tasks") if isinstance(parsed, Mapping) else None
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            try:
                task = self._from_mapping(row)
            except (TypeError, ValueError):
                continue
            self._tasks[task.task_id] = task
            if task.idempotency_key:
                self._idempotency[(task.owner_member_id, task.idempotency_key)] = task.task_id

    def _from_mapping(self, row: Mapping[str, Any]) -> Task:
        owner = str(row.get("owner_member_id") or "").strip()
        kind = str(row.get("kind") or "")
        title = str(row.get("title") or "").strip()
        status = str(row.get("status") or "")
        visibility = str(row.get("visibility") or "PRIVATE")
        due = row.get("due_at")
        if not owner or not title or kind not in KINDS or status not in STATUSES or visibility not in VISIBILITIES:
            raise ValueError("invalid persisted task")
        if len(title) > 200:
            raise ValueError("task title too long")
        if due is not None:
            _parse_aware(str(due))
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        _reject_raw_metadata(metadata)
        return Task(
            task_id=str(row.get("task_id") or ""),
            owner_member_id=owner,
            kind=kind,
            title=title,
            due_at=str(due) if due is not None else None,
            timezone=str(row.get("timezone") or "UTC"),
            status=status,
            visibility=visibility,
            source_event_id=str(row.get("source_event_id") or "") or None,
            idempotency_key=str(row.get("idempotency_key") or "") or None,
            created_at=str(row.get("created_at") or ""),
            updated_at=str(row.get("updated_at") or ""),
            metadata=dict(metadata),
            completed_at=str(row.get("completed_at") or "") or None,
            cancelled_at=str(row.get("cancelled_at") or "") or None,
            last_attempt_at=str(row.get("last_attempt_at") or "") or None,
            result=str(row.get("result") or "") or None,
        )

    def create_task(
        self,
        *,
        owner_member_id: str,
        title: str,
        due_at: str | None = None,
        timezone_name: str = "UTC",
        kind: str = "reminder",
        visibility: str = "PRIVATE",
        source_event_id: str | None = None,
        idempotency_key: str | None = None,
        status: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Task:
        owner = str(owner_member_id or "").strip()
        text = str(title or "").strip()
        if not owner:
            raise ValueError("owner_member_id is required")
        if self._member_ids and owner not in self._member_ids:
            raise ValueError("owner_member_id is not registered in this family")
        if not text or len(text) > 200:
            raise ValueError("title must contain 1–200 characters")
        if kind not in KINDS:
            raise ValueError("invalid task kind")
        if visibility not in VISIBILITIES:
            raise ValueError("invalid visibility")
        if due_at is not None:
            _parse_aware(due_at)
        if not str(timezone_name or "").strip():
            raise ValueError("timezone_name is required")
        meta = dict(metadata or {})
        _reject_raw_metadata(meta)
        key = str(idempotency_key or "").strip() or None
        if key:
            existing_id = self._idempotency.get((owner, key))
            if existing_id and existing_id in self._tasks:
                return self._tasks[existing_id]
        resolved_status = status or ("scheduled" if due_at else "proposed")
        if resolved_status not in STATUSES:
            raise ValueError("invalid task status")
        if resolved_status == "scheduled" and not due_at:
            raise ValueError("scheduled task requires due_at")
        now = _iso_now(self._clock)
        task = Task(
            task_id=f"task_{uuid4().hex}",
            owner_member_id=owner,
            kind=kind,
            title=text,
            due_at=_parse_aware(due_at).isoformat() if due_at else None,
            timezone=str(timezone_name),
            status=resolved_status,
            visibility=visibility,
            source_event_id=str(source_event_id or "") or None,
            idempotency_key=key,
            created_at=now,
            updated_at=now,
            metadata=meta,
        )
        self._tasks[task.task_id] = task
        if key:
            self._idempotency[(owner, key)] = task.task_id
        self._save()
        return task

    def get_task(self, task_id: str, *, viewer_id: str | None) -> Task | None:
        task = self._tasks.get(str(task_id))
        if task is None or not self._can_view(task, viewer_id):
            return None
        return task

    def list_tasks(
        self,
        *,
        viewer_id: str | None,
        statuses: set[str] | frozenset[str] | None = None,
        include_family: bool = True,
        limit: int = 100,
    ) -> list[Task]:
        if not viewer_id or limit <= 0:
            return []
        wanted = set(statuses or STATUSES)
        if not wanted <= STATUSES:
            raise ValueError("invalid task status filter")
        rows = [
            task for task in self._tasks.values()
            if task.status in wanted
            and self._can_view(task, viewer_id, include_family=include_family)
        ]
        rows.sort(key=lambda task: (task.due_at or "9999", task.created_at))
        return rows[: min(limit, 500)]

    def due_tasks(self, *, now: datetime | None = None, viewer_id: str | None) -> list[Task]:
        when = now or self._clock()
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        due: list[Task] = []
        for task in self.list_tasks(viewer_id=viewer_id, statuses={"scheduled"}):
            parsed = _parse_aware(task.due_at)
            if parsed is not None and parsed <= when:
                due.append(task)
        return due

    def claim_due(self, task_id: str, *, owner_member_id: str, now: datetime | None = None) -> Task | None:
        """Atomically claim a due reminder within this service instance.

        A claimed task becomes running before delivery, so subsequent scans do not
        replay it. Deploy one scheduler process per data home; the JSON repository
        is not a cross-process locking database.
        """
        task = self._tasks.get(str(task_id))
        if task is None or task.owner_member_id != str(owner_member_id or "").strip():
            return None
        if task.status != "scheduled" or not task.due_at:
            return None
        current = now or self._clock()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        due = _parse_aware(task.due_at)
        if due is None or due > current:
            return None
        task.status = "running"
        task.last_attempt_at = _iso_now(self._clock)
        task.updated_at = task.last_attempt_at
        task.result = "delivery_started"
        self._save()
        return task

    def finish_delivery(
        self,
        task_id: str,
        *,
        owner_member_id: str,
        success: bool,
        result: str | None = None,
    ) -> Task:
        """Record delivery adapter outcome; success means adapter returned success."""
        task = self._require_owner(task_id, owner_member_id)
        if task.status != "running":
            raise ValueError("only a running task can finish delivery")
        now = _iso_now(self._clock)
        task.status = "done" if success else "failed"
        task.updated_at = now
        task.completed_at = now if success else None
        task.result = (str(result or ("delivery_command_succeeded" if success else "delivery_failed")).strip()[:300] or None)
        self._save()
        return task

    def reschedule(self, task_id: str, *, owner_member_id: str, due_at: str, timezone_name: str | None = None) -> Task:
        task = self._require_owner(task_id, owner_member_id)
        if task.status not in {"proposed", "needs_confirmation", "scheduled", "failed"}:
            raise ValueError("task is not reschedulable in its current status")
        due = _parse_aware(due_at)
        if due is None:
            raise ValueError("due_at is required")
        task.due_at = due.isoformat()
        if timezone_name:
            task.timezone = str(timezone_name)
        task.status = "scheduled"
        task.updated_at = _iso_now(self._clock)
        task.result = None
        self._save()
        return task

    def complete(self, task_id: str, *, owner_member_id: str, result: str | None = None) -> Task:
        task = self._require_owner(task_id, owner_member_id)
        if task.status == "done":
            return task
        if task.status in {"cancelled", "failed"}:
            raise ValueError("cancelled/failed task cannot be completed without rescheduling")
        task.status = "done"
        task.completed_at = _iso_now(self._clock)
        task.updated_at = task.completed_at
        task.result = (str(result or "").strip()[:300] or None)
        self._save()
        return task

    def cancel(self, task_id: str, *, owner_member_id: str) -> Task:
        task = self._require_owner(task_id, owner_member_id)
        if task.status == "cancelled":
            return task
        if task.status == "done":
            raise ValueError("completed task cannot be cancelled")
        task.status = "cancelled"
        task.cancelled_at = _iso_now(self._clock)
        task.updated_at = task.cancelled_at
        self._save()
        return task

    def mark_attempt(self, task_id: str, *, owner_member_id: str, result: str | None = None) -> Task:
        task = self._require_owner(task_id, owner_member_id)
        if task.status not in {"scheduled", "running"}:
            raise ValueError("only scheduled/running task can record an attempt")
        task.last_attempt_at = _iso_now(self._clock)
        task.result = (str(result or "").strip()[:300] or None)
        task.updated_at = task.last_attempt_at
        self._save()
        return task

    def _require_owner(self, task_id: str, owner_member_id: str) -> Task:
        task = self._tasks.get(str(task_id))
        if task is None or task.owner_member_id != str(owner_member_id or "").strip():
            raise PermissionError("task not found for this owner")
        return task

    def _can_view(self, task: Task, viewer_id: str | None, *, include_family: bool = True) -> bool:
        viewer = str(viewer_id or "").strip()
        if not viewer:
            return False
        if task.owner_member_id == viewer:
            return True
        return (
            include_family
            and task.visibility == "FAMILY"
            and viewer in self._member_ids
            and task.owner_member_id in self._member_ids
        )

    def _save(self) -> None:
        if not self._persist:
            return
        path = self.path
        if path is None:
            raise ValueError("persistent TaskService requires a data home")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "tasks": [asdict(task) for task in self._tasks.values()]}
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
