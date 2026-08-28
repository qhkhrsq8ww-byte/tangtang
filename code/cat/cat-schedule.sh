#!/bin/bash
# 糖糖语音时刻表
#   ./cat-schedule.sh list      看几点说什么
#   ./cat-schedule.sh today     今天会响哪些
#   ./cat-schedule.sh preview   打印全部文案（不发声）
#   ./cat-schedule.sh crontab   生成可粘贴的 crontab
#   ./cat-schedule.sh fire <事件> [参数]  立刻出声（Mac）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

SCHED="$CAT_DIR/tangtang-schedule.conf"
CMD="${1:-list}"

schedule_lines() {
  grep -v '^[[:space:]]*#' "$SCHED" | grep -v '^[[:space:]]*$'
}

sched_note() {
  local bits=()
  if [ "${TANGTANG_SCHED_DOW:-*}" != "*" ]; then
    if [ "$TANGTANG_SCHED_DOW" = "1-5" ]; then
      bits+=("工作日")
    elif [ "$TANGTANG_SCHED_DOW" = "0,6" ] || [ "$TANGTANG_SCHED_DOW" = "6,0" ]; then
      bits+=("周末")
    else
      bits+=("星期$TANGTANG_SCHED_DOW")
    fi
  fi
  [ -n "${TANGTANG_SCHED_FROM:-}" ] && bits+=("从$TANGTANG_SCHED_FROM")
  [ -n "${TANGTANG_SCHED_UNTIL:-}" ] && bits+=("到$TANGTANG_SCHED_UNTIL")
  if [ "${TANGTANG_SCHED_PRESENCE:-}" = "0" ]; then
    bits+=("必响")
  fi
  if [ ${#bits[@]} -gt 0 ]; then
    printf ' (%s)' "$(IFS=' '; echo "${bits[*]}")"
  fi
}

sched_active_today() {
  tangtang_dow_match "${TANGTANG_SCHED_DOW:-*}" || return 1
  tangtang_date_in_window "${TANGTANG_SCHED_FROM:-}" "${TANGTANG_SCHED_UNTIL:-}" || return 1
  if [ "${TANGTANG_SCHED_EVENT:-}" = "alarm" ] || [ "${TANGTANG_SCHED_EVENT:-}" = "english" ]; then
    tangtang_is_school_day || return 1
  fi
  return 0
}

print_sched_row() {
  local extra
  extra="$(sched_note)"
  if [ -n "${TANGTANG_SCHED_ARG:-}" ]; then
    printf '%02d:%02d\t%s %s%s\n' "$TANGTANG_SCHED_HOUR" "$TANGTANG_SCHED_MIN" "$TANGTANG_SCHED_EVENT" "$TANGTANG_SCHED_ARG" "$extra"
  else
    printf '%02d:%02d\t%s%s\n' "$TANGTANG_SCHED_HOUR" "$TANGTANG_SCHED_MIN" "$TANGTANG_SCHED_EVENT" "$extra"
  fi
}

cron_env_prefix() {
  local p=""
  [ -n "${TANGTANG_SCHED_FROM:-}" ] && p="${p}TANGTANG_FROM=$TANGTANG_SCHED_FROM "
  [ -n "${TANGTANG_SCHED_UNTIL:-}" ] && p="${p}TANGTANG_UNTIL=$TANGTANG_SCHED_UNTIL "
  if [ "${TANGTANG_SCHED_PRESENCE:-}" = "0" ]; then
    p="${p}TANGTANG_REQUIRE_PRESENCE=0 "
  fi
  printf '%s' "$p"
}

case "$CMD" in
  list)
    echo "语音时刻表（friend 口吻，不上投影）"
    printf '%s\t%s\n' "时间" "事件"
    while read -r line; do
      [ -n "$line" ] || continue
      tangtang_parse_schedule_line "$line"
      [ -n "$TANGTANG_SCHED_EVENT" ] || continue
      print_sched_row
    done < <(schedule_lines)
    echo
    echo "今天会响: ./cat-schedule.sh today"
    echo "预览文案: ./cat-schedule.sh preview"
    echo "谁在客厅: ./cat-presence.sh"
    echo "装到 Mac: ./cat-schedule.sh crontab  → 粘进 crontab -e"
    echo "试闹铃(跳过日期/在场): ./cat-schedule.sh fire --force alarm school"
    ;;
  today)
    echo "今天 $(tangtang_today) 会响的条目"
    local_count=0
    while read -r line; do
      [ -n "$line" ] || continue
      tangtang_parse_schedule_line "$line"
      [ -n "$TANGTANG_SCHED_EVENT" ] || continue
      if sched_active_today; then
        print_sched_row
        local_count=$((local_count + 1))
      fi
    done < <(schedule_lines)
    if [ "$local_count" = "0" ]; then
      echo "（今天没有）"
    fi
    ;;
  preview)
    export TANGTANG_REMIND_PROFILE="${TANGTANG_REMIND_PROFILE:-friend}"
    while read -r line; do
      [ -n "$line" ] || continue
      tangtang_parse_schedule_line "$line"
      [ -n "$TANGTANG_SCHED_EVENT" ] || continue
      tmp=$(mktemp -d)
      extra="$(sched_note)"
      mark=""
      sched_active_today || mark="  [今天不响]"
      hm=$(printf '%02d:%02d' "$TANGTANG_SCHED_HOUR" "$TANGTANG_SCHED_MIN")
      if [ -n "${TANGTANG_SCHED_ARG:-}" ]; then
        text=$(TANGTANG_DATA_DIR="$tmp" TANGTANG_FAKE_TIME="$hm" "$CAT_DIR/cat-remind.sh" --print "$TANGTANG_SCHED_EVENT" "$TANGTANG_SCHED_ARG")
        printf '%02d:%02d  %s %s%s%s\n  %s\n' "$TANGTANG_SCHED_HOUR" "$TANGTANG_SCHED_MIN" "$TANGTANG_SCHED_EVENT" "$TANGTANG_SCHED_ARG" "$extra" "$mark" "${text:-（这次不说）}"
      else
        text=$(TANGTANG_DATA_DIR="$tmp" TANGTANG_FAKE_TIME="$hm" "$CAT_DIR/cat-remind.sh" --print "$TANGTANG_SCHED_EVENT")
        printf '%02d:%02d  %s%s%s\n  %s\n' "$TANGTANG_SCHED_HOUR" "$TANGTANG_SCHED_MIN" "$TANGTANG_SCHED_EVENT" "$extra" "$mark" "${text:-（这次不说）}"
      fi
      rm -rf "$tmp"
    done < <(schedule_lines)
    ;;
  crontab)
    echo "# 糖糖语音提醒 · 先 crontab -l 备份，再粘贴"
    echo "# 上学闹铃：上学日 06:30（放假/周末不响；调休上课日也响）"
    echo "# 白天小朋友上学时只跟爷爷奶奶说；航航16:00到、洽洽18:00到才跟小朋友互动"
    echo "# 其它提醒播前检测洽洽/航航手机；没人则静音跳过"
    echo "# 记忆写在本机硬盘，不写路由器盘：\$HOME/Library/Application Support/Tangtang"
    echo "MAILTO=\"\""
    echo "SHELL=/bin/bash"
    echo "PATH=/usr/bin:/bin:/usr/local/bin"
    echo "TANGTANG_REMIND_PROFILE=friend"
    echo "TANGTANG_SCHOOL_START=2026-09-01"
    while read -r line; do
      [ -n "$line" ] || continue
      tangtang_parse_schedule_line "$line"
      [ -n "$TANGTANG_SCHED_EVENT" ] || continue
      dow="${TANGTANG_SCHED_DOW:-*}"
      prefix="$(cron_env_prefix)"
      if [ -n "${TANGTANG_SCHED_ARG:-}" ]; then
        echo "$TANGTANG_SCHED_MIN $TANGTANG_SCHED_HOUR * * $dow ${prefix}$CAT_DIR/cat-remind.sh $TANGTANG_SCHED_EVENT $TANGTANG_SCHED_ARG"
      else
        echo "$TANGTANG_SCHED_MIN $TANGTANG_SCHED_HOUR * * $dow ${prefix}$CAT_DIR/cat-remind.sh $TANGTANG_SCHED_EVENT"
      fi
    done < <(schedule_lines)
    ;;
  fire)
    shift
    if [ -z "${1:-}" ]; then
      echo "用法: ./cat-schedule.sh fire [--force] <事件> [参数]"
      exit 1
    fi
    exec "$CAT_DIR/cat-remind.sh" "$@"
    ;;
  presence)
    exec "$CAT_DIR/cat-presence.sh"
    ;;
  selftest)
    fail=0
    TANGTANG_FAKE_TODAY=2026-09-01
    u="$(tangtang_weekday)"
    [ "$u" = "2" ] || { echo "fail weekday 2026-09-01 got $u"; fail=1; }
    tangtang_dow_match "1-5" "$u" || { echo "fail Tue should match 1-5"; fail=1; }
    TANGTANG_FAKE_TODAY=2026-09-05
    u="$(tangtang_weekday)"
    [ "$u" = "6" ] || { echo "fail weekday Sat got $u"; fail=1; }
    if tangtang_dow_match "1-5" "$u"; then echo "fail Sat should not match 1-5"; fail=1; fi
    tangtang_date_in_window "2026-09-01" "" || { echo "fail Sep5 from Sep1"; fail=1; }
    TANGTANG_FAKE_TODAY=2026-08-28
    if tangtang_date_in_window "2026-09-01" ""; then echo "fail Aug28 before school"; fail=1; fi
    tangtang_date_in_window "" "2026-08-31" || { echo "fail Aug28 until Aug31"; fail=1; }
    TANGTANG_FAKE_TODAY=2026-09-01
    if tangtang_date_in_window "" "2026-08-31"; then echo "fail Sep1 after wake until"; fail=1; fi
    tangtang_parse_schedule_line "30 6 alarm school from=2026-09-01 presence=0"
    [ "$TANGTANG_SCHED_EVENT" = "alarm" ] && [ "$TANGTANG_SCHED_ARG" = "school" ] \
      && [ "$TANGTANG_SCHED_PRESENCE" = "0" ] \
      || { echo "fail parse alarm line"; fail=1; }
    TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=12:00
    tangtang_is_school_day || { echo "fail Sep1 is school day"; fail=1; }
    tangtang_child_at_school hanghang || { echo "fail hanghang at school noon"; fail=1; }
    tangtang_child_at_school qiaqia || { echo "fail qiaqia at school noon"; fail=1; }
    TANGTANG_FAKE_TIME=16:00
    if tangtang_child_at_school hanghang; then echo "fail hanghang should be home 16:00"; fail=1; fi
    tangtang_child_at_school qiaqia || { echo "fail qiaqia still at school 16:00"; fail=1; }
    TANGTANG_FAKE_TIME=18:00
    if tangtang_child_at_school qiaqia; then echo "fail qiaqia should be home 18:00"; fail=1; fi
    TANGTANG_FAKE_TODAY=2026-09-25 TANGTANG_FAKE_TIME=12:00
    if tangtang_is_school_day; then echo "fail mid-autumn should not be school"; fail=1; fi
    TANGTANG_FAKE_TODAY=2026-09-20
    tangtang_is_school_day || { echo "fail Sep20 makeup school"; fail=1; }
    TANGTANG_FAKE_TODAY=2026-10-10
    tangtang_is_school_day || { echo "fail Oct10 makeup school"; fail=1; }
    if [ "$fail" = "0" ]; then
      echo "cat-schedule selftest ok"
      exit 0
    fi
    echo "cat-schedule selftest failed"
    exit 1
    ;;
  *)
    echo "用法: list | today | preview | crontab | presence | selftest | fire [--force] <事件>"
    exit 1
    ;;
esac
