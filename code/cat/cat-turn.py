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
from tangtang_paths import data_dir, now_dt  # noqa: E402

LEDGER_NAME = "cat-turn-ledger.json"
MAX_TURNS = 400
FORBIDDEN_KEYS = ("text", "transcript", "utterance", "pcm", "words", "say")


def ledger_path(root=None):
    return os.path.join(root or data_dir(), LEDGER_NAME)


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


def append_turn(event, who, result, stt, presence, seconds, rms, root=None, ts=None,
                window=None, persona=None, spoke=None, scene=None):
    result = result if result in ("joined", "silent", "wont") else "wont"
    presence = presence if presence in ("home", "away", "unknown") else "unknown"
    if ts is None:
        ts = now_dt().isoformat(timespec="seconds")
    who = who or ""
    row = {
        "ts": ts,
        "event": event or "turn",
        "who": who,
        "audience": who,
        "persona": (persona or "").strip() or "",
        "result": result,
        "scene": scene or result,
        "stt": bool(stt),
        "spoke": bool(spoke) if spoke is not None else False,
        "presence": presence,
        "seconds": int(seconds or 0),
        "rms": int(rms or 0),
        "window": window or "unknown",
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
    last = json.loads(open(path, encoding="utf-8").read())["turns"][-1]
    for bad in FORBIDDEN_KEYS:
        if bad in last:
            raise AssertionError("ledger leaked %s" % bad)
    return row


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
    assert data["turns"][-1].get("window") == "unknown"
    os.environ["CAT_NOW"] = "2026-08-28 14:05:00"
    assert now_dt().strftime("%Y-%m-%d %H:%M") == "2026-08-28 14:05"
    os.environ.pop("CAT_NOW", None)
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
        # ledger <event> <who> <result> <stt 0|1> <presence> <seconds> <rms> [spoke] [window] [persona] [scene]
        event = sys.argv[2] if len(sys.argv) > 2 else "turn"
        who = sys.argv[3] if len(sys.argv) > 3 else ""
        result = sys.argv[4] if len(sys.argv) > 4 else "wont"
        stt_raw = sys.argv[5] if len(sys.argv) > 5 else "0"
        presence = sys.argv[6] if len(sys.argv) > 6 else "unknown"
        seconds = sys.argv[7] if len(sys.argv) > 7 else "0"
        rms = sys.argv[8] if len(sys.argv) > 8 else "0"
        spoke = None
        window = None
        persona = None
        scene = None
        if len(sys.argv) > 9:
            spoke = sys.argv[9] in ("1", "true", "yes")
        if len(sys.argv) > 10:
            window = sys.argv[10]
        if len(sys.argv) > 11:
            persona = sys.argv[11]
        if len(sys.argv) > 12:
            scene = sys.argv[12]
        row = append_turn(
            event=event, who=who, result=result,
            stt=stt_raw in ("1", "true", "yes"),
            presence=presence, seconds=seconds, rms=rms,
            spoke=spoke, window=window, persona=persona, scene=scene,
        )
        print(row["result"])
        return
    print("用法: energy | pcm | sentence | canned | ledger | selftest", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
