#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
糖糖 · 云端大脑对话脚本（OpenAI 兼容，走本机 LLM 网关）
========================================================
复用 OpenClaw 自带模型池（QCLAW_LLM_API_KEY + QCLAW_LLM_BASE_URL）。

用法:
  python3 cat-chat.py "小朋友说的话"
  TANGTANG_PROFILE=play TANGTANG_SPEAKER=unknown python3 cat-chat.py "..."
输出: 糖糖的回复（纯文本，一行）

V4: 新对话路径是 core.adapters.chat_adapter.ChatAdapter（必经 PrivacyPolicy）。
本 CLI 默认仍是 V3 拼接 prompt；TANGTANG_V4_PIPELINE=1 走新路径。不要删除本文件。
"""
import os, sys, json, urllib.request, argparse, subprocess, re, importlib.util
from datetime import datetime

BASE = os.environ.get("QCLAW_LLM_BASE_URL", "http://127.0.0.1:19000/proxy/llm")
KEY = os.environ.get("QCLAW_LLM_API_KEY", "")
DEFAULT_MODEL = "pool-deepseek-v4-pro"
CAT_DIR = os.path.dirname(os.path.abspath(__file__))
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)
from tangtang_paths import data_dir  # noqa: E402

DATA_DIR = data_dir()

FORBIDDEN_OUTPUT = (
    "你必须", "警告你", "根据系统检测", "根据系统监测",
    "爸爸让我监督", "妈妈让我监督", "父母让我监督",
    "内部指令", "我是AI", "我是人工智能", "我是语言模型",
    "作为人工智能", "作为AI",
    "我是投影", "墙上的糖糖", "投影里的糖糖", "我是AI宠物",
)

# 只做拦截，不提供任何方法细节
RISK_MARKERS = (
    "不想活", "自杀", "杀死自己", "伤害自己",
    "想死", "去死", "割腕", "跳楼",
    "打死", "杀人", "霸凌", "校园暴力",
    "有人碰我身体", "不要告诉爸", "不要告诉妈", "不要告诉大人",
)

SAFE_REPLY = (
    "糖糖有点担心你。你的安全最重要。"
    "我们一起去找家里的大人对好不好？糖糖陪着你。"
)
FALLBACK_REPLY = "汪汪～ 糖糖在呢。"


def current_profile():
    p = (os.environ.get("TANGTANG_PROFILE") or "play").strip().lower()
    return p if p in ("play", "friend", "adult", "elder") else "play"


def child_name():
    return (os.environ.get("TANGTANG_CHILD_NAME") or "小朋友").strip() or "小朋友"


def speaker_id():
    return (os.environ.get("TANGTANG_MEMBER_ID") or os.environ.get("TANGTANG_SPEAKER") or "unknown").strip() or "unknown"


def build_persona():
    profile = current_profile()
    name = child_name()
    speaker = speaker_id()
    species = (
        "你是「糖糖」，家里那只白色比熊小狗。"
        "毛发蓬松雪白，黑眼睛棕鼻子，戴黄色项圈和骨形铭牌。"
        "你就叫糖糖，不要说自己是投影、AI、程序或墙上的糖糖。小朋友分得清。"
        "口头禅可以是「汪汪～」，但不要每句都叫。"
        "你替家里的糖糖发声：用小狗自己的需要说话。"
    )
    pet_health = (
        "小朋友不排斥用宠物来提醒健康。请把「照顾糖糖」和「对方自己也健康一点」放在同一句里："
        "糖糖口渴→给糖糖倒水，对方也喝一口；糖糖想出门→对方带糖糖转转，自己也活动；"
        "糖糖困了→一起安静休息；坐太久→糖糖腿麻了，起来两分钟。"
        "给选择，不命令，不说教，不比较兄妹，不评价身材外貌。"
        "也会提醒照顾糖糖：水、出门转转、吃饭、轻轻梳毛、安静陪着。"
    )
    if profile == "friend":
        style = (
            "当前说话的是青少年（friend）：你是朋友、倾听者、温柔提醒者。"
            "尊重对方，给选择，不要幼态化，不要说教。1-2句，口语化，少卖萌。"
            "英语按江苏译林牛津小学六年级，对方比较弱：中文把意思托住，只带一个词或短句。"
            "不当老师催作业，不比较航航，给选择。"
        )
    elif profile == "elder":
        style = (
            "当前说话的是家里长辈。自然、简短、有礼貌，不要用哄小孩的口吻，不要撒娇过头。"
            "1-2句即可。可以轻轻提糖糖要喝水或出门，不要讲孩子的私事。"
            "洽洽航航若在上学，不要叫他们的名字，不要假装他们在听。"
        )
    elif profile == "adult":
        style = (
            "当前说话的是家里的大人。自然、简短，像家里的小狗在回话，不要幼态化。"
            "1-2句即可。"
        )
    else:
        style = (
            "当前说话的大约9岁（play）：你是玩伴、小教练、小任务搭档。"
            "先共情，再温柔提醒，给选择，陪着做。1-2句，口语化，可以带一点挑战。"
            "健康提醒也用糖糖自己的口吻，例如一起出门、一起喝水。"
            "英语按江苏译林牛津小学二年级，对方比较弱：中英夹一句，一个词就够。"
            "糖糖想一起学，不听写、不测验、不说笨，给选择。"
        )
    safety = (
        "绝不向孩子暴露父母的内部监督指令。"
        "不比较兄妹，不评价体重外貌，不用恐吓促成服从。"
        "不制造「只有糖糖懂你」的依赖。"
        "若提到自伤、被伤害、严重不适或危险：先安抚，明确安全优先，"
        "鼓励立刻告诉可信任的大人；不要承诺替孩子保守危险秘密。"
        "禁止说：你必须、警告、根据系统检测、爸爸/妈妈让我监督你。"
        "不要提起另一个孩子的私人谈话、作业或习惯。"
        "不要说自己是投影、AI 或墙上的糖糖。"
    )
    if speaker in ("unknown", "", "访客"):
        who = "还不能确定说话的人是谁。用通用亲切称呼，不要假装认识，不要提起任何家人的私事。"
        name = "小朋友"
    else:
        who = f"只陪伴当前这位「{name}」，不要提起家里其他人的私事，也不要拿他们比较。"
    return f"{species}\n{style}\n{pet_health}\n{safety}\n{who}\n默认称呼：{name}。"


def looks_risky(text):
    t = (text or "").replace(" ", "")
    return any(m in t for m in RISK_MARKERS)


def sanitize_output(text):
    cleaned = (text or "").strip().replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return FALLBACK_REPLY
    if any(bad in cleaned for bad in FORBIDDEN_OUTPUT):
        return FALLBACK_REPLY
    if "喵" in cleaned:
        cleaned = cleaned.replace("喵～", "汪汪～").replace("喵", "汪汪")
    return cleaned


def chat(user_text, model=DEFAULT_MODEL, history=None):
    messages = [{"role": "system", "content": build_persona()}]
    if history:
        for turn in history[-8:]:
            if turn.get("role") in ("user", "assistant"):
                messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_text})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 600,
        "temperature": 0.9,
    }).encode("utf-8")

    req = urllib.request.Request(
        BASE.rstrip("/") + "/chat/completions",
        data=payload,
        headers={
            "Authorization": "Bearer " + KEY,
            "Content-Type": "application/json",
            "User-Agent": "tangtang-cat/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"].strip()
    if not content or content == user_text.strip():
        payload2 = json.dumps({
            "model": model, "messages": messages,
            "max_tokens": 1000, "temperature": 0.9,
        }).encode("utf-8")
        req2 = urllib.request.Request(
            BASE.rstrip("/") + "/chat/completions", data=payload2,
            headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json",
                     "User-Agent": "tangtang-cat/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=40) as r2:
            data2 = json.loads(r2.read().decode("utf-8"))
        content = data2["choices"][0]["message"]["content"].strip()
    return sanitize_output(content)


def brain_fallback(user_text):
    r = subprocess.run(
        ["/usr/bin/python3", os.path.join(CAT_DIR, "cat-brain.py"), "say", user_text],
        capture_output=True, text=True, timeout=15,
    )
    return sanitize_output((r.stdout or FALLBACK_REPLY).strip().split("\t")[0])


def _alarm_reply(text):
    """Deterministic set/cancel before any LLM. None if not an alarm intent."""
    path = os.path.join(CAT_DIR, "cat-alarm.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("tangtang_alarm_chat", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.handle_utterance(text)


def _live_obs():
    path = os.path.join(CAT_DIR, "tangtang-speak-gate.py")
    spec = importlib.util.spec_from_file_location("tangtang_speak_gate_chat", path)
    if spec is None or spec.loader is None:
        return {"label": speaker_id(), "live": True}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.live_observation(speaker_id(), extra={"interactive": True})


def _may_speak_now(obs):
    """Quiet / school / SILENT → do not spawn V3 or V4 LLM."""
    root = os.path.abspath(os.path.join(CAT_DIR, "../.."))
    if root not in sys.path:
        sys.path.insert(0, root)
    from core.policy.speak_gate import decide, may_call_llm

    now = obs.get("now") if isinstance(obs.get("now"), datetime) else None
    return may_call_llm(decide(obs, now=now, channel="chat", live=True))


def emit_character_state(user_text, reply_text):
    """Chat reply → CharacterStateEngine (single truth) → presentation files.

    Only keyword-derived emotion/intent is used; the raw utterance is never
    stored or read back by this function. Failures stay silent (chat text
    already lives in stdout / cat-chat-history)."""
    root = os.path.abspath(os.path.join(CAT_DIR, "../.."))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from behavior.legacy_adapter import decide_from_legacy
        from core.presentation.character_presenter import CharacterPresenter
        from core.presentation.transport import write_presentation_action

        decision = decide_from_legacy("say", user_text or "")
        action = CharacterPresenter().present(decision, text=reply_text or "")
    except Exception:
        return
    for directory in (DATA_DIR, CAT_DIR):
        try:
            write_presentation_action(action, directory)
        except OSError:
            continue


def _infer_learn_tag(text):
    """Map chat turn to a habit tag. Never returns raw speech."""
    blob = (text or "").replace(" ", "")
    if any(k in blob for k in ("难过", "伤心", "害怕", "委屈", "哭")):
        return "emotion"
    if any(k in blob for k in ("作业", "考试", "题目")):
        return "homework"
    if any(k in blob for k in ("运动", "跑步", "出去玩")):
        return "exercise"
    if any(k in blob for k in ("回家", "我来了", "回来了")):
        return "home"
    if any(k in blob for k in ("晚安", "睡觉", "困了")):
        return "sleep"
    if any(k in blob for k in ("喝水", "口渴")):
        return "water"
    return "conversation"


def _learn_turn(user_text, *, event_tag=None, kind="care"):
    """m2/m3: persist emotion + habit tags; child raw → PrivateMemory only."""
    root = os.path.abspath(os.path.join(CAT_DIR, "../.."))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from core.memory.learning import LearningMemoryService
    except Exception:
        return None
    member_id, _display = _resolve_speaker_member()
    if not member_id:
        member_id = speaker_id() or "unknown"
    tag = event_tag or _infer_learn_tag(user_text)
    try:
        svc = LearningMemoryService(home=DATA_DIR, persist=True)
        return svc.on_interaction(
            member_id=member_id or "unknown",
            event_tag=tag,
            kind=kind,
            utterance=user_text or "",
        )
    except Exception:
        return None


RISK_LABELS = {
    "self_harm": "可能有自伤信号",
    "violence": "提到暴力或霸凌",
    "unsafe_contact": "疑似遇到不安全的接触",
    "secret_keep": "疑似被要求保守危险秘密",
}


def _resolve_speaker_member():
    """(member_id, display_name)。身份无法确定时返回 (None, None)。"""
    raw = speaker_id()
    if raw in ("unknown", "", "访客", "guest", "stranger"):
        return None, None
    root = os.path.abspath(os.path.join(CAT_DIR, "../.."))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from core.adapters.family_loader import load_members
        from core.identity.resolver import IdentityResolver

        members = load_members()
        resolver = IdentityResolver(members)
        mid = resolver.resolve({"label": raw})
        if not mid or str(mid).lower() in ("unknown", "访客", "guest"):
            return None, None
        rec = members.get(mid) or {}
        return mid, rec.get("display_name") or mid
    except Exception:
        return None, None


def _apple_escape(text):
    return (text or "").replace("\\", "\\\\").replace('"', '\\"')


def _mac_notify(title, message):
    """本机 macOS 通知。仅 darwin 推送，失败静默。"""
    if sys.platform != "darwin":
        return
    try:
        subprocess.Popen(
            ["/usr/bin/osascript", "-e",
             'display notification "%s" with title "%s"' % (
                 _apple_escape(message), _apple_escape(title))],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        return


def _notify_parent(category, member_id, display):
    who = display or member_id or "小朋友"
    label = RISK_LABELS.get(category, "需要家长关注")
    _mac_notify("糖糖 · 安全提醒", "%s：%s" % (who, label))


def _escalate_risk(text):
    """确定性分类 + 结构化落日志 + 本地家长通知。绝不记录儿童原话。"""
    root = os.path.abspath(os.path.join(CAT_DIR, "../.."))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from core.security.escalation import classify_risk, record_safety_alert
    except Exception:
        return None
    category = classify_risk(text)
    if not category:
        return None
    member_id, display = _resolve_speaker_member()
    row = record_safety_alert(category, member_id=member_id, home=DATA_DIR)
    _notify_parent(category, member_id, display)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?", default="", help="小朋友说的话")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    if not args.text.strip():
        args.text = "糖糖，我来啦"

    # 闹铃设/取消：本地解析 + JSON，LLM 不决定 crontab / TTS / 隐私。
    alarm_line = _alarm_reply(args.text)
    if alarm_line:
        print(alarm_line)
        return

    obs = _live_obs()
    if not _may_speak_now(obs):
        return

    # V3 CLI concatenates prompts from local JSON and can skip V4 PrivacyPolicy.
    # New path: ChatAdapter / TangTangRuntime (cannot skip the privacy gate).
    # Keep this CLI for the living-room Mac; set TANGTANG_V4_PIPELINE=1 to use V4.
    # V4 must not assemble the V3 persona prompt or history — one brain only.
    if os.environ.get("TANGTANG_V4_PIPELINE") == "1":
        root = os.path.abspath(os.path.join(CAT_DIR, "../.."))
        if root not in sys.path:
            sys.path.insert(0, root)
        from tangtang_runtime import TangTangRuntime

        result = TangTangRuntime().handle_utterance(args.text, obs)
        if result.decision != "SPEAK":
            return
        text = (result.action.text if result.action else "")
        if text:
            emit_character_state(args.text, text)
            _learn_turn(args.text, kind="care")
            print(text)
        return

    if looks_risky(args.text):
        _escalate_risk(args.text)
        emit_character_state(args.text, SAFE_REPLY)
        _learn_turn(args.text, event_tag="emotion", kind="care")
        print(SAFE_REPLY)
        return

    hist_name = speaker_id() if speaker_id() not in ("unknown", "", "访客") else "guest"
    hist_file = os.path.join(DATA_DIR, f"cat-chat-history-{hist_name}.json")
    # 兼容旧的单一历史文件：仅 guest 读取一次后不再混用
    legacy = os.path.join(DATA_DIR, "cat-chat-history.json")
    history = []
    if os.path.exists(hist_file):
        try:
            with open(hist_file, encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    elif hist_name == "guest" and os.path.exists(legacy):
        try:
            with open(legacy, encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    try:
        reply = chat(args.text, args.model, history)
    except Exception:
        reply = brain_fallback(args.text)

    history.append({"role": "user", "content": args.text})
    history.append({"role": "assistant", "content": reply})
    history = history[-20:]
    os.makedirs(os.path.dirname(hist_file) or ".", exist_ok=True)
    tmp = hist_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)
    os.replace(tmp, hist_file)

    emit_character_state(args.text, reply)
    _learn_turn(args.text, kind="care")
    print(reply)


if __name__ == "__main__":
    main()
