#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 家庭设备定时管控（幂等执行器，launchd 每 5 分钟）
规则 cat-schedule.json: 18:00 断孩子手机 → 20:00 静默（保持断网）→ 次日 07:00 恢复
家长/IoT 设备永不管控。状态机：仅状态变化时调用路由器 API。
"""
import sys, os, json, time, datetime, subprocess, importlib.util, re

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

def normalize_mac(value):
    compact = re.sub(r"[:-]", "", str(value or "")).lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise ValueError("MAC 地址格式无效")
    octets = [int(compact[i:i + 2], 16) for i in range(0, 12, 2)]
    if all(x == 0 for x in octets) or all(x == 255 for x in octets) or octets[0] & 1:
        raise ValueError("拒绝使用全零、广播或组播 MAC")
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))

def validate_schedule(sched):
    if not isinstance(sched, dict) or not isinstance(sched.get("window"), dict):
        raise ValueError("缺少有效的 window 配置")
    start = sched["window"].get("start")
    restore = sched["window"].get("restore")
    for value in (start, restore):
        if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
            raise ValueError("时间必须使用 HH:MM 格式")
        h, m = map(int, value.split(":"))
        if h > 23 or m > 59:
            raise ValueError("时间超出有效范围")
    targets = sched.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("targets 必须是非空列表")
    protected_items = sched.get("protected")
    if not isinstance(protected_items, list) or not protected_items:
        raise ValueError("protected 必须是非空的家长/基础设施设备保护名单")
    protected = {
        normalize_mac(x.get("mac"))
        for x in protected_items
        if isinstance(x, dict) and x.get("mac")
    }
    if not protected:
        raise ValueError("protected 未包含有效 MAC，拒绝启用自动管控")
    seen = set()
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError("target 配置格式无效")
        mac = normalize_mac(target.get("mac"))
        if mac in seen:
            raise ValueError("targets 存在重复 MAC")
        if mac in protected:
            raise ValueError("拒绝管控受保护设备：" + mac)
        seen.add(mac)
        if not target.get("member") or not target.get("name"):
            raise ValueError("target 缺少 name/member")
    return True

def desired_state(sched, now=None):
    now = now or datetime.datetime.now()
    minutes = now.hour * 60 + now.minute
    start = parse_hm(sched["window"]["start"])
    restore = parse_hm(sched["window"]["restore"])
    if sched.get("weekend_exempt") and now.isoweekday() >= 6:
        return "unblock"
    if minutes >= start or minutes < restore:
        return "block"
    return "unblock"

def main():
    try:
        with open(SCHED, encoding="utf-8") as f:
            sched = json.load(f)
        validate_schedule(sched)
        desired = desired_state(sched)
        prev = open(STATE).read().strip() if os.path.exists(STATE) else "init"
        if prev == desired:
            return 0
        log("状态切换: %s → %s" % (prev, desired))
        action = "block" if desired == "block" else "unblock"
        spec = importlib.util.spec_from_file_location("cr", os.path.join(HERE, "cat-router.py"))
        if spec is None or spec.loader is None:
            raise RuntimeError("无法加载路由器控制模块")
        cr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cr)
        results = []
        failed = False
        for target in sched["targets"]:
            try:
                stok = cr.login()
                mac = normalize_mac(target["mac"])
                r = cr.api(stok, "/api/xqsystem/set_mac_filter?mac=%s&wan=%d" % (mac, 0 if action == "block" else 1))
                if r.get("code") != 0:
                    failed = True
                    results.append("%s:API_ERROR %s" % (target["member"], r.get("code")))
                else:
                    results.append("%s:OK" % target["member"])
            except Exception as e:
                failed = True
                results.append("%s:ERR %s" % (target["member"], str(e)[:80]))
        log("  执行 %s → %s" % (action, ", ".join(results)))
        if failed:
            log("  存在失败设备，不写入状态文件；下次调度将重试")
            return 1
        with open(STATE + ".tmp", "w", encoding="utf-8") as f:
            f.write(desired)
        os.replace(STATE + ".tmp", STATE)
        return 0
    except Exception as e:
        try:
            log("执行失败，保持原状态并等待下次重试：" + str(e))
        except Exception:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())
