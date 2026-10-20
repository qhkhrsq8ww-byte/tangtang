"""Conservative Chinese voice intents for local tasks.

Only explicit reminder/task language is stored. Raw utterances are never persisted.
Ambiguous time is left as a proposed task and the child is asked to confirm a time.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.tasks.service import TaskService

ADD_MARKERS = ("提醒我", "帮我提醒", "安排个任务", "安排一个任务", "加个任务", "添加任务")
LIST_MARKERS = ("我的任务", "我的提醒", "我有什么要做", "有哪些任务", "提醒列表", "计划列表")
DONE_RE = re.compile(r"^(?:我)?(?:做完了|完成了|完成任务|我完成了)\s*(.+?)\s*[。！!？?]*$")
CANCEL_RE = re.compile(r"^(?:帮我)?(?:取消任务|取消提醒|删除任务)\s*(.+?)\s*[。！!？?]*$")
CLOCK_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
CN_CLOCK_RE = re.compile(r"(早上|上午|中午|下午|傍晚|晚上|夜里|凌晨)?\s*([零〇一二两三四五六七八九十\d]{1,3})\s*点(?:\s*(半|[零〇一二两三四五六七八九十\d]{1,2})\s*分?)?")
CN_NUM = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _number(raw: str) -> int | None:
    if raw.isdigit():
        return int(raw)
    if raw == "十":
        return 10
    if "十" in raw:
        left, right = raw.split("十", 1)
        a = _number(left) if left else 1
        b = _number(right) if right else 0
        return None if a is None or b is None else a * 10 + b
    if len(raw) == 1:
        return CN_NUM.get(raw)
    return None


def parse_due(text: str, *, now: datetime | None = None, timezone_name: str = "Asia/Shanghai") -> str | None:
    """Parse only explicit, bounded Chinese date/time phrases into ISO-8601."""
    zone = ZoneInfo(timezone_name)
    current = now or datetime.now(zone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=zone)
    current = current.astimezone(zone)
    day = current.date()
    if "后天" in text:
        day += timedelta(days=2)
    elif "明天" in text or "明早" in text:
        day += timedelta(days=1)
    elif "今天" in text or "今晚" in text:
        pass

    hour = minute = None
    match = CLOCK_RE.search(text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
    else:
        match = CN_CLOCK_RE.search(text)
        if match:
            period, raw_hour, raw_minute = match.groups()
            hour = _number(raw_hour)
            if raw_minute == "半":
                minute = 30
            elif raw_minute:
                minute = _number(raw_minute)
            else:
                minute = 0
            if hour is not None:
                if period in ("下午", "傍晚", "晚上") and hour < 12:
                    hour += 12
                elif period in ("凌晨", "夜里") and hour == 12:
                    hour = 0
                elif period in ("中午",) and hour < 11:
                    hour += 12
    if hour is None or minute is None or not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    due = datetime.combine(day, datetime.min.time(), tzinfo=zone).replace(hour=hour, minute=minute)
    if due <= current and not any(word in text for word in ("今天", "今晚", "明天", "明早", "后天")):
        due += timedelta(days=1)
    return due.isoformat()


def _clean_title(text: str) -> str:
    title = text
    for phrase in ADD_MARKERS:
        title = title.replace(phrase, "", 1)
    title = re.sub(r"(后天|明天|明早|今天|今晚|早上|上午|中午|下午|傍晚|晚上|夜里|凌晨)\s*", " ", title)
    title = CLOCK_RE.sub(" ", title)
    title = CN_CLOCK_RE.sub(" ", title)
    title = re.sub(r"^[，,：:\s]+|[，,。！!？?\s]+$", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def looks_like_task_intent(text: str) -> bool:
    utterance = (text or "").strip()
    return (
        any(marker in utterance for marker in ADD_MARKERS + LIST_MARKERS)
        or DONE_RE.match(utterance) is not None
        or CANCEL_RE.match(utterance) is not None
    )


def handle_voice_task(
    text: str,
    *,
    owner_member_id: str | None,
    members: dict,
    home: str,
    timezone_name: str = "Asia/Shanghai",
    now: datetime | None = None,
) -> str | None:
    """Return a spoken response when text is a task intent; otherwise None."""
    utterance = (text or "").strip()
    if not utterance:
        return None
    service = TaskService(home=home, persist=True, members=members)
    owner = str(owner_member_id or "").strip()

    if any(marker in utterance for marker in LIST_MARKERS):
        if not owner:
            return "我还没认出你是谁，所以先不读取个人任务。"
        tasks = service.list_tasks(viewer_id=owner, statuses={"proposed", "needs_confirmation", "scheduled", "failed"}, limit=10)
        if not tasks:
            return "你现在没有待办任务。想安排什么，可以直接告诉我。"
        rows = []
        for task in tasks:
            due = task.due_at or "时间待定"
            rows.append(f"{task.title}（{due}）")
        return "你现在有这些待办：" + "；".join(rows[:5])

    done_match = DONE_RE.match(utterance)
    cancel_match = CANCEL_RE.match(utterance)
    if done_match or cancel_match:
        if not owner:
            return "我还没认出你是谁，不能替你修改个人任务。"
        target = (done_match or cancel_match).group(1).strip()
        tasks = service.list_tasks(viewer_id=owner, statuses={"proposed", "needs_confirmation", "scheduled", "failed"}, limit=100)
        matches = [task for task in tasks if task.title == target]
        if len(matches) != 1:
            return "我没找到唯一匹配的任务。你可以先问我“我的任务”，再说完整任务名称。"
        task = matches[0]
        if done_match:
            service.complete(task.task_id, owner_member_id=owner)
            return f"好，已经把“{task.title}”标记完成啦。"
        service.cancel(task.task_id, owner_member_id=owner)
        return f"好，已经取消“{task.title}”啦。"

    if not any(marker in utterance for marker in ADD_MARKERS):
        return None
    if not owner:
        return "我还没认出你是谁，暂时不能替你保存个人提醒。"
    title = _clean_title(utterance)
    if len(title) < 2:
        return "你想让我提醒你做什么？告诉我具体事情就好。"
    due_at = parse_due(utterance, now=now, timezone_name=timezone_name)
    visibility = "FAMILY" if any(word in utterance for word in ("全家", "大家", "我们家一起", "家庭")) else "PRIVATE"
    key = f"voice:{owner}:{due_at or 'unscheduled'}:{title}"
    task = service.create_task(
        owner_member_id=owner,
        title=title,
        due_at=due_at,
        timezone_name=timezone_name,
        kind="reminder",
        visibility=visibility,
        idempotency_key=key,
        metadata={"source": "voice_intent", "category": "daily_life"},
    )
    if not due_at:
        return f"我先记下“{task.title}”。你想让我几点提醒你？例如“明天晚上八点”。"
    visibility_text = "家庭共享" if visibility == "FAMILY" else "只对你可见"
    local_due = datetime.fromisoformat(due_at).astimezone(ZoneInfo(timezone_name))
    due_label = local_due.strftime("%m月%d日 %H:%M")
    return f"好，我会在{due_label}提醒你“{task.title}”。这是{visibility_text}提醒。"
