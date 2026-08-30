#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 客厅在场（便宜、非声纹主路径）

优先级：
  1. WiFi/LAN（ARP / 已登记 IP）认人
  2. 本回合已录短窗的 RMS/峰值：只判断「屋里有没有人说话」
  3. maybe_voiceprint() 默认 unknown，不建档、不写 embedding、不给儿童建声纹

不新开麦守护进程。不 24 小时听。不覆盖 CLI 显式 MEMBER_ID。
上学作息复用 cat-lib.sh 同一组环境变量与日历文件；夜间复用 tangtang-quiet-hours。
在场 ≠ 可以说话。

用法:
  ./cat-presence.py hint [--clip FILE] [--arp FILE] [--config FILE] [--no-probe]
  ./cat-presence.py suggest [--clip FILE] [--explicit ID]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import struct
import subprocess
import sys
import wave
from datetime import datetime

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)
from tangtang_paths import data_dir  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(CAT_DIR, "..", ".."))
HINT_NAME = "cat-presence.json"
SEEN_NAME = "cat-presence-seen.json"

ADULT_IDS = frozenset({"grandpa", "grandma", "dad"})
CHILD_IDS = frozenset({"qiaqia", "hanghang"})
ALIASES = {
    "爷爷": "grandpa",
    "grandpa": "grandpa",
    "grandmother": "grandma",
    "奶奶": "grandma",
    "grandma": "grandma",
    "爸爸": "dad",
    "爸": "dad",
    "dad": "dad",
    "父亲": "dad",
    "洽洽": "qiaqia",
    "qiaqia": "qiaqia",
    "姐姐": "qiaqia",
    "child_12": "qiaqia",
    "航航": "hanghang",
    "hanghang": "hanghang",
    "弟弟": "hanghang",
    "child_9": "hanghang",
}
SOURCES = ("wifi", "mic_energy", "voiceprint_optional", "unknown")
MAC_RE = re.compile(r"(?P<mac>(?:[0-9a-fA-F]{1,2}[:-]){5}[0-9a-fA-F]{1,2})")
IP_RE = re.compile(r"\((?P<ip>\d{1,3}(?:\.\d{1,3}){3})\)")


def _data_dir():
    env = (os.environ.get("TANGTANG_DATA_DIR") or "").strip()
    if env:
        os.makedirs(env, exist_ok=True)
        return env
    return data_dir()


def load_json(path, default):
    if not path or not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    return data if data is not None else default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def canonical_member(who):
    key = (who or "").strip()
    if not key or key.lower() in ("unknown", "访客", "guest", ""):
        return ""
    if key in ALIASES:
        return ALIASES[key]
    low = key.lower()
    if low in ALIASES:
        return ALIASES[low]
    if key in ADULT_IDS or key in CHILD_IDS:
        return key
    return key


def is_adult(member_id):
    return canonical_member(member_id) in ADULT_IDS


def is_child(member_id):
    return canonical_member(member_id) in CHILD_IDS


def _today():
    return (os.environ.get("TANGTANG_FAKE_TODAY") or "").strip() or datetime.now().strftime("%Y-%m-%d")


def _now_hm():
    return (os.environ.get("TANGTANG_FAKE_TIME") or "").strip() or datetime.now().strftime("%H:%M")


def _clock():
    try:
        return datetime.strptime("%s %s" % (_today(), _now_hm()), "%Y-%m-%d %H:%M")
    except ValueError:
        return datetime.now()


def hm_min(hm):
    h, m = hm.split(":", 1)
    return int(h) * 60 + int(m)


def time_in_away(start, end, now_hm=None):
    now_hm = now_hm or _now_hm()
    n, s, e = hm_min(now_hm), hm_min(start), hm_min(end)
    return s <= n < e


def _calendar_file():
    for p in (
        (os.environ.get("TANGTANG_CALENDAR") or "").strip(),
        os.path.join(_data_dir(), "school_calendar.txt"),
        os.path.join(CAT_DIR, "school_calendar.txt"),
        os.path.join(REPO_ROOT, "data", "school_calendar.txt"),
    ):
        if p and os.path.isfile(p):
            return p
    return ""


def _rest_days_file():
    for p in (
        (os.environ.get("TANGTANG_REST_DAYS") or "").strip(),
        os.path.join(_data_dir(), "rest_days.txt"),
        os.path.join(CAT_DIR, "rest_days.txt"),
        os.path.join(REPO_ROOT, "data", "rest_days.txt"),
    ):
        if p and os.path.isfile(p):
            return p
    return ""


