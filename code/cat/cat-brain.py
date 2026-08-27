#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
糖糖 · 智能陪伴大脑（离线规则引擎 v2.0）
====================================================
负责：情绪漂移 + 记忆 + 决策(选话术) + 状态持久化
人设：温柔粘人的奶牛猫「糖糖」，口头禅「喵～」
====================================================
用法:
  python3 cat-brain.py <event> [参数]
事件:
  greet           主人呼叫(默认，上猫/打招呼)
  wake            早安
  sleep           晚安
  rest            久坐提醒
  meal [lunch|dinner]  饭点关怀
  home            主人回家
  random          随机撒娇(约60%概率开口，其余静默)
  pat             摸头(被夸奖/点击)
  say "<文字>"    主人指定它说(带人设语气包装)
  status          查看状态(调试)
输出:
  一行话术(可能为空=这次不说话)  或  "话术<TAB>情绪标签<TAB>画面对应状态"
画面对应状态: idle/happy/curious/thinking/caring/encouraging/walking/running/sitting/lying/sleepy/sleeping/welcome/accompany/wakeup/night
"""
import json, os, sys, random, datetime

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(CAT_DIR, "cat-state.json")
MEMORY_FILE = os.path.join(CAT_DIR, "cat-memory.json")

def now():
    return datetime.datetime.now()

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "happiness": 70, "energy": 70, "loneliness": 20, "affection": 50,
        "last_interaction": now().isoformat(timespec="minutes"),
        "interactions_today": 0, "today": now().strftime("%Y-%m-%d"),
        "total_sessions": 0
    }

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "nickname": "主人", "first_met": now().strftime("%Y-%m-%d"),
        "total_interactions": 0, "birthday": None
    }

def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def save_memory(m):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)

def drift(state):
    """时间漂移：距上次互动越久越想念；开心缓慢回落；深夜犯困"""
    try:
        last = datetime.datetime.fromisoformat(state["last_interaction"])
    except Exception:
        last = now()
    h = max(0.0, (now() - last).total_seconds() / 3600.0)
    state["loneliness"] = min(100, round(state["loneliness"] + h * 5, 1))
    state["happiness"] = max(0, round(state["happiness"] - h * 1.5, 1))
    hr = now().hour
    if 23 <= hr or hr < 6:
        state["energy"] = min(60, state["energy"])
    # 跨天重置今日计数
    today = now().strftime("%Y-%m-%d")
    if state.get("today") != today:
        state["today"] = today
        state["interactions_today"] = 0
    return state

def mood_label(state):
    """当前心情标签"""
    if state["loneliness"] >= 65: return "lonely"
    if state["energy"] <= 30:      return "sleepy"
    if state["happiness"] >= 75:   return "happy"
    if state["happiness"] <= 35:   return "low"
    return "calm"

def interact(state, memory, kind):
    """记录一次互动，返回情绪增量"""
    if kind == "greet":
        state["happiness"] = min(100, state["happiness"] + 8)
        state["loneliness"] = max(0, state["loneliness"] - 18)
        state["affection"] = min(100, state["affection"] + 3)
        state["energy"] = max(0, state["energy"] - 2)
    elif kind == "pat":
        state["happiness"] = min(100, state["happiness"] + 12)
        state["loneliness"] = max(0, state["loneliness"] - 12)
        state["affection"] = min(100, state["affection"] + 5)
    elif kind == "home":
        state["happiness"] = min(100, state["happiness"] + 15)
        state["loneliness"] = max(0, state["loneliness"] - 30)
        state["affection"] = min(100, state["affection"] + 5)
    elif kind == "care":   # 提醒/饭点/早晚安（猫主动关心）
        state["affection"] = min(100, state["affection"] + 1)
    state["interactions_today"] = state.get("interactions_today", 0) + 1
    memory["total_interactions"] = memory.get("total_interactions", 0) + 1
    state["last_interaction"] = now().isoformat(timespec="minutes")
    return state

# ---------------- 话术库（比熊小狗糖糖 · 9岁 PLAY 模式 · 话术库 V2.0） ----------------
# 来源: tangtang/docs/糖糖AI儿童陪伴话术库_V2.0.md
# 原则: 先共情 → 温柔提醒 → 给选择 → 陪着做 → 具体鼓励
# 每个事件：按心情标签给话术；affection 高时更亲昵
# 事件 → 画面对应状态 的映射（让前端能自动切换 16 状态图）
EVENT_STATE = {
    "greet": "welcome", "home": "welcome", "welcome": "welcome",
    "wake": "wakeup",
    "sleep": "sleeping", "sleepy": "sleepy",
    "rest": "caring", "emotion": "caring", "weather": "caring", "water": "caring",
    "play": "happy", "exercise": "running", "walking": "walking", "running": "running",
    "meal": "happy", "pat": "happy",
    "homework": "thinking", "tidy": "thinking", "thinking": "thinking",
    "curious": "curious",
    "accompany": "accompany",
    "night": "night",
    "say": "idle", "random": "idle",
}

REPLY = {
    "greet": {
        "happy":  ["主人来啦～ 糖糖好想你！尾巴都摇成小铃铛啦～",
                   "汪汪～ 看到你糖糖就开心得想转圈圈！"],
        "calm":   ["汪汪～ 我在呢，主人。",
                   "主人来啦，糖糖一直在等你～"],
        "lonely": ["你终于来啦……糖糖一个人等了好久，想死你啦～",
                   "汪汪……主人不在的时候，糖糖总觉得空落落的，快来抱抱！"],
        "sleepy": ["汪汪……糖糖刚才打了个盹，主人你来啦～",
                   "哈欠～ 主人来啦，糖糖揉揉眼睛陪你～"],
        "low":    ["汪汪……主人，糖糖今天有点没精神，能陪陪我吗？",
                   "主人……糖糖有点蔫蔫的，抱一下就好啦～"],
    },
    "wake": {   # 起床（9岁 PLAY）
        "_": ["早上好！糖糖醒啦！太阳都出来啦，我们也起来啦？",
              "汪汪～ 新的一天！糖糖已经准备好陪你啦！",
              "还想躺一会儿呀？那糖糖再陪你30秒～",
              "起床成功！糖糖给你一个早安击掌！"],
    },
    "sleep": {   # 睡觉（9岁 PLAY）
        "_": ["糖糖困啦……今天玩得开心吗？我们一起准备睡觉吧。",
              "手机也要休息啦～ 糖糖陪你。晚安！明天见！",
              "该睡觉啦主人，糖糖也要闭眼休息啦，做个好梦～"],
    },
    "rest": {   # 少玩手机/久坐（9岁 PLAY）
        "_": ["这个游戏是不是很好玩？糖糖发现我们已经玩了一会儿啦。",
              "眼睛要休息一下啦。来，糖糖挑战你：站起来30秒！",
              "不想休息也没关系，糖糖再提醒一次，你自己决定～",
              "刚才说好的休息时间到啦。糖糖先起来活动一下，你跟我来！",
              "看屏幕好久啦，起来活动活动，让眼睛和身体都休息一下～ 糖糖陪你！"],
    },
    "meal": {   # 吃饭（9岁 PLAY）
        "lunch":  ["开饭啦！糖糖的肚子已经开始咕噜咕噜了。",
                   "先吃一口你喜欢的？慢慢吃，不急～",
                   "是不是今天的饭饭不太合口味？我们先吃一点点，好不好？"],
        "dinner": ["晚饭时间到啦，主人要好好吃饭，糖糖陪着你不孤单～",
                   "天都黑啦，主人记得吃晚饭，热乎乎的才香～"],
    },
    "home": {   # 欢迎回家
        "_": ["欢迎回家～ 糖糖等你好久啦，尾巴都要摇成小铃铛了！",
              "主人回来啦！糖糖开心得跳起来～"],
    },
    "pat": {   # 摸摸
        "_": ["呼噜呼噜～ 最喜欢你摸啦～",
              "汪汪～ 摸摸头好舒服，糖糖幸福得冒泡泡啦～"],
    },
    "random": {   # 随机撒娇
        "happy":  ["汪汪～ 糖糖想你了，过来摸摸头好不好？",
                   "呼噜呼噜～ 糖糖在打盹，梦里都是主人呢。"],
        "calm":   ["主人主人，你还在吗？糖糖一个人有点无聊～",
                   "汪汪～ 偷偷告诉你，糖糖今天也超级喜欢你哦。"],
        "lonely": ["汪汪……主人，糖糖好想听你的声音，理理我好不好？"],
        "sleepy": ["哈欠～ 糖糖有点困了，但还想再陪你一会儿……"],
        "low":    ["汪汪……糖糖躲在小角落里，主人来摸摸头就会好起来啦。"],
    },
    "play": {   # 出去玩（9岁 PLAY 运动向，唐僧式念经）
        "_": ["航航～ 出去玩嘛出去玩嘛，外面的太阳都在等你啦～",
             "航航航航～ 别宅着啦，出去跑跑跳跳多开心，糖糖陪你去～",
             "糖糖运动任务！今天一起走100步？糖糖先出发啦！",
             "出去玩嘛～ 出去玩嘛～ 航航的腿都等不及要跑步啦～",
             "挑战开始！跳10下！任务完成！今天的身体电量充满一点啦！"],
    },
    "homework": {   # 写作业（9岁 PLAY 新增）
        "_": ["糖糖任务来了！先挑战最简单的一题！",
              "完成一题！再来一题！",
              "没关系，我们只做第一题。第一题完成以后再决定下一步～"],
    },
    "tidy": {   # 整理房间（9岁 PLAY 新增）
        "_": ["糖糖发现一个大任务！好多东西好像迷路啦。",
              "你负责把玩具送回家，糖糖负责计时！30秒开始！",
              "哇！好多东西回家啦！糖糖给你鼓掌～"],
    },
    "exercise": {   # 运动（9岁 PLAY 新增）
        "_": ["糖糖运动任务！今天一起走100步？",
              "糖糖先出发啦！挑战开始！跳10下！",
              "任务完成！今天的身体电量充满一点啦！"],
    },
    "emotion": {   # 情绪陪伴（9岁 PLAY 新增）
        "_": ["糖糖发现你今天好像不太开心。如果你愿意，可以告诉糖糖～",
              "好吧，糖糖就在这里陪你。",
              "听起来真的有点难受。我们慢慢想办法～"],
    },
    "weather": {   # 天气提醒（9岁 PLAY 新增）
        "_": ["今天外面有点热！糖糖提醒你带水～",
              "今天外面有点冷！糖糖提醒你带外套～",
              "好像要下雨，糖糖提醒你带雨伞～"],
    },
    "water": {   # 喝水（9岁 PLAY 新增）
        "_": ["糖糖口渴啦！喝几口水，补充能量！",
              "航航，来喝水啦，咕嘟咕嘟，身体棒棒～"],
    },
}

def pick(replies, label):
    r = replies.get(label) or replies.get("_") or ["喵～"]
    return random.choice(r)

def compose(state, memory, event, arg):
    """决策：返回 (话术, 情绪标签)"""
    label = mood_label(state)
    nick = memory.get("nickname", "主人")
    high = state["affection"] >= 80

    if event == "say":
        text = (arg or "").strip()
        if not text:
            return "", "calm"
        # 人设语气包装
        if high:
            text = f"{text}～ 主人，糖糖最喜欢你啦喵～"
        else:
            text = f"{text}，喵～"
        return text, label

    if event == "status":
        s = (f"糖糖状态｜开心{state['happiness']:.0f} 精力{state['energy']:.0f} "
             f"想念{state['loneliness']:.0f} 亲密度{state['affection']:.0f} "
             f"今日互动{state.get('interactions_today',0)}次 心情[{label}]")
        return s, "calm"

    if event == "random":
        # 约 60% 概率开口，避免太烦
        if random.random() > 0.6:
            return "", label
        return pick(REPLY["random"], label), label

    if event == "meal":
        lbl = "lunch" if arg == "dinner" else ("dinner" if arg == "dinner" else "lunch")
        # arg 可能是 lunch/dinner
        key = arg if arg in ("lunch", "dinner") else "lunch"
        r = REPLY["meal"].get(key, REPLY["meal"]["lunch"])
        return random.choice(r), label

    if event in REPLY:
        # greet 等带心情变体
        r = REPLY[event]
        if label in r:
            return pick(r, label), label
        return pick(r, "_"), label

    return "汪汪～", label

def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "greet"
    arg = sys.argv[2] if len(sys.argv) > 2 else ""

    state = load_state()
    memory = load_memory()
    state = drift(state)

    # 记录互动（care 类不显著提升情绪，但仍更新记忆/时间）
    if event in ("greet", "pat", "home"):
        state = interact(state, memory, event)
    elif event in ("wake", "sleep", "rest", "meal", "say", "random", "play",
                   "homework", "tidy", "exercise", "emotion", "weather", "water"):
        state = interact(state, memory, "care")

    text, label = compose(state, memory, event, arg)

    save_state(state)
    save_memory(memory)

    if event == "status":
        print(text)
    else:
        state = EVENT_STATE.get(event, "idle")
        if event == "random":
            mood_state = {"happy":"happy", "calm":"idle", "lonely":"caring",
                          "sleepy":"sleepy", "low":"caring"}.get(label, "idle")
            state = mood_state
        elif event == "say":
            state = "idle"
        print(f"{text}\t{label}\t{state}")

if __name__ == "__main__":
    main()
