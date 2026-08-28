#!/bin/bash
# ============================================================
# 糖糖 V3.1 · 路径迁移脚本（crontab + launchd）
# 将生产环境从旧目录迁移到 tangtang 仓库
# 用法: ./migrate-paths.sh          # 预览
#       ./migrate-paths.sh --apply  # 实际执行
# ============================================================
set -u
OLD_HOME="/Users/lv/.qclaw/workspace/cat"
NEW_HOME="/Users/lv/.qclaw/workspace/tangtang"
APPLY="${1:-}"
echo "═══════════════════════════════════════════"
echo "糖糖路径迁移：$OLD_HOME → $NEW_HOME"
echo "═══════════════════════════════════════════"

# ---------- 1. crontab 迁移 ----------
echo ""
echo "【1/2】crontab 迁移"
if crontab -l > /tmp/tangtang_cron_backup.txt 2>/dev/null; then
  echo "  ✅ 已备份当前 crontab → /tmp/tangtang_cron_backup.txt"
  NEW_CRON=$(sed "s|$OLD_HOME|$NEW_HOME/code/cat|g" /tmp/tangtang_cron_backup.txt)
  # 标记已废弃的一次性唤醒任务（2026-08-28 已执行完）
  NEW_CRON=$(echo "$NEW_CRON" | sed 's|^0 7 28 8 \*|# [DEPRECATED-20260828] 0 7 28 8 *|; s|^1 7 28 8 \*|# [DEPRECATED-20260828] 1 7 28 8 *|')
  if [ "$APPLY" = "--apply" ]; then
    echo "$NEW_CRON" | crontab - && echo "  ✅ crontab 已迁移到新路径"
  else
    echo "  📋 预览（--apply 生效）："
    echo "$NEW_CRON" | grep -E "tangtang/code/cat|DEPRECATED" | head -20
  fi
else
  echo "  ⚠️ 无法读取 crontab"
fi

# ---------- 2. launchd 迁移 ----------
echo ""
echo "【2/2】launchd 迁移"
PLIST="$HOME/Library/LaunchAgents/com.tangtang.cat-server.plist"
if [ -f "$PLIST" ]; then
  echo "  ✅ 找到生产 plist: $PLIST"
  # 生成迁移版本（仅替换目录路径，不改其他配置）
  sed "s|$OLD_HOME|$NEW_HOME/code/cat|g" "$PLIST" > /tmp/com.tangtang.cat-server.new.plist
  if [ "$APPLY" = "--apply" ]; then
    cp /tmp/com.tangtang.cat-server.new.plist "$PLIST" && echo "  ✅ plist 已迁移到新路径"
    echo "  ℹ️ 需要重启服务: launchctl unload $PLIST && launchctl load $PLIST"
  else
    echo "  📋 迁移后路径预览："
    grep -E "directory|WorkingDirectory" /tmp/com.tangtang.cat-server.new.plist
  fi
else
  echo "  ⚠️ 生产 plist 不存在（跳过）"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "完成。运行 ./migrate-paths.sh --apply 生效"
echo "═══════════════════════════════════════════"
