#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖用户闹铃：本地 JSON + 确定性解析，不走 LLM，不改 crontab。

到期出声必须走 cat-say.sh（客厅默认输出 / 同一只蓝牙音箱）。
响铃顺序：短 Glass 铃 → 糖糖说话 → 轻音乐。不另开音箱、不新开守护进程。
夜间静默不挡响铃。上学闹铃仍在 tangtang-schedule.conf，互不抢。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import uuid
from datetime import datetime, timedelta

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)
from tangtang_paths import data_dir  # noqa: E402

STORE_NAME = "cat-alarms.json"
SAY_SCRIPT = os.path.join(CAT_DIR, "cat-say.sh")
LIB_SCRIPT = os.path.join(CAT_DIR, "cat-lib.sh")
MOOD_FILE = os.path.join(CAT_DIR, "cat-mood.txt")
BUNDLED_MUSIC = os.path.join(CAT_DIR, "assets", "alarm_light.wav")
WAKE_MUSIC = os.path.join(CAT_DIR, "assets", "wake_music_3min.mp3")

# Last ring() plan (chime / say / music). Tests inspect this; playback is skipped when TANGTANG_TTS=0.
last_ring_plan = None

# 设/定/叫我/闹铃/闹钟 — 取消优先。明早+时刻也算设。
SET_MARK = re.compile(r"(设(个|一个|定)?|定(个|一个)|叫我|闹铃|闹钟|明早|明天)")
CANCEL_ALL_MARK = re.compile(r"(不要叫我了|别叫我了|不用叫我了|别再叫我)")
CANCEL_MARK = re.compile(r"(取消|关掉|关闭|不要).{0,8}(闹铃|闹钟|叫我)|(闹铃|闹钟).{0,6}(取消|关掉)")
LIST_MARK = re.compile(r"(有(什么|哪些)?闹[铃钟]|闹[铃钟](几点|有哪些|列表))")

CN_DIGIT = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
CN_HOUR = "零一二三四五六七八九十"

MEMBER_ALIASES = (
    ("hanghang", ("航航", "弟弟")),
    ("qiaqia", ("洽洽", "姐姐")),
    ("grandpa", ("爷爷",)),
    ("grandma", ("奶奶",)),
    ("dad", ("爸爸",)),
)

_CLOCK_RE = re.compile(r"(?<!\d)(\d{1,2})[:：](\d{2})(?!\d)")
_CN_TIME_RE = re.compile(
    r"(早上|上午|中午|下午|傍晚|晚上|夜里|凌晨)?"
    r"([零〇一二三四五六七八九十两\d]{1,3})\s*[点點时時钟鐘]"
    r"(?:(半)|([零〇一二三四五六七八九十两\d]{1,3})\s*分?)?"
)


def now_dt():
    day = (os.environ.get("TANGTANG_FAKE_TODAY") or "").strip()
    hm = (os.environ.get("TANGTANG_FAKE_TIME") or "").strip()
    if day and hm:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(day + " " + hm, fmt)
            except ValueError:
                continue
    if day:
        try:
            base = datetime.strptime(day, "%Y-%m-%d")
            n = datetime.now()
            return base.replace(hour=n.hour, minute=n.minute, second=n.second, microsecond=0)
        except ValueError:
            pass
    if hm:
        try:
            h, m = hm.split(":", 1)
            n = datetime.now()
            return n.replace(hour=int(h), minute=int(m.split(":")[0]), second=0, microsecond=0)
        except (ValueError, IndexError):
            pass
    return datetime.now().replace(microsecond=0)


def store_path():
    return os.path.join(data_dir(), STORE_NAME)


def load_alarms():
    path = store_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get("alarms") or []
    if not isinstance(data, list):
        return []
    return [a for a in data if isinstance(a, dict)]


