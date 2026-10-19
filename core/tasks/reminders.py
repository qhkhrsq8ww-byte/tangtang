"""Conservative Chinese reminder phrase parser. Unclear times never become scheduled tasks."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class ReminderIntent:
    action: str
    title: str | None = None
    due_at: str | None = None
    timezone_name: str | None = None


_NUM = r"(?:\d{1,2}|[零〇一二两三四五六七八九十]{1,3})"
_DATE = r"(今天|明天|后天)"
_CLOCK = rf"(?:(上午|早上|中午|下午|傍晚|晚上)\s*)?({_NUM})(?:点|时)(半|\d{{1,2}}分?)?"
_CLOCK24 = r"(\d{1,2}):(\d{2})"


def _number(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        return (digits.get(left, 1) if left else 1) * 10 + (digits.get(right, 0) if right else 0)
    result = 0
    for char in value:
        result = result * 10 + digits[char]
    return result


def _timezone(now: datetime, timezone_name: str | None):
    if timezone_name:
        try:
            return ZoneInfo(timezone_name), timezone_name
        except ZoneInfoNotFoundError:
            pass
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.tzinfo, str(now.tzinfo)


def _parse_due(text: str, now: datetime, timezone_name: str | None) -> tuple[str | None, str | None]:
    tz, tz_label = _timezone(now, timezone_name)
    local_now = now.replace(tzinfo=timezone.utc).astimezone(tz) if now.tzinfo is None else now.astimezone(tz)
    date_match = re.search(_DATE, text)
    clock_match = re.search(_CLOCK, text)
    clock24 = re.search(_CLOCK24, text)
    if not clock_match and not clock24:
        return None, tz_label
    # An hour without a period (e.g. "明天八点") is ambiguous.
    # Do not silently turn it into morning; caller must clarify.
    if clock_match and not clock_match.group(1):
        return None, tz_label
    if date_match:
        day_delta = {"今天": 0, "明天": 1, "后天": 2}[date_match.group(1)]
        day = (local_now + timedelta(days=day_delta)).date()
    else:
        day = local_now.date()
    if clock24:
        hour, minute = int(clock24.group(1)), int(clock24.group(2))
        if hour > 23 or minute > 59:
            return None, tz_label
    else:
        period, raw_hour, raw_minute = clock_match.groups()
        hour = _number(raw_hour)
        minute = 30 if raw_minute == "半" else int(re.sub(r"分$", "", raw_minute)) if raw_minute else 0
        if hour < 1 or hour > 12 or minute > 59:
            return None, tz_label
        if period in {"下午", "傍晚", "晚上"} and hour < 12:
            hour += 12
        elif period in {"上午", "早上"} and hour == 12:
            hour = 0
        elif period == "中午" and hour < 11:
            hour += 12
    due = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute, tzinfo=tz)
    if not date_match and due <= local_now:
        due += timedelta(days=1)
    return due.isoformat(), tz_label


def parse_reminder_intent(
    text: str | None, *, now: datetime | None = None, timezone_name: str | None = None
) -> ReminderIntent | None:
    """Parse explicit reminders; if time is absent, create a confirmation-needed draft."""
    raw = " ".join(str(text or "").strip().split()).strip(" ，,。.!！?？:：")
    if not raw or len(raw) > 180:
        return None
    if re.fullmatch(r"(?:糖糖[，, ]*)?(?:我的)?(?:提醒有哪些|查看提醒|列出提醒|提醒清单|我的提醒有哪些)(?:吗)?", raw):
        return ReminderIntent("list")
    cancel = re.match(r"^(?:糖糖[，, ]*)?(?:取消|删除)(?:提醒|闹钟)[：:,， ]*(.{1,120})$", raw)
    if cancel:
        return ReminderIntent("cancel", cancel.group(1).strip(" ，,。.!！?？:："))
    has_reminder_cue = bool(
        re.search(r"(提醒我|提醒一下我|提醒我一下|到时提醒我)", raw)
        or (re.search(r"(修改|调整|改到|改为|改成)", raw) and re.search(r"提醒", raw))
    )
    has_time_cue = bool(re.search(r"(今天|明天|后天|上午|早上|中午|下午|傍晚|晚上|\d{1,2}:\d{2}|点|时)", raw))
    if not has_reminder_cue:
        if has_time_cue:
            due_at, tz_label = _parse_due(raw, now or datetime.now().astimezone(), timezone_name)
            return ReminderIntent("time_reply", due_at=due_at, timezone_name=tz_label) if due_at else None
        return None
    if not has_time_cue:
        title = re.sub(r"^(?:糖糖[，, ]*)?(?:请)?(?:到时候)?提醒(?:一下)?我(?:一下)?", "", raw).strip(" ，,。.!！?？:：")
        title = re.sub(r"^(?:记得|别忘了|要)?", "", title).strip()
        if title:
            return ReminderIntent("needs_time", title[:120])
        return ReminderIntent("needs_details")
    clock_text = raw
    due_at, tz_label = _parse_due(clock_text, now or datetime.now().astimezone(), timezone_name)
    if due_at and re.search(r"(修改|调整|改到|改为|改成)", raw):
        title = raw
        title = re.sub(r"^(?:糖糖[，, ]*)?(?:请)?(?:把|帮我把)?", "", title)
        title = re.sub(r"(提醒我|提醒一下我|提醒我一下|到时提醒我|提醒)", " ", title)
        title = re.sub(_DATE, " ", title)
        title = re.sub(_CLOCK, " ", title)
        title = re.sub(_CLOCK24, " ", title)
        title = re.sub(r"(今天|明天|后天|上午|早上|中午|下午|傍晚|晚上|修改|调整|改到|改为|改成|时间|到)", " ", title)
        title = " ".join(title.split()).strip(" ，,。.!！?？:：")
        if title:
            return ReminderIntent("reschedule", title[:120], due_at, tz_label)
    if not due_at:
        # Preserve the reminder subject and ask for an explicit morning/afternoon/evening.
        ambiguous_clock = re.search(_CLOCK, raw)
        if ambiguous_clock and not ambiguous_clock.group(1):
            title = re.sub(r"^(?:糖糖[，, ]*)?(?:请)?(?:到时候)?提醒(?:一下)?我(?:一下)?", "", raw).strip(" ，,。.!！?？:：")
            title = re.sub(_DATE, " ", title)
            title = re.sub(_CLOCK, " ", title)
            title = re.sub(_CLOCK24, " ", title)
            title = re.sub(r"(上午|早上|中午|下午|傍晚|晚上|提醒我|提醒一下我|到时提醒我)", " ", title)
            title = " ".join(title.split()).strip(" ，,。.!！?？:：")
            return ReminderIntent("needs_period", title[:120] or None, timezone_name=tz_label)
        title = re.sub(r"^(?:糖糖[，, ]*)?(?:请)?(?:到时候)?提醒(?:一下)?我(?:一下)?", "", raw).strip(" ，,。.!！?？:：")
        title = re.sub(r"(今天|明天|后天|上午|早上|中午|下午|傍晚|晚上|\d{1,2}:\d{2}|点半?|时|\d+分?)", " ", title)
        title = " ".join(title.split()).strip(" ，,。.!！?？:：")
        return ReminderIntent("needs_time", title[:120] or None, timezone_name=tz_label)
    title = raw
    title = re.sub(r"^糖糖[，, ]*", "", title)
    title = re.sub(r"^(?:请)?(?:到时)?提醒(?:一下)?我(?:一下)?", "", title)
    title = re.sub(_DATE, " ", title)
    title = re.sub(_CLOCK, " ", title)
    title = re.sub(_CLOCK24, " ", title)
    title = re.sub(r"(上午|早上|中午|下午|傍晚|晚上|提醒我|提醒一下我|到时提醒我)", " ", title)
    title = re.sub(r"^(?:在|记得|别忘了|要)\s*", "", title)
    title = " ".join(title.split()).strip(" ，,。.!！?？:：")
    if not title:
        return ReminderIntent("needs_details", due_at=due_at, timezone_name=tz_label)
    return ReminderIntent("schedule", title[:120], due_at, tz_label)
