#!/bin/bash
# ============================================================
# 糖糖定时触发（走智能大脑，带冷却；只决策一次）
# 用法: ./cat-remind.sh <事件> [参数]
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

EVENT="${1:-rest}"
ARG="${2:-}"

# 投影在线只保证舞台在，不再 greet，避免一次提醒说三遍
if tangtang_projector_on; then
  if ! tangtang_ensure_stage; then
    echo "糖糖舞台启动失败，本次提醒取消" >&2
    exit 1
  fi
fi

if [ -n "$ARG" ]; then
  "$CAT_DIR/cat-talk.sh" "$EVENT" "$ARG"
else
  "$CAT_DIR/cat-talk.sh" "$EVENT"
fi
talk_status=$?
if [ "$talk_status" -ne 0 ]; then
  echo "糖糖语音输出失败或正在播放其它语音，本次提醒跳过" >&2
  exit "$talk_status"
fi
exit 0
