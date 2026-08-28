#!/bin/bash
# ============================================================
# 糖糖语音提醒（不上投影；播前检测客厅是否有小朋友）
# 用法:
#   ./cat-remind.sh pet_walk
#   ./cat-remind.sh meal lunch
#   ./cat-remind.sh --print water     # 只打印文案，不做在场检测、不 TTS
#   ./cat-remind.sh --force pet_walk  # 跳过在场检测，强制出声
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

PRINT=0
FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --print|-n) PRINT=1; export TANGTANG_TTS=0; shift;;
    --force) FORCE=1; shift;;
    *) break;;
  esac
done

EVENT="${1:-rest}"
ARG="${2:-}"

# 房间喇叭默认 friend；若只检测到航航则改 play
export TANGTANG_PROFILE="${TANGTANG_REMIND_PROFILE:-friend}"

log_skip() {
  local reason="$1"
  local ts
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  printf '%s\tSKIP\t%s\t%s\t%s\n' "$ts" "$EVENT" "${ARG:-}" "$reason" >> "$TANGTANG_REMIND_LOG"
  echo "[糖糖] $reason" >&2
}

if [ "$PRINT" != "1" ] && [ "$FORCE" != "1" ] && [ "${TANGTANG_REQUIRE_PRESENCE:-1}" = "1" ]; then
  present="$(tangtang_kids_present)"
  prc=$?
  if [ "$prc" = "2" ]; then
    log_skip "未配置小朋友手机IP，跳过播放。请填写 TANGTANG_HOST_QIAQIA / TANGTANG_HOST_HANGHANG"
    exit 0
  fi
  if [ "$prc" != "0" ]; then
    log_skip "客厅未检测到洽洽或航航，这次不说"
    exit 0
  fi
  export TANGTANG_PRESENT_KIDS="$present"
  if [ "$present" = "航航" ]; then
    export TANGTANG_PROFILE=play
  else
    export TANGTANG_PROFILE="${TANGTANG_REMIND_PROFILE:-friend}"
  fi
fi

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
  printf '%s\t%s\t%s\t%s\t%s\n' "$ts" "$EVENT" "${ARG:-}" "${TANGTANG_PRESENT_KIDS:-}" "$out" >> "$TANGTANG_REMIND_LOG"
fi
exit 0