def _date_between(day, start, end):
    return start <= day <= end


def calendar_kind_today(want, day=None):
    path = _calendar_file()
    if not path:
        return False
    day = day or _today()
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read().splitlines()
    except OSError:
        return False
    for line in raw:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2 or parts[0] != want:
            continue
        span = parts[1]
        if ".." in span:
            a, b = span.split("..", 1)
        else:
            a = b = span
        if _date_between(day, a, b):
            return True
    return False


def is_holiday(day=None):
    return calendar_kind_today("holiday", day=day)


def is_makeup_school(day=None):
    return calendar_kind_today("school", day=day)


def is_rest_day(day=None):
    flag = (os.environ.get("CAT_CHILD_HOME") or os.environ.get("TANGTANG_CHILD_HOME") or "").strip().lower()
    if flag in ("1", "yes", "true", "on", "home"):
        return True
    if calendar_kind_today("rest", day=day):
        return True
    path = _rest_days_file()
    if not path:
        return False
    day = day or _today()
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read().splitlines()
    except OSError:
        return False
    for line in raw:
        token = line.split("#", 1)[0].strip().split()
        if token and token[0] == day:
            return True
    return False


def weekday_iso(day=None):
    day = day or _today()
    try:
        return datetime.strptime(day, "%Y-%m-%d").isoweekday()
    except ValueError:
        return datetime.now().isoweekday()


def dow_match(spec, day=None):
    spec = (spec or "*").strip()
    if spec == "*":
        return True
    u = weekday_iso(day)
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            try:
                a, b = int(lo) or 7, int(hi) or 7
            except ValueError:
                continue
            if a <= u <= b:
                return True
        else:
            try:
                t = int(part) or 7
            except ValueError:
                continue
            if t == u:
                return True
    return False


def is_school_day(day=None):
    """Same clock as tangtang_is_school_day in cat-lib.sh."""
    day = day or _today()
    start = (os.environ.get("TANGTANG_SCHOOL_START") or "2026-09-01").strip()
    if day < start:
        return False
    if is_holiday(day):
        return False
    if is_makeup_school(day):
        return True
    return dow_match(os.environ.get("TANGTANG_ALARM_DOW") or "1-5", day)


def child_at_school(who, now_hm=None):
    """Same window as tangtang_child_at_school: leave 07:30, hanghang 16:00, qiaqia 18:00."""
    mid = canonical_member(who)
    leave = (os.environ.get("TANGTANG_SCHOOL_LEAVE") or "07:30").strip()
    if mid == "qiaqia":
        home = (os.environ.get("TANGTANG_HOME_QIAQIA") or "18:00").strip()
    elif mid == "hanghang":
        home = (os.environ.get("TANGTANG_HOME_HANGHANG") or "16:00").strip()
    else:
        return False
    if is_rest_day():
        return False
    if not is_school_day():
        return False
    return time_in_away(leave, home, now_hm=now_hm)


