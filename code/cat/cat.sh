#!/bin/bash
# ============================================================
# 糖糖统一入口（自动适配投影状态，走智能大脑）
# 用法:
#   ./cat.sh                  # 上糖糖（投影开着->全屏舞台；没开->语音报平安）
#   ./cat.sh "想说的话"       # 说一句话（带人设语气包装）
#   ./cat.sh -f               # 强制仅声音（不管投影）
#   ./cat.sh -p               # 强制透明宠物浮现（cat-desktop-pet.html）
#   ./cat.sh -s               # 强制全屏舞台
#   ./cat.sh status           # 查看糖糖当前心情状态
#   ./cat.sh chat "想聊的"     # 云端真对话
#   ./cat.sh alarm list        # 查看闹铃
#   ./cat.sh alarm cancel      # 取消全部闹铃
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

MOOD_FILE="$CAT_DIR/cat-mood.txt"
if [ "${1:-}" = "task" ]; then
  shift
  exec /usr/bin/python3 "$CAT_DIR/cat-tasks.py" "$@"
fi
TEXT=""
MEMORY_REQ=0
ALARM_REQ=0
ALARM_ACTION=""
STATUS_REQ=0
CHAT_REQ=0
ALARM_REQ=0
FORCE_VOICE=0
FORCE_STAGE=0
FORCE_PET=0
while [ $# -gt 0 ]; do
  case "$1" in
    -f) FORCE_VOICE=1; shift;;
    -s) FORCE_STAGE=1; shift;;
    -p) FORCE_PET=1; shift;;
    memory) MEMORY_REQ=1; shift;;
    alarm) ALARM_REQ=1; shift; if [ $# -gt 0 ]; then ALARM_ACTION="$1"; shift; fi;;
    status) STATUS_REQ=1; shift;;
    chat) CHAT_REQ=1; shift;;
    *) TEXT="$1"; shift;;
  esac
done

brain_say(){
  local event="$1"; local arg="${2:-}"
  if [ -n "$arg" ]; then
    "$CAT_DIR/cat-talk.sh" "$event" "$arg"
  else
    "$CAT_DIR/cat-talk.sh" "$event"
  fi
}

if [ "$ALARM_REQ" = "1" ]; then
  case "$ALARM_ACTION" in
    list) /usr/bin/python3 "$CAT_DIR/cat-alarm.py" list; exit $?;;
    cancel) /usr/bin/python3 "$CAT_DIR/cat-alarm.py" cancel_all; exit $?;;
    *) echo "用法: ./cat.sh alarm list | alarm cancel" >&2; exit 2;;
  esac
fi

if [ "$MEMORY_REQ" = "1" ]; then
  /usr/bin/python3 "$CAT_DIR/cat-memory.py" "${TEXT:-today}"
  exit $?
fi

if [ "$STATUS_REQ" = "1" ]; then
  /usr/bin/python3 "$CAT_DIR/cat-brain.py" status
  exit 0
fi

if [ "$CHAT_REQ" = "1" ]; then
  gate="$("$CAT_DIR/tangtang-speak-gate.py" --channel chat --member "${TANGTANG_MEMBER_ID:-${TANGTANG_SPEAKER:-unknown}}" 2>/dev/null || true)"
  if [ "$gate" != "speak" ]; then exit 0; fi
  if tangtang_projector_on; then
    tangtang_ensure_stage
  fi
  if [ -z "$TEXT" ]; then
    TEXT="糖糖，我来啦"
  fi
  TANGTANG_V4_PIPELINE=1 reply="$(TANGTANG_V4_PIPELINE=1 /usr/bin/python3 "$CAT_DIR/cat-chat.py" "$TEXT")"
  echo "[idle] $reply" > "$MOOD_FILE"
  "$CAT_DIR/cat-say.sh" "$reply" cute
  echo "[糖糖·云端对话] 回复：$reply"
  exit 0
fi

if [ "$FORCE_VOICE" = "1" ]; then
  MODE="voice"
elif [ "$FORCE_STAGE" = "1" ]; then
  MODE="stage"
elif [ "$FORCE_PET" = "1" ]; then
  MODE="pet"
elif tangtang_projector_on; then
  MODE="stage"
else
  MODE="voice"
fi

case "$MODE" in
  stage)
    tangtang_ensure_stage
    if ! system_profiler SPDisplaysDataType 2>/dev/null | grep -q "Mirror: On"; then
      echo "提示：未检测到镜像。点菜单栏『屏幕镜像』选投影；连上后糖糖舞台自动上屏，点画面可进全屏。"
    fi
    if [ -n "$TEXT" ]; then
      brain_say "say" "$TEXT"
    else
      brain_say "greet"
    fi
    echo "[糖糖] 投影在线 → 全屏舞台 + 智能说话"
    ;;
  pet)
    tangtang_ensure_server
    tangtang_ensure_pet || exit $?
    osascript -e "tell application \"Safari\" to if (count of windows) > 0 then set URL of front document to \"http://127.0.0.1:8080/cat-desktop-pet.html\"" 2>/dev/null
    if ! system_profiler SPDisplaysDataType 2>/dev/null | grep -q "Mirror: On"; then
      echo "提示：未检测到镜像。点菜单栏『屏幕镜像』选投影；连上后糖糖自动上屏，不弹窗遮挡。"
    fi
    if [ -n "$TEXT" ]; then
      brain_say "say" "$TEXT"
    else
      brain_say "greet"
    fi
    echo "[糖糖] 投影在线 → 透明浮现宠物 + 智能说话"
    ;;
  voice)
    if [ -n "$TEXT" ]; then
      brain_say "say" "$TEXT"
    else
      brain_say "greet"
    fi
    echo "[糖糖] 投影离线 → 仅声音(智能)"
    ;;
esac
exit 0
