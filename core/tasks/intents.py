"""Conservative parser for explicit local todo commands (not reminder scheduling)."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskIntent:
    action: str
    title: str | None = None


_CREATE = re.compile(
    r"^(?:糖糖[，, ]*)?(?:请)?(?:帮我)?"
    r"(?:记个待办|记一个待办|记一下待办|添加待办|新增待办)"
    r"(?:事项)?[：:,， ]*(.{1,120})$"
)
_LIST = re.compile(
    r"^(?:糖糖[，, ]*)?(?:我的待办有哪些|我还有什么待办|还有什么待办"
    r"|看看我的待办|查看待办|列出待办|待办清单)(?:吗)?$"
)
_COMPLETE = re.compile(
    r"^(?:糖糖[，, ]*)?(?:完成待办|做完待办|标记完成)[：:,， ]*(.{1,120})$"
)
_CANCEL = re.compile(
    r"^(?:糖糖[，, ]*)?(?:取消待办|删除待办|忘掉待办)[：:,， ]*(.{1,120})$"
)


def _clean(value: str) -> str:
    return value.strip(" ，,。.!！?？:：").strip()


def parse_task_intent(text: str | None) -> TaskIntent | None:
    """Only explicit todo commands are handled; date-based alarms remain with cat-alarm.py."""
    raw = " ".join(str(text or "").strip().split()).strip(" ，,。.!！?？:：")
    if not raw or len(raw) > 150:
        return None

    match = _CREATE.fullmatch(raw)
    if match:
        title = _clean(match.group(1))
        if title and len(title) <= 120:
            return TaskIntent("create", title)

    if _LIST.fullmatch(raw):
        return TaskIntent("list")

    match = _COMPLETE.fullmatch(raw)
    if match:
        title = _clean(match.group(1))
        if title:
            return TaskIntent("complete", title[:120])

    match = _CANCEL.fullmatch(raw)
    if match:
        title = _clean(match.group(1))
        if title:
            return TaskIntent("cancel", title[:120])

    return None
