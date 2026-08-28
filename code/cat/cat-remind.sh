#!/bin/bash
# ============================================================
# 糖糖语音提醒（不上投影）
# 用法:
#   ./cat-remind.sh pet_walk
#   ./cat-remind.sh meal lunch
#   ./cat-remind.sh --print water    # 只打印文案，不 TTS
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

PRINT=0
if [ "${1:-}" = "--print" ] || [ "${1:-}" = "-n" ]; then
  PRINT=1
  export TANGTANG_TTS=0
  shift
fi

EVENT="${1:-rest}"
ARG="${2:-}"

# 房间喇叭默认 friend：少卖萌，洽洽/航航都能听；可在 tangtang-config.sh 覆盖
export TANGTANG_PROFILE="${TANGTANG_REMIND_PROFILE:-friend}"

if [ -n "$ARG" ]; then
  out="$("$CAT_DIR/cat-talk.sh" "$EVENT" "$ARG")"
else
  out="$("$CAT_DIR/cat-talk.sh" "$EVENT")"
fi

if [ "$PRINT" = "1" ]; then
  if [ -n "$out" ]; then
    echo "$out"
  fi
  exit 0
fi

if [ -n "$out" ]; then
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  printf '%s\t%s\t%s\t%s\n' "$ts" "$EVENT" "${ARG:-}" "$out" >> "$CAT_DIR/cat-remind-log.txt"
fi
exit 0
