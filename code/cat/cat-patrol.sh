#!/bin/bash
# ============================================================
# 糖糖 · 23:30 睡觉巡逻（投影优先，电视声音兜底）
# 1) 投影 AirPlay 通 → 开投屏糖糖形象 + 播语音催睡觉
# 2) 投影不通 → 检测客厅电视声音(麦克风音量)：
#      有声音 → 播提示语催小朋友睡觉
#      没声音 → 静默(已睡)
# 语音内容: "实在太晚了，洽洽，你真的要睡觉啦！"
# ============================================================
CAT_DIR="/Users/lv/tangtang/cat"
PROJECTOR_IP="192.168.31.104"
AIRPLAY_PORT="61949"
MSG="实在太晚了，洽洽，你真的要睡觉啦！"
LOG="$CAT_DIR/logs/cat-patrol-$(date +%Y%m%d).log"

log(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# ---- 1. 先试投影 ----
if nc -z -w 3 "$PROJECTOR_IP" "$AIRPLAY_PORT" 2>/dev/null; then
  log "投影在线 → 上屏糖糖形象 + 播语音"
  # 起本地服务(若有)
  if ! curl -s -o /dev/null "http://127.0.0.1:8080/cat-stage.html"; then
    nohup /usr/bin/python3 -m http.server 8080 --bind 127.0.0.1 --directory "$CAT_DIR" >/tmp/cathttp.log 2>&1 &
    sleep 2
  fi
  # 投屏糖糖形象
  open "http://127.0.0.1:8080/cat-stage.html"
  osascript -e 'tell application "Safari" to if (count of windows) > 0 then set URL of front document to "http://127.0.0.1:8080/cat-stage.html"' 2>/dev/null
  # 播语音（投影蓝牙若连上则走投影出声）
  "$CAT_DIR/cat-say.sh" "$MSG" cute
  log "完成：语音已播 ($MSG)"
  exit 0
fi

log "投影离线 → 检测电视声音"
# ---- 2. 投影不通，检测客厅电视声音 ----
# 录 5 秒环境音，音量 >= 阈值(0.02) 视为电视在响
NOISE="$("$CAT_DIR/check_noise" 5 0.02 2>/dev/null)"
echo "$NOISE" >> "$LOG"
if echo "$NOISE" | grep -q "LOUD"; then
  log "检测到客厅有声音(电视) → 播提示语催睡"
  "$CAT_DIR/cat-say.sh" "$MSG" cute
  log "完成：提示语已播 ($MSG)"
else
  log "客厅安静 → 小朋友已睡，静默不打扰"
fi
exit 0
