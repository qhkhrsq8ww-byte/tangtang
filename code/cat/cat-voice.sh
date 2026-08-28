#!/bin/bash
# 糖糖 · 语音对话 v4
# 链路：听 → 辨 → 解析家庭角色 → 懂 → 答 → 说
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/cat-lib.sh"
DUR="${1:-5}"
PCM="/tmp/tangtang_voice.pcm"
PROFILE="${TANGTANG_PROFILE:-}"

echo "🎤 糖糖在听...（${DUR}秒）"
if ! "$CAT_DIR/cat-listen.sh" "$DUR" "$PCM" >/dev/null 2>&1; then
  echo "❌ 麦克风录音失败"
  exit 1
fi
WHO=$("$CAT_DIR/cat-vp.py" identify "$PCM" 2>/dev/null | tail -1)
[ -z "$WHO" ] && WHO="unknown"
echo "👤 识别状态: $WHO"
if [ "$WHO" != "unknown" ]; then
  PROFILE="$(/usr/bin/python3 "$CAT_DIR/tangtang-profile.py" --speaker "$WHO" 2>/dev/null | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin).get("profile","play"))' 2>/dev/null || echo "play")"
fi
case "$PROFILE" in play|friend|adult|elder) ;; *) PROFILE="play" ;; esac
export TANGTANG_PROFILE="$PROFILE"

echo "🧠 识别中..."
TEXT=$("$CAT_DIR/cat-stt-baidu.sh" "$PCM" 2>/dev/null | tr -d '\n')
if [ -z "$TEXT" ]; then
  "$CAT_DIR/cat-say.sh" "没听清，再说一次好不好？" cute
  rm -f "$PCM"
  exit 0
fi

echo "   你说: $TEXT"
if [ "$WHO" != "unknown" ]; then
  "$CAT_DIR/cat-vp.py" log "$WHO" "$TEXT" >/dev/null 2>&1 || true
else
  "$CAT_DIR/cat-vp.py" log "unknown" "" >/dev/null 2>&1 || true
fi
REPLY=$(TANGTANG_PROFILE="$PROFILE" TANGTANG_SPEAKER="$WHO" /usr/bin/python3 "$CAT_DIR/cat-chat.py" "$TEXT" 2>/dev/null | tr -d '\n')
[ -z "$REPLY" ] && REPLY="糖糖刚才有点走神啦，我们再聊聊？"
echo "   糖糖: $REPLY"
printf '%s\n' "[idle] $REPLY" > "$CAT_DIR/cat-mood.txt"
"$CAT_DIR/cat-say.sh" "$REPLY" cute
rm -f "$PCM"
