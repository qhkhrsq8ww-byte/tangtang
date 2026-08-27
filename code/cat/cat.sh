#!/bin/bash
# ============================================================
# 猫咪「糖糖」统一入口（自动适配投影状态，走智能大脑）
# 用法:
#   ./cat.sh                  # 上猫（投影开着->全屏舞台；没开->语音报平安）
#   ./cat.sh "想说的话"       # 说一句话（带人设语气包装）
#   ./cat.sh -f               # 强制仅声音（不管投影）
#   ./cat.sh -p               # 强制透明宠物浮现（浮在别的内容上时用）
#   ./cat.sh -s               # 强制全屏舞台（不管投影）
#   ./cat.sh status           # 查看糖糖当前心情状态
#   ./cat.sh chat "想聊的"     # 云端真对话（走 LLM 网关，能真聊天）
# 说话内容由 cat-brain.py 大脑决策（带情绪），chat 则走云端 LLM 真对话。
# 注意：不主动弹系统设置窗口，以免遮挡投影画面。
# ============================================================
CAT_DIR="/Users/lv/.qclaw/workspace/cat"
MOOD_FILE="$CAT_DIR/cat-mood.txt"
PROJECTOR_IP="192.168.31.104"
AIRPLAY_PORT="61949"
TEXT=""
STATUS_REQ=0
CHAT_REQ=0

# 参数解析
FORCE_VOICE=0; FORCE_STAGE=0; FORCE_PET=0
while [ $# -gt 0 ]; do
  case "$1" in
    -f) FORCE_VOICE=1; shift;;
    -s) FORCE_STAGE=1; shift;;
    -p) FORCE_PET=1; shift;;
    status) STATUS_REQ=1; shift;;
    chat) CHAT_REQ=1; shift;;
    *) TEXT="$1"; shift;;
  esac
done

# 确保本地服务在跑（投屏用）
ensure_server(){
  if ! curl -s -o /dev/null "http://127.0.0.1:8080/cat-stage.html"; then
    nohup /usr/bin/python3 -m http.server 8080 --bind 0.0.0.0 --directory "$CAT_DIR" >/tmp/cathttp.log 2>&1 &
    sleep 2
  fi
}

# 投影是否在线（=开着且可投屏）
projector_on(){
  nc -z -w 3 "$PROJECTOR_IP" "$AIRPLAY_PORT" 2>/dev/null
}

# 本机是否已在镜像（避免重弹设置窗口遮挡投影）
mirroring_on(){
  system_profiler SPDisplaysDataType 2>/dev/null | grep -q "Mirror: On"
}

# 把心情写进文件（猫脸轮询读取）
write_mood(){
  echo "$1" > "$MOOD_FILE"
}

# 让大脑说一句话（带情绪），并出声
brain_say(){
  local event="$1"; local arg="${2:-}"
  if [ -n "$arg" ]; then
    "$CAT_DIR/cat-talk.sh" "$event" "$arg"
  else
    "$CAT_DIR/cat-talk.sh" "$event"
  fi
}

# ---- 决策 ----
if [ "$STATUS_REQ" = "1" ]; then
  /usr/bin/python3 "$CAT_DIR/cat-brain.py" status
  exit 0
fi

if [ "$CHAT_REQ" = "1" ]; then
  # 云端真对话：先上屏(投影开)再对话，回复写气泡+出声
  if projector_on; then
    ensure_server
    # 只在未打开时打开；已打开不重复刷新（避免老Mac Safari高CPU/卡顿）
    if ! pgrep -f "Safari.*cat-stage" >/dev/null 2>&1; then
      open "http://127.0.0.1:8080/cat-stage.html"
      ( osascript -e "tell application \"Safari\" to if (count of windows) > 0 then set URL of front document to \"http://127.0.0.1:8080/cat-stage.html\"" 2>/dev/null & )
    fi
  fi
  if [ -z "$TEXT" ]; then
    TEXT="糖糖，主人来啦"
  fi
  reply="$(/usr/bin/python3 "$CAT_DIR/cat-chat.py" "$TEXT")"
  echo "$reply" > "$MOOD_FILE"
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
elif projector_on; then
  MODE="stage"
else
  MODE="voice"
fi

case "$MODE" in
  stage)
    ensure_server
    # 只在未打开时打开；已打开不重复刷新（避免老Mac Safari高CPU/卡顿）
    if ! curl -s -o /dev/null --max-time 3 "http://127.0.0.1:8080/cat-stage.html"; then
      ensure_server
    fi
    if ! pgrep -f "Safari.*cat-stage" >/dev/null 2>&1; then
      open "http://127.0.0.1:8080/cat-stage.html"
      ( osascript -e "tell application \"Safari\" to if (count of windows) > 0 then set URL of front document to \"http://127.0.0.1:8080/cat-stage.html\"" 2>/dev/null & )
    fi
    if ! mirroring_on; then
      echo "提示：未检测到镜像。点菜单栏『屏幕镜像』选 OBE_R3Ultra 旗舰版(OBE)501；连上后糖糖舞台自动上屏，点画面可进全屏。"
    fi
    if [ -n "$TEXT" ]; then
      brain_say "say" "$TEXT"
    else
      brain_say "greet"
    fi
    echo "[糖糖] 投影在线 → 全屏舞台(大钟+角落糖糖) + 智能说话"
    ;;
  pet)
    ensure_server
    open "http://127.0.0.1:8080/cat-pet.html"
    osascript -e "tell application \"Safari\" to if (count of windows) > 0 then set URL of front document to \"http://127.0.0.1:8080/cat-pet.html\"" 2>/dev/null
    if ! mirroring_on; then
      echo "提示：未检测到镜像。点菜单栏『屏幕镜像』选投影；连上后小猫自动上屏，不弹窗遮挡。"
    fi
    if [ -n "$TEXT" ]; then
      brain_say "say" "$TEXT"
    else
      brain_say "greet"
    fi
    echo "[糖糖] 投影在线 → 透明浮现宠物(角落) + 智能说话"
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
