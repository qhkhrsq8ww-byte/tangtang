#!/bin/bash
# 糖糖 · 录音入口：单实例锁、失败清理、明确返回码
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

DUR="${1:-5}"
OUT="${2:-/tmp/cat_voice.pcm}"
LOCK_DIR="${TMPDIR:-/tmp}/tangtang-mic-capture.lock"
LOCK_ACQUIRED=0
RECORDING_COMPLETE=0

release_capture_lock() {
  if [ "$LOCK_ACQUIRED" = "1" ] && [ -d "$LOCK_DIR" ]; then
    local lock_pid=""
    [ -f "$LOCK_DIR/pid" ] && lock_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [ "$lock_pid" = "$$" ]; then
      rm -rf "$LOCK_DIR"
    fi
  fi
}
cleanup_recording() {
  if [ "$LOCK_ACQUIRED" = "1" ] && [ "$RECORDING_COMPLETE" != "1" ]; then
    rm -f "$OUT"
  fi
  release_capture_lock
}
trap cleanup_recording EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if ! [[ "$DUR" =~ ^[0-9]+([.][0-9]+)?$ ]] || ! awk "BEGIN {exit !($DUR > 0 && $DUR <= 99)}"; then
  echo "录音时长无效" >&2
  exit 2
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  lock_pid=""
  [ -f "$LOCK_DIR/pid" ] && lock_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
    echo "另一个录音任务正在使用麦克风" >&2
    exit 75
  fi
  stale_dir="$LOCK_DIR.stale.$$"
  if mv "$LOCK_DIR" "$stale_dir" 2>/dev/null; then
    rm -rf "$stale_dir"
  fi
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "另一个录音任务正在使用麦克风" >&2
    exit 75
  fi
fi
LOCK_ACQUIRED=1
printf '%s\n' "$$" > "$LOCK_DIR/pid"

FF="$(tangtang_ffmpeg)"
rm -f "$OUT"
# 外置麦默认索引 :2；测试或其他设备可通过 TANGTANG_AUDIO_INPUT 覆盖
INPUT="${TANGTANG_AUDIO_INPUT:-:2}"
GAIN="${TANGTANG_AUDIO_GAIN:-15dB}"
"$FF" -hide_banner -loglevel error \
  -f avfoundation -i "$INPUT" \
  -af "volume=$GAIN" \
  -t "$DUR" -ar 16000 -ac 1 -f s16le -y "$OUT"
ffmpeg_status=$?
if [ "$ffmpeg_status" -ne 0 ]; then
  echo "录音程序失败（状态码 $ffmpeg_status）" >&2
  exit "$ffmpeg_status"
fi
if [ ! -s "$OUT" ]; then
  echo "没有生成有效录音文件" >&2
  exit 1
fi
RECORDING_COMPLETE=1
ls -la "$OUT" 2>/dev/null | awk '{print "录音文件:", $5, "字节"}'
exit 0
