#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客厅语音小回合：能量、关键词分类、短回句、账本、策略闸门。

糖糖是比熊玩伴，不是监督机器人。一轮最多回一句。
账本只写标签，不写儿童原话。记忆目录在 Mac Air 本机硬盘。
听写只用于判定 oppose/wont/stop/joined；PCM 回合结束由调用方删除。
"""
import array
import json
import math
import os
import random
import re
import sys
import tempfile

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)
from tangtang_paths import data_dir  # noqa: E402

LEDGER_NAME = "cat-turn-ledger.json"
MAX_TURNS = 400
FORBIDDEN_KEYS = ("text", "transcript", "utterance", "pcm", "words", "say")
RESULTS = (
    "joined", "joined_soft", "silent", "oppose", "wont", "stop", "unclear",
)
COOL_RESULTS = ("silent", "oppose")
SYSTEM_RESULTS = RESULTS + ("wont",)

DEFAULT_SPEAK = {
    "joined": True,
    "joined_soft": False,
    "silent": False,
    "oppose": True,
    "wont": True,
    "stop": True,
    "unclear": False,
}


def _repo_data():
    return os.path.abspath(os.path.join(CAT_DIR, "..", "..", "data"))


def _first_file(name, env_key):
    env = (os.environ.get(env_key) or "").strip()
    for p in (
        env,
        os.path.join(CAT_DIR, name),
        os.path.join(_repo_data(), name),
    ):
        if p and os.path.isfile(p):
            return p
    return None


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


def keywords():
    path = _first_file("cat-turn-keywords.json", "TANGTANG_TURN_KEYWORDS")
    data = load_json(path, {})
    data.setdefault("priority", ["stop", "oppose", "wont", "joined"])
    data.setdefault("cool_streak", 2)
    data.setdefault("scratch", [])
    data.setdefault("joined_short", ["好", "嗯", "来", "行"])
    data.setdefault("forbidden_reply", [])
    data.setdefault("scenes", [])
    return data


def replies_table():
    path = _first_file("cat-turn-replies.json", "TANGTANG_TURN_REPLIES")
    return load_json(path, {})


def ledger_path(root=None):
    return os.path.join(root or data_dir(), LEDGER_NAME)


def pcm_rms(path):
    if not path or not os.path.isfile(path) or os.path.getsize(path) < 2:
        return 0.0
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) < 2:
        return 0.0
    samples = array.array("h")
    try:
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
    except Exception:
        return 0.0
    if not samples:
        return 0.0
    acc = 0.0
    for s in samples:
        acc += float(s) * float(s)
    return math.sqrt(acc / len(samples))


def energy_label(path, threshold=None):
    if threshold is None:
        try:
            threshold = float(os.environ.get("TANGTANG_TURN_RMS") or "300")
        except ValueError:
            threshold = 300.0
    rms = pcm_rms(path)
    label = "joined" if rms >= threshold else "silent"
    return int(round(rms)), label


def write_pcm(kind, path, seconds=2, rate=16000):
    n = int(rate * seconds)
    if kind == "silent":
        samples = array.array("h", [0] * n)
    elif kind in ("quiet", "low", "scratch"):
        amp = 500 if kind != "scratch" else 5000
        burst = n if kind != "scratch" else max(1, int(rate * 0.08))
        samples = array.array("h", [0] * n)
        for i in range(burst):
            samples[i] = int(amp * math.sin(2 * math.pi * 440 * i / rate))
    else:
        samples = array.array("h")
        for i in range(n):
            samples.append(int(6000 * math.sin(2 * math.pi * 440 * i / rate)))
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(samples.tobytes())
    return path


def one_sentence(text, limit=80):
    s = (text or "").replace("\n", " ").replace("\r", " ").strip()
    if not s:
        return ""
    seps = ("。", "！", "？", "!", "?", "～", "~")
    cut = None
    for i, ch in enumerate(s):
        if ch in seps:
            cut = i
            break
    if cut is not None:
        s = s[: cut + 1].strip()
    s = " ".join(s.split())
    if len(s) > limit:
        s = s[:limit].rstrip()
    return s


def normalize_who(who):
    w = (who or "").strip().lower()
    if w in ("qiaqia", "洽洽", "6", "grade6", "g6"):
        return "qiaqia"
    if w in ("hanghang", "航航", "2", "grade2", "g2"):
        return "hanghang"
    if w in ("grandpa", "爷爷"):
        return "grandpa"
    if w in ("grandma", "奶奶"):
        return "grandma"
    return w or ""


def profile_for_who(who):
    w = normalize_who(who)
    if w == "qiaqia":
        return "friend"
    if w == "hanghang":
        return "play"
    if w in ("grandpa", "grandma"):
        return "elder"
    p = (os.environ.get("TANGTANG_PROFILE") or "play").strip().lower()
    return p if p in ("play", "friend", "elder") else "play"


def _kw_list(block):
    if isinstance(block, dict):
        return list(block.get("zh") or []) + list(block.get("en") or [])
    if isinstance(block, list):
        return list(block)
    return []


def _compact(s):
    return re.sub(r"\s+", "", (s or "").lower())


def _has_keyword(text, kw):
    if not kw:
        return False
    raw = (text or "").lower()
    k = kw.lower()
    if k in raw:
        return True
    return _compact(k) in _compact(raw)


def _strip_scratch(text, scratch):
    s = (text or "").strip()
    s = re.sub(r"[。，、！？,.!?;；~～…\s]+", "", s)
    items = sorted((scratch or []), key=len, reverse=True)
    changed = True
    while changed and s:
        changed = False
        for token in items:
            if token and s.startswith(token):
                s = s[len(token):]
                changed = True
                break
            if token and s.endswith(token):
                s = s[:-len(token)]
                changed = True
                break
    return s


def keyword_label(text, kw=None):
    """只看听写文本。返回 stop/oppose/wont/joined 或空。"""
    kw = kw or keywords()
    raw = (text or "").strip()
    if not raw:
        return ""
    for cat in kw.get("priority") or ("stop", "oppose", "wont", "joined"):
        phrases = _kw_list(kw.get(cat) or {})
        phrases = sorted(phrases, key=len, reverse=True)
        for p in phrases:
            if _has_keyword(raw, p):
                return cat
    compact = _strip_scratch(raw, kw.get("scratch") or [])
    if compact and len(_compact(compact)) <= 4:
        for short in kw.get("joined_short") or []:
            if _has_keyword(compact, short):
                return "joined"
    return ""


def _react():
    import importlib.util
    path = os.path.join(CAT_DIR, "cat-react.py")
    spec = importlib.util.spec_from_file_location("cat_react_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rms_for(energy, rms):
    try:
        val = float(rms or 0)
    except (TypeError, ValueError):
        val = 0.0
    e = (energy or "silent").strip().lower()
    if e in ("silent", "timeout"):
        return 0.0, True
    if val > 0:
        return val, False
    if e in ("quiet", "low"):
        return 400.0, False
    if e in ("voiced", "joined", "tone"):
        return 2000.0, False
    return 0.0, True


def classify(energy, stt_status, text="", rms=0, profile="play", who="hanghang", event="english"):
    """energy: silent|voiced|quiet；分类以 data/child_reactions.json 为准。"""
    react = _react()
    spec = react.load_spec()
    val, timeout = _rms_for(energy, rms)
    raw = (text or "").strip()
    stt = (stt_status or "off").strip().lower()
    if raw.startswith("[STT") or stt == "fail":
        raw = ""
    d = react.classify(
        spec, text=raw, rms=val, timeout=timeout,
        persona=profile or profile_for_who(who),
        event=event, audience=normalize_who(who) or who or "hanghang",
    )
    return d["scene"]


def _sibling_tokens(who):
    w = normalize_who(who)
    if w == "hanghang":
        return ("洽洽", "姐姐")
    if w == "qiaqia":
        return ("航航", "弟弟")
    return ("洽洽", "航航")


def _reply_forbidden(text, who, kw=None):
    kw = kw or keywords()
    s = text or ""
    for bad in kw.get("forbidden_reply") or []:
        if bad and bad in s:
            return True
    for tok in _sibling_tokens(who):
        if tok and tok in s:
            return True
    return False


def should_speak_label(label, table=None):
    table = table if table is not None else replies_table()
    speak_map = dict(DEFAULT_SPEAK)
    speak_map.update(table.get("speak") or {})
    return bool(speak_map.get(label, False))


def pick_reply(label, profile="play", who="", table=None, kw=None, index=None):
    """从 child_reactions.json 取一句。空=不说话。"""
    react = _react()
    spec = react.load_spec()
    sid = {"stop": "stop_today"}.get(label, label)
    persona = profile if profile in ("play", "friend", "elder") else profile_for_who(who)
    audience = normalize_who(who) or ("hanghang" if persona == "play" else "qiaqia")
    prompt = (os.environ.get("TANGTANG_LAST_PROMPT") or "").strip()
    return react.pick_reply(
        spec, sid, persona, audience, prompt, "english",
        last_joined=False, deterministic=(index is not None),
    )


def canned_reply(profile="play"):
    text = pick_reply("joined", profile=profile, index=0)
    if text:
        return text
    return "汪汪～"


def decide(energy, stt_status, text="", rms=0, profile="play", who="", index=None, event="english"):
    react = _react()
    spec = react.load_spec()
    val, timeout = _rms_for(energy, rms)
    raw = (text or "").strip()
    stt = (stt_status or "off").strip().lower()
    if raw.startswith("[STT") or stt == "fail":
        raw = ""
    persona = profile if profile in ("play", "friend", "elder") else profile_for_who(who)
    audience = normalize_who(who) or who or "hanghang"
    prompt = (os.environ.get("TANGTANG_LAST_PROMPT") or "").strip()
    d = react.decide(
        spec, text=raw, rms=val, timeout=timeout, persona=persona,
        event=event, audience=audience, prompt=prompt,
        deterministic=(index is not None),
    )
    return {
        "result": d.get("scene") or "silent",
        "speak": bool(d.get("speak_again") and d.get("reply")),
        "reply": d.get("reply") or "",
        "voice": d.get("voice") or "none",
        "scene": d.get("scene") or "silent",
        "persona": d.get("persona") or persona,
    }


def today_str():
    fake = (os.environ.get("TANGTANG_FAKE_TODAY") or "").strip()
    if fake:
        return fake
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def load_ledger(root=None):
    return load_json(ledger_path(root), {"version": 1, "turns": []})


def _day_of(ts):
    s = (ts or "").strip()
    return s[:10] if len(s) >= 10 else today_str()


def turns_today(who, event, root=None, day=None):
    day = day or today_str()
    who = normalize_who(who)
    event = event or "turn"
    data = load_ledger(root)
    out = []
    for row in data.get("turns") or []:
        if not isinstance(row, dict):
            continue
        if _day_of(row.get("ts")) != day:
            continue
        if normalize_who(row.get("who") or "") != who:
            continue
        if (row.get("event") or "turn") != event:
            continue
        out.append(row)
    return out


def cool_streak_n(kw=None):
    try:
        n = int((kw or keywords()).get("cool_streak") or 2)
    except (TypeError, ValueError):
        n = 2
    return max(2, min(n, 3))


def trailing_cool_streak(rows):
    n = 0
    for row in reversed(rows or []):
        if (row.get("result") or "") in COOL_RESULTS:
            n += 1
        else:
            break
    return n


def gate_status(event, who, root=None, day=None):
    """(allow: bool, reason: str, detail: str) — 冷却以 child_reactions 账本为准。"""
    react = _react()
    muted, reason = react.is_muted(event or "turn", who, root=root)
    if muted:
        tag = reason or "cool"
        if tag in ("silent", "oppose", "stop_today", "defer", "defer_done"):
            if tag == "silent":
                tag = "cool"
            if tag == "stop_today":
                tag = "stop"
        return False, tag, "今天这条先不叫了"
    return True, "ok", ""


def gate_allows(event, who, root=None, day=None):
    ok, _reason, _detail = gate_status(event, who, root=root, day=day)
    return ok


def append_turn(event, who, result, stt, presence, seconds, rms,
                root=None, ts=None, speak=None):
    react = _react()
    spec = react.load_spec()
    sid = {"stop": "stop_today", "joined_soft": "joined"}.get(result, result or "silent")
    scene_spec = (spec.get("scenes") or {}).get(sid) or {}
    decision = {
        "scene": sid,
        "ledger": scene_spec.get("ledger") or sid,
        "speak_again": bool(speak),
        "cooldown": "none",
        "persona": profile_for_who(who),
        "audience": normalize_who(who) or who or "hanghang",
        "event": event or "turn",
        "reply": "",
    }
    row, _dec = react.append_decision(decision, root=root, spoke_again=bool(speak))
    row["stt"] = bool(stt)
    row["presence"] = presence if presence in ("home", "away", "unknown") else "unknown"
    row["seconds"] = int(seconds or 0)
    row["rms"] = int(rms or 0)
    if speak is not None:
        row["speak"] = bool(speak)
        row["spoke_again"] = bool(speak)
    # 写回额外非原话字段（stt/presence/rms），仍不含儿童原话
    path = react.ledger_path(root)
    data = react.load_json(path, {"version": 2, "turns": []})
    if data.get("turns"):
        data["turns"][-1].update({
            "stt": row["stt"],
            "presence": row["presence"],
            "seconds": row["seconds"],
            "rms": row["rms"],
        })
        if speak is not None:
            data["turns"][-1]["speak"] = bool(speak)
            data["turns"][-1]["spoke_again"] = bool(speak)
        for k in FORBIDDEN_KEYS:
            data["turns"][-1].pop(k, None)
        react.save_json(path, data)
        row = data["turns"][-1]
    return row


def preview_scenes(event="english", who="hanghang"):
    who = normalize_who(who) or "hanghang"
    profile = profile_for_who(who)
    other = "洽洽" if who == "hanghang" else "航航"
    react = _react()
    spec = react.load_spec()
    lines = [
        "客厅短窗反应预览（不开麦、不录音、不写账本）",
        "事件 %s · 当前 %s · 人格 %s · 不提%s的表现" % (
            event or "english", who, profile, other,
        ),
        "判定顺序: " + " > ".join(spec.get("decision_order") or []),
        "",
    ]
    demos = [
        ("joined", "好啊", "voiced"),
        ("oppose", "不要", "voiced"),
        ("silent", "", "silent"),
        ("defer", "等会儿", "voiced"),
        ("wont", "不会", "voiced"),
        ("unclear", "", "quiet"),
        ("stop_today", "今天别叫我", "voiced"),
        ("perfunctory", "嗯", "quiet"),
        ("timeout", "", "silent"),
    ]
    for sid, text, energy in demos:
        scene = (spec.get("scenes") or {}).get(sid) or {}
        d = decide(energy, "ok" if text else "off", text=text, rms=0,
                   profile=profile, who=who, index=0, event=event)
        shown = d["reply"] if d["reply"] else "（不回）"
        lines.append("【%s】%s  例句「%s」→ %s  糖糖「%s」" % (
            scene.get("name") or sid, sid, text or "无声", d["result"], shown,
        ))
        other_p = "friend" if profile == "play" else "play"
        other_who = "qiaqia" if other_p == "friend" else "hanghang"
        other_d = decide(energy, "ok" if text else "off", text=text, rms=0,
                         profile=other_p, who=other_who, index=0, event=event)
        if d["reply"] and other_d["reply"] and other_d["reply"] != d["reply"]:
            lines.append("  另一人格：「%s」" % other_d["reply"])
    ok, reason, detail = gate_status(event, who)
    lines.append("当前闸门：%s %s %s" % ("开" if ok else "关", reason, detail))
    return "\n".join(lines).rstrip() + "\n"


def _selftest():
    tmp = tempfile.mkdtemp(prefix="tangtang-turn-")
    os.environ["TANGTANG_DATA_DIR"] = tmp
    os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-01"
    os.environ["TANGTANG_FAKE_TIME"] = "16:20"
    silent = os.path.join(tmp, "silent.pcm")
    tone = os.path.join(tmp, "tone.pcm")
    quiet = os.path.join(tmp, "quiet.pcm")
    write_pcm("silent", silent)
    write_pcm("tone", tone)
    write_pcm("quiet", quiet)
    rms_s, lab_s = energy_label(silent, 300)
    rms_t, lab_t = energy_label(tone, 300)
    rms_q, lab_q = energy_label(quiet, 300)
    assert lab_s == "silent" and rms_s == 0, (rms_s, lab_s)
    assert lab_t == "joined" and rms_t > 800, (rms_t, lab_t)
    assert lab_q == "joined" and rms_q < 800, (rms_q, lab_q)
    assert one_sentence("糖糖听到啦。还要再说吗？") == "糖糖听到啦。"

    assert classify("voiced", "ok", "不要") == "oppose"
    assert classify("voiced", "ok", "不要叫了") == "stop_today"
    assert classify("silent", "off", "") == "timeout"
    assert classify("voiced", "ok", "等会儿") == "defer"
    assert classify("voiced", "ok", "不会") == "wont"
    assert classify("voiced", "ok", "好") == "joined"
    assert classify("quiet", "ok", "嗯", rms=400) == "perfunctory"
    assert classify("voiced", "ok", "知道了") == "noncoop"
    assert classify("quiet", "fail", "", rms=400) == "unclear"

    play = decide("voiced", "ok", "不要", profile="play", who="hanghang", index=0)
    friend = decide("voiced", "ok", "不要", profile="friend", who="qiaqia", index=0)
    assert play["reply"] and friend["reply"] and play["reply"] != friend["reply"]
    assert "汪汪" in play["reply"] and "汪汪" in friend["reply"]
    assert "洽洽" not in play["reply"]
    assert "航航" not in friend["reply"]
    silent_d = decide("silent", "off", "", index=0)
    assert silent_d["speak"] is False

    row = append_turn(
        event="english", who="hanghang", result="oppose",
        stt=True, presence="home", seconds=5, rms=2000, root=tmp, speak=True,
    )
    assert "text" not in row and "transcript" not in row
    assert row.get("scene") == "oppose"
    assert row.get("audience") == "hanghang"
    ok, reason, _ = gate_status("english", "hanghang", root=tmp)
    assert ok is False
    ok_q, _, _ = gate_status("english", "qiaqia", root=tmp)
    assert ok_q is True

    prev = preview_scenes("english", "hanghang")
    assert "配合" in prev and "反对" in prev
    assert "糖糖去喝水了" in prev or "好吧" in prev
    print("cat-turn.py selftest ok")
    print("silent", rms_s, lab_s)
    print("tone", rms_t, lab_t)
    print("play_oppose", play["reply"])
    print("friend_oppose", friend["reply"])

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd in ("--selftest", "selftest"):
        _selftest()
        return
    if cmd == "energy":
        path = sys.argv[2] if len(sys.argv) > 2 else ""
        thr = float(sys.argv[3]) if len(sys.argv) > 3 else None
        rms, label = energy_label(path, thr)
        print("%s\t%s" % (rms, label))
        return
    if cmd == "pcm":
        kind = sys.argv[2] if len(sys.argv) > 2 else "silent"
        path = sys.argv[3] if len(sys.argv) > 3 else "/tmp/tangtang_turn.pcm"
        write_pcm(kind, path)
        print(path)
        return
    if cmd == "sentence":
        print(one_sentence(" ".join(sys.argv[2:])))
        return
    if cmd == "canned":
        print(canned_reply(sys.argv[2] if len(sys.argv) > 2 else "play"))
        return
    if cmd == "classify":
        energy = sys.argv[2] if len(sys.argv) > 2 else "silent"
        stt = sys.argv[3] if len(sys.argv) > 3 else "off"
        rms = sys.argv[4] if len(sys.argv) > 4 else "0"
        text = " ".join(sys.argv[5:]) if len(sys.argv) > 5 else ""
        print(classify(energy, stt, text=text, rms=int(float(rms) or 0)))
        return
    if cmd == "decide":
        energy = sys.argv[2] if len(sys.argv) > 2 else "silent"
        stt = sys.argv[3] if len(sys.argv) > 3 else "off"
        rms = sys.argv[4] if len(sys.argv) > 4 else "0"
        profile = sys.argv[5] if len(sys.argv) > 5 else "play"
        who = sys.argv[6] if len(sys.argv) > 6 else ""
        text = " ".join(sys.argv[7:]) if len(sys.argv) > 7 else ""
        d = decide(
            energy, stt, text=text, rms=int(float(rms) or 0),
            profile=profile, who=who,
            event=(os.environ.get("TANGTANG_TURN_EVENT") or "english"),
        )
        print("%s\t%s\t%s\t%s" % (
            d["result"], "1" if d["speak"] else "0", d["reply"], d.get("voice") or "none",
        ))
        return
    if cmd == "reply":
        label = sys.argv[2] if len(sys.argv) > 2 else "joined"
        profile = sys.argv[3] if len(sys.argv) > 3 else "play"
        who = sys.argv[4] if len(sys.argv) > 4 else ""
        print(pick_reply(label, profile=profile, who=who))
        return
    if cmd == "gate":
        event = sys.argv[2] if len(sys.argv) > 2 else "english"
        who = sys.argv[3] if len(sys.argv) > 3 else "hanghang"
        root = sys.argv[4] if len(sys.argv) > 4 else None
        ok, reason, detail = gate_status(event, who, root=root)
        if ok:
            print("ALLOW\t%s" % reason)
        else:
            print("SKIP\t%s\t%s" % (reason, detail))
            sys.exit(2)
        return
    if cmd in ("preview", "--print"):
        event = sys.argv[2] if len(sys.argv) > 2 else "english"
        who = sys.argv[3] if len(sys.argv) > 3 else "hanghang"
        sys.stdout.write(preview_scenes(event, who))
        return
    if cmd == "ledger":
        event = sys.argv[2] if len(sys.argv) > 2 else "turn"
        who = sys.argv[3] if len(sys.argv) > 3 else ""
        result = sys.argv[4] if len(sys.argv) > 4 else "silent"
        stt_raw = sys.argv[5] if len(sys.argv) > 5 else "0"
        presence = sys.argv[6] if len(sys.argv) > 6 else "unknown"
        seconds = sys.argv[7] if len(sys.argv) > 7 else "0"
        rms = sys.argv[8] if len(sys.argv) > 8 else "0"
        speak = None
        if len(sys.argv) > 9:
            speak = sys.argv[9] in ("1", "true", "yes")
        row = append_turn(
            event=event, who=who, result=result,
            stt=stt_raw in ("1", "true", "yes"),
            presence=presence, seconds=seconds, rms=rms, speak=speak,
        )
        print(row["result"])
        return
    print(
        "用法: energy | pcm | sentence | canned | classify | decide | "
        "reply | gate | preview | ledger | selftest",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
