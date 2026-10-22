#!/bin/bash
# 糖糖 · 主动性桥接（launchd 每 30 分钟触发，按小时挑事件，冷却由大脑管）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"
hour=$(date +%H | sed 's/^0//')
case "$hour" in
  7) E=wake;;   8) E=water;;  9) E=rest;;   10) E=exercise;;
  11) E=water;; 12) E=meal;;  13) E=rest;;  14) E=homework;;
  15) E=water;; 16) E=play;;  17) E=homework;; 18) E=meal;;
  19) E=exercise;; 20) E=water;; 21) E=tidy;; 22) E=sleep;;
  *) exit 0;;
esac
# Keep scheduler diagnostics local and timestamped; logging failure must not block reminders.
LOG_DIR="${HOME}/Library/Logs/tangtang"
LOG_FILE="${LOG_DIR}/proactive.log"
mkdir -p "$LOG_DIR" 2>/dev/null || true
{
  printf '[%s] scheduled event=%s start\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$E"
  "$SCRIPT_DIR/cat-remind.sh" "$E"
  rc=$?
  printf '[%s] scheduled event=%s exit=%s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$E" "$rc"
  exit "$rc"
} >> "$LOG_FILE" 2>&1
