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
FORBIDDEN_KEYS = (
    "text", "transcript", "utterance", "pcm", "words", "say",
    "stt_text", "audio", "speech", "raw",
)
RESULTS = (
    "joined", "joined_soft", "silent", "oppose", "wont", "stop", "unclear",
    "defer", "stop_today", "skip", "timeout", "perfunctory", "noncoop",
)
COOL_RESULTS = ("silent", "oppose")
SYSTEM_RESULTS = RESULTS

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
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("cat_react_mod", path)
    if not spec or not spec.loader:
        return None
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
    """energy: silent|voiced|quiet。优先走 cat-react.py；没有则用关键词薄适配。"""
    react = _react()
    if react is not None:
        try:
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
            scene = d.get("scene") if isinstance(d, dict) else d
            if scene:
                return scene
        except Exception:
            pass
    e = (energy or "silent").strip().lower()
    stt = (stt_status or "off").strip().lower()
    raw = (text or "").strip()
    if raw.startswith("[STT") or stt == "fail":
        if e in ("silent", "timeout"):
            return "silent"
        return "unclear"
    if e in ("silent", "timeout"):
        return "silent"
    kw = keywords()
    compact = _strip_scratch(raw, kw.get("scratch") or [])
    lab = keyword_label(raw, kw)
    if lab:
        return lab
    if raw and not compact:
        return "silent"
    if not raw:
        if e in ("quiet", "low"):
            return "unclear"
        if e in ("voiced", "joined", "tone"):
            return "joined_soft"
        return "silent"
    if e in ("quiet", "low"):
        return "unclear"
    if e in ("voiced", "joined", "tone"):
        return "joined"
    return "silent"


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
    """返回一句或空。空=不说话。preview 传 index=0，现场随机。"""
    if not should_speak_label(label, table):
        return ""
    table = table if table is not None else replies_table()
    kw = kw or keywords()
    p = (profile or "play").strip().lower()
    if p not in ("play", "friend", "elder"):
        p = profile_for_who(who)
    block = table.get(p) or table.get("play") or {}
    choices = [c for c in (block.get(label) or []) if isinstance(c, str)]
    choices = [c.strip() for c in choices if c.strip()]
    safe = [c for c in choices if not _reply_forbidden(c, who, kw)]
    pool = safe or choices
    if not pool:
        return ""
    if index is None:
        text = one_sentence(random.choice(pool))
    else:
        text = one_sentence(pool[int(index) % len(pool)])
    if _reply_forbidden(text, who, kw):
        return ""
    return text


def canned_reply(profile="play"):
    text = pick_reply("joined", profile=profile, index=0)
    if text:
        return text
    p = (profile or "play").strip().lower()
    if p == "friend":
        return "嗯，糖糖听到了。"
    if p == "elder":
        return "好的。"
    return "汪汪，糖糖听到啦。"


