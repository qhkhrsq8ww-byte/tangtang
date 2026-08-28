#!/bin/bash
# 糖糖语音时刻表
#   ./cat-schedule.sh list      看几点说什么
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

case "$CMD" in
  list)
    echo "语音时刻表（friend 口吻，不上投影）"
    printf '%s\t%s\n' "时间" "事件"
    while read -r min hour event arg; do
      [ -n "$event" ] || continue
      if [ -n "${arg:-}" ]; then
        printf '%02d:%02d\t%s %s\n' "$hour" "$min" "$event" "$arg"
      else
        printf '%02d:%02d\t%s\n' "$hour" "$min" "$event"
      fi
    done < <(schedule_lines)
    echo
    echo "预览文案: ./cat-schedule.sh preview"
    echo "装到 Mac: ./cat-schedule.sh crontab  → 粘进 crontab -e"
    ;;
  preview)
    export TANGTANG_REMIND_PROFILE="${TANGTANG_REMIND_PROFILE:-friend}"
    while read -r min hour event arg; do
      [ -n "$event" ] || continue
      tmp=$(mktemp -d)
      export TANGTANG_DATA_DIR="$tmp"
      if [ -n "${arg:-}" ]; then
        text=$("$CAT_DIR/cat-remind.sh" --print "$event" "$arg")
        printf '%02d:%02d  %s %s\n  %s\n' "$hour" "$min" "$event" "$arg" "${text:-（这次不说）}"
      else
        text=$("$CAT_DIR/cat-remind.sh" --print "$event")
        printf '%02d:%02d  %s\n  %s\n' "$hour" "$min" "$event" "${text:-（这次不说）}"
      fi
      rm -rf "$tmp"
    done < <(schedule_lines)
    ;;
  crontab)
    echo "# 糖糖语音提醒 · 先 crontab -l 备份，再粘贴"
    echo "SHELL=/bin/bash"
    echo "PATH=/usr/bin:/bin:/usr/local/bin"
    echo "TANGTANG_REMIND_PROFILE=friend"
    while read -r min hour event arg; do
      [ -n "$event" ] || continue
      if [ -n "${arg:-}" ]; then
        echo "$min $hour * * * $CAT_DIR/cat-remind.sh $event $arg"
      else
        echo "$min $hour * * * $CAT_DIR/cat-remind.sh $event"
      fi
    done < <(schedule_lines)
    ;;
  fire)
    shift
    if [ -z "${1:-}" ]; then
      echo "用法: ./cat-schedule.sh fire <事件> [参数]"
      exit 1
    fi
    exec "$CAT_DIR/cat-remind.sh" "$@"
    ;;
  *)
    echo "用法: list | preview | crontab | fire <事件>"
    exit 1
    ;;
esac
