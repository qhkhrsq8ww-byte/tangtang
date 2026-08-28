#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客厅语音小回合的本机零件：能量、账本、一句回复裁剪。

账本只写标签，不写儿童原话。记忆目录在 Mac Air 本机硬盘。
"""
import array
import json
import math
import os
import sys
import tempfile

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)
from tangtang_paths import data_dir  # noqa: E402

LEDGER_NAME = "cat-turn-ledger.json"
MAX_TURNS = 400
FORBIDDEN_KEYS = ("text", "transcript", "utterance", "pcm", "words", "say")
LEDGER_RESULTS = (
    "joined", "joined_soft", "silent", "oppose", "defer", "wont",
    "unclear", "skip", "stop",
)
OPENCLAW_EVENTS = ("ask", "english", "move", "rest")


def ledger_path(root=None):
    return os.path.join(root or data_dir(), LEDGER_NAME)


def load_ledger(root=None):
    return load_json(ledger_path(root), {"version": 1, "turns": []})


def load_json(path, default):
    if not os.path.exists(path):
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
    cut = -1
    for i, ch in enumerate(s):
        if ch in seps:
            cut = i
            break
    if cut >= 0:
        s = s[: cut + 1].strip()
    s = " ".join(s.split())
    if len(s) > limit:
        s = s[:limit].rstrip()
    return s


def today_str():
    fake = (os.environ.get("TANGTANG_FAKE_TODAY") or "").strip()
    if fake:
        return fake
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def _day_of(ts):
    s = (ts or "").strip()
    return s[:10] if len(s) >= 10 else today_str()


def normalize_ledger_result(result):
    r = (result or "").strip()
    if r in LEDGER_RESULTS:
        return r
    return "skip"


def append_turn(event, who, result, stt, presence, seconds, rms, root=None, ts=None):
    result = normalize_ledger_result(result)
    presence = presence if presence in ("home", "away", "unknown") else "unknown"
    if ts is None:
        from datetime import datetime
        fake_day = (os.environ.get("TANGTANG_FAKE_TODAY") or "").strip()
        fake_time = (os.environ.get("TANGTANG_FAKE_TIME") or "").strip()
        if fake_day and fake_time:
            ts = "%sT%s:00" % (fake_day, fake_time)
        else:
            ts = datetime.now().isoformat(timespec="seconds")
    row = {
        "ts": ts,
        "event": event or "turn",
        "who": who or "",
        "result": result,
        "stt": bool(stt),
        "presence": presence,
        "seconds": int(seconds or 0),
        "rms": int(rms or 0),
    }
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
    return row


def today_report(who="hanghang", day=None, root=None, events=None):
    """只打标签，不打儿童原话。"""
    day = day or today_str()
    who = (who or "hanghang").strip() or "hanghang"
    events = events or OPENCLAW_EVENTS
    data = load_ledger(root)
    last = {}
    for row in data.get("turns") or []:
        if not isinstance(row, dict):
            continue
        if _day_of(row.get("ts")) != day:
            continue
        row_who = (row.get("who") or "").strip()
        if row_who and row_who != who:
            continue
        ev = (row.get("event") or "").strip()
        if not ev:
            continue
        lab = normalize_ledger_result(row.get("result"))
        last[ev] = lab
    lines = [
        "=== today-report ===",
        "%s %s" % (day, who),
    ]
    for ev in events:
        lines.append("%s\t%s" % (ev, last.get(ev, "skip")))
    lines.append("=== today-report end ===")
    return "\n".join(lines)


def canned_reply(profile="play"):
    p = (profile or "play").strip().lower()
    if p == "friend":
        return "嗯，糖糖听到了。"
    if p == "elder":
        return "好的。"
    return "汪汪，糖糖听到啦。"


def _selftest():
    tmp = tempfile.mkdtemp(prefix="tangtang-turn-")
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
    oppose = append_turn(
        event="ask", who="hanghang", result="oppose",
        stt=False, presence="home", seconds=5, rms=0, root=tmp,
        ts="2026-08-28T14:00:00",
    )
    assert oppose["result"] == "oppose"
    skip = append_turn(
        event="move", who="hanghang", result="skip",
        stt=False, presence="unknown", seconds=0, rms=0, root=tmp,
        ts="2026-08-28T16:00:00",
    )
    assert skip["result"] == "skip"
    bogus = append_turn(
        event="rest", who="hanghang", result="child-said-hello",
        stt=False, presence="unknown", seconds=0, rms=0, root=tmp,
        ts="2026-08-28T17:00:00",
    )
    assert bogus["result"] == "skip"
    assert "text" not in bogus and "transcript" not in bogus
    os.environ["TANGTANG_FAKE_TODAY"] = "2026-08-28"
    os.environ["TANGTANG_DATA_DIR"] = tmp
    rep = today_report("hanghang", day="2026-08-28", root=tmp)
    assert "ask\toppose" in rep
    assert "move\tskip" in rep
    assert "hello" not in rep
    print("cat-turn.py selftest ok")
    print("silent", rms_s, lab_s)
    print("tone", rms_t, lab_t)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd in ("--selftest", "selftest"):
        _selftest()
        return
    if cmd == "energy":
        path = sys.argv[2] if len(sys.argv) > 2 else ""
        thr = float(sys.argv[3]) if len(sys.argv) > 3 else None
        rms, label = energy_label(path, thr)
        print("%s|%s" % (rms, label))
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
    if cmd == "ledger":
        # ledger <event> <who> <result> <stt 0|1> <presence> <seconds> <rms>
        event = sys.argv[2] if len(sys.argv) > 2 else "turn"
        who = sys.argv[3] if len(sys.argv) > 3 else ""
        result = sys.argv[4] if len(sys.argv) > 4 else "wont"
        stt_raw = sys.argv[5] if len(sys.argv) > 5 else "0"
        presence = sys.argv[6] if len(sys.argv) > 6 else "unknown"
        seconds = sys.argv[7] if len(sys.argv) > 7 else "0"
        rms = sys.argv[8] if len(sys.argv) > 8 else "0"
        row = append_turn(
            event=event, who=who, result=result,
            stt=stt_raw in ("1", "true", "yes"),
            presence=presence, seconds=seconds, rms=rms,
        )
        print(row["result"])
        return
    if cmd in ("report", "today-report"):
        who = sys.argv[2] if len(sys.argv) > 2 else "hanghang"
        day = sys.argv[3] if len(sys.argv) > 3 else None
        print(today_report(who=who, day=day))
        return
    print(
        "用法: energy | pcm | sentence | canned | ledger | report | selftest",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
