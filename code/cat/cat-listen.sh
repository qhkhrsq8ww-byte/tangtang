#!/bin/bash
# 糖糖 · 听（外置麦 MAONO AU-BM10 录音，带 30dB 增益）
# 用法: ./cat-listen.sh [秒数=5]
DUR="${1:-5}"
FF=/Users/lv/.qclaw/workspace/cat/bin/ffmpeg
OUT="${2:-/tmp/cat_voice.pcm}"
# 外置麦索引 :2（MAONO AU-BM10），信号弱需 30dB 增益
"$FF" -hide_banner -loglevel error \
  -f avfoundation -i ":2" \
  -af "volume=30dB" \
  -t "$DUR" -ar 16000 -ac 1 -f s16le -y "$OUT" 2>/dev/null
ls -la "$OUT" 2>/dev/null | awk '{print "录音文件:", $5, "字节"}'
