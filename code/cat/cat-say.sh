#!/bin/bash
# ============================================================
# 糖糖「晓晓」发声（微软神经语音 · 正式音色）
# 用法: ./cat-say.sh "想说的话" [mode]
#   mode: cute(默认, 晓晓温暖女声) / fast / soft / sys(系统嗓回退)
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

TEXT="${1:-汪汪}"
MODE="${2:-cute}"
TTS_MP3="/tmp/cat_tts.mp3"

speak_with_fallback() {
  local rate="$1"
  local pitch="$2"
  local baidu_spd="$3"
  local say_rate="$4"
  local say_pitch="${5:-118}"
  if /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$TEXT" "$rate" "$pitch" 2>/dev/null; then
    tangtang_play_audio "$TTS_MP3"
    return 0
  fi
  if node "$CAT_DIR/cat-tts-baidu.mjs" "$TEXT" "$baidu_spd" 2>/dev/null; then
    tangtang_play_audio "$TTS_MP3"
    return 0
  fi
  say -v Ting-Ting "[[rate ${say_rate}]][[pitch ${say_pitch}]]$TEXT"
}

case "$MODE" in
  sys)
    say -v Ting-Ting "[[rate 150]][[pitch 118]]$TEXT"
    ;;
  fast)
    speak_with_fallback 5 5 6 175 120
    ;;
  soft)
    speak_with_fallback -20 5 2 130 110
    ;;
  *)
    speak_with_fallback -10 5 4 150 118
    ;;
esac
exit 0
