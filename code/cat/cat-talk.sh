#!/bin/bash
# ============================================================
# 糖糖 · 智能说话（接大脑 + 情绪音色）
# 用法: ./cat-talk.sh <事件> [参数]
# 大脑决定话术+情绪 → 按情绪选音色 → 更新画面 → 出声
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

MOOD_FILE="$CAT_DIR/cat-mood.txt"

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
