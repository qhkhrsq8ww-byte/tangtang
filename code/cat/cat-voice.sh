#!/bin/bash
# 糖糖 · 语音对话（听→懂→答→说）
# 链路: 外置麦录音 → 百度STT → 云端LLM → 百度甜嗓TTS
# 用法: ./cat-voice.sh [听几秒=5]
CAT_DIR="$(dirname "$0")"
DUR="${1:-5}"
WAV=/tmp/cat_voice.wav
echo "🎤 糖糖在听...（请说话，${DUR}秒）"
"$CAT_DIR/cat-listen.sh" "$DUR" "$WAV" >/dev/null 2>&1
echo "🧠 识别中..."
TEXT=$("$CAT_DIR/cat-stt-baidu.sh" "$WAV" 2>/dev/null | tr -d '\n')
if [ -z "$TEXT" ]; then
  echo "😿 没听清，再试一次喵～"
  "$CAT_DIR/cat-say.sh" "没听清，再试一次喵～" cute
  exit 0
fi
echo "   你说: $TEXT"
echo "💬 糖糖思考中..."
REPLY=$("/usr/bin/python3" "$CAT_DIR/cat-chat.py" "$TEXT" 2>/dev/null | tr -d '\n')
echo "   糖糖: $REPLY"
echo "🔊 糖糖说:"
echo "$REPLY" > "$CAT_DIR/cat-mood.txt"
"$CAT_DIR/cat-say.sh" "$REPLY" cute
