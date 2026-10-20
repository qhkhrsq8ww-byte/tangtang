#!/bin/bash
# 糖糖发声：串行输出，任何最终播放失败均返回非零状态
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

TEXT="${1:-汪汪}"
MODE="${2:-cute}"
TTS_MP3="/tmp/cat_tts.mp3"
rm -f "$TTS_MP3"
tangtang_tts_lock || exit $?
trap 'rm -f "$TTS_MP3"' EXIT

play_generated() {
  tangtang_play_audio "$TTS_MP3"
}

speak_with_fallback() {
  local rate="$1"
  local pitch="$2"
  local baidu_spd="$3"
  local say_rate="$4"
  local say_pitch="${5:-118}"
  if /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$TEXT" "$rate" "$pitch" 2>/dev/null && [ -s "$TTS_MP3" ]; then
    play_generated
    return $?
  fi
  rm -f "$TTS_MP3"
  if node "$CAT_DIR/cat-tts-baidu.mjs" "$TEXT" "$baidu_spd" 2>/dev/null && [ -s "$TTS_MP3" ]; then
    play_generated
    return $?
  fi
  rm -f "$TTS_MP3"
  say -v Ting-Ting "[[rate ${say_rate}]][[pitch ${say_pitch}]]$TEXT"
  return $?
}

case "$MODE" in
  sys)
    say -v Ting-Ting "[[rate 150]][[pitch 118]]$TEXT"
    exit $?
    ;;
  fast) speak_with_fallback 5 5 6 175 120; exit $? ;;
  soft) speak_with_fallback -20 5 2 130 110; exit $? ;;
  *) speak_with_fallback -10 5 4 150 118; exit $? ;;
esac
