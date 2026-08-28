#!/bin/bash
# OpenClaw 下午实测：preview、--now 不挂死、四步顺序、hwcheck 非 Darwin 跳过
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CAT="$ROOT/code/cat"
# shellcheck source=../code/cat/cat-lib.sh
. "$CAT/cat-lib.sh"

fail=0
ok() { echo "ok  $1"; }
bad() { echo "fail  $1"; fail=1; }

export TZ=Asia/Shanghai
export TANGTANG_TTS=0
export TANGTANG_TURN_STT=0
export TANGTANG_TURN_LLM=0
export TANGTANG_TURN_GAP=0
export TANGTANG_OPENCLAW_GAP=0
export TANGTANG_OPENCLAW_WAIT_CAP=0
export TANGTANG_SCHOOL_START=2026-09-01
unset TANGTANG_CALENDAR TANGTANG_REST_DAYS TANGTANG_TODAY_PLAN
unset TANGTANG_HOST_HANGHANG TANGTANG_HOST_QIAQIA

tmp="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-openclaw.XXXXXX")"
export TANGTANG_DATA_DIR="$tmp"
trap 'rm -rf "$tmp"' EXIT

bash -n "$CAT/openclaw-today.sh" || bad "bash -n openclaw-today.sh"
bash -n "$CAT/cat.sh" || bad "bash -n cat.sh"
bash -n "$CAT/cat-today.sh" || bad "bash -n cat-today.sh"
/usr/bin/python3 "$CAT/cat-turn.py" selftest >/dev/null || bad "cat-turn.py selftest"

# 1) ./cat.sh openclaw --preview ：一屏计划 + 四步顺序 + 不开麦
out="$(TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=13:00 \
  "$CAT/cat.sh" openclaw --preview 2>&1)" || { bad "preview exit"; out=""; }
echo "$out" | grep -q "休息日 · 航航 · 14:00问糖糖 → 15:00英语 → 16:00锻炼 → 17:00休息" \
  || bad "one-screen plan"
echo "$out" | grep -q "preview 不开麦" || bad "preview should say 不开麦"
echo "$out" | grep -qE "开麦 [0-9]+s" && bad "preview opened mic log"
echo "$out" | grep -qi "录音" && bad "preview claimed 录音"
echo "$out" | grep -q "按回车" && bad "preview should not wait 回车"
ask_n="$(echo "$out" | grep -n "14:00  1. 问糖糖" | head -n 1 | cut -d: -f1)"
eng_n="$(echo "$out" | grep -n "15:00  2. 学英语" | head -n 1 | cut -d: -f1)"
move_n="$(echo "$out" | grep -n "16:00  3. 锻炼身体" | head -n 1 | cut -d: -f1)"
rest_n="$(echo "$out" | grep -n "17:00  4. 注意休息" | head -n 1 | cut -d: -f1)"
[ -n "$ask_n" ] && [ -n "$eng_n" ] && [ -n "$move_n" ] && [ -n "$rest_n" ] \
  || bad "preview missing timed steps"
if [ -n "$ask_n" ] && [ -n "$eng_n" ] && [ -n "$move_n" ] && [ -n "$rest_n" ]; then
  [ "$ask_n" -lt "$eng_n" ] && [ "$eng_n" -lt "$move_n" ] && [ "$move_n" -lt "$rest_n" ] \
    || bad "preview step order $ask_n $eng_n $move_n $rest_n"
fi
echo "$out" | grep -q "汪汪～ 航航" || bad "play ask line"
echo "$out" | grep -q "=== today-report ===" || bad "preview missing today-report"
echo "$out" | grep -q "ask	skip" || bad "preview report ask skip"
echo "$out" | grep -q "english	skip" || bad "preview report english skip"
echo "$out" | grep -q "move	skip" || bad "preview report move skip"
echo "$out" | grep -q "rest	skip" || bad "preview report rest skip"
echo "$out" | grep -q "hello" && bad "preview leaked child text"
ok "preview plan + four-step order"

# 2) --who qiaqia
out_q="$(TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=13:00 \
  TANGTANG_DATA_DIR="$(mktemp -d "${tmp}/qia.XXXXXX")" \
  "$CAT/cat.sh" openclaw --preview --who qiaqia 2>&1)" || { bad "preview qiaqia exit"; out_q=""; }
echo "$out_q" | grep -q "休息日 · 洽洽 · 14:00问糖糖 → 15:00英语 → 16:00锻炼 → 17:00休息" \
  || bad "qiaqia plan"
echo "$out_q" | grep -q "汪汪" && bad "friend should not 汪汪"
echo "$out_q" | grep -q "洽洽要是想聊" || bad "friend ask line"
ok "who qiaqia"

# 3) Linux --now：不挂死、hwcheck 跳过、四步顺序、today-report
start=$(date +%s)
out_now="$(TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=13:10 \
  TANGTANG_OPENCLAW_GAP=0 TANGTANG_TTS=0 \
  "$CAT/cat.sh" openclaw --now 2>&1)" || { bad "--now exit"; out_now=""; }