def decide(energy, stt_status, text="", rms=0, profile="play", who="", index=None):
    label = classify(energy, stt_status, text=text, rms=rms)
    reply = pick_reply(label, profile=profile, who=who, index=index)
    return {
        "result": label,
        "speak": bool(reply),
        "reply": reply,
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
    """(allow: bool, reason: str, detail: str)"""
    who = normalize_who(who)
    event = event or "turn"
    rows = turns_today(who, event, root=root, day=day)
    if any((r.get("result") or "") == "stop" for r in rows):
        return False, "stop", "今天说过到此为止，这类不再开窗"
    streak = trailing_cool_streak(rows)
    need = cool_streak_n()
    if streak >= need:
        return False, "cool", "连续%d次没应或反对，今晚这类先不说" % streak
    return True, "ok", ""


def gate_allows(event, who, root=None, day=None):
    ok, _reason, _detail = gate_status(event, who, root=root, day=day)
    return ok


def gate_allows(event, who, root=None, day=None):
    ok, _reason, _detail = gate_status(event, who, root=root, day=day)
    return ok


def _notify_habits(row, root=None):
    try:
        import importlib.util
        path = os.path.join(CAT_DIR, "cat-habits.py")
        spec = importlib.util.spec_from_file_location("tangtang_habits", path)
        if not spec or not spec.loader:
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.apply_turn(row, root=root)
    except Exception:
        return


def append_turn(event, who, result, stt, presence, seconds, rms,
                root=None, ts=None, speak=None, line_id=None, spoke=None):
    result = result if result in SYSTEM_RESULTS else "silent"
    presence = presence if presence in ("home", "away", "unknown") else "unknown"
    if ts is None:
        from datetime import datetime
        fake_day = (os.environ.get("TANGTANG_FAKE_TODAY") or "").strip()
        fake_time = (os.environ.get("TANGTANG_FAKE_TIME") or "").strip()
        if fake_day and fake_time:
            ts = "%sT%s:00" % (fake_day, fake_time)
        else:
            ts = datetime.now().isoformat(timespec="seconds")
    if speak is None and spoke is not None:
        speak = bool(spoke)
    row = {
        "ts": ts,
        "event": event or "turn",
        "who": normalize_who(who) or (who or ""),
        "result": result,
        "stt": bool(stt),
        "presence": presence,
        "seconds": int(seconds or 0),
        "rms": int(rms or 0),
    }
    if speak is not None:
        row["speak"] = bool(speak)
        row["spoke"] = bool(speak)
    lid = (line_id or os.environ.get("TANGTANG_LINE_ID") or "").strip()
    if lid:
        row["line_id"] = lid[:80]
    for k in FORBIDDEN_KEYS:
        row.pop(k, None)
    path = ledger_path(root)
    data = load_json(path, {"version": 1, "turns": []})
    data["version"] = 1
    turns = list(data.get("turns") or [])
    turns.append(row)
    data["turns"] = turns[-MAX_TURNS:]
    save_json(path, data)
    json.loads(open(path, encoding="utf-8").read())
    _notify_habits(row, root)
    return row


def preview_scenes(event="english", who="hanghang"):
    who = normalize_who(who) or "hanghang"
    profile = profile_for_who(who)
    other = "洽洽" if who == "hanghang" else "航航"
    kw = keywords()
    lines = []
    lines.append("客厅短窗反应预览（不开麦、不录音、不写账本）")
    lines.append("事件 %s · 当前 %s · 人格 %s · 不提%s的表现" % (
        event or "english", who, profile, other,
    ))
    lines.append("")
    demo = {
        "joined": ("好啊", "voiced", "ok"),
        "oppose": ("不要", "voiced", "ok"),
        "silent": ("", "silent", "off"),
        "wont": ("好难", "voiced", "ok"),
        "unclear": ("", "voiced", "fail"),
        "stop": ("今天别叫我", "voiced", "ok"),
        "scratch": ("啊", "voiced", "ok"),
        "timeout": ("", "silent", "off"),
    }
    for scene in kw.get("scenes") or []:
        sid = scene.get("id") or ""
        title = scene.get("title") or sid
        lines.append("【%s】%s" % (title, sid))
        lines.append("  判定：%s" % (scene.get("signal") or ""))
        lines.append("  糖糖：%s" % (scene.get("speak") or ""))
        if sid in demo:
            text, energy, stt = demo[sid]
            d = decide(energy, stt, text=text, profile=profile, who=who, index=0)
            shown = d["reply"] if d["reply"] else "（不说话）"
            lines.append("  例句：%s → 账本 %s → 糖糖说「%s」" % (
                text or "（无声/无听写）", d["result"], shown,
            ))
            other_p = "friend" if profile == "play" else "play"
            other_who = "qiaqia" if other_p == "friend" else "hanghang"
            other_d = decide(
                energy, stt, text=text, profile=other_p,
                who=other_who, index=0,
            )
            if sid in ("joined", "oppose", "wont", "stop") and other_d["reply"]:
                lines.append("  另一人格会说：「%s」" % other_d["reply"])
        lines.append("  账本：%s" % (scene.get("ledger") or ""))
        lines.append("  下次：%s" % (scene.get("next") or ""))
        lines.append("")
    ok, reason, detail = gate_status(event, who)
    lines.append("当前闸门：%s %s %s" % (
        "开" if ok else "关", reason, detail,
    ))
    fj = pick_reply("joined", "friend", who="qiaqia", index=0)
    pj = pick_reply("joined", "play", who="hanghang", index=0)
    lines.append("人格对照 配合：洽洽「%s」 / 航航「%s」" % (fj, pj))
    return "\n".join(lines).rstrip() + "\n"


def _selftest():
    tmp = tempfile.mkdtemp(prefix="tangtang-turn-")
    os.environ["TANGTANG_DATA_DIR"] = tmp
    silent = os.path.join(tmp, "silent.pcm")
    tone = os.path.join(tmp, "tone.pcm")
    write_pcm("silent", silent)
    write_pcm("tone", tone)
    rms_s, lab_s = energy_label(silent, 300)
    rms_t, lab_t = energy_label(tone, 300)
    assert lab_s == "silent" and rms_s == 0, (rms_s, lab_s)
    assert lab_t == "joined" and rms_t > 300, (rms_t, lab_t)
    assert one_sentence("糖糖听到啦。还要再说吗？") == "糖糖听到啦。"
    assert one_sentence("今天作业写完了！我们再玩。") == "今天作业写完了！"
    assert "再玩" not in one_sentence("今天作业写完了！我们再玩。")

    assert classify("voiced", "ok", "好啊") == "joined"
    assert classify("voiced", "ok", "嗯") == "joined"
    assert classify("voiced", "ok", "不要") == "oppose"
    assert classify("voiced", "ok", "讨厌") == "oppose"
    assert classify("voiced", "ok", "别说了") == "oppose"
    assert classify("voiced", "ok", "烦不烦") == "oppose"
    assert classify("voiced", "ok", "滚") == "oppose"
    assert classify("silent", "off", "") == "silent"
    assert classify("voiced", "ok", "不会") == "wont"
    assert classify("voiced", "ok", "好难") == "wont"
    assert classify("voiced", "ok", "明天再学") == "wont"
    assert classify("voiced", "fail", "") == "unclear"
    assert classify("voiced", "ok", "今天别叫我") == "stop"
    assert classify("voiced", "ok", "不想学了") == "stop"
    assert classify("voiced", "empty", "啊") == "silent"
    assert classify("voiced", "ok", "啊呃") == "silent"
    assert classify("silent", "off", "") == "silent"
    assert classify("voiced", "off", "") == "joined_soft"
    assert classify("voiced", "ok", "It's a dog") == "joined"
    assert keyword_label("好难") == "wont"

    friend_j = pick_reply("joined", "friend", who="qiaqia", index=0)
    play_j = pick_reply("joined", "play", who="hanghang", index=0)
    assert friend_j and play_j and friend_j != play_j, (friend_j, play_j)
    friend_o = pick_reply("oppose", "friend", who="qiaqia", index=0)
    play_o = pick_reply("oppose", "play", who="hanghang", index=0)
    assert friend_o and play_o and friend_o != play_o
    assert "再试" not in friend_o and "再试" not in play_o
    assert pick_reply("silent", "play") == ""
    assert pick_reply("unclear", "friend") == ""
    wont_p = pick_reply("wont", "play", who="hanghang", index=0)
    assert "不会" in wont_p or "学不会" in wont_p or "没关系" in wont_p
    for sample in (friend_j, play_j, friend_o, play_o, wont_p):
        assert "正确" not in sample
        assert "你必须" not in sample
        assert "根据系统" not in sample
        assert "哥哥" not in sample and "弟弟" not in sample
        assert "洽洽" not in sample and "航航" not in sample

    d = decide("voiced", "ok", "滚", profile="play", who="hanghang", index=0)
    assert d["result"] == "oppose"
    assert "滚" not in d["reply"]
    assert "再试" not in d["reply"]

    row = append_turn(
        event="english", who="hanghang", result="silent",
        stt=False, presence="home", seconds=5, rms=0, root=tmp,
        ts="2026-09-01T16:20:00",
    )
    assert "text" not in row
    path = ledger_path(tmp)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["turns"][-1]["result"] == "silent"
    assert "text" not in data["turns"][-1]

    os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-01"
    append_turn(
        event="english", who="hanghang", result="silent",
        stt=False, presence="home", seconds=5, rms=0, root=tmp,
        ts="2026-09-01T16:21:00",
    )
    ok, reason, _detail = gate_status(
        "english", "hanghang", root=tmp, day="2026-09-01",
    )
    assert not ok and reason == "cool", (ok, reason)

    append_turn(
        event="english", who="qiaqia", result="stop",
        stt=True, presence="home", seconds=5, rms=800, root=tmp,
        ts="2026-09-01T19:10:00", speak=True,
    )
    ok_q, reason_q, _ = gate_status(
        "english", "qiaqia", root=tmp, day="2026-09-01",
    )
    assert not ok_q and reason_q == "stop"
    ok_h2, _, _ = gate_status("english", "hanghang", root=tmp, day="2026-09-02")
    assert ok_h2

    prev = preview_scenes("english", "hanghang")
    assert "配合" in prev and "反对" in prev and "不开麦" in prev
    assert "正确" not in prev
    assert "糖糖不吵你" in prev
    assert "糖糖不说了" in prev

    print("cat-turn.py selftest ok")
    print("silent", rms_s, lab_s)
    print("tone", rms_t, lab_t)
    print("friend_joined", friend_j)
    print("play_joined", play_j)


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
        )
        print("%s\t%s\t%s" % (d["result"], "1" if d["speak"] else "0", d["reply"]))
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
        line_id = sys.argv[10] if len(sys.argv) > 10 else ""
        row = append_turn(
            event=event, who=who, result=result,
            stt=stt_raw in ("1", "true", "yes"),
            presence=presence, seconds=seconds, rms=rms, speak=speak,
            line_id=line_id,
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
