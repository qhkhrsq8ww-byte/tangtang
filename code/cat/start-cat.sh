#!/bin/bash
# 糖糖 · 一键启动（投屏后运行）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

if ! tangtang_ensure_stage; then
  echo "糖糖舞台启动失败，已停止后续启动流程。" >&2
  exit 1
fi
if ! tangtang_ensure_pet; then
  echo "糖糖宠物页面启动失败，请检查本地页面服务。" >&2
  exit 1
fi

echo "🐾 糖糖全屏舞台已启动。"
echo "   1) 菜单栏『屏幕镜像』选投影（不弹窗、不遮挡）。"
echo "   2) 在 Mac 上点一下糖糖画面 → 进 Safari 全屏。"
echo "   测试： ./cat.sh \"糖糖来啦\""