def save_alarms(alarms):
    path = store_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(list(alarms), f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _cn_int(token):
    s = (token or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if s.startswith("十"):
        rest = _cn_int(s[1:])
        return 10 + (rest or 0)
    if "十" in s:
        left, right = s.split("十", 1)
        tens = _cn_int(left)
        if tens is None:
            return None
        ones = _cn_int(right) if right else 0
        return tens * 10 + (ones or 0)
    if len(s) == 1 and s in CN_DIGIT:
        return CN_DIGIT[s]
    acc = 0
    for ch in s:
        if ch not in CN_DIGIT:
            return None
        acc = acc * 10 + CN_DIGIT[ch]
    return acc


def _apply_period(hour, period):
    if period in ("下午", "傍晚"):
        if hour < 12:
            return hour + 12
        return hour
    if period in ("晚上",):
        if hour == 12:
            return 0
        if hour < 12:
            return hour + 12
        return hour
    if period in ("中午",) and hour == 12:
        return 12
    if period in ("凌晨", "夜里") and hour == 12:
        return 0
    return hour


def _valid_hm(hour, minute):
    if hour is None or minute is None:
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def parse_time_token(text):
    """Return first HH:MM in text, or None. 一点都 is not a clock."""
    raw = (text or "").replace("一点都", " ").replace("一点也", " ")
    m = _CLOCK_RE.search(raw)
    if m:
        return _valid_hm(int(m.group(1)), int(m.group(2)))
    m = _CN_TIME_RE.search(raw)
    if not m:
        return None
    period, htok, half, mtok = m.group(1), m.group(2), m.group(3), m.group(4)
    hour = _cn_int(htok)
    if hour is None:
        return None
    hour = _apply_period(hour, period)
    if half:
        minute = 30
    elif mtok:
        minute = _cn_int(mtok)
        if minute is None:
            return None
    else:
        minute = 0
    return _valid_hm(hour, minute)


def _parse_member(text):
    t = text or ""
    for mid, aliases in MEMBER_ALIASES:
        for alias in aliases:
            if alias in t:
                return mid
    return None


def _parse_days(text, hm, now=None):
    t = text or ""
    now = now or now_dt()
    if any(w in t for w in ("每天", "天天", "每日")):
        return "daily", None
    if "今晚" in t:
        return "once", now.strftime("%Y-%m-%d")
    if "今天" in t:
        return "once", now.strftime("%Y-%m-%d")
    if "明早" in t or "明天" in t:
        return "once", (now + timedelta(days=1)).strftime("%Y-%m-%d")
    # 默认：下一次该时刻（已过则明天），一次
    if hm:
        try:
            h, m = map(int, hm.split(":"))
            candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        except ValueError:
            candidate = now
        if candidate <= now:
            candidate = candidate + timedelta(days=1)
        return "once", candidate.strftime("%Y-%m-%d")
    return "once", None


def parse(text, now=None):
    """Conservative intent. Non-alarm → action none."""
    raw = (text or "").strip()
    compact = raw.replace(" ", "")
    now = now or now_dt()
    result = {
        "action": "none",
        "time": None,
        "days": None,
        "date": None,
        "label": "",
        "member": _parse_member(compact),
        "text": raw,
    }
    if not compact:
        return result

    if CANCEL_ALL_MARK.search(compact):
        result["action"] = "cancel_all"
        result["time"] = parse_time_token(compact)
        return result
    if CANCEL_MARK.search(compact):
        hm = parse_time_token(compact)
        result["time"] = hm
        result["action"] = "cancel" if hm else "cancel_all"
        return result

    hm = parse_time_token(compact)
    result["time"] = hm
    if LIST_MARK.search(compact) and not hm:
        result["action"] = "list"
        return result
    if hm and SET_MARK.search(compact):
        days, date = _parse_days(compact, hm, now=now)
        result["action"] = "set"
        result["days"] = days
        result["date"] = date
        return result
    return result


def _new_id():
    return "alm_" + uuid.uuid4().hex[:10]


def set_alarm(time_hm, days="once", date=None, label="", member=None, enabled=True, now=None):
    hm = parse_time_token(str(time_hm)) or (time_hm if _CLOCK_RE.fullmatch(str(time_hm) or "") else None)
    if not hm:
        # already HH:MM
        if isinstance(time_hm, str) and re.fullmatch(r"\d{1,2}:\d{2}", time_hm):
            h, m = time_hm.split(":")
            hm = _valid_hm(int(h), int(m))
    if not hm:
        raise ValueError("bad time")
    now = now or now_dt()
    days = days or "once"
    if days == "once" and not date:
        _, date = _parse_days("", hm, now=now)
    alarms = load_alarms()
    for row in alarms:
        if (
            row.get("enabled")
            and row.get("time") == hm
            and (row.get("days") or "once") == days
            and (row.get("member") or None) == (member or None)
        ):
            row["date"] = date
            row["label"] = label or row.get("label") or ""
            row["enabled"] = True
            save_alarms(alarms)
            return row
    row = {
        "id": _new_id(),
        "time": hm,
        "days": days,
        "date": date,
        "label": label or "",
        "member": member or None,
        "enabled": bool(enabled),
        "created_at": now.isoformat(timespec="seconds"),
        "last_rung": None,
    }
    alarms.append(row)
    save_alarms(alarms)
    return row


def cancel(time_hm=None, member=None):
    """Remove matching enabled alarms. No time → all. Idempotent."""
    alarms = load_alarms()
    if not alarms:
        return 0
    hm = None
    if time_hm and time_hm not in ("all", "*", "全部"):
        hm = parse_time_token(str(time_hm)) or time_hm
        if isinstance(hm, str) and re.fullmatch(r"\d{1,2}:\d{2}", hm):
            h, m = hm.split(":")
            hm = _valid_hm(int(h), int(m))
    kept = []
    n = 0
    for row in alarms:
        match_time = hm is None or row.get("time") == hm
        match_mem = member is None or (row.get("member") or None) == member
        if row.get("enabled") and match_time and match_mem:
            n += 1
            continue
        kept.append(row)
    if n:
        save_alarms(kept)
    return n


def cancel_all(member=None):
    return cancel(None, member=member)


def list_alarms(enabled_only=True):
    rows = load_alarms()
    if enabled_only:
        rows = [r for r in rows if r.get("enabled")]
    return rows


def _weekday_ok(days, now):
    if not days or days in ("daily", "*", "once"):
        return True
    # 0=Sun ... 6=Sat (cron) or 1-5
    u = now.weekday()  # Mon=0
    cron = (u + 1) % 7  # Sun=0
    token = str(days)
    if token == "1-5":
        return u < 5
    parts = []
    for bit in token.split(","):
        bit = bit.strip()
        if "-" in bit:
            a, b = bit.split("-", 1)
            try:
                parts.extend(range(int(a), int(b) + 1))
            except ValueError:
                continue
        else:
            try:
                parts.append(int(bit))
            except ValueError:
                continue
    return cron in parts or (u + 1) in parts


def due(now=None):
    """Enabled alarms whose HH:MM matches now and should ring this minute."""
    now = now or now_dt()
    hm = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")
    stamp = now.strftime("%Y-%m-%d %H:%M")
    out = []
    for row in load_alarms():
        if not row.get("enabled"):
            continue
        if row.get("time") != hm:
            continue
        if row.get("last_rung") == stamp:
            continue
        days = row.get("days") or "once"
        if days == "once":
            date = row.get("date")
            if date and date != today:
                continue
        elif not _weekday_ok(days, now):
            continue
        out.append(row)
    return out


def format_time_zh(hhmm):
    try:
        h, m = map(int, hhmm.split(":"))
    except (ValueError, AttributeError):
        return hhmm or ""

    def n(x):
        if x <= 10:
            return "十" if x == 10 else CN_HOUR[x]
        if x < 20:
            return "十" + CN_HOUR[x - 10]
        return CN_HOUR[x // 10] + "十" + (CN_HOUR[x % 10] if x % 10 else "")

    if m == 0:
        return f"{n(h)}点"
    if m == 30:
        return f"{n(h)}点半"
    return f"{n(h)}点{n(m)}分"


def ring_line(alarm=None):
    label = ((alarm or {}).get("label") or "").strip()
    if label:
        return f"汪汪～ {label}"
    return "汪汪～ 该起床了"


def write_alarm_light_wav(path, seconds=24, rate=22050):
    """Original soft pentatonic bells + pad. No third-party / commercial samples.

    Not a downloaded ringtone. Safe to ship; keep under 1.5MB.
    """
    import math
    import struct
    import wave

    seconds = max(8, min(int(seconds), 40))
    n = int(rate * seconds)
    samples = [0.0] * n
    # C major pentatonic (Hz)
    notes = (523.25, 587.33, 659.25, 783.99, 880.00, 783.99, 659.25, 587.33)

    def add_bell(t0, freq, dur=1.85, amp=0.17):
        length = int(dur * rate)
        for i in range(length):
            idx = t0 + i
            if idx >= n:
                break
            t = i / rate
            env = math.exp(-t * 2.35) * (1.0 - math.exp(-t * 70.0))
            sig = (
                math.sin(2 * math.pi * freq * t)
                + 0.32 * math.sin(2 * math.pi * freq * 2.01 * t)
                + 0.10 * math.sin(2 * math.pi * freq * 3.02 * t)
            )
            samples[idx] += amp * env * sig

    t0 = int(0.28 * rate)
    step = int(1.42 * rate)
    i = 0
    while t0 < n - int(0.5 * rate):
        add_bell(t0, notes[i % len(notes)], amp=0.20 if i % 4 == 0 else 0.15)
        t0 += step
        i += 1

    fade_in = int(1.2 * rate)
    fade_out = int(1.6 * rate)
    for i in range(n):
        t = i / rate
        edge = 1.0
        if i < fade_in:
            edge = i / fade_in
        elif i > n - fade_out:
            edge = max(0.0, (n - i) / fade_out)
        pad = 0.035 * edge * (
            0.55 * math.sin(2 * math.pi * 130.81 * t)
            + 0.35 * math.sin(2 * math.pi * 196.00 * t)
        )
        samples[i] = samples[i] * edge + pad

    delay = int(0.20 * rate)
    wet = samples[:]
    for i in range(delay, n):
        wet[i] += 0.20 * samples[i - delay]
    samples = wet

    peak = max(1e-9, max(abs(x) for x in samples))
    scale = 0.52 / peak
    frames = b"".join(
        struct.pack("<h", max(-32767, min(32767, int(x * scale * 32767))))
        for x in samples
    )
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return path


def alarm_music_path():
    """Local light music: TANGTANG_ALARM_MUSIC → bundled wav → wake_music → synthesize."""
    env = (os.environ.get("TANGTANG_ALARM_MUSIC") or "").strip()
    if env and os.path.isfile(env):
        return os.path.abspath(env)
    if os.path.isfile(BUNDLED_MUSIC):
        return BUNDLED_MUSIC
    if os.path.isfile(WAKE_MUSIC):
        return WAKE_MUSIC
    dest = BUNDLED_MUSIC
    try:
        write_alarm_light_wav(dest)
        if os.path.isfile(dest):
            return dest
    except OSError:
        dest = os.path.join("/tmp", "tangtang_alarm_light.wav")
        write_alarm_light_wav(dest)
        return dest
    return dest


def ring_plan(alarm=None):
    """Describe the one-speaker ring: Glass → cat-say → light music."""
    return {
        "chime": "glass",
        "say": ring_line(alarm),
        "say_script": SAY_SCRIPT,
        "music": alarm_music_path(),
        "order": ("chime", "say", "music"),
        "speaker": "default",
    }


def _tts_enabled():
    return os.environ.get("TANGTANG_TTS", "1") != "0"


def play_alarm_chime():
    """Brief existing Glass.aiff via tangtang_alarm_chime. Same default output."""
    if not _tts_enabled():
        return
    if not os.path.isfile(LIB_SCRIPT):
        return
    subprocess.run(
        ["/bin/bash", "-c", ". " + shlex.quote(LIB_SCRIPT) + " && tangtang_alarm_chime"],
        timeout=20,
        check=False,
    )


def play_alarm_music(path=None):
    """Play light music through tangtang_play_audio (afplay / default Bluetooth)."""
    if not _tts_enabled():
        return
    path = path or alarm_music_path()
    if not path or not os.path.isfile(path):
        return
    if not os.path.isfile(LIB_SCRIPT):
        return
    seconds = (os.environ.get("TANGTANG_ALARM_MUSIC_SECONDS") or "30").strip() or "30"
    try:
        limit = max(8, min(int(seconds), 40))
    except ValueError:
        limit = 30
    cmd = (
        ". "
        + shlex.quote(LIB_SCRIPT)
        + " && tangtang_play_audio "
        + shlex.quote(path)
        + " "
        + str(limit)
    )
    subprocess.run(
        ["/bin/bash", "-c", cmd],
        timeout=limit + 20,
        check=False,
    )


def emit_wakeup_mood(text):
    """Reuse existing cat-mood.txt wakeup hook; do not invent visual states."""
    try:
        with open(MOOD_FILE, "w", encoding="utf-8") as f:
            f.write(f"[wakeup] {text}\n")
    except OSError:
        pass


def speak_via_say(text, mode="cute"):
    """Same speaker path as 糖糖 speech. TANGTANG_TTS=0 skips playback (tests)."""
    if not _tts_enabled():
        return text
    if not os.path.isfile(SAY_SCRIPT):
        return text
    subprocess.run(
        ["/bin/bash", SAY_SCRIPT, text, mode],
        timeout=90,
        check=False,
    )
    return text


def _mark_rung(alarm, now):
    stamp = now.strftime("%Y-%m-%d %H:%M")
    alarms = load_alarms()
    for row in alarms:
        if row.get("id") != alarm.get("id"):
            continue
        row["last_rung"] = stamp
        if (row.get("days") or "once") == "once":
            row["enabled"] = False
        break
    save_alarms(alarms)


def ring(alarm, now=None, speak_fn=None):
    """Glass chime → cat-say.sh → light music. Quiet hours must not block this.

    Sequential on the same default speaker. speak_fn / TANGTANG_TTS=0 skip afplay.
    """
    global last_ring_plan
    now = now or now_dt()
    plan = ring_plan(alarm)
    last_ring_plan = plan
    line = plan["say"]
    emit_wakeup_mood(line)
    fn = speak_fn or speak_via_say
    if speak_fn is None:
        play_alarm_chime()
    fn(line)
    if speak_fn is None:
        play_alarm_music(plan["music"])
    _mark_rung(alarm, now)
    return line


def ring_due(now=None, speak_fn=None):
    now = now or now_dt()
    lines = []
    for alarm in due(now):
        lines.append(ring(alarm, now=now, speak_fn=speak_fn))
    return lines


def confirm_set(alarm):
    zh = format_time_zh(alarm.get("time") or "")
    when = ""
    if (alarm.get("days") or "once") == "once" and alarm.get("date"):
        try:
            d = datetime.strptime(alarm["date"], "%Y-%m-%d").date()
            today = now_dt().date()
            if d == today + timedelta(days=1):
                when = "明早"
            elif d == today:
                when = "今天"
        except ValueError:
            pass
    if (alarm.get("days") or "") == "daily":
        return f"汪汪～ 好，每天{zh}叫你。"
    return f"汪汪～ 好，{when}{zh}叫你。"


def confirm_cancel(n):
    if n:
        return "汪汪～ 闹铃取消了。"
    return "汪汪～ 现在没有闹铃。"


def confirm_list(rows):
    enabled = [r for r in rows if r.get("enabled")]
    if not enabled:
        return "汪汪～ 现在没有闹铃。"
    bits = [format_time_zh(r.get("time") or "") for r in enabled]
    return "汪汪～ 有" + "、".join(bits) + "的闹铃。"


def handle_utterance(text, now=None, speak=False, speak_fn=None):
    """If text is alarm intent, apply store and return fixed 糖糖 copy. Else None."""
    intent = parse(text, now=now)
    action = intent.get("action")
    if action == "none":
        return None
    if action == "set":
        alarm = set_alarm(
            intent["time"],
            days=intent.get("days") or "once",
            date=intent.get("date"),
            label=intent.get("label") or "",
            member=intent.get("member"),
            now=now,
        )
        line = confirm_set(alarm)
    elif action == "cancel":
        n = cancel(intent.get("time"), member=intent.get("member"))
        line = confirm_cancel(n)
    elif action == "cancel_all":
        n = cancel_all(member=intent.get("member"))
        line = confirm_cancel(n)
    elif action == "list":
        line = confirm_list(list_alarms())
    else:
        return None
    if speak:
        (speak_fn or speak_via_say)(line)
    return line


def _print(line):
    if line:
        print(line)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="cat-alarm.py")
    sub = ap.add_subparsers(dest="cmd")

    p_parse = sub.add_parser("parse")
    p_parse.add_argument("text", nargs="+")

    p_handle = sub.add_parser("handle")
    p_handle.add_argument("text", nargs="+")
    p_handle.add_argument("--speak", action="store_true")

    p_set = sub.add_parser("set")
    p_set.add_argument("time")
    p_set.add_argument("--daily", action="store_true")
    p_set.add_argument("--once", action="store_true")
    p_set.add_argument("--date", default="")
    p_set.add_argument("--label", default="")
    p_set.add_argument("--member", default="")

    p_cancel = sub.add_parser("cancel")
    p_cancel.add_argument("time", nargs="?", default="all")

    sub.add_parser("list")
    sub.add_parser("cancel_all")

    p_due = sub.add_parser("due")
    p_due.add_argument("--ring", action="store_true")

    p_ring = sub.add_parser("ring")
    p_ring.add_argument("id", nargs="?")

    sub.add_parser("music-path")

    args = ap.parse_args(argv)
    cmd = args.cmd
    if not cmd:
        ap.print_help()
        return 2

    if cmd == "parse":
        print(json.dumps(parse("".join(args.text)), ensure_ascii=False))
        return 0
    if cmd == "handle":
        line = handle_utterance("".join(args.text), speak=args.speak)
        if line:
            print(line)
            return 0
        return 1
    if cmd == "set":
        days = "daily" if args.daily else "once"
        row = set_alarm(
            args.time,
            days=days,
            date=args.date or None,
            label=args.label,
            member=args.member or None,
        )
        print(confirm_set(row))
        return 0
    if cmd == "cancel":
        n = cancel(None if args.time in ("all", "", "*") else args.time)
        print(confirm_cancel(n))
        return 0
    if cmd == "cancel_all":
        print(confirm_cancel(cancel_all()))
        return 0
    if cmd == "list":
        print(confirm_list(list_alarms(enabled_only=False)))
        for row in list_alarms(enabled_only=False):
            flag = "开" if row.get("enabled") else "关"
            extra = row.get("days") or "once"
            print(f"{row.get('time')}\t{extra}\t{flag}\t{row.get('id')}")
        return 0
    if cmd == "due":
        rows = due()
        if args.ring:
            for line in ring_due():
                print(line)
            return 0
        print(json.dumps(rows, ensure_ascii=False))
        return 0
    if cmd == "ring":
        rows = load_alarms()
        target = None
        if args.id:
            target = next((r for r in rows if r.get("id") == args.id), None)
        if target is None:
            due_rows = due()
            target = due_rows[0] if due_rows else None
        if not target:
            return 1
        print(ring(target))
        return 0
    if cmd == "music-path":
        print(alarm_music_path())
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
