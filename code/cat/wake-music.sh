#!/bin/bash
# 糖糖 · 播放 3 分钟唤醒音乐
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"
MUSIC="$CAT_DIR/assets/wake_music_3min.mp3"
[ -f "$MUSIC" ] || exit 1
afplay "$MUSIC" >/dev/null 2>&1 &
exit 0
