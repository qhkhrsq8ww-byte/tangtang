#!/bin/bash
# 糖糖 · 听（外置麦 MAONO AU-BM10 录音，带增益）
# 采集点：客厅 Mac 旁。语音互动只在客厅，不要把麦拉进儿童房。
# 用法: ./cat-listen.sh [秒数=5] [输出pcm=/tmp/cat_voice.pcm]
set -u -o pipefail
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
record_status=$?
if [ "$record_status" -ne 0 ]; then
  rm -f "$OUT"
  echo "录音程序失败（状态码: $record_status）" >&2
  exit "$record_status"
fi
if [ ! -s "$OUT" ]; then
  echo "录音程序退出成功，但没有生成有效录音文件" >&2
  exit 1
fi
ls -la "$OUT" 2>/dev/null | awk '{print "录音文件:", $5, "字节"}'
