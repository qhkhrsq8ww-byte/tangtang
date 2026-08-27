#!/bin/bash
# ============================================================
# 糖糖「晓晓」发声（微软神经语音 · 正式音色）
# 用法: ./cat-say.sh "想说的话" [mode]
#   mode: cute(默认, 晓晓温暖女声) / fast / soft / sys(系统嗓回退)
# 声音优先走系统默认输出（小米蓝牙音箱 XMFHZ02）
# ============================================================
TEXT="${1:-汪汪}"
MODE="${2:-cute}"
CAT_DIR="/Users/lv/.qclaw/workspace/cat"
TTS_MP3="/tmp/cat_tts.mp3"

# 播放函数：afplay 走系统默认输出，超时保护防蓝牙挂死
play_audio() {
  local f="$1"
  [ -f "$f" ] || return 1
  afplay "$f" >/dev/null 2>&1 &
  local ap_pid=$!
  local waited=0
  while kill -0 "$ap_pid" 2>/dev/null; do
    sleep 0.3
    waited=$((waited+3))
    [ "$waited" -ge 120 ] && { kill -9 "$ap_pid" 2>/dev/null; break; }
  done
  wait "$ap_pid" 2>/dev/null
  return 0
}

case "$MODE" in
  sys)
    # 系统嗓（纯离线，机械但绝不失败）
    say -v Ting-Ting "[[rate 150]][[pitch 118]]$TEXT"
    ;;
  fast)
    # 晓晓 + 快语速（开心/正常播报）
    if /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$TEXT" 5 5 2>/dev/null; then
      play_audio "$TTS_MP3"
    else
      node "$CAT_DIR/cat-tts-baidu.mjs" "$TEXT" 6 2>/dev/null && play_audio "$TTS_MP3" || say -v Ting-Ting "[[rate 175]]$TEXT"
    fi
    ;;
  soft)
    # 晓晓 + 慢柔（困了/睡前/想念时）
    if /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$TEXT" -20 5 2>/dev/null; then
      play_audio "$TTS_MP3"
    else
      node "$CAT_DIR/cat-tts-baidu.mjs" "$TEXT" 2 2>/dev/null && play_audio "$TTS_MP3" || say -v Ting-Ting "[[rate 130]][[pitch 110]]$TEXT"
    fi
    ;;
  *)
    # cute 默认：晓晓温暖女声（语速 -10%，音高 +5Hz，声音标准）
    if /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$TEXT" -10 5 2>/dev/null; then
      play_audio "$TTS_MP3"
    else
      # 回退链：百度翻译 TTS → 系统嗓
      node "$CAT_DIR/cat-tts-baidu.mjs" "$TEXT" 4 2>/dev/null && play_audio "$TTS_MP3" || say -v Ting-Ting "[[rate 150]][[pitch 118]]$TEXT"
    fi
    ;;
esac
exit 0
