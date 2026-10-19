#!/bin/bash
# ============================================================
# 糖糖 · 全语音对话循环（听 → 识别 → 云端大脑 → 开口）
# 用法: ./cat-talk.sh [最大轮数=30]
# 退出: 连续 2 轮没听到话 / 说"到此为止" / Ctrl-C
# 麦克风: cat-listen.sh 的 MAONO AU-BM10 (:2)
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

MAX_ROUNDS="${1:-30}"
SILENCE_LIMIT=2
silence=0
round=0

trap 'echo "[talk] 再见，糖糖先去玩啦"; exit 0' INT TERM

echo "[talk] 语音对话开始（最多 $MAX_ROUNDS 轮，Ctrl-C 退出）"
"$SCRIPT_DIR/cat-say.sh" "汪汪～糖糖在听，你想聊什么呀？" cute

while [ "$round" -lt "$MAX_ROUNDS" ]; do
  round=$((round+1))
  # 1) 听 6 秒
  "$SCRIPT_DIR/cat-listen.sh" 6 >/dev/null 2>&1
  PCM=/tmp/cat_voice.pcm
  [ -s "$PCM" ] || { silence=$((silence+1)); [ "$silence" -ge "$SILENCE_LIMIT" ] && break; continue; }

  # 2) 识别（脚本会消费 pcm 文件）
  TEXT=$("$SCRIPT_DIR/cat-stt-baidu.sh" "$PCM" 2>/dev/null | tail -1)
  [ -z "$TEXT" ] && { silence=$((silence+1)); [ "$silence" -ge "$SILENCE_LIMIT" ] && break; continue; }
  case "$TEXT" in
    *到此为止*|*别说了*|*休息吧*)
      "$SCRIPT_DIR/cat-say.sh" "汪汪～好的，糖糖先去玩啦，想我了随时叫我！" cute
      break;;
  esac
  silence=0
  echo "[talk] 航航: $TEXT"

  # 3) 云端大脑
  REPLY=$("/usr/bin/python3" "$SCRIPT_DIR/cat-chat.py" "$TEXT" 2>/dev/null)
  [ -z "$REPLY" ] && REPLY="汪汪～ 糖糖在呢。"

  # 4) 开口
  echo "[talk] 糖糖: $REPLY"
  "$SCRIPT_DIR/cat-say.sh" "$REPLY" cute
done

echo "[talk] 对话结束，共 $round 轮"
