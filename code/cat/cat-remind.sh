#!/bin/bash
# ============================================================
# 糖糖语音提醒（不上投影）
# 上学日白天只跟爷爷奶奶说；航航 16:00、洽洽 18:00 到家后才跟小朋友互动
# 用法:
#   ./cat-remind.sh pet_walk
#   ./cat-remind.sh meal lunch
#   ./cat-remind.sh alarm school
#   ./cat-remind.sh --print water
#   ./cat-remind.sh --force alarm school
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

# 房间喇叭默认 friend；上学日按作息改：白天 elder，航航到家后 play
export TANGTANG_PROFILE="${TANGTANG_REMIND_PROFILE:-friend}"

# 上学闹铃：卧室也要听到，默认不看出门；只在上学日响
if [ "$EVENT" = "alarm" ]; then
  : "${TANGTANG_FROM:=${TANGTANG_SCHOOL_START:-2026-09-01}}"
  if [ "${TANGTANG_ALARM_REQUIRE_PRESENCE:-0}" != "1" ]; then
    TANGTANG_REQUIRE_PRESENCE=0
  fi
fi

apply_audience() {
  local kids rc
  if ! tangtang_is_school_day; then
    return 2
  fi
  kids="$(tangtang_kids_interactable)"
  rc=$?
  if [ "$rc" != "0" ]; then
    export TANGTANG_PROFILE=elder
    export TANGTANG_CHILD_NAME="爷爷奶奶"
    export TANGTANG_PRESENT_KIDS=""
    export TANGTANG_SCHOOL_DAYTIME=1
    TANGTANG_REQUIRE_PRESENCE=0
    return 1
  fi
  export TANGTANG_PRESENT_KIDS="$kids"
  export TANGTANG_SCHOOL_DAYTIME=0
  if [ "$kids" = "航航" ]; then
    export TANGTANG_PROFILE=play
    export TANGTANG_CHILD_NAME="航航"
  elif [ "$kids" = "洽洽" ]; then
    export TANGTANG_PROFILE=friend
    export TANGTANG_CHILD_NAME="洽洽"
  else
    export TANGTANG_PROFILE="${TANGTANG_REMIND_PROFILE:-friend}"
  fi
  TANGTANG_REQUIRE_PRESENCE=0
  return 0
}

if [ "$FORCE" != "1" ]; then
  apply_audience || true
fi

log_skip() {
  local reason="$1"
  local ts
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  printf '%s\tSKIP\t%s\t%s\t%s\n' "$ts" "$EVENT" "${ARG:-}" "$reason" >> "$TANGTANG_REMIND_LOG"
  echo "[糖糖] $reason" >&2
}

if [ "$PRINT" != "1" ] && [ "$FORCE" != "1" ]; then
  if ! tangtang_date_in_window "${TANGTANG_FROM:-}" "${TANGTANG_UNTIL:-}"; then
    log_skip "今天不在提醒日期内，这次不说"
    exit 0
  fi
  if [ "$EVENT" = "alarm" ] && ! tangtang_is_school_day; then
    log_skip "今天不上学，闹铃休息"
    exit 0
  fi
  if [ "$EVENT" = "english" ]; then
    if ! tangtang_is_school_day; then
      log_skip "周末/放假，英语小伴读休息"
      exit 0
    fi
    case "${ARG:-hanghang}" in
      qiaqia|洽洽|6|grade6)
        if tangtang_child_at_school qiaqia; then
          log_skip "洽洽还没到家，英语小伴读跳过"
          exit 0
        fi
        export TANGTANG_PROFILE=friend
        export TANGTANG_CHILD_NAME="洽洽"
        export TANGTANG_MEMBER_ID="${TANGTANG_MEMBER_ID:-qiaqia}"
        export TANGTANG_SPEAKER="${TANGTANG_SPEAKER:-qiaqia}"
        ;;
      *)
        if tangtang_child_at_school hanghang; then
          log_skip "航航还没到家，英语小伴读跳过"
          exit 0
        fi
        export TANGTANG_PROFILE=play
        export TANGTANG_CHILD_NAME="航航"
        export TANGTANG_MEMBER_ID="${TANGTANG_MEMBER_ID:-hanghang}"
        export TANGTANG_SPEAKER="${TANGTANG_SPEAKER:-hanghang}"
        ;;
    esac
    # 当天说过「到此为止」，或连续沉默/反对：这类先不说，不加重
    if ! tangtang_turn_gate_open english "$(tangtang_turn_who english "${ARG:-hanghang}")"; then
      log_skip "今天这类先不说了"
      exit 0
    fi
  fi
fi

# 周末/节假日：仍看出门。上学日白天对爷爷奶奶说，不要求小朋友手机。
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
    export TANGTANG_CHILD_NAME="航航"
  else
    export TANGTANG_PROFILE="${TANGTANG_REMIND_PROFILE:-friend}"
  fi
fi

if [ "$PRINT" != "1" ] && [ "$EVENT" = "alarm" ]; then
  tangtang_alarm_chime
fi

# 本地习惯：反对/今天别叫/连续沉默则少说。--force 仍说。dry-run 打印原因。
if [ "$FORCE" != "1" ]; then
  hwho=""
  case "$EVENT" in
    english)
      case "${ARG:-hanghang}" in
        qiaqia|洽洽|6|grade6) hwho="qiaqia" ;;
        *) hwho="hanghang" ;;
      esac
      ;;
    *)
      hwho="${TANGTANG_MEMBER_ID:-${TANGTANG_SPEAKER:-}}"
      ;;
  esac
  if [ -n "$hwho" ]; then
    if [ "$PRINT" = "1" ]; then
      export TANGTANG_HABIT_READONLY=1
    fi
    gate="$(/usr/bin/python3 "$CAT_DIR/cat-habits.py" should-speak "$EVENT" "$hwho" 2>/dev/null || true)"
    unset TANGTANG_HABIT_READONLY
    if printf '%s\n' "$gate" | grep -q '^skip'; then
      reason="${gate#skip|}"
      if [ "$PRINT" = "1" ]; then
        echo "这次不说（习惯：$reason）"
        exit 0
      fi
      log_skip "这次不说（习惯：$reason）"
      exit 0
    fi
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

# 上学闹铃：Glass 短铃（上面）→ 糖糖说话 → 同一只音箱轻音乐。不另开音箱。
if [ "$PRINT" != "1" ] && [ "$EVENT" = "alarm" ] && [ -n "$out" ]; then
  tangtang_alarm_music
fi

# 出声完成（cat-talk 已等 afplay）后再决定是否开客厅窗。--print 不会走到这里。
# 默认只给 english 开窗；其它提醒单向，除非 TANGTANG_TURN_ALL=1。
# 没真正出声（冷却空话）就不开麦。
if tangtang_turn_event_enabled "$EVENT" && [ -n "$out" ]; then
  "$CAT_DIR/cat-turn.sh" --follow "$EVENT" "${ARG:-}"
else
  tangtang_note_presence_for_event "$EVENT" "$ARG" >/dev/null || true
fi
exit 0
