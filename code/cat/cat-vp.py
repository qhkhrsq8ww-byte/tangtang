#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 本地声纹识别 + 家庭习惯记录

重要：声纹库和习惯库均为本地隐私数据，禁止提交 Git。
用法：
  建档: ./cat-vp.py enroll <名字> <pcm文件...>
  识别: ./cat-vp.py identify <pcm文件>
  记录: ./cat-vp.py log <名字> <文本>
  总结: ./cat-vp.py summary [天数]
  列出: ./cat-vp.py list

识别阈值可通过环境变量 TANGTANG_VOICE_THRESHOLD 调整，默认 0.995。
实际部署前应使用家庭成员的真实样本做误识别/拒识测试，不应把 0.995 视为科学固定值。
"""
import json, os, sys, math, subprocess
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
VP_FILE = os.path.join(BASE, "cat-voiceprints.json")
HABIT_FILE = os.path.join(BASE, "cat-habits.json")
FEATURE_SH = os.path.join(BASE, "cat-vp-feature.sh")
THRESHOLD = float(os.environ.get("TANGTANG_VOICE_THRESHOLD", "0.995"))

KEYS = ["low", "mid", "midhi", "high", "rms", "peak", "lra", "zcr"]

def extract_features(pcm):
    if not pcm or not os.path.exists(pcm):
        return None
    try:
        r = subprocess.run([FEATURE_SH, pcm], capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return None

def cosine_sim(a, b):
    va = [float(a.get(k, 0)) for k in KEYS]
    vb = [float(b.get(k, 0)) for k in KEYS]
    dot = sum(x*y for x,y in zip(va,vb))
    na = math.sqrt(sum(x*x for x in va)) or 1
    nb = math.sqrt(sum(y*y for y in vb)) or 1
    return dot / (na*nb)

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def load_vp():
    return load_json(VP_FILE, {})

def save_vp(db):
    save_json(VP_FILE, db)

def enroll(name, files):
    db = load_vp(); feats=[]
    for pcm in files:
        feat=extract_features(pcm)
        if feat:
            feats.append(feat)
            print(f"  ✓ {os.path.basename(pcm)}")
        else:
            print(f"  ✗ 特征提取失败: {pcm}")
    if not feats:
        print("❌ 没有成功提取到特征"); return 1
    avg={k:sum(float(f.get(k,0)) for f in feats)/len(feats) for k in KEYS}
    db[name]={"samples":feats,"avg":avg,"created":datetime.now().isoformat()}
    save_vp(db)
    print(f"✅ 已建档「{name}」({len(feats)} 段样本)")
    return 0

def identify(pcm):
    db=load_vp()
    feat=extract_features(pcm)
    if not db or not feat:
        return "unknown"
    best_name,best_score="unknown",-1
    for name,data in db.items():
        avg=data.get("avg",{})
        score=cosine_sim(feat,avg)
        if score>best_score:
            best_name,best_score=name,score
    return best_name if best_score>=THRESHOLD else "unknown"

def load_habits():
    return load_json(HABIT_FILE, {"members":{},"logs":[]})

def save_habits(h):
    save_json(HABIT_FILE,h)

def log(name,text=""):
    h=load_habits(); now=datetime.now()
    entry={"name":name,"text":text,"time":now.strftime("%Y-%m-%d %H:%M:%S"),"hour":now.hour,"weekday":now.strftime("%A")}
    h.setdefault("logs",[]).append(entry)
    m=h.setdefault("members",{}).setdefault(name,{"total":0,"by_hour":{},"days":[],"last":None})
    m["total"]+=1
    hour=str(now.hour); m["by_hour"][hour]=m["by_hour"].get(hour,0)+1
    day=now.strftime("%Y-%m-%d")
    if day not in m["days"]: m["days"].append(day)
    m["last"]=entry["time"]
    save_habits(h); return entry

def summary(days=7):
    h=load_habits(); cutoff=(datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d")
    logs=[e for e in h.get("logs",[]) if e.get("time","")[:10]>=cutoff]
    print(f"📊 最近 {days} 天互动总结（共 {len(logs)} 次）\n")
    if not logs: print("暂无数据，先和糖糖说说话吧～"); return
    by_name={}
    for e in logs: by_name.setdefault(e.get("name","unknown"),[]).append(e)
    for name,entries in by_name.items():
        print(f"👤 {name}: {len(entries)} 次互动")
        active=sorted(set(e.get("hour",0) for e in entries))
        if active: print("   活跃时段: "+", ".join(f"{h}点" for h in active))
        texts=[e.get("text") for e in entries if e.get("text")]
        if texts: print(f"   最近说的: {texts[-3:]}")
        print()

if __name__ == "__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "list"
    if cmd=="enroll":
        name=sys.argv[2] if len(sys.argv)>2 else None; files=sys.argv[3:]
        if not name or not files: print("用法: cat-vp.py enroll <名字> <pcm文件...>"); sys.exit(1)
        sys.exit(enroll(name,files))
    elif cmd=="identify":
        pcm=sys.argv[2] if len(sys.argv)>2 else None; print(identify(pcm) if pcm else "unknown")
    elif cmd=="log":
        name=sys.argv[2] if len(sys.argv)>2 else "unknown"; text=sys.argv[3] if len(sys.argv)>3 else ""
        e=log(name,text); print(f"✅ 已记录: {e['time']} {name}")
    elif cmd=="summary": summary(int(sys.argv[2]) if len(sys.argv)>2 else 7)
    elif cmd=="list":
        db=load_vp()
        print("📭 声纹库为空" if not db else "\n".join(f"👤 {n}: {len(d.get('samples',[]))} 段样本" for n,d in db.items()))
