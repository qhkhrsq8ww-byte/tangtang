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
  tangtang_ensure_stage
fi

if [ -n "$ARG" ]; then
  "$CAT_DIR/cat-talk.sh" "$EVENT" "$ARG"
else
  "$CAT_DIR/cat-talk.sh" "$EVENT"
fi
exit 0
