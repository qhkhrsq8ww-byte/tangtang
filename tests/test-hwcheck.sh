#!/bin/bash
# Linux hwcheck：跳过实声，exit 0（skip-not-fail），不假装测过客厅麦/音箱
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CAT="$ROOT/code/cat"

fail=0
ok() { echo "ok  $1"; }
bad() { echo "fail  $1"; fail=1; }

bash -n "$CAT/cat-hwcheck.sh" || bad "bash -n cat-hwcheck.sh"

out="$("$CAT/cat.sh" hwcheck 2>&1)" || { echo "hwcheck exit $?"; echo "$out"; bad "hwcheck nonzero"; out=""; }
echo "$out" | grep -q "云上无客厅麦/音箱，跳过实声" || bad "missing skip message"
echo "$out" | grep -q "skip-not-fail" || bad "missing skip-not-fail"
echo "$out" | grep -q "^os	Linux" || echo "$out" | grep -qi "Linux" || bad "should detect Linux"
echo "$out" | grep -q "MAONO" && bad "linux hwcheck should not claim MAONO"
echo "$out" | grep -q "avfoundation :2" && bad "linux hwcheck should not claim avfoundation :2"
echo "$out" | grep -qiE "测过客厅|实机已验" && bad "must not claim living-room devices tested"
ok "linux hwcheck skip-not-fail"

if [ "$fail" = "0" ]; then
  echo "test-hwcheck ok"
  exit 0
fi
echo "test-hwcheck failed"
exit 1
