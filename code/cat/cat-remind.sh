#!/bin/bash
# ============================================================
# 猫咪「糖糖」定时触发（走智能大脑，带情绪决策）
# 用法: ./cat-remind.sh <事件> [参数]
#   事件: rest(久坐/少玩手机)/sleep(晚安)/wake(早安)/meal lunch|dinner(饭点)
#         random(随机撒娇)/home(回家)/play(出去玩)/homework(写作业)/tidy(整理房间)
#         exercise(运动)/emotion(情绪)/weather(天气)/water(喝水)
# 大脑决定话术+情绪 → 自适应投影状态(开投影上屏+出声；没开仅声音)
# ============================================================
CAT_DIR="/Users/lv/.qclaw/workspace/cat"
EVENT="${1:-rest}"
ARG="${2:-}"

# 记录一下即将说的话（供画面轮询冒泡），先由大脑生成
text="$(/usr/bin/python3 "$CAT_DIR/cat-brain.py" "$EVENT" "$ARG" 2>/dev/null | sed 's/\t.*//')"
if [ -n "$text" ]; then
  echo "$text" > "$CAT_DIR/cat-mood.txt"
fi

# 投影在线则上屏+出声，否则仅出声
if nc -z -w 3 "192.168.31.104" "61949" 2>/dev/null; then
  "$CAT_DIR/cat.sh" -s >/dev/null 2>&1
  "$CAT_DIR/cat-talk.sh" "$EVENT" "$ARG"
else
  "$CAT_DIR/cat-talk.sh" "$EVENT" "$ARG"
fi
exit 0
