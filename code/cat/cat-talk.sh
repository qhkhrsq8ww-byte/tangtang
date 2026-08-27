#!/bin/bash
# ============================================================
# 糖糖 · 智能说话（接大脑 + 情绪音色）
# 用法: ./cat-talk.sh <事件> [参数]
#   事件: greet/wake/sleep/rest/meal/pat/home/random/say/status/play/homework/tidy/exercise/emotion/weather/water
#   示例: ./cat-talk.sh greet
#         ./cat-talk.sh say "今天天气真好"
#         ./cat-talk.sh meal lunch
# 大脑决定话术+情绪 → 按情绪选音色 → 更新画面 → 出声
# ============================================================
CAT_DIR="/Users/lv/.qclaw/workspace/cat"
MOOD_FILE="$CAT_DIR/cat-mood.txt"

# 调大脑拿 (话术 + 情绪标签 + 画面对应状态)，tab 分隔
result="$(/usr/bin/python3 "$CAT_DIR/cat-brain.py" "$@")"
# 拆分（支持 1/2/3 字段）
state="idle"
# 先按 tab 切
IFS=$'\t' read -r f1 f2 f3 <<< "$result"
if [ -z "$f2" ]; then
  # 无 tab：只有话术
  text="$f1"; label="calm"
elif [ -z "$f3" ]; then
  # 2 字段：话术 + 标签
  text="$f1"; label="$f2"
else
  # 3 字段：话术 + 标签 + 状态
  text="$f1"; label="$f2"; state="$f3"
fi

# 空话术 = 这次不说话（如 random 静默）
if [ -z "$text" ]; then
  exit 0
fi

# 把话术+状态写进画面（猫脸/舞台轮询读取，自动切状态）
echo "[$state] $text" > "$MOOD_FILE"

# 播放：走童声 per=3（度小萌），afplay 走系统默认（小米音箱）
play_audio(){
  local f="$1"; [ -f "$f" ] || return 1
  afplay "$f" >/dev/null 2>&1 &
  local ap=$! waited=0
  while kill -0 $ap 2>/dev/null; do sleep .3; waited=$((waited+3))
    [ $waited -ge 120 ] && { kill -9 $ap 2>/dev/null; break; }
  done; wait $ap 2>/dev/null
}

# 按情绪选音色
case "$label" in
  happy)
    # 开心：语速快一点、音调高
    ( /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$text" 5 8 && play_audio /tmp/cat_tts.mp3 ) || node "$CAT_DIR/cat-tts-baidu.mjs" "$text" 6 2>/dev/null && play_audio /tmp/cat_tts.mp3 || say -v Ting-Ting "[[rate 175]][[pitch 120]]$text"
    ;;
  sleepy)
    # 困：慢、拖长
    ( /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$text" -20 3 && play_audio /tmp/cat_tts.mp3 ) || node "$CAT_DIR/cat-tts-baidu.mjs" "$text" 2 2>/dev/null && play_audio /tmp/cat_tts.mp3 || say -v Ting-Ting "[[rate 130]][[pitch 110]]$text"
    ;;
  lonely|low)
    # 想念/低落：更慢、更柔
    ( /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$text" -15 5 && play_audio /tmp/cat_tts.mp3 ) || node "$CAT_DIR/cat-tts-baidu.mjs" "$text" 3 2>/dev/null && play_audio /tmp/cat_tts.mp3 || say -v Ting-Ting "[[rate 140]][[pitch 115]]$text"
    ;;
  *)
    # calm 默认：慢柔可爱
    ( /usr/bin/python3 "$CAT_DIR/cat-tts-edge.py" "$text" -10 5 && play_audio /tmp/cat_tts.mp3 ) || node "$CAT_DIR/cat-tts-baidu.mjs" "$text" 4 2>/dev/null && play_audio /tmp/cat_tts.mp3 || say -v Ting-Ting "[[rate 150]][[pitch 118]]$text"
    ;;
esac
exit 0
