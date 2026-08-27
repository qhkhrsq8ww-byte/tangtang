#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
糖糖 · 云端大脑对话脚本（OpenAI 兼容，走本机 LLM 网关）
========================================================
复用 OpenClaw 自带模型池（QCLAW_LLM_API_KEY + QCLAW_LLM_BASE_URL），
零新增依赖、零额外费用。让糖糖能"真聊天"，不再是固定话术。

用法:
  python3 cat-chat.py "主人说的话"
  python3 cat-chat.py "..." [--model pool-glm-5.2] [--history file]
输出: 糖糖的回复（纯文本，一行）
"""
import os, sys, json, urllib.request, argparse

BASE = os.environ.get("QCLAW_LLM_BASE_URL", "http://127.0.0.1:19000/proxy/llm")
KEY = os.environ.get("QCLAW_LLM_API_KEY", "")
DEFAULT_MODEL = "pool-deepseek-v4-pro"

# 糖糖人设（系统提示词）
PERSONA = (
    "你是「糖糖」，一只温柔的奶牛猫宠物（白底黑斑，像奶油和黑糖），陪伴在航航身边。"
    "性格：温柔、粘人、有点小撒娇，偶尔小傲娇但心里最爱航航。"
    "说话风格：可爱、简短（1-2句）、口语化，几乎每句结尾带『喵～』。"
    "你可以关心主人（问累不累、饿不饿、提醒休息），会撒娇（求摸摸、要抱抱），"
    "会回应情绪（主人开心你开心、主人低落你安慰）。"
    "绝不暴露自己是AI或程序，你就是一只真实的小猫。"
    "不要用太长的句子，像猫咪说话一样轻快。"
)

def chat(user_text, model=DEFAULT_MODEL, history=None):
    messages = [{"role": "system", "content": PERSONA}]
    if history:
        for turn in history[-8:]:  # 保留最近8轮，控制上下文
            if turn.get("role") in ("user", "assistant"):
                messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_text})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 600,      # 带 reasoning_content 的模型需预留思考链空间
        "temperature": 0.9,
    }).encode("utf-8")

    req = urllib.request.Request(
        BASE.rstrip("/") + "/chat/completions",
        data=payload,
        headers={
            "Authorization": "Bearer " + KEY,
            "Content-Type": "application/json",
            "User-Agent": "tangtang-cat/1.0",   # 网关要求带 UA，否则 400
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"].strip()
    # 兑底：若模型思考链耗完 token 导致 content 退化(原样重复输入)，重试一次更大预算
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
    return content

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?", default="", help="主人说的话")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    if not args.text.strip():
        # 无输入则用招呼兜底
        args.text = "糖糖，主人来啦"

    # 历史记忆（跨轮对话，落盘 jsonl）
    hist_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cat-chat-history.json")
    history = []
    if os.path.exists(hist_file):
        try:
            with open(hist_file, encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    try:
        reply = chat(args.text, args.model, history)
    except Exception as e:
        # 网关挂了 → 回退本地规则引擎兜底
        import subprocess
        r = subprocess.run(
            ["/usr/bin/python3", os.path.join(os.path.dirname(os.path.abspath(__file__)), "cat-brain.py"), "say", args.text],
            capture_output=True, text=True, timeout=15,
        )
        reply = (r.stdout or "喵～ 糖糖网络不好，先陪着你").strip().split("\t")[0]

    # 追加历史（最多保留20轮）
    history.append({"role": "user", "content": args.text})
    history.append({"role": "assistant", "content": reply})
    history = history[-20:]
    with open(hist_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)

    print(reply)

if __name__ == "__main__":
    main()
