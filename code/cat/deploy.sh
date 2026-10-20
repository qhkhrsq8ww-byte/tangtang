#!/bin/bash
# ============================================================
# 糖糖 · 部署脚本（repo → 运行目录，单向）
# 用法: 在 repo/code/cat 下执行 ./deploy.sh
# 规则: 代码与 UI 从仓库流向运行目录；
#       密钥(cat-stt-config.sh/.llm_key/.baidu_token)与运行时状态
#       (state/memory/history/habits/mood)永不被覆盖
# ============================================================
SRC="$(cd "$(dirname "$0")" && pwd)"
DST="${TANGTANG_LIVE_DIR:-$HOME/tangtang/cat}"
[ -d "$DST" ] || { echo "运行目录不存在: $DST" >&2; exit 1; }
rsync -av \
  --exclude 'bin/' --exclude 'logs/' --exclude '__pycache__/' \
  --exclude 'cat-stt-config.sh' --exclude '.llm_key' --exclude '.baidu_token' \
  --exclude 'cat-state.json' --exclude 'cat-memory.json' \
  --exclude 'cat-chat-history.json' --exclude 'cat-habits.json' \
  --exclude 'cat-mood.txt' --exclude 'cat-presentation-action.json' \
  "$SRC/" "$DST/"
echo "部署完成 → $DST （密钥与运行时数据未动）"
