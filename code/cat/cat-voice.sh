#!/bin/bash
# 糖糖 · 语音对话 v3
# 链路：听 → 在场（WiFi/ARP，必要时短窗能量）→ 辨 → 记习惯 → 懂 → 答 → 说
# 时刻表不要接本脚本（先录满再 LLM）。客厅短回合请用 cat-turn.sh：
# 先看作息再开麦；声纹不当主路径；只在客厅；沉默不追问。
# 声纹/习惯数据仅写入本地，不提交 Git。不给小朋友建声纹。
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"
# 客厅生产对话走 V4 PrivacyPolicy / TangTangRuntime（LLM 不决定隐私）
export TANGTANG_V4_PIPELINE=1

DUR="${1:-5}"
PCM="/tmp/tangtang_voice.pcm"
# 显式 MEMBER_ID / -p 指定的人不被在场层覆盖
EXPLICIT_MEMBER="${TANGTANG_MEMBER_ID:-${TANGTANG_SPEAKER:-}}"

# 已知必须静默（夜间 / 指定孩子还在上学）时不开麦、不 STT、不 LLM
GATE_MEMBER=""
if [ -n "$EXPLICIT_MEMBER" ] && [ "$EXPLICIT_MEMBER" != "unknown" ]; then
  GATE_MEMBER="$EXPLICIT_MEMBER"
fi
if [ "$(/usr/bin/python3 "$CAT_DIR/tangtang-speak-gate.py" --channel voice --member "$GATE_MEMBER")" != "speak" ]; then
  exit 0
fi

echo "🎤 糖糖在听...（${DUR}秒）"
if ! "$CAT_DIR/cat-listen.sh" "$DUR" "$PCM" >/dev/null 2>&1; then
  echo "❌ 麦克风录音失败"
  exit 1
fi

MEMBER_ID="unknown"
DISPLAY=""
PROFILE="play"
SCORE=""

if [ -n "$EXPLICIT_MEMBER" ] && [ "$EXPLICIT_MEMBER" != "unknown" ]; then
  WHO_LINE=$(/usr/bin/python3 "$CAT_DIR/cat-family.py" resolve "$EXPLICIT_MEMBER" 2>/dev/null | tail -1)
  IFS=$'\t' read -r MEMBER_ID DISPLAY PROFILE <<< "$WHO_LINE"
  MEMBER_ID="${MEMBER_ID:-$EXPLICIT_MEMBER}"
  PROFILE="${PROFILE:-play}"
  echo "👤 指定: ${DISPLAY:-$MEMBER_ID}（${PROFILE}）"
else
  # 未指定时：WiFi/ARP 只在恰好一名可互动成人时认人；多个手机不猜；不自动对小朋友开口
  SUGGEST=$(/usr/bin/python3 "$CAT_DIR/cat-presence.py" suggest --clip "$PCM" 2>/dev/null | tail -1)
  SUGGEST="${SUGGEST:-unknown}"
  if [ -n "$SUGGEST" ] && [ "$SUGGEST" != "unknown" ]; then
    WHO_LINE=$(/usr/bin/python3 "$CAT_DIR/cat-family.py" resolve "$SUGGEST" 2>/dev/null | tail -1)
    IFS=$'\t' read -r MEMBER_ID DISPLAY PROFILE <<< "$WHO_LINE"
    MEMBER_ID="${MEMBER_ID:-$SUGGEST}"
    PROFILE="${PROFILE:-play}"
    echo "👤 在场: ${DISPLAY:-$MEMBER_ID}（${PROFILE}）"
  else
    WHO_LINE=$(/usr/bin/python3 "$CAT_DIR/cat-family.py" who "$PCM" 2>/dev/null | tail -1)
    IFS=$'\t' read -r MEMBER_ID DISPLAY PROFILE SCORE <<< "$WHO_LINE"
  fi
fi
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
  if [ -n "${SCORE:-}" ]; then
    echo "👤 识别: ${DISPLAY}（${PROFILE}，置信 ${SCORE}）"
  fi
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
  # 没听清：不追问、不开第二轮
  rm -f "$PCM"
  exit 0
fi

echo "   你说: $TEXT"
# 闹铃设/取消在 LLM 之前：本地解析，固定汪汪回复。不把原话当习惯。
ALARM_LINE=$(/usr/bin/python3 "$CAT_DIR/cat-alarm.py" handle "$TEXT" 2>/dev/null || true)
if [ -n "$ALARM_LINE" ]; then
  echo "   糖糖: $ALARM_LINE"
  printf '%s\n' "[idle] $ALARM_LINE" > "$CAT_DIR/cat-mood.txt"
  "$CAT_DIR/cat-say.sh" "$ALARM_LINE" cute
  rm -f "$PCM"
  exit 0
fi

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
  rm -f "$PCM"
  exit 0
fi

echo "   糖糖: $REPLY"
# 情绪状态已由 cat-chat.py 经 CharacterStateEngine 写入 cat-presentation-action.json / cat-mood.txt
"$CAT_DIR/cat-say.sh" "$REPLY" cute
rm -f "$PCM"
