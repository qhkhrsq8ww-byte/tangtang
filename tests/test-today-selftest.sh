#!/bin/bash
# 下午无人值守自测：四步顺序、休息日不禁童、夹具 silent/joined、账本无原话
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CAT="$ROOT/code/cat"
# shellcheck source=../code/cat/cat-lib.sh
. "$CAT/cat-lib.sh"

fail=0
ok() { echo "ok  $1"; }
bad() { echo "fail  $1"; fail=1; }

tmp="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-selftest.XXXXXX")"
export TANGTANG_DATA_DIR="$tmp"
export TANGTANG_TTS=0
export TANGTANG_TURN_STT=0
export TANGTANG_TURN_LLM=0
export TANGTANG_TURN_GAP=0
export TANGTANG_TODAY_GAP=2
export TANGTANG_SCHOOL_START=2026-09-01
export TANGTANG_FIXTURE=1
unset TANGTANG_HOST_HANGHANG TANGTANG_HOST_QIAQIA
unset CAT_CHILD_HOME TANGTANG_CHILD_HOME

bash -n "$CAT/cat-today.sh" || bad "bash -n cat-today.sh"
bash -n "$CAT/cat-hwcheck.sh" || bad "bash -n cat-hwcheck.sh"

# rest-day home → child allowed（即使拨到上学日中午）
export TANGTANG_REST_DAY=1
export CAT_CHILD_HOME=1
TANGTANG_FAKE_TODAY=2026-09-01
TANGTANG_FAKE_TIME=12:00
if tangtang_child_at_school hanghang; then
  bad "rest-day override should allow hanghang"
fi
ok "rest-day home child allowed"

# preview opens no mic
out="$(CAT_NOW='2026-08-28 14:05:00' "$CAT/cat.sh" today --preview hanghang 2>&1)" || bad "preview exit"
echo "$out" | grep -q "preview 不开麦" || bad "preview missing 不开麦"
echo "$out" | grep -q "开麦 " && bad "preview opened mic"
echo "$out" | grep -q "按回车" && bad "preview waited Enter"
ok "preview opens no mic"

# auto four steps order ask→english→move→rest，不按回车
out="$(CAT_NOW='2026-08-28 10:00:00' TANGTANG_TODAY_GAP=2 TANGTANG_DATA_DIR="$tmp" \
  TANGTANG_TTS=0 "$CAT/cat.sh" today-selftest 2>&1)" || { bad "selftest exit"; echo "$out"; }
echo "$out" | grep -q "按回车" && bad "selftest waited Enter"
ask_n="$(echo "$out" | grep -n "^1\\. 问糖糖" | head -n 1 | cut -d: -f1)"
eng_n="$(echo "$out" | grep -n "^2\\. 学英语" | head -n 1 | cut -d: -f1)"
move_n="$(echo "$out" | grep -n "^3\\. 锻炼身体" | head -n 1 | cut -d: -f1)"
rest_n="$(echo "$out" | grep -n "^4\\. 注意休息" | head -n 1 | cut -d: -f1)"
[ -n "$ask_n" ] && [ "$ask_n" -lt "$eng_n" ] && [ "$eng_n" -lt "$move_n" ] && [ "$move_n" -lt "$rest_n" ] \
  || bad "selftest step order $ask_n $eng_n $move_n $rest_n"
echo "$out" | grep -q "should_speak=yes persona=play audience=hanghang" || bad "missing play persona"
echo "$out" | grep -q "stub 听窗 silent" || bad "missing silent stub"
echo "$out" | grep -q "stub 听窗 joined" || bad "missing joined stub"
echo "$out" | grep -q "开麦 " && bad "selftest claimed live 开麦"
echo "$out" | grep -q "汪汪" || bad "hanghang play should 汪汪"
echo "$out" | grep -q "再试一次" && bad "should not chase"
ok "auto four steps + fixtures"

# ledger labels only
/usr/bin/python3 - "$tmp/cat-turn-ledger.json" <<'PY' || bad "ledger labels"
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
rows = d.get("turns") or []
assert len(rows) >= 4, rows
ev = [r.get("event") for r in rows[-4:]]
assert ev == ["ask", "english", "move", "rest"], ev
scenes = [r.get("scene") or r.get("result") for r in rows[-4:]]
assert scenes[0] == "silent", scenes
assert scenes[1] == "joined", scenes
assert scenes[2] == "silent", scenes
assert scenes[3] == "joined", scenes
assert rows[-4]["spoke"] is False
assert rows[-3]["spoke"] is True
assert rows[-2]["spoke"] is False
assert rows[-1]["spoke"] is True
for r in rows[-4:]:
    for badk in ("text", "transcript", "utterance", "pcm", "words", "say", "stt_text"):
        assert badk not in r, r
    assert r.get("window") == "stub"
    assert r.get("persona") == "play"
    assert r.get("audience") == "hanghang" or r.get("who") == "hanghang"
print("ledger four steps ok", scenes)
PY
ok "ledger labels only, no raw text"

# silent → no second prompt; joined → at most one reply
echo "$out" | grep -c "糖糖听到" | grep -Eq '^[12]$' || {
  # canned reply may appear once per joined step (2 times max)
  n="$(echo "$out" | grep -c "糖糖听到" || true)"
  [ "$n" -le 2 ] || bad "joined replied too many times: $n"
}
echo "$out" | grep -q "你怎么不说话" && bad "silence chased"
ok "silence no second prompt; joined at most one reply"

# fake STT not in family memory
if [ -f "$tmp/cat-habits.json" ]; then
  /usr/bin/python3 - "$tmp/cat-habits.json" <<'PY' || bad "habits stored fake STT"
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for e in d.get("events") or []:
    t = e.get("text") or ""
    assert "好啊" not in t, e
    assert "糖糖你好" not in t, e
print("habits no fake stt")
PY
fi
ok "no fake STT in family memory"

# today-report readable
rep="$(TANGTANG_DATA_DIR="$tmp" CAT_NOW='2026-08-28 17:05:00' "$CAT/cat.sh" today-report 2>&1)" || bad "report exit"
echo "$rep" | grep -q "step	audience	persona	spoke	window	scene" || bad "report header"
echo "$rep" | grep -q "ask	hanghang	play	0	stub	silent" || bad "report ask row: $rep"
echo "$rep" | grep -q "english	hanghang	play	1	stub	joined" || bad "report english row"
echo "$rep" | grep -q "move	hanghang	play	0	stub	silent" || bad "report move row"
echo "$rep" | grep -q "rest	hanghang	play	1	stub	joined" || bad "report rest row"
echo "$rep" | grep -q "好啊" && bad "report leaked transcript"
ok "today-report readable"

rm -rf "$tmp"
if [ "$fail" = "0" ]; then
  echo "test-today-selftest ok"
  exit 0
fi
echo "test-today-selftest failed"
exit 1
