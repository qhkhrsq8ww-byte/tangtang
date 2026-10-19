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
# cat-voice.sh 与 cat-turn.sh 共用同一支麦克风：在采集入口加跨进程锁，
# 避免并发写入同一设备/PCM。mkdir 为原子操作，兼容未安装 flock 的 macOS。
LOCK_DIR="${TMPDIR:-/tmp}/tangtang-mic-capture.lock"
LOCK_ACQUIRED=0
RECORDING_COMPLETE=0
release_capture_lock() {
  if [ "$LOCK_ACQUIRED" = "1" ] && [ "$RECORDING_COMPLETE" != "1" ]; then
    rm -f "$OUT"
  }
  if [ "$LOCK_ACQUIRED" = "1" ] && [ -f "$LOCK_DIR/pid" ]; then
    lock_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [ "$lock_pid" = "$$" ]; then
      rm -f "$LOCK_DIR/pid"
      rmdir "$LOCK_DIR" 2>/dev/null || true
    fi
  fi
}
trap release_capture_lock EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
attempt=0
while ! mkdir "$LOCK_DIR" 2>/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -le 5 ] && [ ! -f "$LOCK_DIR/pid" ]; then
    sleep 0.1
    continue
  fi
  lock_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  case "$lock_pid" in
    ''|*[!0-9]*)
      echo "麦克风采集锁状态不明；为避免并发录音，本次退出。可检查并清理 $LOCK_DIR" >&2
      exit 75
      ;;
  esac
  if kill -0 "$lock_pid" 2>/dev/null; then
    echo "麦克风正在被另一个录音任务使用（PID: $lock_pid）；本次跳过，避免音频冲突。" >&2
    exit 75
  fi
  # PID 已不存在：先原子移走旧锁目录，再尝试获取。
  stale_dir="$LOCK_DIR.stale.$$"
  if mv "$LOCK_DIR" "$stale_dir" 2>/dev/null; then
    rm -rf "$stale_dir"
  fi
  attempt=0
done
LOCK_ACQUIRED=1
printf '%s\n' "$$" > "$LOCK_DIR/pid"
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
RECORDING_COMPLETE=1
ls -la "$OUT" 2>/dev/null | awk '{print "录音文件:", $5, "字节"}'
