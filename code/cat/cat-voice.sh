#!/bin/bash
# 糖糖 · 语音对话 v2（听→辨→懂→答→说）
# 链路: 外置麦录音 → 声纹识别(谁) → 百度STT(说了啥) → 云端LLM(答) → 晓晓TTS(说)
# 自动记录: 谁在什么时候说了什么（习惯库）
# 用法: ./cat-voice.sh [听几秒=5]
CAT_DIR="$(dirname "$0")"
DUR="${1:-5}"
PCM=/tmp/cat_voice.pcm
echo "🎤 糖糖在听...（请说话，${DUR}秒）"
"$CAT_DIR/cat-listen.sh" "$DUR" "$PCM" >/dev/null 2>&1

# 1) 声纹识别：谁在说话
WHO=$("$CAT_DIR/cat-vp.py" identify "$PCM" 2>/dev/null | tail -1)
if [ "$WHO" = "unknown" ] || [ -z "$WHO" ]; then
  WHO="朋友"
fi
echo "👤 识别到: $WHO"

# 2) 语音识别：说了什么
echo "🧠 识别中..."
TEXT=$("$CAT_DIR/cat-stt-baidu.sh" "$PCM" 2>/dev/null | tr -d '\n')
if [ -z "$TEXT" ]; then
  echo "😿 没听清，再试一次喵～"
  "$CAT_DIR/cat-say.sh" "没听清，再试一次喵～" cute
  exit 0
fi
echo "   你说: $TEXT"

# 3) 记录习惯（谁/何时/说了啥）
"$CAT_DIR/cat-vp.py" log "$WHO" "$TEXT" >/dev/null 2>&1
echo "   📝 已记录到习惯库"

# 4) 云端回复
echo "💬 糖糖思考中..."
REPLY=$("/usr/bin/python3" "$CAT_DIR/cat-chat.py" "$TEXT" 2>/dev/null | tr -d '\n')
echo "   糖糖: $REPLY"
echo "🔊 糖糖说:"
echo "$REPLY" > "$CAT_DIR/cat-mood.txt"
"$CAT_DIR/cat-say.sh" "$REPLY" cute
