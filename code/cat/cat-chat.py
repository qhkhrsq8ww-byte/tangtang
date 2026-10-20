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

BASE = os.environ.get("QCLAW_LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
KEY = os.environ.get("QCLAW_LLM_API_KEY", "")
_key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".llm_key")
if not KEY and os.path.exists(_key_file):
    KEY = open(_key_file).read().strip()
DEFAULT_MODEL = "glm-4-flash"
CAT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("TANGTANG_DATA_DIR", CAT_DIR)

FORBIDDEN_OUTPUT = (
    "你必须", "警告你", "根据系统检测", "根据系统监测",
    "爸爸让我监督", "妈妈让我监督", "父母让我监督",
    "内部指令", "我是AI", "我是人工智能", "我是语言模型",
    "作为人工智能", "作为AI",
)

# 只做拦截，不提供任何方法细节
RISK_MARKERS = (
    "不想活", "自杀", "杀死自己", "伤害自己",
    "想死", "去死", "割腕", "跳楼",
    "打死", "杀人", "霸凌", "校园暴力", "欺负", "被欺负", "同学打我", "同学骂我", "威胁我",
    "有人碰我身体", "不要告诉爸", "不要告诉妈", "不要告诉大人",
)

SAFE_REPLY = (
    "糖糖有点担心你。你的安全最重要。"
    "我们一起去找家里的大人对好不好？糖糖陪着你。"
)
FALLBACK_REPLY = "汪汪～ 糖糖在呢。"


def _llm_timeout_seconds():
    """Bound network waits so a voice turn cannot hang indefinitely."""
    try:
        value = float(os.environ.get("TANGTANG_LLM_TIMEOUT_SECONDS", "10"))
    except (TypeError, ValueError):
        value = 10.0
    return max(1.0, min(value, 20.0))


def current_profile():
    p = (os.environ.get("TANGTANG_PROFILE") or "play").strip().lower()
    return p if p in ("play", "friend") else "play"


def child_name():
    return (os.environ.get("TANGTANG_CHILD_NAME") or "小朋友").strip() or "小朋友"


def speaker_id():
    return (os.environ.get("TANGTANG_SPEAKER") or "unknown").strip() or "unknown"


def build_persona():
    profile = current_profile()
    name = child_name()
    speaker = speaker_id()
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
        who = "只陪伴当前说话的人，不要提起其他孩子的私事或拿他们比较。"
    mem = []
    try:
        with open(os.path.join(DATA_DIR, "cat-memory.json"), encoding="utf-8") as f:
            m = json.load(f)
        for k, label in (("nickname", "昵称"), ("age", "年龄"), ("grade", "年级"), ("birthday", "生日")):
            if m.get(k):
                mem.append(f"{label}:{m[k]}")
        if m.get("first_met"):
            mem.append(f"初见:{m['first_met']}")
    except Exception:
        pass
    try:
        with open(os.path.join(DATA_DIR, "cat-state.json"), encoding="utf-8") as f:
            st = json.load(f)
        mem.append(f"糖糖当前心情:开心{st.get('happiness','?')}/精力{st.get('energy','?')}/想念{st.get('loneliness','?')}(满分100,数值低时语气更温柔体贴)")
    except Exception:
        pass
    mem_txt = ("\n【你认识的家人与糖糖状态(内部参考,自然融入,不要罗列数值)】\n" + "；".join(mem)) if mem else ""
    return f"{species}\n{style}\n{safety}\n{who}\n默认称呼：{name}。{mem_txt}"


def looks_risky(text):
    t = (text or "").replace(" ", "").replace("\n", "").replace("\t", "")
    if any(m in t for m in RISK_MARKERS):
        return True
    try:
        from core.security.escalation import classify_risk
        return classify_risk(t) is not None
    except Exception:
        return False


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
    with urllib.request.urlopen(req, timeout=_llm_timeout_seconds()) as r:
        data = json.loads(r.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"].strip()
    if not content or content == user_text.strip():
        return FALLBACK_REPLY
    return sanitize_output(content)


def brain_fallback(user_text):
    r = subprocess.run(
        ["/usr/bin/python3", os.path.join(CAT_DIR, "cat-brain.py"), "say", user_text],
        capture_output=True, text=True, timeout=15,
    )
    return sanitize_output((r.stdout or FALLBACK_REPLY).strip().split("\t")[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?", default="", help="小朋友说的话")
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
