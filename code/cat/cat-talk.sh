#!/bin/bash
# ============================================================
# 糖糖 · 智能说话（接大脑 + 情绪音色）
# 用法: ./cat-talk.sh <事件> [参数]
#   事件含: greet/wake/alarm/english/sleep/rest/meal/water/exercise/play/pet_walk/pet_water/pet_food/pet_groom ...
# 大脑决定话术+情绪 → 按情绪选音色 → 更新画面 → 出声
# 夜间主动提醒受统一 quiet-hours 闸门保护（22:30–07:00，speech_allowed=false）。
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

MOOD_FILE="$CAT_DIR/cat-mood.txt"

# 互动设/取消闹铃：在静默闸门和大脑之前。响铃本身走 cat-alarm.py → cat-say.sh。
if [ "${1:-}" = "say" ] && [ -n "${2:-}" ]; then
  alarm_line="$(/usr/bin/python3 "$CAT_DIR/cat-alarm.py" handle "$2" 2>/dev/null || true)"
  if [ -n "$alarm_line" ]; then
    echo "[idle] $alarm_line" > "$MOOD_FILE"
    echo "$alarm_line"
    if [ "${TANGTANG_TTS:-1}" != "0" ]; then
      "$CAT_DIR/cat-say.sh" "$alarm_line" cute
    fi
    exit 0
  fi
fi

if [ "${TANGTANG_INTERACTIVE:-0}" != "1" ]; then
  quiet="$(/usr/bin/python3 "$CAT_DIR/tangtang-quiet-hours.py" 2>/dev/null || echo speak)"
  if [ "$quiet" = "quiet" ]; then
    exit 0
  fi
fi

result="$(/usr/bin/python3 "$CAT_DIR/cat-brain.py" "$@")"
state="idle"
IFS=$'\t' read -r f1 f2 f3 <<< "$result"
if [ -z "$f2" ]; then
  text="$f1"; label="calm"
elif [ -z "$f3" ]; then
  text="$f1"; label="$f2"
else
  text="$f1"; label="$f2"; state="$f3"
fi

if [ -z "$text" ]; then
  exit 0
fi

echo "[$state] $text" > "$MOOD_FILE"
echo "$text"

if [ "${TANGTANG_TTS:-1}" = "0" ]; then
  exit 0
fi

# 英语小伴读与闹铃同一条出声路径（cat-say → 默认蓝牙音箱）。不另开音箱。
if [ "${1:-}" = "english" ]; then
  "$CAT_DIR/cat-say.sh" "$text" cute
  exit 0
fi

speak_with_fallback() {
  local rate="$1"
  local pitch="$2"
  local baidu_spd="$3"
  local say_rate="$4"
  local say_pitch="$5"
  if /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$text" "$rate" "$pitch" >/dev/null 2>&1; then
    tangtang_play_audio /tmp/cat_tts.mp3
    return 0
  fi
  if node "$CAT_DIR/cat-tts-baidu.mjs" "$text" "$baidu_spd" >/dev/null 2>&1; then
    tangtang_play_audio /tmp/cat_tts.mp3
    return 0
  fi
  say -v Ting-Ting "[[rate ${say_rate}]][[pitch ${say_pitch}]]$text"
}

case "$label" in
  happy)
    speak_with_fallback 5 8 6 175 120
    ;;
  sleepy)
    speak_with_fallback -20 3 2 130 110
    ;;
  lonely|low)
    speak_with_fallback -15 5 3 140 115
    ;;
  *)
    speak_with_fallback -10 5 4 150 118
    ;;
esac
exit 0
