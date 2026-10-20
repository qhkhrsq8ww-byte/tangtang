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
TANGTANG_LIVING_V4="${TANGTANG_LIVING_V4:-1}"

# V4 living-room scenes use InterruptPolicy; a silent/log-only result must not be spoken.
case "$EVENT" in
  phone|screen|rest|sitting|meal|exercise|play|sleep|sleepy|home|welcome|away|water|手机|久坐|吃饭|运动|睡觉|回家|离家)
    if [ "$TANGTANG_LIVING_V4" = "1" ]; then
      if [ -n "$ARG" ]; then
        line="$(/usr/bin/python3 "$CAT_DIR/cat-living.py" "$EVENT" "$ARG")"
      else
        line="$(/usr/bin/python3 "$CAT_DIR/cat-living.py" "$EVENT")"
      fi
      living_status=$?
      if [ "$living_status" -ne 0 ]; then
        echo "客厅场景决策失败，本次提醒取消" >&2
        exit "$living_status"
      fi
      if [ -z "$line" ]; then
        exit 0
      fi
      "$CAT_DIR/cat-say.sh" "$line" cute
      say_status=$?
      if [ "$say_status" -ne 0 ]; then
        echo "糖糖语音输出失败或正在播放其它语音，本次提醒跳过" >&2
        exit "$say_status"
      fi
      exit 0
    fi
    ;;
esac

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
# 上学闹铃：Glass 短铃只允许在上面的语音输出成功后继续执行。
if [ "$EVENT" = "school" ] || [ "$EVENT" = "school_alarm" ]; then
  tangtang_alarm_chime || exit $?
  tangtang_alarm_music || exit $?
fi
exit 0