end=$(date +%s)
elapsed=$((end - start))
[ "$elapsed" -lt 25 ] || bad "--now hung ${elapsed}s"
echo "$out_now" | grep -q "=== hwcheck ===" || bad "--now missing hwcheck"
echo "$out_now" | grep -q "非 Darwin：跳过麦/音箱实测" || bad "linux hwcheck should skip"
echo "$out_now" | grep -q "=== hwcheck skip ===" || bad "linux hwcheck skip footer"
echo "$out_now" | grep -q "=== hwcheck fail ===" && bad "linux hwcheck must not fail"
echo "$out_now" | grep -q "一次跑完四步" || bad "--now banner"
echo "$out_now" | grep -qE "开麦 [0-9]+s" && bad "--now linux opened mic"
ask_n="$(echo "$out_now" | grep -n "14:00  1. 问糖糖" | head -n 1 | cut -d: -f1)"
eng_n="$(echo "$out_now" | grep -n "15:00  2. 学英语" | head -n 1 | cut -d: -f1)"
move_n="$(echo "$out_now" | grep -n "16:00  3. 锻炼身体" | head -n 1 | cut -d: -f1)"
rest_n="$(echo "$out_now" | grep -n "17:00  4. 注意休息" | head -n 1 | cut -d: -f1)"
[ -n "$ask_n" ] && [ -n "$eng_n" ] && [ -n "$move_n" ] && [ -n "$rest_n" ] \
  || bad "--now missing timed steps"
if [ -n "$ask_n" ] && [ -n "$eng_n" ] && [ -n "$move_n" ] && [ -n "$rest_n" ]; then
  [ "$ask_n" -lt "$eng_n" ] && [ "$eng_n" -lt "$move_n" ] && [ "$move_n" -lt "$rest_n" ] \
    || bad "--now step order $ask_n $eng_n $move_n $rest_n"
fi
echo "$out_now" | grep -q "=== today-report ===" || bad "--now missing today-report"
echo "$out_now" | grep -q "ask	skip" || bad "--now report ask"
echo "$out_now" | grep -q "rest	skip" || bad "--now report rest"
echo "$out_now" | grep -E "transcript|utterance" && bad "--now leaked transcript key"
ok "--now linux four steps + hwcheck skip (${elapsed}s)"

# 4) 已过点：不等待。FAKE_TIME 18:00 + 无 --now 也应立刻做完
start=$(date +%s)
out_late="$(TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=18:05 \
  TANGTANG_OPENCLAW_GAP=0 TANGTANG_OPENCLAW_WAIT_CAP=7200 \
  "$CAT/cat.sh" openclaw 2>&1)" || { bad "late exit"; out_late=""; }
end=$(date +%s)
elapsed=$((end - start))
[ "$elapsed" -lt 20 ] || bad "late wait hung ${elapsed}s"
echo "$out_late" | grep -q "已过，现在做" || bad "late should run now"
echo "$out_late" | grep -q "14:00  1. 问糖糖" || bad "late missing step 1"
echo "$out_late" | grep -q "17:00  4. 注意休息" || bad "late missing step 4"
ok "past-hour runs now (${elapsed}s)"

# 5) 默认未到点 + WAIT_CAP=0：不睡，现在做
start=$(date +%s)
out_cap="$(TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=10:00 \
  TANGTANG_OPENCLAW_GAP=0 TANGTANG_OPENCLAW_WAIT_CAP=0 \
  "$CAT/cat.sh" openclaw 2>&1)" || { bad "cap exit"; out_cap=""; }
end=$(date +%s)
elapsed=$((end - start))
[ "$elapsed" -lt 20 ] || bad "cap wait hung ${elapsed}s"
echo "$out_cap" | grep -q "14:00  1. 问糖糖" || bad "cap missing steps"
ok "wait cap does not hang (${elapsed}s)"

# 6) hwcheck / today-report 子命令；./cat.sh today 仍在
hw="$("$CAT/cat.sh" hwcheck 2>&1)" || { bad "hwcheck exit"; hw=""; }
echo "$hw" | grep -q "=== hwcheck skip ===" || bad "hwcheck skip on linux"
echo "$hw" | grep -q "=== hwcheck fail ===" && bad "linux hwcheck fail"
rep="$("$CAT/cat.sh" today-report hanghang 2>&1)" || { bad "today-report exit"; rep=""; }
echo "$rep" | grep -q "=== today-report ===" || bad "today-report header"
echo "$rep" | grep -qE "ask	(skip|joined|silent|oppose|wont|unclear|defer)" \
  || bad "today-report ask label"
feat="$("$CAT/cat.sh" features 2>&1)"
echo "$feat" | grep -q "./cat.sh openclaw" || bad "features missing openclaw"
echo "$feat" | grep -q "./cat.sh today" || bad "features missing today"
[ -x "$CAT/openclaw-today.sh" ] || bad "openclaw-today.sh not executable"
[ -x "$CAT/cat-today.sh" ] || bad "cat-today.sh not executable"
ok "hwcheck + today-report + today still there"

# 7) 账本没有儿童原话字段
/usr/bin/python3 - "$tmp" <<'PY' || bad "ledger json leaked text"
import json, os, sys
root = sys.argv[1]
path = os.path.join(root, "cat-turn-ledger.json")
if not os.path.isfile(path):
    sys.exit(0)
data = json.load(open(path, encoding="utf-8"))
for row in data.get("turns") or []:
    for k in ("text", "transcript", "utterance", "pcm", "words", "say"):
        if k in row:
            raise SystemExit("leaked %s" % k)
PY
ok "ledger labels only"

if [ "$fail" = "0" ]; then
  echo "test-openclaw-plan ok"
  exit 0
fi
echo "test-openclaw-plan failed"
exit 1
