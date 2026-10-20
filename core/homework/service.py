"""Local-first homework checklist. Photo bytes stay outside this metadata store."""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

STATUSES = frozenset({"pending", "in_progress", "needs_photo", "needs_review", "complete"})
SUBJECTS = frozenset({"语文", "数学", "英语", "科学", "其他"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_member(value: str) -> str:
    value = str(value or "").strip()
    if not value or len(value) > 80 or not re.fullmatch(r"[\w\-\u4e00-\u9fff]+", value):
        raise ValueError("invalid member id")
    return value


@dataclass
class HomeworkItem:
    item_id: str
    owner_member_id: str
    due_date: str
    subject: str
    title: str
    expected_pages: int | None = None
    status: str = "pending"
    notes: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


@dataclass
class HomeworkEvidence:
    evidence_id: str
    item_id: str
    owner_member_id: str
    local_relative_path: str
    review_status: str = "needs_review"
    review_summary: str = "尚未检查"
    created_at: str = field(default_factory=_now)


class HomeworkService:
    """Small local JSON repository; never stores raw image bytes or full OCR text."""

    def __init__(self, *, home: str | Path, members: dict[str, Any], persist: bool = True):
        self.home = Path(home).expanduser().resolve()
        self.members = {str(k) for k in members}
        self.persist = persist
        self.path = self.home / "homework" / "homework.json"
        self.items: dict[str, HomeworkItem] = {}
        self.evidence: dict[str, HomeworkEvidence] = {}
        if persist:
            self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        for row in data.get("items", []):
            try:
                item = HomeworkItem(**row)
                if item.owner_member_id in self.members and item.status in STATUSES:
                    self.items[item.item_id] = item
            except (TypeError, ValueError):
                continue
        for row in data.get("evidence", []):
            try:
                evidence = HomeworkEvidence(**row)
                if evidence.owner_member_id in self.members and evidence.item_id in self.items:
                    self.evidence[evidence.evidence_id] = evidence
            except (TypeError, ValueError):
                continue

    def _save(self) -> None:
        if not self.persist:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "version": 1,
            "items": [asdict(x) for x in self.items.values()],
            "evidence": [asdict(x) for x in self.evidence.values()],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
        os.chmod(self.path, 0o600)

    def add_item(self, *, owner_member_id: str, due_date: str, subject: str,
                 title: str, expected_pages: int | None = None, notes: str = "") -> HomeworkItem:
        owner = _safe_member(owner_member_id)
        if owner not in self.members:
            raise ValueError("unknown family member")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(due_date or "")):
            raise ValueError("due_date must be YYYY-MM-DD")
        if subject not in SUBJECTS:
            raise ValueError("unsupported subject")
        title = str(title or "").strip()
        if not title or len(title) > 240:
            raise ValueError("title must contain 1–240 characters")
        if expected_pages is not None and not 1 <= int(expected_pages) <= 200:
            raise ValueError("expected_pages must be 1–200")
        item = HomeworkItem(
            item_id=f"hw_{uuid4().hex}", owner_member_id=owner, due_date=due_date,
            subject=subject, title=title, expected_pages=expected_pages,
            notes=str(notes or "").strip()[:500],
        )
        self.items[item.item_id] = item
        self._save()
        return item

    def list_items(self, *, viewer_member_id: str, due_date: str | None = None) -> list[HomeworkItem]:
        viewer = _safe_member(viewer_member_id)
        if viewer not in self.members:
            return []
        rows = [x for x in self.items.values()
                if x.owner_member_id == viewer and (due_date is None or x.due_date == due_date)]
        return sorted(rows, key=lambda x: (x.due_date, x.subject, x.created_at))

    def set_status(self, item_id: str, *, owner_member_id: str, status: str) -> HomeworkItem:
        owner = _safe_member(owner_member_id)
        item = self.items.get(item_id)
        if not item or item.owner_member_id != owner:
            raise PermissionError("homework item not found for this member")
        if status not in STATUSES:
            raise ValueError("invalid status")
        item.status = status
        item.updated_at = _now()
        self._save()
        return item

    def add_evidence(self, item_id: str, *, owner_member_id: str,
                     local_relative_path: str) -> HomeworkEvidence:
        owner = _safe_member(owner_member_id)
        item = self.items.get(item_id)
        if not item or item.owner_member_id != owner:
            raise PermissionError("homework item not found for this member")
        rel = str(local_relative_path or "").strip().replace("\\", "/")
        if not rel or rel.startswith("/") or ".." in Path(rel).parts or len(rel) > 500:
            raise ValueError("evidence path must be a safe relative path")
        if not rel.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".heic")):
            raise ValueError("unsupported image type")
        evidence = HomeworkEvidence(
            evidence_id=f"evi_{uuid4().hex}", item_id=item_id,
            owner_member_id=owner, local_relative_path=rel,
        )
        self.evidence[evidence.evidence_id] = evidence
        item.evidence_ids.append(evidence.evidence_id)
        item.status = "needs_review"
        item.updated_at = _now()
        self._save()
        return evidence

    def record_review(self, evidence_id: str, *, owner_member_id: str,
                      review_status: str, summary: str) -> HomeworkEvidence:
        owner = _safe_member(owner_member_id)
        evidence = self.evidence.get(evidence_id)
        if not evidence or evidence.owner_member_id != owner:
            raise PermissionError("evidence not found for this member")
        if review_status not in {"looks_complete", "possible_missing", "blurry", "needs_human"}:
            raise ValueError("invalid review status")
        evidence.review_status = review_status
        # Keep a short finding, not OCR transcripts or the child's full answers.
        evidence.review_summary = str(summary or "").strip()[:300]
        self._save()
        item = self.items[evidence.item_id]
        if review_status == "looks_complete":
            # AI evidence alone must not mark the assignment complete.
            item.status = "needs_review"
        elif review_status == "blurry":
            item.status = "needs_photo"
        else:
            item.status = "needs_review"
        item.updated_at = _now()
        self._save()
        return evidence