def _load_quiet():
    path = os.path.join(CAT_DIR, "tangtang-quiet-hours.py")
    spec = importlib.util.spec_from_file_location("tangtang_quiet_hours_presence", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def in_quiet_hours(now=None):
    """Compose with tangtang-quiet-hours; honor TANGTANG_FAKE_TIME / INTERACTIVE."""
    try:
        q = _load_quiet()
        return bool(q.is_quiet(now or _clock()))
    except Exception:
        return False


def member_interactable(member_id, now=None):
    mid = canonical_member(member_id)
    if not mid:
        return False
    if is_child(mid) and child_at_school(mid):
        return False
    if in_quiet_hours(now=now):
        return False
    return True


def normalize_mac(value):
    raw = (value or "").strip().lower().replace("-", ":")
    if not raw:
        return ""
    parts = raw.split(":")
    if len(parts) != 6:
        return raw
    try:
        return ":".join("%02x" % int(p, 16) for p in parts)
    except ValueError:
        return raw


def normalize_host(value):
    return (value or "").strip().lower().rstrip(".")


def parse_arp(text):
    """Parse `arp -a` / `arp -an` text. Incomplete rows are ignored."""
    rows = []
    for line in (text or "").splitlines():
        if "incomplete" in line.lower():
            continue
        mac_m = MAC_RE.search(line)
        if not mac_m:
            continue
        ip_m = IP_RE.search(line)
        host = line.strip().split()[0] if line.strip() else ""
        if host == "?":
            host = ""
        rows.append({
            "ip": (ip_m.group("ip") if ip_m else ""),
            "mac": normalize_mac(mac_m.group("mac")),
            "hostname": normalize_host(host),
        })
    return rows


def read_arp_table():
    for args in (("arp", "-an"), ("arp", "-a")):
        try:
            proc = subprocess.run(
                args, capture_output=True, text=True, timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        out = (proc.stdout or "") + (proc.stderr or "")
        if out.strip():
            return out
    return ""


def ping_listed_ip(ip):
    if not ip:
        return False
    if sys.platform == "darwin":
        cmd = ["ping", "-c", "1", "-t", "1", ip]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", ip]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def load_presence_config(path=None):
    paths = []
    if path:
        paths.append(path)
    env = (os.environ.get("TANGTANG_PRESENCE_CONFIG") or "").strip()
    if env:
        paths.append(env)
    paths.append(os.path.join(_data_dir(), "tangtang-presence.json"))
    for candidate in paths:
        data = load_json(candidate, None)
        if isinstance(data, dict) and isinstance(data.get("devices"), dict):
            return data
    return {"devices": {}, "rms_threshold": 300}


def iter_devices(config=None):
    config = config or load_presence_config()
    devices = config.get("devices") or {}
    for raw_id, spec in devices.items():
        mid = canonical_member(raw_id)
        if not mid or not isinstance(spec, dict):
            continue
        macs = []
        for key in ("mac", "macs"):
            val = spec.get(key)
            if isinstance(val, str):
                macs.append(normalize_mac(val))
            elif isinstance(val, list):
                macs.extend(normalize_mac(x) for x in val)
        hosts = []
        for key in ("hostname", "host", "mdns"):
            val = spec.get(key)
            if isinstance(val, str) and val.strip():
                hosts.append(normalize_host(val))
            elif isinstance(val, list):
                hosts.extend(normalize_host(x) for x in val if x)
        ips = []
        for key in ("ip", "ips"):
            val = spec.get(key)
            if isinstance(val, str) and val.strip():
                ips.append(val.strip())
            elif isinstance(val, list):
                ips.extend(str(x).strip() for x in val if x)
        env_ip = ""
        if mid == "qiaqia":
            env_ip = (os.environ.get("TANGTANG_HOST_QIAQIA") or "").strip()
        elif mid == "hanghang":
            env_ip = (os.environ.get("TANGTANG_HOST_HANGHANG") or "").strip()
        if env_ip:
            ips.append(env_ip)
        macs = [m for m in macs if m]
        hosts = [h for h in hosts if h]
        ips = [i for i in ips if i]
        if not (macs or hosts or ips):
            continue
        yield {"member_id": mid, "macs": macs, "hosts": hosts, "ips": ips}


def match_wifi_members(arp_rows, config=None, ping_ips=None):
    """Return member_ids seen on LAN. Multiple phones → multiple ids, no single guess."""
    ping_ips = set(ping_ips or [])
    found = []
    seen = set()
    for dev in iter_devices(config):
        hit = False
        for row in arp_rows:
            if dev["macs"] and row.get("mac") in dev["macs"]:
                hit = True
                break
            if dev["hosts"] and row.get("hostname") and row["hostname"] in dev["hosts"]:
                hit = True
                break
            if dev["ips"] and row.get("ip") and row["ip"] in dev["ips"]:
                hit = True
                break
        if not hit and ping_ips:
            for ip in dev["ips"]:
                if ip in ping_ips:
                    hit = True
                    break
        if hit and dev["member_id"] not in seen:
            seen.add(dev["member_id"])
            found.append(dev["member_id"])
    return found


def _read_int16_pcm(path):
    if not path or not os.path.isfile(path) or os.path.getsize(path) < 2:
        return []
    lower = path.lower()
    if lower.endswith(".wav"):
        try:
            with wave.open(path, "rb") as w:
                frames = w.readframes(w.getnframes())
                width = w.getsampwidth()
                nch = w.getnchannels() or 1
        except (OSError, wave.Error):
            return []
        if width != 2:
            return []
        samples = []
        step = width * nch
        for i in range(0, len(frames) - (len(frames) % step), step):
            samples.append(struct.unpack_from("<h", frames, i)[0])
        return samples
    with open(path, "rb") as f:
        raw = f.read()
    samples = []
    for i in range(0, len(raw) - (len(raw) % 2), 2):
        samples.append(struct.unpack_from("<h", raw, i)[0])
    return samples


def clip_energy(path, threshold=None):
    """RMS/peak of an already-captured wav/pcm. Does not record."""
    if threshold is None:
        try:
            threshold = float(
                os.environ.get("TANGTANG_PRESENCE_RMS")
                or os.environ.get("TANGTANG_TURN_RMS")
                or "300"
            )
        except ValueError:
            threshold = 300.0
    samples = _read_int16_pcm(path)
    if not samples:
        return {"rms": 0.0, "peak": 0, "in_room_speech": False, "threshold": threshold}
    acc = 0.0
    peak = 0
    for s in samples:
        acc += float(s) * float(s)
        a = abs(s)
        if a > peak:
            peak = a
    rms = math.sqrt(acc / len(samples))
    return {
        "rms": rms,
        "peak": peak,
        "in_room_speech": rms >= threshold,
        "threshold": threshold,
    }


def maybe_voiceprint(wav):
    """Tertiary stub. Never enrolls. Never writes embeddings. Never IDs children.

    cat-vp.py exists as a coarse local matcher, but presence must not use it
    as an identity path and must not persist child audio or voiceprints.
    """
    return {"member_id": "unknown", "confidence": 0.0, "enrolled": False}


def empty_hint(reason="no_signal"):
    return {
        "source": "unknown",
        "member_ids": [],
        "in_room_speech": False,
        "confidence": 0.0,
        "reason": reason,
        "interactable": False,
        "interactable_ids": [],
        "present_on_wifi": [],
    }


def _remember_wifi(member_ids, now=None):
    if not member_ids:
        return
    path = os.path.join(_data_dir(), SEEN_NAME)
    data = load_json(path, {"version": 1, "last_seen": {}})
    if not isinstance(data, dict):
        data = {"version": 1, "last_seen": {}}
    seen = data.setdefault("last_seen", {})
    ts = (now or _clock()).isoformat(timespec="seconds")
    for mid in member_ids:
        seen[mid] = {"ts": ts, "source": "wifi"}
    save_json(path, data)


def detect_presence(
    arp_text=None,
    clip_path=None,
    config=None,
    config_path=None,
    allow_probe=False,
    now=None,
    persist=True,
):
    """Return PresenceHint. Pure data, no LLM. Tests inject arp_text / clip_path."""
    cfg = config if isinstance(config, dict) else load_presence_config(config_path)
    env_arp = (os.environ.get("TANGTANG_PRESENCE_ARP") or "").strip()
    if arp_text is None and env_arp:
        if os.path.isfile(env_arp):
            try:
                with open(env_arp, encoding="utf-8") as fh:
                    arp_text = fh.read()
            except OSError:
                arp_text = ""
        else:
            arp_text = env_arp

    ping_hits = []
    if arp_text is None and allow_probe:
        arp_text = read_arp_table()
        # Ping only IPs listed in config, and only as a live fallback.
        listed = []
        for dev in iter_devices(cfg):
            listed.extend(dev["ips"])
        for ip in listed:
            if ping_listed_ip(ip):
                ping_hits.append(ip)

    rows = parse_arp(arp_text or "")
    wifi_ids = match_wifi_members(rows, config=cfg, ping_ips=ping_hits)
    energy = clip_energy(clip_path) if clip_path else {
        "rms": 0.0, "peak": 0, "in_room_speech": False, "threshold": 300,
    }
    speech = bool(energy.get("in_room_speech"))
    vp = maybe_voiceprint(clip_path) if clip_path else {"member_id": "unknown", "confidence": 0.0}

    interactable_ids = [m for m in wifi_ids if member_interactable(m, now=now)]
    if wifi_ids:
        source = "wifi"
        if len(wifi_ids) == 1:
            reason = "wifi_single"
            confidence = 0.72
        else:
            reason = "wifi_multiple"
            confidence = 0.48
        if speech:
            reason = reason + "+speech"
            confidence = min(0.9, confidence + 0.08)
    elif speech:
        source = "mic_energy"
        reason = "mic_speech_unknown_who"
        confidence = 0.4
    elif vp.get("member_id") and vp.get("member_id") != "unknown":
        source = "voiceprint_optional"
        reason = "voiceprint_optional"
        confidence = float(vp.get("confidence") or 0.0)
    else:
        source = "unknown"
        reason = "no_wifi_no_speech"
        confidence = 0.0

    hint = {
        "source": source if source in SOURCES else "unknown",
        "member_ids": list(wifi_ids),
        "in_room_speech": speech,
        "confidence": round(float(confidence), 3),
        "reason": reason,
        "interactable": bool(interactable_ids),
        "interactable_ids": interactable_ids,
        "present_on_wifi": list(wifi_ids),
        "rms": round(float(energy.get("rms") or 0.0), 1),
        "voiceprint": "unknown",
    }
    if persist and wifi_ids:
        _remember_wifi(wifi_ids, now=now)
    if persist:
        write_hint_log(hint, clip_path=clip_path)
    return hint


def write_hint_log(hint, clip_path=None):
    """Local cat-*.json only. Never store audio, paths of child clips, or embeddings."""
    row = {
        "ts": _clock().isoformat(timespec="seconds"),
        "source": hint.get("source"),
        "member_ids": list(hint.get("member_ids") or []),
        "in_room_speech": bool(hint.get("in_room_speech")),
        "confidence": hint.get("confidence"),
        "reason": hint.get("reason"),
        "interactable": bool(hint.get("interactable")),
        "interactable_ids": list(hint.get("interactable_ids") or []),
        "present_on_wifi": list(hint.get("present_on_wifi") or []),
        "voiceprint": "unknown",
    }
    # Do not persist clip paths (child audio must not land in family stores).
    path = os.path.join(_data_dir(), HINT_NAME)
    data = load_json(path, {"version": 1, "hints": []})
    if not isinstance(data, dict):
        data = {"version": 1, "hints": []}
    hints = data.setdefault("hints", [])
    hints.append(row)
    data["hints"] = hints[-80:]
    data["last"] = row
    save_json(path, data)
    return path


def suggest_member_id(explicit=None, hint=None, **detect_kwargs):
    """If CLI MEMBER_ID is set, keep it. Else one interactable adult, or unknown.

    Never auto-picks qiaqia/hanghang. Multiple adults → unknown (let -p / turn win).
    """
    raw = explicit if explicit is not None else (
        os.environ.get("TANGTANG_MEMBER_ID") or os.environ.get("TANGTANG_SPEAKER") or ""
    )
    raw = (raw or "").strip()
    if raw and raw.lower() not in ("unknown", "访客", "guest"):
        return canonical_member(raw) or raw
    hint = hint if hint is not None else detect_presence(**detect_kwargs)
    adults = [m for m in (hint.get("interactable_ids") or []) if is_adult(m)]
    if len(adults) == 1:
        return adults[0]
    return "unknown"


def _read_text(path):
    if not path:
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _cli_hint(args):
    hint = detect_presence(
        arp_text=_read_text(args.arp),
        clip_path=args.clip,
        config_path=args.config,
        allow_probe=not args.no_probe and not args.arp,
        persist=not args.no_log,
    )
    print(json.dumps(hint, ensure_ascii=False, indent=2))
    return 0


def _cli_suggest(args):
    mid = suggest_member_id(
        explicit=args.explicit,
        arp_text=_read_text(args.arp),
        clip_path=args.clip,
        config_path=args.config,
        allow_probe=not args.no_probe and not args.arp,
        persist=not args.no_log,
    )
    print(mid or "unknown")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tangtang living-room presence (wifi + clip RMS)")
    sub = parser.add_subparsers(dest="cmd")

    def add_common(p):
        p.add_argument("--clip", default="", help="already-captured wav/pcm from this listen window")
        p.add_argument("--arp", default="", help="arp -a text file (tests / fixtures)")
        p.add_argument("--config", default="", help="presence devices json")
        p.add_argument("--no-probe", action="store_true", help="do not run arp/ping")
        p.add_argument("--no-log", action="store_true", help="do not write cat-presence.json")
        return p

    add_common(sub.add_parser("hint"))
    sug = add_common(sub.add_parser("suggest"))
    sug.add_argument("--explicit", default="", help="CLI MEMBER_ID; never overridden")

    args = parser.parse_args(argv)
    if not args.cmd:
        args = parser.parse_args(["hint"] + (argv or []))
    args.clip = args.clip or None
    args.arp = args.arp or None
    args.config = args.config or None
    if args.cmd == "suggest":
        return _cli_suggest(args)
    return _cli_hint(args)


if __name__ == "__main__":
    sys.exit(main())
