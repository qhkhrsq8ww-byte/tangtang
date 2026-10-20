#!/bin/bash
# 糖糖 · 语音对话入口
# 统一复用 cat-voice.sh，避免语音入口与事件发声器 cat-talk.sh 发生同名职责覆盖。
# 用法: ./cat-voice-chat.sh [录音秒数=6]
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DUR="${1:-6}"

if ! [[ "$DUR" =~ ^[1-9][0-9]?$ ]]; then
  echo "用法: $0 [录音秒数，1-99]" >&2
  exit 2
fi

VOICE_IMPL="$SCRIPT_DIR/cat-voice.sh"
if [ ! -x "$VOICE_IMPL" ]; then
  echo "语音对话实现不存在或不可执行: $VOICE_IMPL" >&2
  exit 1
fi

exec "$VOICE_IMPL" "$DUR"
