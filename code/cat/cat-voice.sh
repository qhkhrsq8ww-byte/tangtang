#!/bin/bash
# 糖糖 · 语音对话 v3
# 链路：听 → 辨 → 懂 → 答 → 说
# 说明：声纹/习惯数据仅写入本地，不提交Git。
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

DUR="${1:-5}"
PCM="/tmp/tangtang_voice.pcm"

PROFILE="${TANGTANG_PROFILE:-play}"
case "$PROFILE" in
  play|friend) ;;
  *) PROFILE="play" ;;
esac
export TANGTANG_PROFILE="$PROFILE"

echo "🎤 糖糖在听...（${DUR}秒，${PROFILE}模式）"
if ! "$CAT_DIR/cat-listen.sh" "$DUR" "$PCM" >/dev/null 2>&1; then
  echo "❌ 麦克风录音失败"
  exit 1
fi

WHO=$("$CAT_DIR/cat-vp.py" identify "$PCM" 2>/dev/null | tail -1)
[ -z "$WHO" ] && WHO="unknown"
echo "👤 识别状态: $WHO"

echo "🧠 识别中..."
TEXT=$("$CAT_DIR/cat-stt-baidu.sh" "$PCM" 2>/dev/null | tr -d '\n')
if [ -z "$TEXT" ]; then
  "$CAT_DIR/cat-say.sh" "没听清，再说一次好不好？" cute
  rm -f "$PCM"
  exit 0
fi

echo "   你说: $TEXT"
# unknown 只作为本地匿名访客，不冒充家庭成员
if [ "$WHO" != "unknown" ]; then
  "$CAT_DIR/cat-vp.py" log "$WHO" "$TEXT" >/dev/null 2>&1 || true
else
  "$CAT_DIR/cat-vp.py" log "unknown" "" >/dev/null 2>&1 || true
fi

echo "💬 糖糖思考中..."
REPLY=$(TANGTANG_PROFILE="$PROFILE" TANGTANG_SPEAKER="$WHO" /usr/bin/python3 "$CAT_DIR/cat-chat.py" "$TEXT" 2>/dev/null | tr -d '\n')
if [ -z "$REPLY" ]; then
  REPLY="糖糖刚才有点走神啦，我们再聊聊？"
fi

echo "   糖糖: $REPLY"
printf '%s\n' "[idle] $REPLY" > "$CAT_DIR/cat-mood.txt"
"$CAT_DIR/cat-say.sh" "$REPLY" cute
rm -f "$PCM"
