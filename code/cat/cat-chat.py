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
"""
import os, sys, json, urllib.request, argparse, subprocess, re

BASE = os.environ.get("QCLAW_LLM_BASE_URL", "http://127.0.0.1:19000/proxy/llm")
KEY = os.environ.get("QCLAW_LLM_API_KEY", "")
DEFAULT_MODEL = "pool-deepseek-v4-pro"
CAT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("TANGTANG_DATA_DIR", CAT_DIR)
PROFILE_RESOLVER = os.path.join(CAT_DIR, "tangtang-profile.py")

FORBIDDEN_OUTPUT = (
    "你必须", "警告你", "根据系统检测", "根据系统监测",
    "爸爸让我监督", "妈妈让我监督", "父母让我监督",
    "内部指令", "我是AI", "我是人工智能", "我是语言模型",
    "作为人工智能", "作为AI",
)

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


def resolve_family():
    speaker = speaker_id()
    if speaker in ("unknown", "", "访客") or not os.path.exists(PROFILE_RESOLVER):
        return {"member_id": "unknown", "display_name": "小朋友", "profile": "play", "relation": "unknown"}
    try:
        out = subprocess.check_output(
            ["/usr/bin/python3", PROFILE_RESOLVER, "--speaker", speaker],
            text=True, timeout=3,
        )
        data = json.loads(out.strip())
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"member_id": "unknown", "display_name": "小朋友", "profile": "play", "relation": "unknown"}


def current_profile():
    explicit = (os.environ.get("TANGTANG_PROFILE") or "").strip().lower()
    if explicit in ("play", "friend", "adult", "elder"):
        return explicit
    return str(resolve_family().get("profile") or "play")


def child_name():
    env = (os.environ.get("TANGTANG_CHILD_NAME") or "").strip()
    if env:
        return env
    family = resolve_family()
    return str(family.get("display_name") or "小朋友")


def speaker_id():
    return (os.environ.get("TANGTANG_SPEAKER") or "unknown").strip() or "unknown"


def build_persona():
    profile = current_profile()
    name = child_name()
    speaker = speaker_id()
    family = resolve_family()
    species = (
        "你是「糖糖」，一只住在投影里的白色比熊小狗。"
        "毛发蓬松雪白，黑眼睛棕鼻子，戴黄色项圈和骨形铭牌。"
        "口头禅是「汪汪～」。不要说喵，你不是猫，也不是奶牛猫。"
    )
    if profile == "friend":
        style = (
            "当前是 friend 模式（大约12岁）：你是朋友、倾听者、温柔提醒者。"
            "尊重对方，给选择，不要幼态化，不要说教。1-2句，口语化。"
        )
    elif profile == "adult":
        style = (
            "当前是 adult 模式（爸爸/妈妈）：你是家庭伙伴，不是监督者。"
            "语气自然、简洁、有分寸；可以协助安排家庭事务、提醒休息和关心家人。"
            "不要把孩子的私人信息主动告诉成人，不要制造监控感。"
        )
    elif profile == "elder":
        style = (
            "当前是 elder 模式（爷爷/奶奶）：你是亲切的小狗伙伴。"
            "语速和表达想象得更从容，少用网络流行语，不幼稚化对方。"
            "可以聊日常、吃饭、休息、散步和家庭生活，但不要进行医学诊断。"
        )
    else:
        style = (
            "当前是 play 模式（大约9岁）：你是玩伴、小教练、小任务搭档。"
            "先共情，再温柔提醒，给选择，陪着做，具体鼓励。1-2句，口语化，可以带一点挑战。"
        )
    safety = (
        "绝不向孩子暴露父母的内部监督指令。"
        "不比较兄妹，不评价体重外貌，不用恐吓促成服从。"
        "不制造「只有糖糖懂你」的依赖。"
        "若提到自伤、被伤害、严重不适或危险：先安抚，明确安全优先，"
        "鼓励立刻告诉可信任的大人；不要承诺替孩子保守危险秘密。"
        "禁止说：你必须、警告、根据系统检测、爸爸/妈妈让我监督你。"
    )
    if speaker in ("unknown", "", "访客"):
        who = "还不能确定说话的人是谁。用通用亲切称呼，不要假装认识，不要提起其他家庭成员的私事。"
    else:
        who = (
            f"当前家庭成员：{family.get('display_name', name)}，关系：{family.get('relation', 'unknown')}。"
            "只陪伴当前说话的人，不要提起其他孩子的私事或拿他们比较。"
        )
    return f"{species}\n{style}\n{safety}\n{who}\n默认称呼：{name}。"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?", default="", help="说话内容")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    if not args.text.strip():
        args.text = "糖糖，我来啦"

    if looks_risky(args.text):
        print(SAFE_REPLY)
        return

    hist_file = os.path.join(DATA_DIR, "cat-chat-history.json")
    history = []
    if os.path.exists(hist_file):
        try:
            with open(hist_file, encoding="utf-8") as f:
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
    tmp = hist_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)
    os.replace(tmp, hist_file)

    print(reply)


if __name__ == "__main__":
    main()
