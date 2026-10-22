#!/bin/bash
# 糖糖 · 每日 06:40 温柔唤醒：先语音问候，再播放现有三分钟音乐
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

MUSIC="$CAT_DIR/assets/wake_music_3min.wav"
VOICE_SCRIPT="$CAT_DIR/cat-say.sh"
LOG_DIR="$HOME/Library/Logs/tangtang"
LOG_FILE="$LOG_DIR/wake-music.log"
GREETING="早上好呀，我是糖糖。新的一天开始啦，先伸个懒腰，慢慢坐起来吧。不用着急，我们一步一步来。希望你们今天都有好心情！"

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

# 语音失败不阻断音乐；cat-say.sh 会按项目既有顺序尝试 Edge TTS、百度 TTS、macOS Ting-Ting。
if [ -x "$VOICE_SCRIPT" ]; then
  log "开始播放温柔起床问候"
  if "$VOICE_SCRIPT" "$GREETING" soft >> "$LOG_FILE" 2>&1; then
    log "起床问候播放完成"
  else
    status=$?
    log "起床问候失败，继续播放音乐，退出码=$status"
  fi
else
  log "未找到可执行的 cat-say.sh，跳过语音问候，继续播放音乐"
fi

log "开始播放起床音乐；输出设备由 macOS 当前音频输出设置决定"
if tangtang_play_audio "$MUSIC" 210; then
  log "起床音乐播放完成"
  exit 0
else
  status=$?
  log "起床音乐播放失败，退出码=$status"
  exit "$status"
fi
