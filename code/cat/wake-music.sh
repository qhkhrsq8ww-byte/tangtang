#!/bin/bash
# 糖糖 · 播放 3 分钟唤醒音乐
MUSIC="/Users/lv/.qclaw/workspace/cat/assets/wake_music_3min.mp3"
afplay "$MUSIC" >/dev/null 2>&1 &
exit 0
