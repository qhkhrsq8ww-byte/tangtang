#!/bin/bash
# 跑仓库里现有自测 + tests/ 新测。失败则非零退出。
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CAT="$ROOT/code/cat"
fail=0

run() {
  echo "=== $1 ==="
  if "$@"; then
    echo "PASS $1"
  else
    echo "FAIL $1"
    fail=1
  fi
}

run /usr/bin/python3 "$CAT/tangtang_paths.py" selftest
run /usr/bin/python3 "$CAT/cat-turn.py" selftest
run "$CAT/cat-schedule.sh" selftest
run "$SCRIPT_DIR/test-today-plan.sh"
run "$SCRIPT_DIR/test-today-selftest.sh"
run "$SCRIPT_DIR/test-hwcheck.sh"

if [ "$fail" = "0" ]; then
  echo "ALL tests ok"
  exit 0
fi
echo "SOME tests failed"
exit 1
