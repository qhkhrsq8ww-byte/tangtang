#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="/usr/bin/python3"
PASS=0
FAIL=0
ok(){ echo "PASS $1"; PASS=$((PASS+1)); }
bad(){ echo "FAIL $1"; FAIL=$((FAIL+1)); }

check(){
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$name"; else bad "$name"; fi
}

check "family json valid" "$PY" -m json.tool "$ROOT/data/family.json"
check "persona grandpa" "$PY" "$ROOT/code/cat/tangtang-profile.py" --speaker grandpa
check "persona grandma" "$PY" "$ROOT/code/cat/tangtang-profile.py" --speaker grandma
check "persona dad" "$PY" "$ROOT/code/cat/tangtang-profile.py" --speaker dad
check "persona qiaqia" "$PY" "$ROOT/code/cat/tangtang-profile.py" --speaker qiaqia
check "persona hanghang" "$PY" "$ROOT/code/cat/tangtang-profile.py" --speaker hanghang
check "alias 姐姐→qiaqia" "$PY" "$ROOT/code/cat/tangtang-profile.py" --speaker 姐姐
check "unknown stays unknown" "$PY" "$ROOT/code/cat/tangtang-profile.py" --speaker unknown
check "chat syntax" "$PY" -m py_compile "$ROOT/code/cat/cat-chat.py"
check "resolver syntax" "$PY" -m py_compile "$ROOT/code/cat/tangtang-profile.py"
check "quiet syntax" "$PY" -m py_compile "$ROOT/code/cat/tangtang-quiet-hours.py"
check "presence syntax" "$PY" -m py_compile "$ROOT/code/cat/cat-presence.py"
check "voice syntax" bash -n "$ROOT/code/cat/cat-voice.sh"
check "talk syntax" bash -n "$ROOT/code/cat/cat-talk.sh"

for p in grandpa grandma dad qiaqia hanghang 姐姐 弟弟; do
  profile="$($PY "$ROOT/code/cat/tangtang-profile.py" --speaker "$p" | $PY -c 'import json,sys; print(json.load(sys.stdin)["profile"])')"
  case "$p:$profile" in
    grandpa:elder|grandma:elder|dad:adult|qiaqia:friend|hanghang:play|姐姐:friend|弟弟:play) ok "profile mapping $p" ;;
    *) bad "profile mapping $p -> $profile" ;;
  esac
done

# Fixed-time checks for the quiet-hours gate.
if TANGTANG_QUIET_START=22:30 TANGTANG_QUIET_END=07:00 "$PY" - <<'PY'
import importlib.util, datetime
spec=importlib.util.spec_from_file_location('q','code/cat/tangtang-quiet-hours.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
assert m.is_quiet(datetime.datetime(2026,8,28,23,0))
assert m.is_quiet(datetime.datetime(2026,8,28,6,30))
assert not m.is_quiet(datetime.datetime(2026,8,28,12,0))
PY
then ok "quiet-hours boundary"; else bad "quiet-hours boundary"; fi

echo "RESULT PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
