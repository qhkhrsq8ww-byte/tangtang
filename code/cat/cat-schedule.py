#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 家庭设备定时管控（幂等执行器，launchd 每 5 分钟）
规则 cat-schedule.json: 18:00 断孩子手机 → 20:00 静默（保持断网）→ 次日 07:00 恢复
家长/IoT 设备永不管控。状态机：仅状态变化时调用路由器 API。
"""
import sys, os, json, time, datetime, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SCHED = os.path.join(HERE, "cat-schedule.json")
STATE = "/tmp/cat-schedule.state"
LOG = os.path.expanduser("~/Library/Logs/tangtang/schedule.log")

def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("[%s] %s\n" % (time.strftime("%m-%d %H:%M:%S"), msg))

def parse_hm(s):
    h, m = s.split(":", 1)
    return int(h) * 60 + int(m)

def desired_state(sched):
    now = datetime.datetime.now()
    minutes = now.hour * 60 + now.minute
    start = parse_hm(sched["window"]["start"])
    restore = parse_hm(sched["window"]["restore"])
    if sched.get("weekend_exempt") and now.isoweekday() >= 6:
        return "unblock"
    if minutes >= start or minutes < restore:
        return "block"
    return "unblock"

def main():
    sched = json.load(open(SCHED, encoding="utf-8"))
    desired = desired_state(sched)
    prev = open(STATE).read().strip() if os.path.exists(STATE) else "init"
    if prev == desired:
        return 0
    log("状态切换: %s → %s" % (prev, desired))
    action = "block" if desired == "block" else "unblock"
    spec = importlib.util.spec_from_file_location("cr", os.path.join(HERE, "cat-router.py"))
    cr = importlib.util.module_from_spec(spec); spec.loader.exec_module(cr)
    results = []
    for t in sched["targets"]:
        try:
            stok = cr.login()
            r = cr.api(stok, "/api/xqsystem/set_mac_filter?mac=%s&wan=%d" % (t["mac"], 0 if action == "block" else 1))
            results.append("%s:%s" % (t["member"], r.get("code")))
        except Exception as e:
            results.append("%s:ERR %s" % (t["member"], str(e)[:40]))
    log("  执行 %s → %s" % (action, ", ".join(results)))
    with open(STATE, "w") as f:
        f.write(desired)
    return 0

import importlib.util
sys.exit(main())
