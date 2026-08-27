#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
糖糖 · 声纹识别 + 家庭习惯记录系统
用法:
  建档:  ./cat-vp.py enroll <名字> <pcm文件> [pcm文件...]
  识别:  ./cat-vp.py identify <pcm文件>          → 输出 "名字" 或 "unknown"
  记录:  ./cat-vp.py log <名字> <文本>           → 记录一次互动（时间/内容/时长）
  总结:  ./cat-vp.py summary [天数]              → 输出习惯总结
  列出:  ./cat-vp.py list
数据文件: cat-voiceprints.json (声纹库) / cat-habits.json (习惯记录)
"""
import json, os, sys, math, subprocess, time
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
VP_FILE = os.path.join(BASE, "cat-voiceprints.json")
HABIT_FILE = os.path.join(BASE, "cat-habits.json")
FEATURE_SH = os.path.join(BASE, "cat-vp-feature.sh")

# ---------- 特征 ----------
def extract_features(pcm):
    """调用 cat-vp-feature.sh 提取特征向量"""
    r = subprocess.run([FEATURE_SH, pcm], capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return None

def cosine_sim(a, b):
    """余弦相似度（特征向量匹配）"""
    keys = ["low", "mid", "midhi", "high", "rms", "peak", "lra", "zcr"]
    va = [float(a.get(k, 0)) for k in keys]
    vb = [float(b.get(k, 0)) for k in keys]
    dot = sum(x * y for x, y in zip(va, vb))
    na = math.sqrt(sum(x * x for x in va)) or 1
    nb = math.sqrt(sum(y * y for y in vb)) or 1
    return dot / (na * nb)

# ---------- 声纹库 ----------
def load_vp():
    if os.path.exists(VP_FILE):
        with open(VP_FILE) as f:
            return json.load(f)
    return {}

def save_vp(db):
    with open(VP_FILE, "w") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def enroll(name, files):
    db = load_vp()
    feats = []
    for pcm in files:
        if not os.path.exists(pcm):
            print(f"⚠️ 文件不存在: {pcm}")
            continue
        feat = extract_features(pcm)
        if feat:
            feats.append(feat)
            print(f"  ✓ {os.path.basename(pcm)}: {feat}")
        else:
            print(f"  ✗ 特征提取失败: {pcm}")
    if not feats:
        print("❌ 没有成功提取到特征")
        return
    # 存样本均值 + 各样本
    avg = {}
    for k in feats[0]:
        avg[k] = sum(f[k] for f in feats) / len(feats)
    db[name] = {"samples": feats, "avg": avg, "created": datetime.now().isoformat()}
    save_vp(db)
    print(f"✅ 已建档「{name}」({len(feats)} 段样本)")

def identify(pcm):
    db = load_vp()
    if not db:
        return "unknown"
    feat = extract_features(pcm)
    if not feat:
        return "unknown"
    best_name, best_score = "unknown", -1
    for name, data in db.items():
        score = cosine_sim(feat, data["avg"])
        if score > best_score:
            best_name, best_score = name, score
    # 相似度阈值 0.995（家庭场景，特征相似度高）
    return best_name if best_score >= 0.995 else "unknown"

# ---------- 习惯记录 ----------
def load_habits():
    if os.path.exists(HABIT_FILE):
        with open(HABIT_FILE) as f:
            return json.load(f)
    return {"members": {}, "logs": []}

def save_habits(h):
    with open(HABIT_FILE, "w") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

def log(name, text=""):
    h = load_habits()
    now = datetime.now()
    entry = {
        "name": name,
        "text": text,
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "hour": now.hour,
        "weekday": now.strftime("%A"),
    }
    h["logs"].append(entry)
    # 成员统计
    m = h["members"].setdefault(name, {"total": 0, "by_hour": {}, "days": [], "last": None})
    m["total"] += 1
    m["by_hour"][str(now.hour)] = m["by_hour"].get(str(now.hour), 0) + 1
    if now.strftime("%Y-%m-%d") not in m["days"]:
        m["days"].append(now.strftime("%Y-%m-%d"))
    m["last"] = entry["time"]
    save_habits(h)
    return entry

def summary(days=7):
    h = load_habits()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    logs = [e for e in h["logs"] if e["time"][:10] >= cutoff]
    print(f"📊 最近 {days} 天互动总结（共 {len(logs)} 次）\n")
    if not logs:
        print("暂无数据，先和糖糖说说话吧～")
        return
    # 按人统计
    by_name = {}
    for e in logs:
        by_name.setdefault(e["name"], []).append(e)
    for name, entries in by_name.items():
        hours = [e["hour"] for e in entries]
        texts = [e["text"] for e in entries if e["text"]]
        print(f"👤 {name}: {len(entries)} 次互动")
        # 活跃时段
        active = sorted(set(hours))
        if active:
            ranges = []
            start = prev = active[0]
            for h in active[1:]:
                if h == prev + 1:
                    prev = h
                else:
                    ranges.append(f"{start}-{prev}点")
                    start = prev = h
            ranges.append(f"{start}-{prev}点")
            print(f"   活跃时段: {', '.join(ranges)}")
        if texts:
            print(f"   最近说的: {texts[-3:]}")
        print()
    # 航航睡眠规律
    if "航航" in by_name:
        night = [e["hour"] for e in by_name["航航"] if e["hour"] >= 21 or e["hour"] < 6]
        if night:
            latest = max(night)
            print(f"🌙 航航最近睡觉时间: 约 {latest} 点")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "enroll":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        files = sys.argv[3:]
        if not name or not files:
            print("用法: cat-vp.py enroll <名字> <pcm文件...>")
            sys.exit(1)
        enroll(name, files)
    elif cmd == "identify":
        pcm = sys.argv[2] if len(sys.argv) > 2 else None
        print(identify(pcm) if pcm else "用法: cat-vp.py identify <pcm文件>")
    elif cmd == "log":
        name = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        text = sys.argv[3] if len(sys.argv) > 3 else ""
        e = log(name, text)
        print(f"✅ 已记录: {e['time']} {name}「{text}」")
    elif cmd == "summary":
        summary(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
    elif cmd == "list":
        db = load_vp()
        if not db:
            print("📭 声纹库为空，先建档: cat-vp.py enroll 航航 xx.pcm")
        else:
            for name, data in db.items():
                print(f"👤 {name}: {len(data['samples'])} 段样本, 建档于 {data['created'][:16]}")
