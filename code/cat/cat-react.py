#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 小朋友反应：按 data/child_reactions.json 分类、回一句、写账本、冷却。

账本只写粗标签，不写儿童原话。一轮最多再出声一次。
"""
from __future__ import print_function

import json
import os
import re
import sys
from datetime import datetime, timedelta

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CAT_DIR, "..", ".."))
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)
from tangtang_paths import data_dir  # noqa: E402

LEDGER_NAME = "cat-turn-ledger.json"
MAX_TURNS = 400
FORBIDDEN_KEYS = (
    "text", "transcript", "utterance", "pcm", "words", "say",
    "stt_text", "child_text", "heard",
)
CHILD_AUDIENCE = ("hanghang", "qiaqia")
ELDER_AUDIENCE = ("grandpa", "grandma", "grandad", "nainai", "yeye", "elder")


def now_dt():
    fake_day = (os.environ.get("TANGTANG_FAKE_TODAY") or "").strip()
    fake_time = (os.environ.get("TANGTANG_FAKE_TIME") or "").strip()
    if fake_day:
        t = fake_time or "12:00"
        if len(t) == 5:
            t = t + ":00"
        elif len(t) == 4:
            t = "0" + t + ":00"
        try:
            return datetime.strptime(fake_day + "T" + t, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return datetime.now().replace(microsecond=0)


def end_of_day(dt, extra_days=0):
    d = (dt + timedelta(days=extra_days)).replace(hour=23, minute=59, second=59)
    return d


def hm_minutes(dt):
    return dt.hour * 60 + dt.minute


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


def spec_paths():
    env = (os.environ.get("TANGTANG_REACTIONS_FILE") or "").strip()
    return [
        env,
        os.path.join(CAT_DIR, "child_reactions.json"),
        os.path.join(REPO_ROOT, "data", "child_reactions.json"),
    ]


def load_spec():
    for path in spec_paths():
        if path and os.path.isfile(path):
            data = load_json(path, None)
            if isinstance(data, dict) and data.get("scenes"):
                return data
    raise SystemExit("找不到 data/child_reactions.json")


def ledger_path(root=None):
    return os.path.join(root or data_dir(), LEDGER_NAME)


def load_ledger(root=None):
    path = ledger_path(root)
    data = load_json(path, {"version": 2, "turns": [], "cooldowns": {}, "defer": {}})
    data.setdefault("version", 2)
    data.setdefault("turns", [])
    data.setdefault("cooldowns", {})
    data.setdefault("defer", {})
    return data, path


def pair_key(event, audience):
    return "%s|%s" % ((event or "turn").strip(), (audience or "").strip())


def normalize_audience(who):
    w = (who or "").strip().lower()
    if w in ("qiaqia", "洽洽", "6", "grade6", "g6"):
        return "qiaqia"
    if w in ("hanghang", "航航", "2", "grade2", "g2"):
        return "hanghang"
    if w in ELDER_AUDIENCE or w in ("爷爷", "奶奶"):
        return "elder"
    return w or "hanghang"


def persona_for(audience, persona=""):
    p = (persona or os.environ.get("TANGTANG_PROFILE") or "").strip().lower()
    if p in ("friend", "play", "elder"):
        return p
    a = normalize_audience(audience)
    if a == "qiaqia":
        return "friend"
    if a == "hanghang":
        return "play"
    if a == "elder":
        return "elder"
    return "play"


def display_name(audience, persona=""):
    a = normalize_audience(audience)
    if a == "qiaqia":
        return "洽洽"
    if a == "hanghang":
        return "航航"
    env = (os.environ.get("TANGTANG_CHILD_NAME") or "").strip()
    return env or "小朋友"


def normalize_text(text):
    s = (text or "").strip()
    if not s:
        return ""
    trans = {
        "\u3000": "",
        " ": "",
        "\t": "",
        "\n": "",
        "\r": "",
        "，": ",",
        "。": ".",
        "！": "!",
        "？": "?",
        "～": "~",
    }
    for a, b in trans.items():
        s = s.replace(a, b)
    return s.lower()


def is_garbage_text(text, spec):
    s = (text or "").strip()
    if not s:
        return True
    prefixes = ((spec.get("scenes") or {}).get("unclear") or {}).get("detect", {}).get(
        "garbage_prefixes"
    ) or ["[STT", "[stt"]
    for p in prefixes:
        if s.startswith(p):
            return True
    return False


def sorted_keywords(words):
    items = [w for w in (words or []) if w]
    items.sort(key=lambda w: (-len(w), w))
    return items


def contains_keyword(norm, keywords):
    for kw in sorted_keywords(keywords):
        needle = normalize_text(kw)
        if needle and needle in norm:
            return kw
    return None


def only_particles(norm, particles):
    if not norm:
        return False
    compact = norm
    for p in sorted_keywords(particles):
        needle = normalize_text(p)
        if needle:
            compact = compact.replace(needle, "")
    compact = re.sub(r"[~.,!?啊呀啦哦嗯呵呃哈唔欸嘿哼]+", "", compact)
    return compact == ""


def listen_cfg(spec):
    listen = spec.get("listen") or {}
    silent_below = float(os.environ.get("TANGTANG_TURN_RMS") or listen.get("energy_silent_below") or 300)
    clear_at = float(os.environ.get("TANGTANG_TURN_RMS_CLEAR") or listen.get("energy_clear_reply_at") or 800)
    return silent_below, clear_at


def english_hint(prompt, spec):
    scene = (spec.get("scenes") or {}).get("wont") or {}
    helper = scene.get("english_helper") or {}
    fallback = helper.get("fallback_hint") or "这个词糖糖也刚学"
    text = (prompt or "").strip()
    if not text:
        return fallback
    m = re.search(
        r"([A-Za-z][A-Za-z' ]{0,24})\s*[，,：:是]\s*([\u4e00-\u9fff]{1,12})",
        text,
    )
    if m:
        return "%s，%s" % (m.group(1).strip(), m.group(2).strip())
    m = re.search(r"([\u4e00-\u9fff]{1,8})[：:，,]\s*([A-Za-z][A-Za-z' ]{0,24})", text)
    if m:
        return "%s，%s" % (m.group(2).strip(), m.group(1).strip())
    return fallback


def strip_other_child(reply, persona):
    names = (((load_spec_cached().get("sibling_present") or {}).get("other_names")) or {}).get(persona) or []
    s = reply or ""
    for n in names:
        s = s.replace(n, "你")
    return s


_SPEC_CACHE = None


def load_spec_cached():
    global _SPEC_CACHE
    if _SPEC_CACHE is None:
        _SPEC_CACHE = load_spec()
    return _SPEC_CACHE


def scene_obj(spec, sid):
    return (spec.get("scenes") or {}).get(sid) or {}


def should_speak_flag(scene, persona):
    flag = scene.get("speak_again")
    if flag is True:
        return True
    if flag is False:
        return False
    if flag == "tiny":
        replies = (scene.get("replies") or {}).get(persona) or []
        return any((r or "").strip() for r in replies)
    return False


def pick_from(options, deterministic):
    items = [r for r in (options or []) if (r or "").strip()]
    if not items:
        return ""
    if deterministic:
        return items[0]
    idx = now_dt().toordinal() + now_dt().hour
    return items[idx % len(items)]


def fill_reply(text, audience, persona, spec, prompt, event):
    s = text or ""
    s = s.replace("{name}", display_name(audience, persona))
    if "{hint}" in s:
        s = s.replace("{hint}", english_hint(prompt, spec))
    s = strip_other_child(s, persona)
    forbidden = spec.get("forbidden_reply_substrings") or []
    for bad in forbidden:
        if bad and bad in s:
            s = "汪汪～"
            break
    return s.strip()


def pick_reply(spec, sid, persona, audience, prompt, event, last_joined=False, deterministic=False):
    scene = scene_obj(spec, sid)
    if sid == "wont" and (event or "") == "english":
        helper = scene.get("english_helper") or {}
        key = "template_play" if persona == "play" else "template_friend"
        tmpl = helper.get(key) or helper.get("template_play") or ""
        if tmpl:
            return fill_reply(tmpl, audience, persona, spec, prompt, event)
    if sid == "joined" and last_joined:
        options = (scene.get("replies_soft") or {}).get(persona) or []
        text = pick_from(options, deterministic=True)
        if text:
            return fill_reply(text, audience, persona, spec, prompt, event)
    options = (scene.get("replies") or {}).get(persona) or []
    text = pick_from(options, deterministic)
    return fill_reply(text, audience, persona, spec, prompt, event)


def classify(spec, text="", rms=0, timeout=False, persona="play",
             event="english", audience="hanghang", prompt="",
             presence="unknown", present_kids=""):
    silent_below, clear_at = listen_cfg(spec)
    try:
        rms = float(rms or 0)
    except (TypeError, ValueError):
        rms = 0.0
    persona = persona_for(audience, persona)
    audience = normalize_audience(audience)
    raw = (text or "").strip()
    if is_garbage_text(raw, spec):
        raw = ""
    norm = normalize_text(raw)
    has_energy = (not timeout) and rms >= silent_below
    clear_reply = has_energy and rms >= clear_at

    def pack(sid, hit=""):
        scene = scene_obj(spec, sid)
        ledger = scene.get("ledger") or sid
        speak = should_speak_flag(scene, persona)
        voice = scene.get("voice") or "none"
        cooldown = (scene.get("cooldown") or {}).get("effect") or "none"
        return {
            "scene": sid,
            "ledger": ledger,
            "speak_again": bool(speak),
            "voice": voice if speak else "none",
            "cooldown": cooldown,
            "persona": persona,
            "audience": audience,
            "event": event or "turn",
            "hit": hit,
            "rms": int(round(rms)),
        }

    if persona == "elder" or audience == "elder":
        return pack("adult_interrupt") if "adult_interrupt" else {
            "scene": "adult_interrupt",
            "ledger": "adult_interrupt",
            "speak_again": False,
            "voice": "none",
            "cooldown": "none",
            "persona": "elder",
            "audience": audience,
            "event": event or "turn",
            "hit": "elder",
            "rms": int(round(rms)),
        }

    # 1. timeout / no energy
    if timeout or not has_energy:
        if timeout or rms <= 0:
            return pack("timeout")
        return pack("silent")

    scenes = spec.get("scenes") or {}

    # 2. stop_today
    hit = contains_keyword(norm, (scenes.get("stop_today") or {}).get("detect", {}).get("keywords"))
    if hit:
        return pack("stop_today", hit)

    # 3. oppose
    hit = contains_keyword(norm, (scenes.get("oppose") or {}).get("detect", {}).get("keywords"))
    if hit:
        return pack("oppose", hit)

    # 4. defer
    hit = contains_keyword(norm, (scenes.get("defer") or {}).get("detect", {}).get("keywords"))
    if hit:
        return pack("defer", hit)

    # 5. wont
    hit = contains_keyword(norm, (scenes.get("wont") or {}).get("detect", {}).get("keywords"))
    if hit:
        return pack("wont", hit)

    # perfunctory: only 嗯/哦/啊 and low energy
    particles = (scenes.get("perfunctory") or {}).get("detect", {}).get("keywords") or ["嗯", "哦", "啊"]
    if norm and not clear_reply and only_particles(norm, particles):
        return pack("perfunctory", "particle")

    # noncoop: 知道了 without doing
    hit = contains_keyword(norm, (scenes.get("noncoop") or {}).get("detect", {}).get("keywords"))
    if hit:
        return pack("noncoop", hit)

    # 6. joined keywords OR (energy + not negative)
    joined_kw = list(((scenes.get("joined") or {}).get("detect") or {}).get("keywords") or [])
    joined_kw += list(((scenes.get("joined") or {}).get("detect") or {}).get("keywords_short") or [])
    hit = contains_keyword(norm, joined_kw)
    if hit:
        return pack("joined", hit)
    if clear_reply:
        return pack("joined", "energy")

    # 7. energy but no useful text
    if has_energy and not norm:
        return pack("unclear")

    # 8. else silent
    return pack("silent")


def parse_schedule_slots(path=None):
    if not path:
        path = (os.environ.get("TANGTANG_SCHEDULE_FILE") or "").strip()
    if not path:
        path = os.path.join(CAT_DIR, "tangtang-schedule.conf")
    slots = []
    if not os.path.isfile(path):
        return slots
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                minute = int(parts[0])
                hour = int(parts[1])
            except ValueError:
                continue
            event = parts[2]
            arg = ""
            for tok in parts[3:]:
                if "=" in tok:
                    continue
                arg = tok
                break
            slots.append({
                "hour": hour,
                "minute": minute,
                "event": event,
                "arg": arg,
                "audience": normalize_audience(arg) if event == "english" else "",
            })
    return slots


def later_slot_exists(event, audience, when=None):
    when = when or now_dt()
    now_m = hm_minutes(when)
    audience = normalize_audience(audience)
    for slot in parse_schedule_slots():
        if slot["event"] != event:
            continue
        slot_aud = slot.get("audience") or ""
        if event == "english" and slot_aud and slot_aud != audience:
            continue
        slot_m = slot["hour"] * 60 + slot["minute"]
        if slot_m > now_m:
            return True
    return False


def last_joined_today(data, event, audience, when=None):
    when = when or now_dt()
    day = when.strftime("%Y-%m-%d")
    audience = normalize_audience(audience)
    for row in reversed(list(data.get("turns") or [])):
        ts = str(row.get("ts") or "")
        if not ts.startswith(day):
            continue
        if (row.get("event") or "") != (event or ""):
            continue
        aud = normalize_audience(row.get("audience") or row.get("who") or "")
        if aud != audience:
            continue
        return (row.get("scene") or row.get("result") or "") == "joined"
    return False


def consecutive_silent(data, event, audience, when=None, hours=24):
    when = when or now_dt()
    audience = normalize_audience(audience)
    spec = load_spec_cached()
    silent_class = set(spec.get("silent_class") or ["silent", "timeout", "perfunctory", "noncoop"])
    count = 0
    cutoff = when - timedelta(hours=hours)
    for row in reversed(list(data.get("turns") or [])):
        if (row.get("event") or "") != (event or ""):
            continue
        aud = normalize_audience(row.get("audience") or row.get("who") or "")
        if aud != audience:
            continue
        ts = parse_ts(row.get("ts"))
        if ts is None or ts < cutoff:
            break
        scene = row.get("scene") or row.get("result") or ""
        ledger = row.get("ledger") or ""
        if scene in silent_class or ledger == "silent":
            count += 1
            continue
        break
    return count


def oppose_count_days(data, event, audience, when=None, days=3):
    when = when or now_dt()
    audience = normalize_audience(audience)
    cutoff = when - timedelta(days=days)
    n = 0
    for row in list(data.get("turns") or []):
        if (row.get("event") or "") != (event or ""):
            continue
        aud = normalize_audience(row.get("audience") or row.get("who") or "")
        if aud != audience:
            continue
        scene = row.get("scene") or row.get("result") or ""
        if scene != "oppose":
            continue
        ts = parse_ts(row.get("ts"))
        if ts is None or ts < cutoff:
            continue
        n += 1
    return n


def parse_ts(value):
    s = str(value or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19] if "T" in s or " " in s else s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def apply_cooldown(data, decision, spec, when=None):
    when = when or now_dt()
    event = decision.get("event") or "turn"
    audience = normalize_audience(decision.get("audience") or "")
    key = pair_key(event, audience)
    scene = decision.get("scene") or ""
    effect = decision.get("cooldown") or "none"
    cooldowns = data.setdefault("cooldowns", {})
    defer = data.setdefault("defer", {})
    decision["muted_until"] = ""
    decision["defer_pending"] = False

    if scene == "defer":
        today = when.strftime("%Y-%m-%d")
        rec = defer.get(key) or {}
        used = int(rec.get("used") or 0)
        if later_slot_exists(event, audience, when) and used < 1:
            defer[key] = {
                "date": today,
                "pending": True,
                "used": used,
                "first_hm": when.strftime("%H:%M"),
            }
            decision["defer_pending"] = True
        else:
            until = end_of_day(when)
            cooldowns[key] = {
                "until_ts": until.isoformat(timespec="seconds"),
                "reason": "defer",
                "skip_tomorrow": False,
            }
            decision["muted_until"] = cooldowns[key]["until_ts"]
            defer[key] = {"date": today, "pending": False, "used": max(used, 1)}
        return data

    if scene == "oppose":
        days = int((spec.get("cooldown_defaults") or {}).get("oppose_skip_tomorrow_if_twice_in_days") or 3)
        n = oppose_count_days(data, event, audience, when, days=days)
        extra = 1 if n >= 2 else 0
        until = end_of_day(when, extra_days=extra)
        cooldowns[key] = {
            "until_ts": until.isoformat(timespec="seconds"),
            "reason": "oppose",
            "skip_tomorrow": bool(extra),
        }
        decision["muted_until"] = cooldowns[key]["until_ts"]
        decision["skip_tomorrow"] = bool(extra)
        return data

    if scene == "stop_today":
        until = end_of_day(when)
        cooldowns[key] = {
            "until_ts": until.isoformat(timespec="seconds"),
            "reason": "stop_today",
            "skip_tomorrow": False,
        }
        decision["muted_until"] = cooldowns[key]["until_ts"]
        return data

    if scene in set(spec.get("silent_class") or []) or effect == "skip_rest_of_today_after_consecutive":
        need = int((spec.get("cooldown_defaults") or {}).get("silent_consecutive_to_skip_today") or 2)
        hours = int((spec.get("cooldown_defaults") or {}).get("silent_consecutive_in_hours") or 24)
        n = consecutive_silent(data, event, audience, when, hours=hours)
        if n >= need:
            until = end_of_day(when)
            cooldowns[key] = {
                "until_ts": until.isoformat(timespec="seconds"),
                "reason": "silent",
                "skip_tomorrow": False,
            }
            decision["muted_until"] = cooldowns[key]["until_ts"]
        return data

    return data


def is_muted(event, audience, root=None, when=None):
    when = when or now_dt()
    data, _path = load_ledger(root)
    audience = normalize_audience(audience)
    key = pair_key(event, audience)
    cool = (data.get("cooldowns") or {}).get(key) or {}
    until = parse_ts(cool.get("until_ts"))
    if until and when <= until:
        return True, cool.get("reason") or "cooldown"
    rec = (data.get("defer") or {}).get(key) or {}
    if rec.get("date") == when.strftime("%Y-%m-%d"):
        if int(rec.get("used") or 0) >= 1 and not rec.get("pending"):
            return True, "defer_done"
        if rec.get("pending"):
            first = rec.get("first_hm") or "00:00"
            try:
                fh, fm = first.split(":")
                first_m = int(fh) * 60 + int(fm)
            except Exception:
                first_m = -1
            if hm_minutes(when) <= first_m:
                return True, "defer_wait"
            return False, "defer_retry"
    return False, ""


def consume_defer_retry(event, audience, root=None, when=None):
    when = when or now_dt()
    data, path = load_ledger(root)
    key = pair_key(event, normalize_audience(audience))
    rec = (data.get("defer") or {}).get(key) or {}
    if not (rec.get("pending") and rec.get("date") == when.strftime("%Y-%m-%d")):
        return False
    first = rec.get("first_hm") or "00:00"
    try:
        fh, fm = first.split(":")
        first_m = int(fh) * 60 + int(fm)
    except Exception:
        first_m = -1
    if hm_minutes(when) <= first_m:
        return False
    rec["pending"] = False
    rec["used"] = int(rec.get("used") or 0) + 1
    data.setdefault("defer", {})[key] = rec
    data.setdefault("cooldowns", {})[key] = {
        "until_ts": end_of_day(when).isoformat(timespec="seconds"),
        "reason": "defer_retry_done",
        "skip_tomorrow": False,
    }
    save_json(path, data)
    return True


def append_decision(decision, root=None, when=None, spoke_again=None):
    when = when or now_dt()
    data, path = load_ledger(root)
    scene = decision.get("scene") or "silent"
    ledger_label = decision.get("ledger") or scene
    if spoke_again is None:
        spoke = bool(decision.get("speak_again"))
        if not (decision.get("reply") or "").strip():
            spoke = False
    else:
        spoke = bool(spoke_again)
    row = {
        "ts": when.isoformat(timespec="seconds"),
        "event": decision.get("event") or "turn",
        "audience": normalize_audience(decision.get("audience") or ""),
        "persona": decision.get("persona") or "play",
        "scene": scene,
        "spoke_again": bool(spoke),
    }
    # 兼容客厅小回合旧字段；仍不含原话
    row["who"] = row["audience"]
    row["result"] = ledger_label
    row["ledger"] = ledger_label
    for k in FORBIDDEN_KEYS:
        row.pop(k, None)
    turns = list(data.get("turns") or [])
    turns.append(row)
    data["turns"] = turns[-MAX_TURNS:]
    apply_cooldown(data, decision, load_spec_cached(), when=when)
    save_json(path, data)
    check = json.loads(open(path, encoding="utf-8").read())
    last = (check.get("turns") or [])[-1]
    for bad in FORBIDDEN_KEYS:
        if bad in last:
            raise AssertionError("ledger leaked %s" % bad)
    return row, decision


def decide(spec, **kwargs):
    deterministic = kwargs.pop("deterministic", False)
    last_joined = kwargs.pop("last_joined", False)
    decision = classify(spec, **kwargs)
    persona = decision["persona"]
    reply = ""
    if decision["speak_again"]:
        reply = pick_reply(
            spec, decision["scene"], persona, decision["audience"],
            kwargs.get("prompt") or "", kwargs.get("event") or "turn",
            last_joined=last_joined, deterministic=deterministic,
        )
    if not reply:
        decision["speak_again"] = False
        decision["voice"] = "none"
    decision["reply"] = reply
    return decision


def run_apply(args):
    spec = load_spec()
    event = args.get("event") or "turn"
    audience = normalize_audience(args.get("audience") or "hanghang")
    persona = persona_for(audience, args.get("persona") or "")
    data, _path = load_ledger()
    last_j = last_joined_today(data, event, audience)
    decision = decide(
        spec,
        text=args.get("text") or "",
        rms=args.get("rms") or 0,
        timeout=bool(args.get("timeout")),
        persona=persona,
        event=event,
        audience=audience,
        prompt=args.get("prompt") or "",
        presence=args.get("presence") or "unknown",
        deterministic=bool(args.get("print")),
        last_joined=last_j,
    )
    if not args.get("print"):
        append_decision(decision, spoke_again=decision["speak_again"])
    return decision


def print_matrix(spec, persona="play"):
    order = spec.get("decision_order") or []
    print("decision_order: %s" % " > ".join(order))
    other = "friend" if persona == "play" else "play"
    for sid in order:
        scene = scene_obj(spec, sid)
        if not scene:
            continue
        speak = scene.get("speak_again")
        aud = "hanghang" if persona == "play" else "qiaqia"
        reply = pick_reply(spec, sid, persona, aud,
                           prompt="aunt，阿姨", event="english", deterministic=True)
        other_aud = "qiaqia" if other == "friend" else "hanghang"
        other_reply = pick_reply(spec, sid, other, other_aud,
                                 prompt="aunt，阿姨", event="english", deterministic=True)
        print("%s\t%s\t%s\tspeak=%s\t%s\t%s" % (
            scene.get("letter") or "",
            scene.get("name") or sid,
            sid,
            speak,
            scene.get("cooldown", {}).get("effect") or "none",
            reply or "（不回）",
        ))
        if other_reply and other_reply != reply:
            print("  另一人格：%s" % other_reply)


def _selftest():
    spec = load_spec()
    assert spec["scenes"]["oppose"]["speak_again"] is True
    assert spec["scenes"]["silent"]["speak_again"] is False

    d = classify(spec, text="不要", rms=2000, persona="play", event="english", audience="hanghang")
    assert d["scene"] == "oppose", d
    d = classify(spec, text="不要叫了", rms=2000, persona="play")
    assert d["scene"] == "stop_today", d
    d = classify(spec, text="", rms=0, timeout=True)
    assert d["scene"] == "timeout", d
    d = classify(spec, text="", rms=0, timeout=False)
    assert d["scene"] in ("timeout", "silent"), d
    d = classify(spec, text="等会儿", rms=2000)
    assert d["scene"] == "defer", d
    d = classify(spec, text="不会", rms=2000)
    assert d["scene"] == "wont", d
    d = classify(spec, text="好", rms=2000)
    assert d["scene"] == "joined", d
    d = classify(spec, text="嗯", rms=400)
    assert d["scene"] == "perfunctory", d
    d = classify(spec, text="嗯", rms=2000)
    assert d["scene"] == "joined", d
    d = classify(spec, text="知道了", rms=2000)
    assert d["scene"] == "noncoop" and d["speak_again"] is False, d
    d = classify(spec, text="", rms=500)
    assert d["scene"] == "unclear", d
    d = classify(spec, text="", rms=2000)
    assert d["scene"] == "joined", d
    d = classify(spec, text="I don't know", rms=2000)
    assert d["scene"] == "wont", d
    d = classify(spec, persona="elder", rms=2000, text="好")
    assert d["scene"] == "adult_interrupt" and d["speak_again"] is False, d

    play = decide(spec, text="不要", rms=2000, persona="play", event="english",
                  audience="hanghang", deterministic=True)
    friend = decide(spec, text="不要", rms=2000, persona="friend", event="english",
                    audience="qiaqia", deterministic=True)
    assert play["reply"] and friend["reply"]
    assert play["reply"] != friend["reply"]
    assert "汪汪" in play["reply"] and "汪汪" in friend["reply"]
    assert "洽洽" not in play["reply"]
    assert "航航" not in friend["reply"]

    silent = decide(spec, text="", rms=0, timeout=True, deterministic=True)
    assert silent["speak_again"] is False and silent["reply"] == ""

    import tempfile
    tmp = tempfile.mkdtemp(prefix="tangtang-react-")
    os.environ["TANGTANG_DATA_DIR"] = tmp
    os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-01"
    os.environ["TANGTANG_FAKE_TIME"] = "16:20"
    global _SPEC_CACHE
    _SPEC_CACHE = spec
    d1 = decide(spec, text="不要", rms=2000, persona="play", event="english",
                audience="hanghang", deterministic=True)
    append_decision(d1)
    muted, reason = is_muted("english", "hanghang")
    assert muted, reason
    muted_q, _ = is_muted("english", "qiaqia")
    assert not muted_q
    print("cat-react.py selftest ok")


def parse_cli(argv):
    args = {
        "cmd": argv[0] if argv else "help",
        "event": "turn",
        "audience": "hanghang",
        "persona": "",
        "text": "",
        "rms": 0,
        "timeout": False,
        "prompt": "",
        "presence": "unknown",
        "print": False,
    }
    rest = argv[1:]
    i = 0
    positional = []
    while i < len(rest):
        a = rest[i]
        if a in ("--print", "--dry-run", "-n"):
            args["print"] = True
        elif a == "--timeout":
            args["timeout"] = True
        elif a == "--event" and i + 1 < len(rest):
            i += 1
            args["event"] = rest[i]
        elif a == "--audience" and i + 1 < len(rest):
            i += 1
            args["audience"] = rest[i]
        elif a == "--persona" and i + 1 < len(rest):
            i += 1
            args["persona"] = rest[i]
        elif a == "--text" and i + 1 < len(rest):
            i += 1
            args["text"] = rest[i]
        elif a == "--rms" and i + 1 < len(rest):
            i += 1
            args["rms"] = rest[i]
        elif a == "--prompt" and i + 1 < len(rest):
            i += 1
            args["prompt"] = rest[i]
        elif a == "--presence" and i + 1 < len(rest):
            i += 1
            args["presence"] = rest[i]
        elif a.startswith("-"):
            pass
        else:
            positional.append(a)
        i += 1
    if positional:
        args["event"] = positional[0]
        if len(positional) > 1:
            args["audience"] = positional[1]
        if len(positional) > 2:
            args["text"] = " ".join(positional[2:])
    env_text = (os.environ.get("TANGTANG_TURN_TEXT") or "").strip()
    if env_text and not args["text"]:
        args["text"] = env_text
    env_prompt = (os.environ.get("TANGTANG_LAST_PROMPT") or "").strip()
    if env_prompt and not args["prompt"]:
        args["prompt"] = env_prompt
    return args


def main():
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "help"
    if cmd in ("selftest", "--selftest"):
        _selftest()
        return
    if cmd in ("help", "-h", "--help"):
        print("用法: classify|apply|muted|matrix|later-slot|selftest")
        print("小朋友反应：配合/反对/沉默/推迟/不会/听不清/今天别叫/敷衍/超时")
        return
    args = parse_cli(argv)
    cmd = args["cmd"]
    spec = load_spec()
    if cmd == "matrix":
        persona = persona_for(args["audience"], args["persona"])
        print_matrix(spec, persona)
        return
    if cmd == "later-slot":
        ok = later_slot_exists(args["event"], args["audience"])
        print("yes" if ok else "no")
        sys.exit(0 if ok else 1)
    if cmd == "muted":
        muted, reason = is_muted(args["event"], args["audience"])
        print("%s\t%s" % ("muted" if muted else "open", reason))
        sys.exit(0 if muted else 1)
    if cmd == "consume-defer":
        ok = consume_defer_retry(args["event"], args["audience"])
        print("consumed" if ok else "none")
        return
    if cmd in ("classify", "apply", "preview"):
        if cmd == "preview":
            args["print"] = True
        if cmd == "classify" or args["print"]:
            data, _p = load_ledger() if cmd == "apply" else ({"turns": []}, "")
            last_j = last_joined_today(data, args["event"], args["audience"]) if cmd == "apply" else False
            decision = decide(
                spec,
                text=args["text"],
                rms=args["rms"],
                timeout=args["timeout"],
                persona=persona_for(args["audience"], args["persona"]),
                event=args["event"],
                audience=args["audience"],
                prompt=args["prompt"],
                presence=args["presence"],
                deterministic=True,
                last_joined=last_j,
            )
            if cmd == "apply" and not args["print"]:
                append_decision(decision)
        else:
            decision = run_apply(args)
        print(json.dumps(decision, ensure_ascii=False))
        return
    print("用法: classify|apply|muted|matrix|later-slot|selftest", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
