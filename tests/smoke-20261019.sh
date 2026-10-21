#!/bin/bash
# ============================================================
# 糖糖 · 全面冒烟测试（2026-10-19 规整版）
# 用法: bash tests/smoke-20261019.sh
# 目标: 运行目录 ~/tangtang/cat（默认）+ 仓库自身
# ============================================================
LIVE="${TANGTANG_LIVE_DIR:-$HOME/tangtang/cat}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS $1"; }
bad(){ FAIL=$((FAIL+1)); echo "  FAIL $1"; }

echo "== 1. 脚本语法（bash -n）=="
for f in "$LIVE"/*.sh; do
  if bash -n "$f" 2>/dev/null; then ok "bash -n $(basename "$f")"; else bad "bash -n $(basename "$f")"; fi
done

echo "== 2. Python 语法（py_compile）=="
for f in "$LIVE"/*.py; do
  if /usr/bin/python3 -m py_compile "$f" 2>/dev/null; then ok "py_compile $(basename "$f")"; else bad "py_compile $(basename "$f")"; fi
done

echo "== 3. 密钥防护 =="
if [ -f "$LIVE/.llm_key" ]; then
  [ "$(stat -f '%Lp' "$LIVE/.llm_key")" = "600" ] && ok ".llm_key 权限 600" || bad ".llm_key 权限"
else bad ".llm_key 不存在"; fi
[ -f "$LIVE/cat-stt-config.sh" ] && [ "$(stat -f '%Lp' "$LIVE/cat-stt-config.sh")" = "600" ] && ok "cat-stt-config.sh 权限 600" || bad "cat-stt-config.sh 权限/缺失"
grep -q "llm_key" "$REPO/.gitignore" && ok ".gitignore 覆盖 .llm_key" || bad ".gitignore 缺 .llm_key"
( cd "$REPO"; ig=0; for p in code/cat/.llm_key code/cat/.baidu_token code/cat/cat-stt-config.sh; do git check-ignore -q "$p" || ig=1; done; [ $ig = 0 ] ) && ok "git check-ignore 三密钥全部忽略" || bad "git check-ignore 未全部忽略"
( cd "$REPO" && git status --porcelain | grep -qE "llm_key|baidu_token|stt-config" ) && bad "暂存区含密钥文件" || ok "暂存区无密钥文件"

echo "== 4. HTTP 安全（cat-serve :8080，若在运行）=="
if curl -s --max-time 3 -o /dev/null http://127.0.0.1:8080/cat-face.html; then
  c1=$(curl -s --max-time 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/.llm_key)
  c2=$(curl -s --max-time 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/cat-face.html)
  [ "$c1" = "404" ] && ok "隐藏文件 404" || bad "隐藏文件 HTTP $c1"
  [ "$c2" = "200" ] && ok "正常文件 200" || bad "正常文件 HTTP $c2"
else
  echo "  SKIP cat-serve 未运行"
fi

echo "== 5. 人设记忆注入 =="
/usr/bin/python3 - "$LIVE" <<'PYEOF' && ok "build_persona 含记忆" || bad "build_persona 缺记忆"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("cc", sys.argv[1] + "/cat-chat.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
p = m.build_persona()
sys.exit(0 if ("昵称" in p or "心情" in p) else 1)
PYEOF

echo "== 6. 静音闸（确定性）=="
q1=$(TANGTANG_QUIET_START=00:00 TANGTANG_QUIET_END=23:59 /usr/bin/python3 "$LIVE/tangtang-quiet-hours.py" 2>/dev/null)
[ "$q1" = "quiet" ] && ok "整窗配置 → quiet" || bad "整窗配置 → $q1"
q2=$(TANGTANG_INTERACTIVE=1 /usr/bin/python3 "$LIVE/tangtang-quiet-hours.py" 2>/dev/null)
[ "$q2" != "quiet" ] && ok "INTERACTIVE=1 → 可发声" || bad "INTERACTIVE 未旁路"

echo "== 7. LaunchAgent =="
launchctl list | grep -q com.tangtang.cat-server && ok "cat-server 已加载" || bad "cat-server 未加载"
launchctl list | grep -q com.tangtang.proactive && ok "proactive 已加载" || bad "proactive 未加载"

echo "== 8. 关键文件就位 =="
for f in cat-talk.sh cat-voice-chat.sh cat-stt-baidu.sh cat-proactive-bridge.sh cat-serve.py deploy.sh tangtang-quiet-hours.py; do
  if [ "$f" = "deploy.sh" ]; then
    [ -x "$REPO/code/cat/$f" ] && ok "$f 可执行(repo侧)" || bad "$f 缺失(repo)";
  else
    [ -x "$LIVE/$f" ] && ok "$f 可执行" || bad "$f 缺失或不可执行";
  fi
done

echo "== 9. repo 与 live 同步（.py/.sh/.mjs）=="
DRIFT=0
for f in "$REPO"/code/cat/*.py "$REPO"/code/cat/*.sh "$REPO"/code/cat/*.mjs; do
  b=$(basename "$f")
  case "$b" in cat-stt-config.sh|tangtang-config.sh) continue;; esac  # 本机配置文件（gitignored），不参与漂移检查
  if [ -f "$REPO/code/cat/.pinned-live-files" ] && grep -qxF "$b" "$REPO/code/cat/.pinned-live-files" 2>/dev/null; then
    echo "  PINNED: $b（受控钉住，见 .pinned-live-files）"; continue
  fi
  [ "$b" = "cat-stt-config.sh" ] && continue
  if [ ! -f "$LIVE/$b" ]; then
    DRIFT=1
    echo "  MISSING: $b (repo 有、live 缺失)"
    continue
  fi
  cmp -s "$f" "$LIVE/$b" || { DRIFT=1; echo "  DRIFT: $b"; }
done
[ "$DRIFT" = "0" ] && ok "脚本零漂移" || bad "存在漂移文件（见上）"

echo
echo "===== 结果: PASS=$PASS FAIL=$FAIL ====="
[ "$FAIL" = "0" ]
