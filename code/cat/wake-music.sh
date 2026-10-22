#!/bin/bash
# 糖糖 · 每日 06:40 起床音乐（先通过 Mac 当前默认音频输出播放）
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

MUSIC="$CAT_DIR/assets/wake_music_3min.mp3"
LOG_DIR="$HOME/Library/Logs/tangtang"
LOG_FILE="$LOG_DIR/wake-music.log"
mkdir -p "$LOG_DIR" || exit 1
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"; }

if [ ! -f "$MUSIC" ]; then
  log "失败：音乐文件不存在：$MUSIC"
  exit 1
fi
if ! command -v afplay >/dev/null 2>&1; then
  log "失败：找不到 macOS afplay"
  exit 1
fi

log "开始播放起床音乐；输出设备由 macOS 当前音频输出设置决定"
if tangtang_play_audio "$MUSIC" 210; then
  log "播放完成"
  exit 0
else
  status=$?
  log "播放失败，退出码=$status"
  exit "$status"
fi
