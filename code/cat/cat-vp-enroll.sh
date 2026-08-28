#!/bin/bash
# 糖糖 · 一键声纹建档
# 用法: ./cat-vp-enroll.sh <名字> [段数=3]
# 会引导用户录 N 段语音（每段 5 秒），然后建档
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"
NAME="${1:?用法: cat-vp-enroll.sh <名字> [段数=3]}"
N="${2:-3}"
FF="$(tangtang_ffmpeg)"
VP="$CAT_DIR/cat-vp.py"
TMP=/tmp/cat_vp_enroll_$$
mkdir -p "$TMP"

echo "🐾 给「$NAME」建档声纹（共 $N 段，每段 5 秒）"
echo "==========================================="
echo "📢 请对着麦克风说话，内容随意（念一段话最好）"
echo "   比如：'大家好，我是$NAME，今天天气真好呀'"
echo "==========================================="

FILES=""
for i in $(seq 1 "$N"); do
  echo ""
  echo "🎙️  第 $i 段：3 秒后开始录音…（请说话）"
  sleep 3
  PCM="$TMP/sample_$i.pcm"
  "$FF" -hide_banner -loglevel error -f avfoundation -i ":2" -t 5 -ar 16000 -ac 1 -af "volume=20dB" -f s16le -y "$PCM" 2>/dev/null
  SIZE=$(stat -f%z "$PCM" 2>/dev/null || echo 0)
  if [ "$SIZE" -gt 80000 ]; then
    echo "  ✅ 录到 $SIZE 字节"
    FILES="$FILES $PCM"
  else
    echo "  ⚠️  声音太小（$SIZE 字节），重录…"
    i=$((i-1))
  fi
done

echo ""
echo "📊 建档中…"
/usr/bin/python3 "$VP" enroll "$NAME" $FILES
rm -rf "$TMP"
echo ""
echo "✅ 完成！现在糖糖可以识别「$NAME」的声音了"
