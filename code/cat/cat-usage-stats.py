#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 上网行为统计采集器
用法: cat-usage-stats.py snapshot|summary [天数]
数据: ~/Library/Logs/tangtang/usage.jsonl（本机，不入库）
设备归属: cat-devices.json {"HONOR-70":{"member":"姐姐"},...}
"""
import sys, os, json, time, importlib.util

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.environ.get("TANGTANG_LOG_DIR", os.path.expanduser("~/Library/Logs/tangtang"))
LOG = os.path.join(LOG_DIR, "usage.jsonl")
MAP_FILE = os.path.join(CAT_DIR, "cat-devices.json")

spec = importlib.util.spec_from_file_location("cr", os.path.join(CAT_DIR, "cat-router.py"))
cr = importlib.util.module_from_spec(spec); spec.loader.exec_module(cr)

def members_map():
    try:
        return json.load(open(MAP_FILE, encoding="utf-8"))
    except Exception:
        return {}

def snapshot():
    stok = cr.login()
    d = cr.api(stok, "/api/misystem/devicelist")
    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    out = {"ts": ts, "devices": []}
    for dev in d.get("list") or []:
        ips = dev.get("ip") or [{}]
        ip0 = ips[0] if isinstance(ips[0], dict) else {}
        out["devices"].append({
            "name": dev.get("name"), "mac": dev.get("mac"),
            "ip": ip0.get("ip"), "online_s": int(ip0.get("online", 0) or 0),
            "down_bps": int(ip0.get("downspeed", 0) or 0),
            "up_bps": int(ip0.get("upspeed", 0) or 0),
            "active": int(ip0.get("active", 0) or 0),
        })
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")
    return out

def summary(days=7):
    import datetime
    cutoff = time.time() - days * 86400
    mem = members_map()
    samples = [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]
    stats = {}
    for s in samples:
        t = time.mktime(time.strptime(s["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
        if t < cutoff: continue
        for dev in s.get("devices", []):
            st = stats.setdefault(dev["name"], {"n": 0, "max_down": 0, "sum_down": 0, "online_s": 0, "active_n": 0, "last": None})
            st["n"] += 1
            st["max_down"] = max(st["max_down"], dev["down_bps"])
            st["sum_down"] += dev["down_bps"]
            st["online_s"] = max(st["online_s"], dev["online_s"])
            st["active_n"] += 1 if dev["active"] else 0
            st["last"] = s["ts"]
    for name, st in sorted(stats.items()):
        who = mem.get(name, {}).get("member", "—")
        avg = st["sum_down"] // max(1, st["n"])
        print("%-22s [%s] 采样%d · 在线%s · 峰值下载%.0fKB/s · 均值%.0fKB/s · 活跃%d" % (
            name, who, st["n"], "%.1fh" % (st["online_s"] / 3600.0),
            st["max_down"] / 1024.0, avg / 1024.0, st["active_n"]))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if cmd == "snapshot": print(json.dumps(snapshot(), ensure_ascii=False)[:400])
    elif cmd == "summary": summary(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
    else: print(__doc__)
