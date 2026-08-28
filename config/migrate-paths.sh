#!/bin/bash
# ============================================================
# 糖糖 · 路径迁移（crontab + launchd）
# 旧目录仅通过 OLD_TANGTANG_HOME 传入。仓库运行时不得写死本机 cat 绝对路径。
#
# 用法:
#   TANGTANG_HOME=/path/to/tangtang OLD_TANGTANG_HOME=/old/cat ./migrate-paths.sh
#   TANGTANG_HOME=... OLD_TANGTANG_HOME=... ./migrate-paths.sh --apply
#
# launchd / crontab 只安装到当前用户（~/Library/LaunchAgents + 用户 crontab）。
# 禁止 sudo / root / /Library/LaunchDaemons。
# ============================================================
set -u
OLD_HOME="${OLD_TANGTANG_HOME:-}"
NEW_HOME="${TANGTANG_HOME:?TANGTANG_HOME is required}"
APPLY="${1:-}"
echo "═══════════════════════════════════════════"
echo "糖糖路径迁移：\${OLD_TANGTANG_HOME} → \${TANGTANG_HOME}"
echo "  OLD=${OLD_HOME:-'(unset)'}"
echo "  NEW=${NEW_HOME}"
echo "═══════════════════════════════════════════"

if [ -z "$OLD_HOME" ]; then
  echo "  ⚠️ OLD_TANGTANG_HOME unset — skip rewrite, only show target"
fi

# ---------- 1. crontab 迁移（用户 crontab，不是 root） ----------
echo ""
echo "【1/2】crontab 迁移（crontab -l，非 sudo）"
if crontab -l > /tmp/tangtang_cron_backup.txt 2>/dev/null; then
  echo "  ✅ 已备份当前 crontab → /tmp/tangtang_cron_backup.txt"
  if [ -n "$OLD_HOME" ]; then
    NEW_CRON=$(sed "s|$OLD_HOME|$NEW_HOME/code/cat|g" /tmp/tangtang_cron_backup.txt)
  else
    NEW_CRON=$(cat /tmp/tangtang_cron_backup.txt)
  fi
  if [ "$APPLY" = "--apply" ]; then
    echo "$NEW_CRON" | crontab - && echo "  ✅ crontab 已迁移到 TANGTANG_HOME"
  else
    echo "  📋 预览（--apply 生效）"
    echo "$NEW_CRON" | grep -E "code/cat|DEPRECATED" | head -20
  fi
else
  echo "  ⚠️ 无法读取用户 crontab"
fi

# ---------- 2. launchd 迁移（用户 LaunchAgents，不是 LaunchDaemons） ----------
echo ""
echo "【2/2】launchd 迁移（~/Library/LaunchAgents）"
PLIST="${HOME}/Library/LaunchAgents/com.tangtang.daemon.plist"
if [ -f "$PLIST" ]; then
  echo "  ✅ 找到用户 plist: $PLIST"
  if [ -n "$OLD_HOME" ]; then
    sed "s|$OLD_HOME|$NEW_HOME/code/cat|g" "$PLIST" > /tmp/com.tangtang.daemon.new.plist
  else
    cp "$PLIST" /tmp/com.tangtang.daemon.new.plist
  fi
  if [ "$APPLY" = "--apply" ]; then
    cp /tmp/com.tangtang.daemon.new.plist "$PLIST" && echo "  ✅ plist 已指向 TANGTANG_HOME"
    echo "  ℹ️ 需要: launchctl unload $PLIST && launchctl load $PLIST"
    echo "  ℹ️ 不要使用 sudo launchctl / /Library/LaunchDaemons"
  else
    echo "  📋 预览 WorkingDirectory："
    grep -E "WorkingDirectory|TANGTANG" /tmp/com.tangtang.daemon.new.plist || true
  fi
else
  echo "  ⚠️ 用户 plist 不存在。复制 config/com.tangtang.daemon.plist.example"
  echo "     到 ~/Library/LaunchAgents/ 并把 __TANGTANG_HOME__ 换成 \$TANGTANG_HOME"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "完成。root 安装不在范围内。"
echo "═══════════════════════════════════════════"
