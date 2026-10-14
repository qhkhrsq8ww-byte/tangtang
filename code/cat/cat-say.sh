#!/bin/bash
# ============================================================
# 糖糖「晓晓」发声（微软神经语音 · 正式音色）
# 客厅互动时音箱应作为 Mac 默认输出；若音箱仍在儿童房，客厅听不见糖糖回话。
# 不要做第二只音箱。
# 用法: ./cat-say.sh "想说的话" [mode]
#   mode: cute(默认, 晓晓温暖女声) / fast / soft / sys(系统嗓); 百度回退需显式开启
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

TEXT="${1:-汪汪}"
MODE="${2:-cute}"
TTS_MP3="/tmp/cat_tts.mp3"

if [ "${TANGTANG_TTS:-1}" = "0" ]; then
  echo "[tts-dry] $TEXT"
  exit 0
fi
if [ "${TANGTANG_TTS}" = "dry" ] || [ "$(uname -s)" != "Darwin" ]; then
  echo "[tts-dry] $TEXT"
  exit 0
fi

speak_with_fallback() {
  local rate="$1"
  local pitch="$2"
  local baidu_spd="$3"
  local say_rate="$4"
  local say_pitch="${5:-118}"

  # Do not accidentally play a previous turn's audio after a TTS failure.
  rm -f "$TTS_MP3"
  if /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$TEXT" "$rate" "$pitch" 2>/dev/null \
      && [ -s "$TTS_MP3" ]; then
    tangtang_play_audio "$TTS_MP3"
    return 0
  fi

  # Baidu's timbre differs noticeably. Keep it opt-in instead of silently
  # changing TangTang's voice mid-conversation.
  if [ "${TANGTANG_TTS_ALLOW_BAIDU_FALLBACK:-0}" = "1" ]; then
    rm -f "$TTS_MP3"
    if node "$CAT_DIR/cat-tts-baidu.mjs" "$TEXT" "$baidu_spd" 2>/dev/null \
        && [ -s "$TTS_MP3" ]; then
      tangtang_play_audio "$TTS_MP3"
      return 0
    fi
  fi

  echo "[tts] Edge TTS unavailable; using macOS Ting-Ting fallback." >&2
  say -v Ting-Ting "[[rate ${say_rate}]][[pitch ${say_pitch}]]$TEXT"
}

case "$MODE" in
  sys)
    say -v Ting-Ting "[[rate 150]][[pitch 118]]$TEXT"
    ;;
  fast)
    speak_with_fallback 3 0 5 165 118
    ;;
  soft)
    speak_with_fallback -12 0 3 140 118
    ;;
  *)
    speak_with_fallback -5 0 4 150 118
    ;;
esac
exit 0
