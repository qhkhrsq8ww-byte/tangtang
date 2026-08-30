#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 本地习惯成长（规则更新，不是训练模型）

从客厅回合账本收集粗标签 → 写本机 cat-habit-growth.json → 下次少说、说得更准时。
不记小朋友原话、不录音、不上传、不改 crontab、不挪上学闹铃。
洽洽的标签不影响航航。

用法:
  ./cat-habits.py observe <who> <event> <scene> [line_id] [spoke 0|1] [presence]
  ./cat-habits.py ingest
  ./cat-habits.py should-speak <event> [who]
  ./cat-habits.py prefer-line <event> [who]
  ./cat-habits.py preview [who] [event]
  ./cat-habits.py note <event> [who]
  ./cat-habits.py decay
"""
import json
import os
import sys
from datetime import datetime, timedelta

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)
from tangtang_paths import data_dir  # noqa: E402

REPO_DATA = os.path.abspath(os.path.join(CAT_DIR, "..", "..", "data"))
STORE_NAME = "cat-habit-growth.json"
LEDGER_NAME = "cat-turn-ledger.json"
COUNTS = (
    "joined", "oppose", "silent", "defer", "wont", "unclear", "stop_today", "skip",
)
DEFAULT_FORBIDDEN = (
    "text", "transcript", "utterance", "pcm", "audio", "words", "say",
    "stt_text", "embedding", "voiceprint", "speech", "raw",
)


def now():
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
            return base.replace(hour=n.hour, minute=n.minute, second=n.second)
        except ValueError:
            pass
    return datetime.now()


def load_json(path, default):
    if not path or not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    return data if isinstance(data, dict) else default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def rules_path():
    env = (os.environ.get("TANGTANG_HABIT_GROWTH_FILE") or "").strip()
    for p in (
        env,
        os.path.join(REPO_DATA, "habit_growth.json"),
        os.path.join(CAT_DIR, "habit_growth.json"),
    ):
        if p and os.path.isfile(p):
            return p
    return os.path.join(REPO_DATA, "habit_growth.json")


def load_rules():
    data = load_json(rules_path(), {})
    if not data:
        data = {"version": 1, "labels": list(COUNTS)}
    data.setdefault("aliases", {})
    data.setdefault("scene_map", {})
    data.setdefault("forbidden_keys", list(DEFAULT_FORBIDDEN))
    data.setdefault("decay_days", 21)
    data.setdefault("max_people", 8)
    data.setdefault("max_events_per_person", 24)
    data.setdefault("max_recent_per_cell", 40)
    data.setdefault("max_line_scores", 12)
    data.setdefault("max_file_bytes", 65536)
    data.setdefault("defer_max_retries", 1)
    data.setdefault("hour_hint_min_joined", 3)
    data.setdefault("roles", {})
    return data


RULES = load_rules()
FORBIDDEN = tuple(RULES.get("forbidden_keys") or DEFAULT_FORBIDDEN)


def store_path(root=None):
    name = RULES.get("store") or STORE_NAME
    return os.path.join(root or data_dir(), name)


def ledger_path(root=None):
    name = RULES.get("ledger") or LEDGER_NAME
    return os.path.join(root or data_dir(), name)


def normalize_who(who):
    key = (who or "").strip()
    if not key:
        return ""
    aliases = RULES.get("aliases") or {}
    if key in aliases:
        return aliases[key]
    low = key.lower()
    if low in aliases:
        return aliases[low]
    return low


def role_of(who):
    who = normalize_who(who)
    roles = RULES.get("roles") or {}
    for name, spec in roles.items():
        if who in (spec.get("ids") or []):
            return name
    if who in ("qiaqia", "hanghang"):
        return "child"
    if who in ("grandpa", "grandma"):
        return "elder"
    return "adult"


def role_spec(who):
    name = role_of(who)
    spec = dict((RULES.get("roles") or {}).get(name) or {})
    spec.setdefault("silent_streak_24h", 2 if name == "child" else 3)
    spec.setdefault("oppose_7d_skip_tomorrow", 2 if name == "child" else 3)
    spec.setdefault("persistent_events", [])
    return spec


def kind_of(ts):
    return "weekend" if ts.weekday() >= 5 else "weekday"


def map_scene(raw, stt=False, rms=0, spoke=None):
    label = (raw or "").strip().lower()
    mapped = (RULES.get("scene_map") or {}).get(label, label)
    if mapped not in COUNTS:
        mapped = "skip"
    # 账本里的 wont：没开窗（无能量）当成 skip，孩子说「不会」才是 wont
    if mapped == "wont" and spoke is False:
        return "skip"
    if mapped == "wont" and spoke is None and not stt and int(rms or 0) <= 0:
        return "skip"
    return mapped


def empty_cell():
    return {
        "counts": {k: 0 for k in COUNTS},
        "last_ts": "",
        "last_scene": "",
        "streak_oppose": 0,
        "streak_silent": 0,
        "preferred_hour_hint": None,
        "hour_buckets": {},
        "muted_until": "",
        "mute_reason": "",
        "preferred_line_id": "",
        "line_scores": {},
        "defer_date": "",
        "defer_retries": 0,
        "spoke": 0,
        "skipped": 0,
        "recent": [],
    }


def strip_forbidden(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k).lower() in FORBIDDEN:
                continue
            out[k] = strip_forbidden(v)
        return out
    if isinstance(obj, list):
        return [strip_forbidden(x) for x in obj]
    return obj


def parse_ts(raw):
    if isinstance(raw, datetime):
        return raw
    s = str(raw or "").strip()
    if not s:
        return None
    s = s.replace(" ", "T")[:19]
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def iso(ts):
    if isinstance(ts, datetime):
        return ts.replace(microsecond=0).isoformat(timespec="seconds")
    return str(ts or "")


def end_of_day(ts):
    return ts.replace(hour=23, minute=59, second=59, microsecond=0)


def load_growth(root=None):
    data = load_json(store_path(root), {"version": 1, "people": {}, "applied": []})
    if not isinstance(data, dict):
        data = {"version": 1, "people": {}, "applied": []}
    data.setdefault("version", 1)
    data.setdefault("people", {})
    data.setdefault("applied", [])
    data.setdefault("last_line", {})
    return strip_forbidden(data)


def cap_growth(data):
    max_people = int(RULES.get("max_people") or 8)
    max_events = int(RULES.get("max_events_per_person") or 24)
    people = data.get("people") or {}
    scored = []
    for who, events in list(people.items()):
        if not isinstance(events, dict):
            continue
        cells = []
        for event, kinds in list(events.items()):
            if not isinstance(kinds, dict):
                continue
            newest = ""
            for kind, cell in kinds.items():
                if not isinstance(cell, dict):
                    continue
                ts = cell.get("last_ts") or ""
                if ts > newest:
                    newest = ts
                recent = list(cell.get("recent") or [])[-int(RULES.get("max_recent_per_cell") or 40):]
                cell["recent"] = recent
                scores = cell.get("line_scores") or {}
                if isinstance(scores, dict) and len(scores) > int(RULES.get("max_line_scores") or 12):
                    keep = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
                    cell["line_scores"] = dict(keep[: int(RULES.get("max_line_scores") or 12)])
            cells.append((newest, event))
        cells.sort()
        while len(cells) > max_events:
            old_event = cells.pop(0)[1]
            events.pop(old_event, None)
        newest_who = cells[-1][0] if cells else ""
        scored.append((newest_who, who))
    scored.sort()
    while len(scored) > max_people:
        old_who = scored.pop(0)[1]
        people.pop(old_who, None)
    data["applied"] = list(data.get("applied") or [])[-400:]
    return data


def save_growth(data, root=None):
    data = strip_forbidden(data)
    data = cap_growth(data)
    data["updated_at"] = iso(now())
    path = store_path(root)
    save_json(path, data)
    limit = int(RULES.get("max_file_bytes") or 65536)
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    if size > limit:
        people = data.get("people") or {}
        scored = []
        for who, events in people.items():
            for event, kinds in (events or {}).items():
                newest = ""
                for cell in (kinds or {}).values():
                    if isinstance(cell, dict) and (cell.get("last_ts") or "") > newest:
                        newest = cell.get("last_ts") or ""
                scored.append((newest, who, event))
        scored.sort()
        while scored and os.path.getsize(path) > limit:
            _, who, event = scored.pop(0)
            ((data.get("people") or {}).get(who) or {}).pop(event, None)
            save_json(path, strip_forbidden(data))
    return data


def get_cell(data, who, event, kind):
    who = normalize_who(who)
    event = (event or "turn").strip() or "turn"
    people = data.setdefault("people", {})
    events = people.setdefault(who, {})
    kinds = events.setdefault(event, {})
    cell = kinds.get(kind)
    if not isinstance(cell, dict):
        cell = empty_cell()
        kinds[kind] = cell
    cell.setdefault("counts", {k: 0 for k in COUNTS})
    for k in COUNTS:
        cell["counts"].setdefault(k, 0)
    cell.setdefault("recent", [])
    cell.setdefault("line_scores", {})
    cell.setdefault("hour_buckets", {})
    return cell


def count_scene_since(cell, scene, cutoff):
    n = 0
    for row in cell.get("recent") or []:
        if (row.get("scene") or "") != scene:
            continue
        ts = parse_ts(row.get("ts"))
        if ts is None:
            continue
        if cutoff is None or ts >= cutoff:
            n += 1
    return n


def parse_schedule_slots(event, who):
    env = (os.environ.get("TANGTANG_HABIT_SLOTS") or "").strip()
    if env:
        return [p.strip() for p in env.split(",") if p.strip()]
    path = os.path.join(CAT_DIR, "tangtang-schedule.conf")
    if not os.path.isfile(path):
        return []
    who = normalize_who(who)
    slots = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        minute, hour, ev = parts[0], parts[1], parts[2]
        arg = parts[3] if len(parts) > 3 and "=" not in parts[3] else ""
        if ev != event:
            continue
        if event == "english":
            arg_who = normalize_who(arg) if arg else "hanghang"
            if who and arg_who != who:
                continue
        try:
            slots.append("%02d:%02d" % (int(hour), int(minute)))
        except ValueError:
            continue
    return slots


def later_slot_exists(event, who, ts):
    hm = ts.strftime("%H:%M")
    return any(slot > hm for slot in parse_schedule_slots(event, who))


def scheduled_hour(event, who):
    slots = parse_schedule_slots(event, who)
    if not slots:
        return None
    try:
        return int(slots[0].split(":")[0])
    except ValueError:
        return None


def best_line(scores):
    if not scores:
        return ""
    positive = {k: v for k, v in scores.items() if (v or 0) > 0}
    pool = positive or scores
    return max(pool, key=lambda k: pool[k])


def bump_line(cell, line_id, scene):
    line_id = (line_id or "").strip()
    if not line_id:
        return
    if any(bad in line_id.lower() for bad in (" ", "说", "said")):
        return
    scores = cell.setdefault("line_scores", {})
    if scene == "joined":
        scores[line_id] = int(scores.get(line_id) or 0) + 1
    elif scene == "oppose":
        scores[line_id] = int(scores.get(line_id) or 0) - 2
    else:
        return
    cell["preferred_line_id"] = best_line(scores) or ""


def update_hour_hint(cell, ts, event, who):
    hour = str(ts.hour)
    buckets = cell.setdefault("hour_buckets", {})
    buckets[hour] = int(buckets.get(hour) or 0) + 1
    min_n = int(RULES.get("hour_hint_min_joined") or 3)
    best_h, best_n = None, 0
    for h, n in buckets.items():
        if int(n) > best_n:
            best_h, best_n = h, int(n)
    if best_h is None or best_n < min_n:
        return
    try:
        hint = int(best_h)
    except ValueError:
        return
    sched = scheduled_hour(event, who)
    if event == "alarm":
        return
    if sched is not None and hint == sched:
        cell["preferred_hour_hint"] = hint
        return
    cell["preferred_hour_hint"] = hint


def apply_rules(cell, scene, who, event, ts, spoke):
    spec = role_spec(who)
    persistent = event in (spec.get("persistent_events") or [])
    today = ts.strftime("%Y-%m-%d")
    if scene == "joined":
        cell["streak_oppose"] = 0
        cell["streak_silent"] = 0
        update_hour_hint(cell, ts, event, who)
        if cell.get("mute_reason") in ("defer_wait", "defer_done") and cell.get("defer_date") == today:
            cell["defer_retries"] = max(int(cell.get("defer_retries") or 0), 1)
        if (cell.get("muted_until") or "") and parse_ts(cell.get("muted_until")) and parse_ts(cell["muted_until"]) <= ts:
            cell["muted_until"] = ""
            cell["mute_reason"] = ""
    elif scene == "oppose":
        cell["streak_oppose"] = int(cell.get("streak_oppose") or 0) + 1
        cell["streak_silent"] = 0
        cell["muted_until"] = iso(end_of_day(ts))
        cell["mute_reason"] = "oppose"
        if event != "alarm":
            need = int(spec.get("oppose_7d_skip_tomorrow") or 2)
            n = count_scene_since(cell, "oppose", ts - timedelta(days=7))
            if n >= need:
                cell["muted_until"] = iso(end_of_day(ts + timedelta(days=1)))
                cell["mute_reason"] = "oppose_7d"
    elif scene == "stop_today":
        cell["streak_oppose"] = int(cell.get("streak_oppose") or 0) + 1
        cell["muted_until"] = iso(end_of_day(ts))
        cell["mute_reason"] = "stop_today"
        if event != "alarm":
            need = int(spec.get("oppose_7d_skip_tomorrow") or 2)
            n = count_scene_since(cell, "oppose", ts - timedelta(days=7)) + count_scene_since(
                cell, "stop_today", ts - timedelta(days=7)
            )
            if n >= need:
                cell["muted_until"] = iso(end_of_day(ts + timedelta(days=1)))
                cell["mute_reason"] = "stop_7d"
    elif scene == "silent":
        cell["streak_silent"] = int(cell.get("streak_silent") or 0) + 1
        need = int(spec.get("silent_streak_24h") or 2)
        if persistent:
            need = max(need, 3)
        n = count_scene_since(cell, "silent", ts - timedelta(hours=24))
        if n >= need:
            cell["muted_until"] = iso(end_of_day(ts))
            cell["mute_reason"] = "silent_streak"
    elif scene == "defer":
        if cell.get("defer_date") != today:
            cell["defer_date"] = today
            cell["defer_retries"] = 0
        used = int(cell.get("defer_retries") or 0)
        waiting = (cell.get("mute_reason") or "") == "defer_wait"
        if used == 0 and not waiting and later_slot_exists(event, who, ts):
            cell["muted_until"] = iso(ts.replace(minute=59, second=59, microsecond=0))
            cell["mute_reason"] = "defer_wait"
        else:
            cell["muted_until"] = iso(end_of_day(ts))
            cell["mute_reason"] = "defer_done"
            cell["defer_retries"] = max(used, 1)
    if spoke:
        cell["spoke"] = int(cell.get("spoke") or 0) + 1
        if scene != "defer" and cell.get("defer_date") == today and (
            (cell.get("mute_reason") or "") in ("defer_wait", "defer_done")
            or int(cell.get("defer_retries") or 0) == 0
        ):
            if (cell.get("mute_reason") or "") == "defer_wait":
                cell["defer_retries"] = max(int(cell.get("defer_retries") or 0), 1)
                cell["mute_reason"] = ""
                cell["muted_until"] = ""
    elif scene == "skip":
        cell["skipped"] = int(cell.get("skipped") or 0) + 1


def decay_cell(cell, ts):
    days = int(RULES.get("decay_days") or 21)
    cutoff = ts - timedelta(days=days)
    kept = []
    for row in cell.get("recent") or []:
        rt = parse_ts(row.get("ts"))
        if rt is None or rt >= cutoff:
            kept.append({"ts": row.get("ts") or "", "scene": row.get("scene") or ""})
    cell["recent"] = kept[-int(RULES.get("max_recent_per_cell") or 40):]
    counts = {k: 0 for k in COUNTS}
    for row in cell["recent"]:
        sc = row.get("scene") or ""
        if sc in counts:
            counts[sc] += 1
    cell["counts"] = counts
    if cell.get("muted_until"):
        until = parse_ts(cell.get("muted_until"))
        if until is not None and until < ts:
            cell["muted_until"] = ""
            if cell.get("mute_reason") not in ("defer_wait",):
                cell["mute_reason"] = ""
    return cell


def decay_all(root=None):
    data = load_growth(root)
    ts = now()
    people = data.get("people") or {}
    for events in people.values():
        if not isinstance(events, dict):
            continue
        for kinds in events.values():
            if not isinstance(kinds, dict):
                continue
            for cell in kinds.values():
                if isinstance(cell, dict):
                    decay_cell(cell, ts)
    save_growth(data, root)
    return data


def turn_key(row):
    return "|".join([
        str(row.get("ts") or ""),
        str(row.get("who") or ""),
        str(row.get("event") or ""),
        str(row.get("result") or row.get("scene") or ""),
        str(row.get("rms") or ""),
    ])


def apply_turn(row, root=None):
    if not isinstance(row, dict):
        return None
    data = load_growth(root)
    key = turn_key(row)
    applied = data.setdefault("applied", [])
    if key in applied:
        return None
    who = normalize_who(row.get("who") or row.get("member") or "")
    event = (row.get("event") or "turn").strip() or "turn"
    if not who:
        return None
    ts = parse_ts(row.get("ts")) or now()
    raw = row.get("scene") or row.get("result") or "skip"
    spoke_raw = row.get("spoke")
    if spoke_raw is None:
        spoke_raw = row.get("should_speak")
    if spoke_raw is None:
        spoke_raw = row.get("speak")
    if spoke_raw in (True, 1, "1", "true", "yes"):
        spoke = True
    elif spoke_raw in (False, 0, "0", "false", "no"):
        spoke = False
    else:
        spoke = None
    scene = map_scene(raw, stt=bool(row.get("stt")), rms=row.get("rms") or 0, spoke=spoke)
    line_id = (row.get("line_id") or "").strip()
    if not line_id:
        line_id = (data.get("last_line") or {}).get("%s|%s" % (who, event)) or ""
    presence = row.get("presence") or ""
    if presence not in ("home", "away", "unknown", ""):
        presence = "unknown"
    kind = kind_of(ts)
    decay_cell(get_cell(data, who, event, kind), ts)
    cell = get_cell(data, who, event, kind)
    cell["recent"].append({"ts": iso(ts), "scene": scene})
    cell["recent"] = cell["recent"][-int(RULES.get("max_recent_per_cell") or 40):]
    cell["counts"][scene] = int(cell["counts"].get(scene) or 0) + 1
    cell["last_ts"] = iso(ts)
    cell["last_scene"] = scene
    if presence:
        cell["last_presence"] = presence
    bump_line(cell, line_id, scene)
    apply_rules(cell, scene, who, event, ts, spoke is True)
    applied.append(key)
    data["applied"] = applied[-400:]
    save_growth(data, root)
    return cell


def remember_line(who, event, line_id, root=None):
    who = normalize_who(who)
    line_id = (line_id or "").strip()
    if not who or not event or not line_id:
        return
    data = load_growth(root)
    data.setdefault("last_line", {})["%s|%s" % (who, event)] = line_id
    save_growth(data, root)


def ingest_ledger(root=None):
    data = load_json(ledger_path(root), {"turns": []})
    turns = data.get("turns") or []
    n = 0
    for row in turns:
        if apply_turn(row, root) is not None:
            n += 1
    if not turns:
        decay_all(root)
    return n


def cell_now(who, event, root=None):
    who = normalize_who(who)
    event = (event or "").strip() or "turn"
    data = load_growth(root)
    ts = now()
    cell = get_cell(data, who, event, kind_of(ts))
    decay_cell(cell, ts)
    return data, cell, ts


def audience(event, arg=""):
    event = (event or "").strip()
    arg = (arg or "").strip()
    env = (os.environ.get("TANGTANG_MEMBER_ID") or os.environ.get("TANGTANG_SPEAKER") or "").strip()
    if event == "english":
        return normalize_who(arg or env or "hanghang") or "hanghang"
    if env:
        return normalize_who(env)
    if arg and normalize_who(arg) in ("grandpa", "grandma", "dad", "qiaqia", "hanghang"):
        return normalize_who(arg)
    return ""


def should_speak(event, who="", root=None, readonly=None):
    who = normalize_who(who) or audience(event, who)
    if not who:
        return True, "ok no-audience"
    data, cell, ts = cell_now(who, event, root)
    if readonly is None:
        readonly = (os.environ.get("TANGTANG_HABIT_READONLY") or "") in ("1", "true", "yes")
    mu = cell.get("muted_until") or ""
    until = parse_ts(mu)
    if until is not None and ts <= until:
        return False, "muted_until=%s last_scene=%s reason=%s" % (
            mu, cell.get("last_scene") or "", cell.get("mute_reason") or "",
        )
    today = ts.strftime("%Y-%m-%d")
    reason = (cell.get("mute_reason") or "")
    if reason == "defer_armed" and cell.get("defer_date") == today:
        return False, "defer_retry_used last_scene=%s" % (cell.get("last_scene") or "defer")
    if (
        cell.get("defer_date") == today
        and int(cell.get("defer_retries") or 0) >= int(RULES.get("defer_max_retries") or 1)
        and reason in ("defer_done", "defer_armed")
    ):
        return False, "defer_retry_used last_scene=%s" % (cell.get("last_scene") or "defer")
    if reason == "defer_wait" and cell.get("defer_date") == today:
        if not readonly:
            cell["defer_retries"] = max(int(cell.get("defer_retries") or 0), 1)
            cell["mute_reason"] = "defer_armed"
            save_growth(data, root)
        return True, "defer_retry last_scene=%s" % (cell.get("last_scene") or "defer")
    return True, "ok last_scene=%s" % (cell.get("last_scene") or "")


def prefer_line(event, who="", root=None):
    who = normalize_who(who) or audience(event, who)
    if not who:
        return ""
    _, cell, _ = cell_now(who, event, root)
    return (cell.get("preferred_line_id") or "").strip()


def preview_line(who, event, root=None):
    who = normalize_who(who)
    event = (event or "").strip()
    if not who or not event:
        return ""
    _, cell, ts = cell_now(who, event, root)
    if not (cell.get("last_scene") or cell.get("muted_until") or cell.get("preferred_line_id")):
        return ""
    ok, reason = should_speak(event, who, root)
    mute = "mute" if not ok else "speak"
    hint = cell.get("preferred_hour_hint")
    hint_s = "" if hint in (None, "") else str(hint)
    parts = [
        who, event, kind_of(ts),
        "last=%s" % (cell.get("last_scene") or "-"),
        mute, reason.replace(" ", "_"),
    ]
    if hint_s:
        parts.append("hour_hint=%s" % hint_s)
    if cell.get("preferred_line_id"):
        parts.append("line=%s" % cell["preferred_line_id"])
    return " ".join(parts)


def preview_all(who=None, event=None, root=None):
    data = load_growth(root)
    who = normalize_who(who) if who else ""
    event = (event or "").strip()
    lines = []
    people = data.get("people") or {}
    order = list(RULES.get("people") or []) + [k for k in people if k not in (RULES.get("people") or [])]
    for mid in order:
        if who and mid != who:
            continue
        events = people.get(mid) or {}
        for ev in sorted(events):
            if event and ev != event:
                continue
            line = preview_line(mid, ev, root)
            if line:
                lines.append(line)
    if not lines:
        return "（还没有习惯标签。回合账本只记配合/沉默/反对等，不记原话。）"
    return "\n".join(lines)


def observe(who, event, scene, line_id="", spoke=None, presence="unknown", ts=None, root=None):
    scene = (scene or "silent").strip()
    if spoke is None and scene in ("joined", "oppose", "defer", "wont", "unclear", "stop_today"):
        spoke = True
    if spoke is None and scene in ("silent", "skip"):
        spoke = False
    row = {
        "ts": iso(ts or now()),
        "who": normalize_who(who),
        "event": event,
        "result": scene,
        "scene": scene,
        "line_id": line_id or "",
        "spoke": spoke,
        "presence": presence or "unknown",
        "stt": False,
        "rms": 0 if scene in ("silent", "skip") else 1,
    }
    return apply_turn(row, root)


def dump_ok(root=None):
    raw = open(store_path(root), encoding="utf-8").read() if os.path.isfile(store_path(root)) else "{}"
    data = load_growth(root)
    blob = json.dumps(data, ensure_ascii=False)
    for key in FORBIDDEN:
        if '"%s"' % key in blob or "'%s'" % key in blob:
            return False, key
        if key in raw:
            return False, key
    return True, ""


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if cmd in ("-h", "--help", "help"):
        print(__doc__.strip())
        return
    if cmd == "observe":
        who = sys.argv[2] if len(sys.argv) > 2 else ""
        event = sys.argv[3] if len(sys.argv) > 3 else "turn"
        scene = sys.argv[4] if len(sys.argv) > 4 else "silent"
        line_id = sys.argv[5] if len(sys.argv) > 5 else ""
        spoke_s = sys.argv[6] if len(sys.argv) > 6 else ""
        presence = sys.argv[7] if len(sys.argv) > 7 else "unknown"
        spoke = None
        if spoke_s in ("1", "true", "yes"):
            spoke = True
        elif spoke_s in ("0", "false", "no"):
            spoke = False
        if line_id in ("-", "none", "0"):
            line_id = ""
        cell = observe(who, event, scene, line_id=line_id, spoke=spoke, presence=presence)
        print((cell or {}).get("last_scene") or scene)
        return
    if cmd == "ingest":
        n = ingest_ledger()
        print("ingested %d" % n)
        return
    if cmd == "should-speak":
        event = sys.argv[2] if len(sys.argv) > 2 else "turn"
        who = sys.argv[3] if len(sys.argv) > 3 else ""
        ok, reason = should_speak(event, who)
        print("%s|%s" % ("speak" if ok else "skip", reason))
        return
    if cmd in ("prefer-line", "prefer"):
        event = sys.argv[2] if len(sys.argv) > 2 else "turn"
        who = sys.argv[3] if len(sys.argv) > 3 else ""
        print(prefer_line(event, who))
        return
    if cmd == "note":
        event = sys.argv[2] if len(sys.argv) > 2 else "turn"
        who = sys.argv[3] if len(sys.argv) > 3 else audience(event)
        if not who:
            print("")
            return
        print(preview_line(who, event))
        return
    if cmd == "preview":
        who = sys.argv[2] if len(sys.argv) > 2 else ""
        event = sys.argv[3] if len(sys.argv) > 3 else ""
        print(preview_all(who, event))
        return
    if cmd == "decay":
        decay_all()
        print("decay ok")
        return
    if cmd == "remember-line":
        who = sys.argv[2] if len(sys.argv) > 2 else ""
        event = sys.argv[3] if len(sys.argv) > 3 else ""
        line_id = sys.argv[4] if len(sys.argv) > 4 else ""
        remember_line(who, event, line_id)
        print(line_id)
        return
    print("用法: observe | ingest | should-speak | prefer-line | preview | note | decay", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
