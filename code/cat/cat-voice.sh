#!/bin/bash
# 糖糖 · 语音对话：听 → 辨 → 懂 → 答 → 说
set -u -o pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

DUR="${1:-5}"
PCM="$SCRIPT_DIR/voice_tmp.pcm"
trap 'rm -f "$PCM"' EXIT
MEMBER_ID="unknown"
PROFILE="${TANGTANG_PROFILE:-play}"
case "$PROFILE" in play|friend) ;; *) PROFILE="play" ;; esac
export TANGTANG_PROFILE="$PROFILE"
export TANGTANG_V4_PIPELINE=1
EXPLICIT_MEMBER="${TANGTANG_MEMBER_ID:-}"

GATE="$("$CAT_DIR/tangtang-speak-gate.py" --channel voice --member "${TANGTANG_SPEAKER:-unknown}" 2>/dev/null || true)"
if [ "$GATE" != "speak" ]; then
  exit 0
fi

echo "🎤 糖糖在听...（${DUR}秒，${PROFILE}模式）"
if ! "$CAT_DIR/cat-listen.sh" "$DUR" "$PCM" >/dev/null 2>&1; then
  echo "❌ 麦克风录音失败" >&2
  exit 1
fi

WHO="$("$CAT_DIR/cat-vp.py" identify "$PCM" 2>/dev/null | tail -1)"
[ -n "$WHO" ] || WHO="unknown"
MEMBER_ID="$WHO"
# Presence may suggest a registered adult only; it never assigns an unknown voice to a child.
SUGGESTED_MEMBER="$(/usr/bin/python3 "$CAT_DIR/cat-presence.py" suggest --explicit "$EXPLICIT_MEMBER" --clip "$PCM" --no-probe --no-log 2>/dev/null || echo unknown)"
if [ "$WHO" = "unknown" ] && [ "$SUGGESTED_MEMBER" != "unknown" ]; then
  WHO="$SUGGESTED_MEMBER"
  MEMBER_ID="$WHO"
fi
echo "👤 识别状态: $WHO"

echo "🧠 识别中..."
set +e
TEXT="$(set -o pipefail; "$CAT_DIR/cat-stt-baidu.sh" "$PCM" 2>/dev/null | tr -d '\n')"
stt_status=$?
set -e
if [ "$stt_status" -ne 0 ]; then
  echo "语音识别进程失败（状态码 $stt_status）" >&2
  exit "$stt_status"
fi
if [ -z "$TEXT" ]; then
  echo "语音识别没有得到有效文本" >&2
  exit 1
fi

echo "   你说: $TEXT"
if [ "$WHO" != "unknown" ]; then
  "$CAT_DIR/cat-vp.py" log "$WHO" "$TEXT" >/dev/null 2>&1 || true
else
  "$CAT_DIR/cat-vp.py" log "unknown" "" >/dev/null 2>&1 || true
fi
# Family memory CLI records only policy-approved, derived signals; child raw speech is excluded there.
"$CAT_DIR/cat-family.py" observe "$WHO" "$TEXT" >/dev/null 2>&1 || true

# 闹铃意图由本地确定性解析处理，不进入普通 LLM。
ALARM_LINE="$(/usr/bin/python3 "$CAT_DIR/cat-alarm.py" parse "$TEXT" 2>/dev/null || true)"
if [ -n "$ALARM_LINE" ]; then
  echo "   糖糖: $ALARM_LINE"
  set +e
  "$CAT_DIR/cat-say.sh" "$ALARM_LINE" cute
  say_status=$?
  set -e
  if [ "$say_status" -ne 0 ]; then
    echo "闹铃回复语音播放失败" >&2
    exit "$say_status"
  fi
  rm -f "$PCM"
  exit 0
fi

echo "💬 糖糖思考中..."
set +e
REPLY="$(TANGTANG_PROFILE="$PROFILE" TANGTANG_SPEAKER="$WHO" /usr/bin/python3 "$CAT_DIR/cat-chat.py" "$TEXT" 2>/dev/null)"
chat_status=$?
set -e
if [ "$chat_status" -ne 0 ]; then
  echo "糖糖对话进程失败（状态码 $chat_status）" >&2
  exit "$chat_status"
fi
if [ -z "$REPLY" ]; then
  echo "糖糖对话返回空内容" >&2
  exit 1
fi

echo "   糖糖: $REPLY"
printf '%s\n' "[idle] $REPLY" > "$CAT_DIR/cat-mood.txt"
set +e
"$CAT_DIR/cat-say.sh" "$REPLY" cute
say_status=$?
set -e
if [ "$say_status" -ne 0 ]; then
  echo "糖糖回复语音播放失败" >&2
  exit "$say_status"
fi
exit 0
