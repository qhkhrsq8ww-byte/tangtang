#!/bin/bash
# ============================================================
# 糖糖 · 一键启动（投屏后运行）
# 1) 起本地服务  2) 开全屏舞台页（大钟+角落糖糖）
# 舞台页点一下画面即可进 Safari 全屏（浏览器要求用户手势）。
# 菜单栏『屏幕镜像』选 OBE_R3Ultra 旗舰版(OBE)501 → 全屏投到投影。
# 不主动弹系统设置窗口（会遮挡投影画面）。
# ============================================================
CAT_DIR="/Users/lv/.qclaw/workspace/cat"
cd "$CAT_DIR"

# 本地服务
if ! curl -s -o /dev/null "http://127.0.0.1:8080/cat-stage.html"; then
  nohup /usr/bin/python3 -m http.server 8080 --bind 0.0.0.0 --directory "$CAT_DIR" >/tmp/cathttp.log 2>&1 &
  sleep 2
fi

# 开全屏舞台页
open "http://127.0.0.1:8080/cat-stage.html"

echo "🐱 糖糖全屏舞台已启动。"
echo "   1) 菜单栏『屏幕镜像』图标(顶部右侧) 选 OBE_R3Ultra 旗舰版(OBE)501（不弹窗、不遮挡）。"
echo "   2) 在 Mac 上点一下糖糖画面 → 进 Safari 全屏，整屏铺满投影。"
echo "   测试： ./cat.sh \"小主人，糖糖来啦\""
