#!/bin/bash
# 糖糖 · 听（外置麦 MAONO AU-BM10 录音，带增益）
# 用法: ./cat-listen.sh [秒数=5]
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

DUR="${1:-5}"
FF="$(tangtang_ffmpeg)"
OUT="${2:-/tmp/cat_voice.pcm}"
# 外置麦索引 :2（MAONO AU-BM10），信号弱需增益
"$FF" -hide_banner -loglevel error \
  -f avfoundation -i ":2" \
  -af "volume=30dB" \
  -t "$DUR" -ar 16000 -ac 1 -f s16le -y "$OUT" 2>/dev/null
ls -la "$OUT" 2>/dev/null | awk '{print "录音文件:", $5, "字节"}'
