#!/bin/bash
# 糖糖 · 语音对话 v3
# 链路：听 → 辨（五口之家）→ 记习惯 → 懂 → 答 → 说
# 时刻表不要接本脚本（先录满再声纹再 LLM）。客厅短回合请用 cat-turn.sh：
# 先看作息再开麦，不先声纹；只在客厅；沉默不追问。
# 声纹/习惯数据仅写入本地，不提交 Git。
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

DUR="${1:-5}"
PCM="/tmp/tangtang_voice.pcm"

echo "🎤 糖糖在听...（${DUR}秒）"
if ! "$CAT_DIR/cat-listen.sh" "$DUR" "$PCM" >/dev/null 2>&1; then
  echo "❌ 麦克风录音失败"
  exit 1
fi

WHO_LINE=$(/usr/bin/python3 "$CAT_DIR/cat-family.py" who "$PCM" 2>/dev/null | tail -1)
IFS=$'\t' read -r MEMBER_ID DISPLAY PROFILE SCORE <<< "$WHO_LINE"
MEMBER_ID="${MEMBER_ID:-unknown}"
PROFILE="${PROFILE:-play}"
case "$PROFILE" in
  play|friend|adult|elder) ;;
  *) PROFILE="play" ;;
esac

if [ "$MEMBER_ID" = "unknown" ] || [ -z "$MEMBER_ID" ]; then
  echo "👤 识别状态: 未确定（不绑定家人）"
  MEMBER_ID="unknown"
  DISPLAY=""
  export TANGTANG_SPEAKER="unknown"
  export TANGTANG_MEMBER_ID="unknown"
  if tangtang_is_school_day && tangtang_child_at_school hanghang && tangtang_child_at_school qiaqia; then
    PROFILE="elder"
    export TANGTANG_CHILD_NAME="爷爷奶奶"
  else
    export TANGTANG_CHILD_NAME="${TANGTANG_CHILD_NAME:-小朋友}"
  fi
  export TANGTANG_PROFILE="$PROFILE"
else
  echo "👤 识别: ${DISPLAY}（${PROFILE}，置信 ${SCORE}）"
  if tangtang_child_at_school "$MEMBER_ID"; then
    echo "[糖糖] 上学期间不跟${DISPLAY}互动（按作息还没到家）"
    rm -f "$PCM"
    exit 0
  fi
  export TANGTANG_SPEAKER="$MEMBER_ID"
  export TANGTANG_MEMBER_ID="$MEMBER_ID"
  export TANGTANG_PROFILE="$PROFILE"
  export TANGTANG_CHILD_NAME="$DISPLAY"
fi

echo "🧠 识别中..."
TEXT=$("$CAT_DIR/cat-stt-baidu.sh" "$PCM" 2>/dev/null | tr -d '\n')
if [ -z "$TEXT" ]; then
  "$CAT_DIR/cat-say.sh" "没听清，再说一次好不好？" cute
  rm -f "$PCM"
  exit 0
fi

echo "   你说: $TEXT"
if [ "$MEMBER_ID" != "unknown" ]; then
  /usr/bin/python3 "$CAT_DIR/cat-family.py" observe "$MEMBER_ID" "$TEXT" >/dev/null 2>&1 || true
else
  /usr/bin/python3 "$CAT_DIR/cat-family.py" observe "unknown" "" >/dev/null 2>&1 || true
fi

echo "💬 糖糖思考中..."
REPLY=$(TANGTANG_PROFILE="$TANGTANG_PROFILE" \
  TANGTANG_SPEAKER="$TANGTANG_SPEAKER" \
  TANGTANG_MEMBER_ID="$TANGTANG_MEMBER_ID" \
  TANGTANG_CHILD_NAME="$TANGTANG_CHILD_NAME" \
  /usr/bin/python3 "$CAT_DIR/cat-chat.py" "$TEXT" 2>/dev/null | tr -d '\n')
if [ -z "$REPLY" ]; then
  REPLY="糖糖刚才有点走神啦，我们再聊聊？"
fi

echo "   糖糖: $REPLY"
printf '%s\n' "[idle] $REPLY" > "$CAT_DIR/cat-mood.txt"
"$CAT_DIR/cat-say.sh" "$REPLY" cute
rm -f "$PCM"
