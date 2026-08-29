#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
糖糖 · 智能陪伴大脑（离线规则引擎 v2.1）
====================================================
负责：情绪漂移 + 记忆 + 打扰冷却 + 话术（JSON 优先）+ 状态持久化
人设：白色比熊小狗「糖糖」，口头禅「汪汪～」
====================================================
用法:
  python3 cat-brain.py <event> [参数]
事件:
  greet / wake / sleep / rest / meal [lunch|dinner] / home / random
  pat / say "<文字>" / status / play / homework / tidy / exercise
  emotion / weather / water / pet_walk / pet_water / pet_food / pet_groom
  alarm [school]
  english [hanghang|qiaqia]
输出:
  一行：话术<TAB>情绪标签<TAB>画面对应状态
  话术为空表示这次不说话（冷却或 random 静默）
"""
import json, os, sys, random, datetime, importlib.util

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)
from tangtang_paths import data_dir  # noqa: E402

DATA_DIR = data_dir()
STATE_FILE = os.path.join(DATA_DIR, "cat-state.json")
MEMORY_FILE = os.path.join(DATA_DIR, "cat-memory.json")

# LEGACY TABLE ONLY. Not the production source of truth.
# Visual state must come from behavior.legacy_adapter → CharacterStateEngine.
EVENT_STATE = {
    "greet": "welcome", "home": "welcome", "welcome": "welcome",
    "wake": "wakeup",
    "alarm": "wakeup",
    "sleep": "sleeping", "sleepy": "sleepy",
    "rest": "caring", "emotion": "caring", "weather": "caring", "water": "caring",
    "play": "happy", "exercise": "running", "walking": "walking", "running": "running",
    "pet_walk": "walking", "pet_water": "caring", "pet_food": "happy", "pet_groom": "caring",
    "meal": "happy", "pat": "happy",
    "homework": "thinking", "tidy": "thinking", "thinking": "thinking",
    "english": "thinking",
    "curious": "curious",
    "accompany": "accompany",
    "night": "night",
    "say": "idle", "random": "idle",
}

EVENT_SCENE = {
    "rest": "phone_break",
    "greet": "greet",
    "wake": "wake",
    "alarm": "alarm",
    "sleep": "sleep",
    "meal": "meal",
    "homework": "homework",
    "tidy": "tidy",
    "exercise": "exercise",
    "play": "exercise",
    "emotion": "emotion",
    "weather": "weather",
    "water": "water",
    "pet_walk": "pet_walk",
    "pet_water": "pet_water",
    "pet_food": "pet_food",
    "pet_groom": "pet_groom",
    "english": "english",
}

# 主动提醒冷却（分钟）。点名/摸摸/指定说不冷却。
COOLDOWN_MINUTES = {
    "rest": 30, "play": 45, "exercise": 45, "water": 60,
    "homework": 40, "tidy": 40, "weather": 180,
    "meal": 90, "wake": 240, "sleep": 180, "emotion": 60,
    "alarm": 20,
    "random": 20, "home": 120,
    "pet_walk": 90, "pet_water": 90, "pet_food": 180, "pet_groom": 240,
    "english": 90,
}
USER_EVENTS = {"greet", "pat", "say", "status"}

REPLY = {
    "greet": {
        "happy":  ["来啦～ 糖糖好想你！尾巴都摇成小铃铛啦～",
                   "汪汪～ 看到你糖糖就开心得想转圈圈！"],
        "calm":   ["汪汪～ 我在呢。",
                   "你来啦，糖糖一直在等你～"],
        "lonely": ["你终于来啦……糖糖一个人等了好久，想死你啦～",
                   "汪汪……你不在的时候，糖糖总觉得空落落的，快来抱抱！"],
        "sleepy": ["汪汪……糖糖刚才打了个盹，你来啦～",
                   "哈欠～ 你来啦，糖糖揉揉眼睛陪你～"],
        "low":    ["汪汪……糖糖今天有点没精神，能陪陪我吗？",
                   "糖糖有点蔫蔫的，抱一下就好啦～"],
    },
    "wake": {
        "_": ["早上好！糖糖醒啦！太阳都出来啦，我们也起来啦？",
              "汪汪～ 新的一天！糖糖已经准备好陪你啦！",
              "还想躺一会儿呀？那糖糖再陪你30秒～",
              "起床成功！糖糖给你一个早安击掌！"],
    },
    "alarm": {
        "_": ["六点半了，该起床上学了。起来后看一眼糖糖的水，你们也清醒一下。",
              "汪汪～ 上学啦。糖糖叫你起床，起来给糖糖倒点水，你也喝一口。"],
    },
    "sleep": {
        "_": ["糖糖困啦……今天玩得开心吗？我们一起准备睡觉吧。",
              "手机也要休息啦～ 糖糖陪你。晚安！明天见！",
              "该睡觉啦，糖糖也要闭眼休息啦，做个好梦～"],
    },
    "rest": {
        "_": ["糖糖腿都坐麻啦。陪糖糖站起来一下，你眼睛也歇歇？",
              "看屏幕好久啦。糖糖先起来转转，你要不要跟来？"],
    },
    "meal": {
        "lunch":  ["开饭啦！糖糖的肚子已经开始咕噜咕噜了。",
                   "先吃一口你喜欢的？慢慢吃，不急～",
                   "是不是今天的饭饭不太合口味？我们先吃一点点，好不好？"],
        "dinner": ["晚饭时间到啦，要好好吃饭，糖糖陪着你不孤单～",
                   "天都黑啦，记得吃晚饭，热乎乎的才香～"],
    },
    "home": {
        "_": ["欢迎回家～ 糖糖等你好久啦，尾巴都要摇成小铃铛了！",
              "回来啦！糖糖开心得跳起来～"],
    },
    "pat": {
        "_": ["汪汪～ 最喜欢你摸啦～",
              "汪汪～ 摸摸头好舒服，糖糖幸福得冒泡泡啦～"],
    },
    "random": {
        "happy":  ["汪汪～ 糖糖想你了，过来摸摸头好不好？",
                   "糖糖在打盹，梦里都是你呢。"],
        "calm":   ["还在吗？糖糖一个人有点无聊～",
                   "汪汪～ 偷偷告诉你，糖糖今天也超级喜欢你哦。"],
        "lonely": ["汪汪……糖糖好想听你的声音，理理我好不好？"],
        "sleepy": ["哈欠～ 糖糖有点困了，但还想再陪你一会儿……"],
        "low":    ["汪汪……糖糖躲在小角落里，来摸摸头就会好起来啦。"],
    },
    "play": {
        "_": ["糖糖想出门转转，你带糖糖去？你也跑两步～",
             "出去走走嘛，糖糖陪你，太阳也在等。"],
    },
    "homework": {
        "_": ["糖糖任务来了！先挑战最简单的一题！",
              "完成一题！再来一题！",
              "没关系，我们只做第一题。第一题完成以后再决定下一步～"],
    },
    "tidy": {
        "_": ["糖糖发现一个大任务！好多东西好像迷路啦。",
              "你负责把玩具送回家，糖糖负责计时！30秒开始！",
              "哇！好多东西回家啦！糖糖给你鼓掌～"],
    },
    "exercise": {
        "_": ["糖糖想出门转转。你带糖糖走两圈，你也活动一下？",
              "糖糖先走起来啦，你要不要一起来？"],
    },
    "emotion": {
        "_": ["糖糖发现你今天好像不太开心。如果你愿意，可以告诉糖糖～",
              "好吧，糖糖就在这里陪你。",
              "听起来真的有点难受。我们慢慢想办法～"],
    },
    "weather": {
        "_": ["出门前看一眼天气，热就带水，冷就带外套～",
              "好像要下雨，糖糖提醒你带雨伞～"],
    },
    "water": {
        "_": ["糖糖口渴啦！给糖糖加点水，你也喝一口～",
              "来喝水啦，糖糖陪你咕嘟咕嘟～"],
    },
    "pet_walk": {
        "_": ["糖糖想出门转转。你带糖糖走一圈，你也活动一下？",
              "糖糖腿等不及了，出去走走好不好？"],
    },
    "pet_water": {
        "_": ["糖糖的水是不是快没了？加一点，你也喝一口。"],
    },
    "pet_food": {
        "_": ["糖糖该吃饭了。你方便的话喂一下，你也记得吃饭。"],
    },
    "pet_groom": {
        "_": ["糖糖毛有点乱。有空轻轻梳两下就好。"],
    },
    "english": {
        "_": ["糖糖想学一个英语词。你要不要当小老师？不学也行。"],
    },
}


def now():
    return datetime.datetime.now()


def current_profile():
    p = (os.environ.get("TANGTANG_PROFILE") or "play").strip().lower()
    return p if p in ("play", "friend", "adult", "elder") else "play"


def child_name(memory):
    env = (os.environ.get("TANGTANG_CHILD_NAME") or "").strip()
    if env:
        return env
    nick = (memory.get("nickname") or "").strip()
    return nick or "小朋友"


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_state():
    return load_json(STATE_FILE, {
        "happiness": 70, "energy": 70, "loneliness": 20, "affection": 50,
        "last_interaction": now().isoformat(timespec="minutes"),
        "interactions_today": 0, "today": now().strftime("%Y-%m-%d"),
        "total_sessions": 0, "proactive_log": {},
    })


def load_memory():
    return load_json(MEMORY_FILE, {
        "nickname": "小朋友", "first_met": now().strftime("%Y-%m-%d"),
        "total_interactions": 0, "birthday": None,
    })


def save_state(s):
    save_json(STATE_FILE, s)


def save_memory(m):
    save_json(MEMORY_FILE, m)


def copy_library_paths():
    repo_data = os.path.abspath(os.path.join(CAT_DIR, "..", "..", "data", "tangtang_copy_library_v2.json"))
    return [
        os.path.join(CAT_DIR, "tangtang_copy_library_v2.json"),
        repo_data,
    ]


def load_copy_library():
    for path in copy_library_paths():
        if os.path.exists(path):
            data = load_json(path, None)
            if isinstance(data, dict) and data.get("items"):
                return data
    return None


COPY_LIB = load_copy_library()


def pick_english_line(who, preferred_id=None):
    path = os.path.join(CAT_DIR, "cat-english.py")
    spec = importlib.util.spec_from_file_location("cat_english", path)
    if not spec or not spec.loader:
        return None, ""
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "pick_with_id"):
        text, lid = mod.pick_with_id(who, preferred_id=preferred_id)
        return ((text or "").strip() or None), (lid or "")
    return ((mod.pick_line(who) or "").strip() or None), ""


def _habits_mod():
    path = os.path.join(CAT_DIR, "cat-habits.py")
    spec = importlib.util.spec_from_file_location("tangtang_habits", path)
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def habit_who(event, arg=""):
    try:
        mod = _habits_mod()
        if mod:
            return mod.audience(event, arg) or ""
    except Exception:
        pass
    return (os.environ.get("TANGTANG_MEMBER_ID") or os.environ.get("TANGTANG_SPEAKER") or "").strip()


def habits_should_speak(event, arg=""):
    try:
        mod = _habits_mod()
        if not mod:
            return True
        ok, reason = mod.should_speak(event, habit_who(event, arg))
        if not ok:
            sys.stderr.write("[habit] skip %s %s %s\n" % (habit_who(event, arg), event, reason))
        return ok
    except Exception:
        return True


def habits_prefer_line(event, arg=""):
    try:
        mod = _habits_mod()
        if not mod:
            return ""
        return (mod.prefer_line(event, habit_who(event, arg)) or "").strip()
    except Exception:
        return ""


def habits_remember_line(event, arg, line_id):
    lid = (line_id or "").strip()
    who = habit_who(event, arg)
    if not lid or not who:
        return
    try:
        mod = _habits_mod()
        if mod:
            mod.remember_line(who, event, lid)
    except Exception:
        return


def pick_from_library(event, profile, preferred_id=None):
    if not COPY_LIB:
        return None, ""
    scene = EVENT_SCENE.get(event)
    if not scene:
        return None, ""
    items = COPY_LIB.get("items") or []
    matched = [i for i in items if i.get("scene") == scene and i.get("profile") == profile]
    if not matched and profile in ("play", "friend"):
        matched = [i for i in items if i.get("scene") == scene and i.get("profile") in ("play", "friend")]
    matched = [i for i in matched if i.get("text")]
    if not matched:
        return None, ""
    pref = (preferred_id or "").strip()
    if pref:
        for i in matched:
            if (i.get("id") or "") == pref:
                return i.get("text"), pref
    choice = random.choice(matched)
    return choice.get("text"), (choice.get("id") or "")


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
    today = now().strftime("%Y-%m-%d")
    if state.get("today") != today:
        state["today"] = today
        state["interactions_today"] = 0
    return state


def mood_label(state):
    if state["loneliness"] >= 65:
        return "lonely"
    if state["energy"] <= 30:
        return "sleepy"
    if state["happiness"] >= 75:
        return "happy"
    if state["happiness"] <= 35:
        return "low"
    return "calm"


def interact(state, memory, kind):
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
    elif kind == "care":
        state["affection"] = min(100, state["affection"] + 1)
    state["interactions_today"] = state.get("interactions_today", 0) + 1
    memory["total_interactions"] = memory.get("total_interactions", 0) + 1
    state["last_interaction"] = now().isoformat(timespec="minutes")
    return state


def _turn_gate_ok(event, arg=""):
    """客厅短窗账本：当天 stop / 连续沉默反对 → 英语这类先不说。"""
    if event not in ("english", "turn"):
        return True
    path = os.path.join(CAT_DIR, "cat-turn.py")
    spec = importlib.util.spec_from_file_location("cat_turn_mod", path)
    if not spec or not spec.loader:
        return True
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        who = (arg or os.environ.get("TANGTANG_MEMBER_ID")
               or os.environ.get("TANGTANG_SPEAKER") or "")
        if event == "english":
            who = mod.normalize_who(who) or "hanghang"
        return bool(mod.gate_allows(event, who))
    except Exception:
        return True


# V4 Round 1: core.compat.should_interrupt is the future policy port.
# This cooldown gate stays. Do not delete. cat-* may later also consult:
#   from core.compat import should_interrupt
def should_speak(state, event, arg=""):
    if event in USER_EVENTS:
        return True
    if not arg:
        arg = sys.argv[2] if len(sys.argv) > 2 else ""
    if not _turn_gate_ok(event, arg):
        return False
    if not habits_should_speak(event, arg):
        return False
    minutes = COOLDOWN_MINUTES.get(event)
    if minutes is None:
        return True
    log = state.get("proactive_log") or {}
    last = log.get(event)
    if not last:
        return True
    try:
        last_dt = datetime.datetime.fromisoformat(last)
    except Exception:
        return True
    delta = (now() - last_dt).total_seconds() / 60.0
    return delta >= minutes


def mark_spoken(state, event):
    if event in USER_EVENTS or event not in COOLDOWN_MINUTES:
        return
    log = state.setdefault("proactive_log", {})
    log[event] = now().isoformat(timespec="minutes")


def pick(replies, label):
    r = replies.get(label) or replies.get("_") or ["汪汪～"]
    return random.choice(r)


def compose(state, memory, event, arg):
    """决策：返回 (话术, 情绪标签)"""
    label = mood_label(state)
    nick = child_name(memory)
    high = state["affection"] >= 80
    profile = current_profile()

    if event == "say":
        text = (arg or "").strip()
        if not text:
            return "", "calm"
        if profile == "elder":
            return text, label
        if high:
            text = f"{text}～ {nick}，糖糖最喜欢你啦汪汪～"
        else:
            text = f"{text}，汪汪～"
        return text, label

    if event == "status":
        s = (f"糖糖状态｜开心{state['happiness']:.0f} 精力{state['energy']:.0f} "
             f"想念{state['loneliness']:.0f} 亲密度{state['affection']:.0f} "
             f"今日互动{state.get('interactions_today', 0)}次 心情[{label}] "
             f"人格[{profile}]")
        return s, "calm"

    if event == "random":
        if random.random() > 0.6:
            return "", label
        return pick(REPLY["random"], label), label

    preferred = habits_prefer_line(event, arg)
    lib_text, lib_id = pick_from_library(event, profile, preferred)
    if event == "english":
        try:
            en_text, en_id = pick_english_line(arg, preferred)
            if en_text:
                lib_text, lib_id = en_text, en_id
        except Exception:
            pass
    if lib_text:
        habits_remember_line(event, arg, lib_id)
        return lib_text, label

    if event == "meal":
        key = arg if arg in ("lunch", "dinner") else "lunch"
        r = REPLY["meal"].get(key, REPLY["meal"]["lunch"])
        return random.choice(r), label

    if event in REPLY:
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
    label = mood_label(state)

    if event == "status":
        text, label = compose(state, memory, event, arg)
        save_state(state)
        save_memory(memory)
        print(text)
        return

    if not should_speak(state, event, arg):
        save_state(state)
        visual, _ = _resolve_character_state(event, arg, "", label)
        print(f"\t{label}\t{visual}")
        return

    if event in ("greet", "pat", "home"):
        state = interact(state, memory, event)
    elif event in ("wake", "alarm", "sleep", "rest", "meal", "say", "play",
                   "homework", "tidy", "exercise", "emotion", "weather", "water",
                   "pet_walk", "pet_water", "pet_food", "pet_groom", "english"):
        state = interact(state, memory, "care")

    text, label = compose(state, memory, event, arg)
    if event == "random" and text:
        state = interact(state, memory, "care")
    if text:
        mark_spoken(state, event)

    save_state(state)
    save_memory(memory)

    visual, text = _resolve_character_state(event, arg, text, label)
    print(f"{text}\t{label}\t{visual}")


def _resolve_character_state(event, arg, text, label):
    """Adapter → CharacterStateEngine → PresentationAction. EVENT_STATE is fallback only."""
    root = os.path.dirname(os.path.dirname(CAT_DIR))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from behavior.legacy_adapter import decide_from_legacy
        from core.presentation.character_presenter import CharacterPresenter
        from core.presentation.transport import write_presentation_action
    except Exception:
        return EVENT_STATE.get(event, "idle"), text

    decision = decide_from_legacy(event, arg)
    if not decision.speech_allowed:
        text = ""
    action = CharacterPresenter().present(decision, text=text)
    try:
        write_presentation_action(action, DATA_DIR)
    except OSError:
        pass
    return action.state, action.text if action.speak else text


if __name__ == "__main__":
    main()
