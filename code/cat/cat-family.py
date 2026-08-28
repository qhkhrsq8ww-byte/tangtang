#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 家庭成员与习惯记录（本地）

五口之家：爷爷 / 奶奶 / 爸爸 / 洽洽 / 航航
- 声纹只回答「是谁」
- 习惯库回答「这个人今天/最近发生了什么」
- unknown 不绑定到任何成员
- 儿童原话默认可进本机私有记录，但不进入家庭共享摘要
- 习惯流水只写本机硬盘，不入库、不写路由器盘（cat-habits.json）

用法:
  ./cat-family.py members
  ./cat-family.py resolve 航航
  ./cat-family.py who <pcm文件>
  ./cat-family.py observe 航航 "我写完作业了"
  ./cat-family.py log 爸爸 meal
  ./cat-family.py today
  ./cat-family.py summary [天数] [成员]
"""
import json, os, sys, uuid, importlib.util
from collections import Counter
from datetime import datetime, timedelta

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)
from tangtang_paths import data_dir, now_dt  # noqa: E402

DATA_DIR = data_dir()
REPO_DATA = os.path.abspath(os.path.join(CAT_DIR, "..", "..", "data"))
HABIT_FILE = os.path.join(DATA_DIR, "cat-habits.json")
MAX_EVENTS = 3000
PROFILES = ("play", "friend", "adult", "elder")

EVENT_TYPES = (
    "wake", "sleep", "meal", "water", "exercise", "screen",
    "study", "work", "outdoor", "home", "away", "chore", "conversation", "mood_signal",
)

CLASSIFY_RULES = (
    ("wake", ("起床", "醒来", "早安", "早上好")),
    ("sleep", ("睡觉", "晚安", "去睡", "困了")),
    ("meal", ("吃饭", "早饭", "午饭", "晚饭", "早餐", "午餐", "晚餐", "饿了")),
    ("study", ("作业", "写作业", "功课", "学习", "考试", "复习")),
    ("screen", ("玩手机", "平板", "看电视", "玩游戏")),
    ("exercise", ("跑步", "运动", "锻炼", "跳绳")),
    ("outdoor", ("遛狗", "牵绳", "带糖糖转转", "带糖糖出门", "出去玩", "出门", "到外面")),
    ("water", ("喝水", "口渴", "加水", "水碗")),
    ("home", ("回家", "到家", "我回来了")),
    ("chore", ("整理房间", "扫地", "洗碗", "做家务", "梳毛", "喂糖糖")),
    ("work", ("上班", "加班", "开会")),
    ("mood_signal", ("难过", "生气", "害怕", "不想上学")),
)


def now():
    return now_dt()


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def family_paths():
    env = (os.environ.get("TANGTANG_FAMILY_FILE") or "").strip()
    paths = []
    if env:
        paths.append(env)
    paths.extend([
        os.path.join(DATA_DIR, "family.json"),
        os.path.join(CAT_DIR, "family.json"),
        os.path.join(REPO_DATA, "family.json"),
    ])
    return paths


def load_family():
    for path in family_paths():
        data = load_json(path, None)
        if isinstance(data, dict) and data.get("members"):
            return data
    return {"version": "1.0", "members": []}


def members():
    return list(load_family().get("members") or [])


def _norm(s):
    return (s or "").strip().lower()


def resolve_member(who):
    """把称呼/别名/member_id 解析成成员。unknown 返回 None。"""
    key = (who or "").strip()
    if not key or key.lower() in ("unknown", "访客", "guest"):
        return None
    want = _norm(key)
    for m in members():
        aliases = [m.get("member_id"), m.get("display_name"), *(m.get("aliases") or [])]
        if any(_norm(a) == want for a in aliases if a):
            return m
    return None


def display_of(member):
    return (member or {}).get("display_name") or "小朋友"


def profile_of(member):
    p = ((member or {}).get("profile") or "play").strip().lower()
    return p if p in PROFILES else "play"


def classify_text(text):
    t = (text or "").replace(" ", "")
    if not t:
        return "conversation"
    for event_type, keys in CLASSIFY_RULES:
        if any(k in t for k in keys):
            return event_type
    return "conversation"


def load_habits():
    data = load_json(HABIT_FILE, {"version": "2", "events": [], "by_member": {}})
    if "events" not in data:
        # 兼容旧版 {logs:[{name,text,time,hour}]}
        events = []
        for row in data.get("logs") or []:
            who = resolve_member(row.get("name"))
            events.append({
                "event_id": "legacy_" + uuid.uuid4().hex[:8],
                "member_id": (who or {}).get("member_id") or "unknown",
                "timestamp": str(row.get("time") or ""),
                "type": classify_text(row.get("text") or ""),
                "source": "voice",
                "privacy": "private",
                "text": row.get("text") or "",
            })
        data = {"version": "2", "events": events, "by_member": data.get("members") or {}}
    data.setdefault("events", [])
    data.setdefault("by_member", {})
    return data


def save_habits(data):
    events = data.get("events") or []
    if len(events) > MAX_EVENTS:
        data["events"] = events[-MAX_EVENTS:]
    save_json(HABIT_FILE, data)


def _parse_ts(ts):
    if not ts:
        return None
    raw = str(ts).replace(" ", "T")[:19]
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def observe(who, text="", source="voice", event_type=None, confidence=None):
    # 自测夹具听写不是孩子原话，不进家庭习惯流水
    if (os.environ.get("TANGTANG_FIXTURE") or "").strip().lower() in ("1", "yes", "true", "on"):
        if source in ("voice", "stt", "listen"):
            return None
    member = resolve_member(who)
    member_id = (member or {}).get("member_id") or "unknown"
    if member_id == "unknown":
        text = ""
        event_type = "conversation"
        privacy = "public"
    else:
        event_type = event_type if event_type in EVENT_TYPES else classify_text(text)
        share = bool((member.get("permissions") or {}).get("family_summary"))
        privacy = "family" if share else "private"
    ts = now()
    entry = {
        "event_id": "evt_" + uuid.uuid4().hex[:12],
        "member_id": member_id,
        "timestamp": ts.isoformat(timespec="seconds"),
        "type": event_type,
        "source": source,
        "confidence": confidence,
        "privacy": privacy,
        "text": (text or "")[:200],
    }
    data = load_habits()
    data["events"].append(entry)
    stats = data["by_member"].setdefault(member_id, {
        "total": 0, "by_type": {}, "by_hour": {}, "days": [], "last": None,
    })
    stats["total"] = stats.get("total", 0) + 1
    stats.setdefault("by_type", {})
    stats["by_type"][event_type] = stats["by_type"].get(event_type, 0) + 1
    hour = str(ts.hour)
    stats.setdefault("by_hour", {})
    stats["by_hour"][hour] = stats["by_hour"].get(hour, 0) + 1
    day = ts.strftime("%Y-%m-%d")
    days = stats.setdefault("days", [])
    if day not in days:
        days.append(day)
        days[:] = days[-60:]
    stats["last"] = entry["timestamp"]
    save_habits(data)
    return entry


def _events_since(days, member_id=None):
    cutoff = now() - timedelta(days=days)
    out = []
    for e in load_habits().get("events") or []:
        ts = _parse_ts(e.get("timestamp") or "")
        if ts is None or ts < cutoff:
            continue
        if member_id and e.get("member_id") != member_id:
            continue
        out.append(e)
    return out


def _member_label(member_id):
    m = resolve_member(member_id)
    if m:
        return m.get("display_name")
    if member_id == "unknown":
        return "未识别访客"
    return member_id


TYPE_LABEL = {
    "wake": "起床", "sleep": "睡觉", "meal": "吃饭", "water": "喝水",
    "exercise": "运动", "screen": "屏幕", "study": "学习", "work": "工作",
    "outdoor": "外出", "home": "回家", "away": "不在家", "chore": "家务",
    "conversation": "说话", "mood_signal": "情绪",
}


def format_member_block(member_id, events, family_view=False):
    member = resolve_member(member_id)
    name = _member_label(member_id)
    types = Counter(e.get("type") or "conversation" for e in events)
    hours = sorted({_parse_ts(e.get("timestamp") or "").hour
                    for e in events if _parse_ts(e.get("timestamp") or "")})
    lines = [f"👤 {name}：{len(events)} 次"]
    if types:
        parts = [f"{TYPE_LABEL.get(t, t)}{n}" for t, n in types.most_common(6)]
        lines.append("   类型: " + "，".join(parts))
    if hours:
        lines.append("   活跃时段: " + "、".join(f"{h}点" for h in hours))
    share = bool((member or {}).get("permissions", {}).get("family_summary")) if member else False
    if (not family_view) and (share or (member and member.get("relation") != "child")):
        quoted = [e.get("text") for e in events if e.get("text") and e.get("type") != "conversation"]
        if quoted:
            lines.append("   最近线索: " + " / ".join(quoted[-2:]))
    # 儿童：家庭视图不展示原话；个人视图也不默认复述原话
    days_14 = []
    hour_days = {}
    for e in events:
        ts = _parse_ts(e.get("timestamp") or "")
        if not ts:
            continue
        d = ts.strftime("%Y-%m-%d")
        hour_days.setdefault(ts.hour, set()).add(d)
        days_14.append(d)
    stable = [h for h, ds in hour_days.items() if len(ds) >= 4]
    if stable:
        lines.append("   较稳规律: 常在 " + "、".join(f"{h}点" for h in sorted(stable)) + " 出现（仍需更多天验证）")
    return "\n".join(lines)


def summary(days=7, who=None, family_view=False):
    member = resolve_member(who) if who else None
    member_id = (member or {}).get("member_id") if member else None
    events = _events_since(days, member_id)
    title = f"最近 {days} 天习惯（共 {len(events)} 条）"
    if member:
        title += f" · {member.get('display_name')}"
    elif family_view:
        title += " · 家庭摘要（不含儿童原话）"
    print(title + "\n")
    if not events:
        print("暂无记录。先给五位家人建声纹，或用 ./cat-family.py observe 记下一条。")
        return
    order = [m["member_id"] for m in members()] + ["unknown"]
    seen = set()
    grouped = {}
    for e in events:
        grouped.setdefault(e.get("member_id") or "unknown", []).append(e)
    for mid in order:
        if mid in grouped:
            if family_view and mid != "unknown":
                m = resolve_member(mid)
                if m and m.get("relation") == "child" and not (m.get("permissions") or {}).get("family_summary"):
                    # 只报次数和类型，不报原话
                    print(format_member_block(mid, grouped[mid], family_view=True))
                    print()
                    seen.add(mid)
                    continue
            print(format_member_block(mid, grouped[mid], family_view=family_view))
            print()
            seen.add(mid)
    for mid, rows in grouped.items():
        if mid not in seen:
            print(format_member_block(mid, rows, family_view=family_view))
            print()


def today():
    summary(days=1, who=None, family_view=True)


def _load_vp():
    path = os.path.join(CAT_DIR, "cat-vp.py")
    spec = importlib.util.spec_from_file_location("tangtang_vp", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def who_from_pcm(pcm):
    vp = _load_vp()
    name, score = vp.identify_with_score(pcm)
    member = resolve_member(name) if name and name != "unknown" else None
    if not member or score < float(os.environ.get("TANGTANG_VOICE_THRESHOLD", "0.995")):
        return {
            "status": "unknown",
            "member_id": "",
            "display_name": "",
            "profile": "play",
            "confidence": round(float(score or 0), 4),
        }
    return {
        "status": "ok",
        "member_id": member["member_id"],
        "display_name": member["display_name"],
        "profile": profile_of(member),
        "confidence": round(float(score), 4),
    }


def print_who_line(info):
    print("{member_id}\t{display_name}\t{profile}\t{confidence}".format(
        member_id=info.get("member_id") or "unknown",
        display_name=info.get("display_name") or "",
        profile=info.get("profile") or "play",
        confidence=info.get("confidence") or 0,
    ))


def print_members():
    rows = members()
    if not rows:
        print("家庭名册为空，请检查 data/family.json")
        return
    print("家庭成员")
    for m in rows:
        print(f"- {m.get('display_name')}  id={m.get('member_id')}  人格={m.get('profile')}  别名={','.join(m.get('aliases') or [])}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "members"
    if cmd == "members":
        print_members()
    elif cmd == "resolve":
        who = sys.argv[2] if len(sys.argv) > 2 else ""
        m = resolve_member(who)
        if not m:
            print("unknown")
            sys.exit(1)
        print("{member_id}\t{display_name}\t{profile}".format(**{
            "member_id": m["member_id"],
            "display_name": m["display_name"],
            "profile": profile_of(m),
        }))
    elif cmd == "who":
        pcm = sys.argv[2] if len(sys.argv) > 2 else ""
        if not pcm:
            print("用法: cat-family.py who <pcm文件>", file=sys.stderr)
            sys.exit(1)
        print_who_line(who_from_pcm(pcm))
    elif cmd == "observe":
        who = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        text = sys.argv[3] if len(sys.argv) > 3 else ""
        e = observe(who, text, source="voice")
        print(f"✅ {e['timestamp']} {_member_label(e['member_id'])} {TYPE_LABEL.get(e['type'], e['type'])}")
    elif cmd == "log":
        who = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        event_type = sys.argv[3] if len(sys.argv) > 3 else "conversation"
        source = sys.argv[4] if len(sys.argv) > 4 else "manual"
        if source not in ("manual", "wifi", "voice", "presence"):
            source = "manual"
        e = observe(who, "", source=source, event_type=event_type)
        print(f"✅ {e['timestamp']} {_member_label(e['member_id'])} {TYPE_LABEL.get(e['type'], e['type'])}")
    elif cmd == "today":
        today()
    elif cmd == "summary":
        days = 7
        who = None
        family_view = False
        args = sys.argv[2:]
        if args and args[0] in ("--family", "family"):
            family_view = True
            args = args[1:]
        if args:
            try:
                days = int(args[0])
                who = args[1] if len(args) > 1 else None
            except ValueError:
                who = args[0]
                if len(args) > 1:
                    try:
                        days = int(args[1])
                    except ValueError:
                        pass
        if who and not resolve_member(who):
            print(f"未找到成员：{who}。可用：爷爷、奶奶、爸爸、洽洽、航航")
            sys.exit(1)
        summary(days=days, who=who, family_view=family_view or who is None)
    else:
        print("用法: members | resolve | who | observe | log | today | summary")
        sys.exit(1)


if __name__ == "__main__":
    main()
