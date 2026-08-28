#!/bin/bash
# 小朋友反应 A–I：关键词夹具，断言回/不回与冷却。不开真麦。
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CAT="$ROOT/code/cat"
REACT="$CAT/cat-react.py"
TURN="$CAT/cat-turn.sh"
fail=0

tmp="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-react-test.XXXXXX")"
export TANGTANG_DATA_DIR="$tmp"
export TANGTANG_TTS=0
export TANGTANG_TURN_STT=0
export TANGTANG_TURN_LLM=0
export TANGTANG_TURN_GAP=0
export TANGTANG_SCHOOL_START=2026-09-01
export TANGTANG_HOME_HANGHANG=16:00
export TANGTANG_HOME_QIAQIA=18:00
unset TANGTANG_HOST_HANGHANG TANGTANG_HOST_QIAQIA
export TANGTANG_FAKE_TODAY=2026-09-01
export TANGTANG_FAKE_TIME=16:20

silent="$tmp/silent.pcm"
tone="$tmp/tone.pcm"
quiet="$tmp/quiet.pcm"
/usr/bin/python3 "$CAT/cat-turn.py" pcm silent "$silent"
/usr/bin/python3 "$CAT/cat-turn.py" pcm tone "$tone"
/usr/bin/python3 "$CAT/cat-turn.py" pcm quiet "$quiet"

classify() {
  /usr/bin/python3 "$REACT" classify --print --event english --audience "$1" --persona "$2" --text "$3" --rms "$4" ${5:+--timeout}
}

scene_of() { /usr/bin/python3 -c "import json,sys; print(json.loads(sys.argv[1])['scene'])" "$1"; }
speak_of() { /usr/bin/python3 -c "import json,sys; print(json.loads(sys.argv[1])['speak_again'])" "$1"; }
reply_of() { /usr/bin/python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('reply') or '')" "$1"; }

check() {
  local name="$1" got="$2" want="$3"
  if [ "$got" != "$want" ]; then
    echo "fail $name: got [$got] want [$want]"
    fail=1
  fi
}

# A 配合
j="$(classify hanghang play 好 2000)"
check A-scene "$(scene_of "$j")" joined
check A-speak "$(speak_of "$j")" True
echo "$(reply_of "$j")" | grep -q "汪汪" || { echo "fail A play 汪汪"; fail=1; }
echo "$(reply_of "$j")" | grep -qE "真好|真厉害|好高兴" || { echo "fail A play praise: $j"; fail=1; }
jf="$(classify qiaqia friend 好啊 2000)"
check A-friend-scene "$(scene_of "$jf")" joined
echo "$(reply_of "$jf")" | grep -q "汪汪" || { echo "fail A friend 汪汪"; fail=1; }
echo "$(reply_of "$jf")" | grep -q "航航" && { echo "fail A friend named 航航"; fail=1; }
[ "$(reply_of "$j")" != "$(reply_of "$jf")" ] || { echo "fail A friend==play"; fail=1; }

# B 反对
o="$(classify hanghang play 不要 2000)"
check B-scene "$(scene_of "$o")" oppose
check B-speak "$(speak_of "$o")" True
echo "$(reply_of "$o")" | grep -qE "去喝水了|不吵你|趴着" || { echo "fail B play yield: $o"; fail=1; }
echo "$(reply_of "$o")" | grep -q "但是英语" && { echo "fail B argued"; fail=1; }
of="$(classify qiaqia friend 不要 2000)"
echo "$(reply_of "$of")" | grep -qE "先不说了|今天到这儿|去趴着" || { echo "fail B friend yield: $of"; fail=1; }
[ "$(reply_of "$o")" != "$(reply_of "$of")" ] || { echo "fail B friend==play"; fail=1; }

# C 沉默
s="$(classify hanghang play "" 0 --timeout)"
check C-scene "$(scene_of "$s")" timeout
check C-speak "$(speak_of "$s")" False

# D 推迟
d="$(classify hanghang play 等会儿 2000)"
check D-scene "$(scene_of "$d")" defer
check D-speak "$(speak_of "$d")" True
echo "$(reply_of "$d")" | grep -q "等一会儿\|不急\|等你" || { echo "fail D reply: $d"; fail=1; }

# E 不会
w="$(classify hanghang play 不会 2000)"
check E-scene "$(scene_of "$w")" wont
check E-speak "$(speak_of "$w")" True
echo "$(reply_of "$w")" | grep -q "说一句就行\|陪你\|不会也" || { echo "fail E reply: $w"; fail=1; }

# F 听不清
u="$(classify hanghang play "" 400)"
check F-scene "$(scene_of "$u")" unclear
echo "$(reply_of "$u")" | grep -qE "再说|重复" && { echo "fail F chased"; fail=1; }

# G 今天别叫
g="$(classify hanghang play 今天别叫我 2000)"
check G-scene "$(scene_of "$g")" stop_today
check G-speak "$(speak_of "$g")" True
echo "$(reply_of "$g")" | grep -q "不叫你了\|今天到这儿" || { echo "fail G reply: $g"; fail=1; }

# H 敷衍
h="$(classify hanghang play 嗯 400)"
check H-scene "$(scene_of "$h")" perfunctory
check H-speak "$(speak_of "$h")" False
echo "$(reply_of "$h")" | grep -qE "真好|真厉害" && { echo "fail H praised"; fail=1; }
h2="$(classify hanghang play 嗯 2000)"
check H-high-energy "$(scene_of "$h2")" joined

# I 超时
t="$(/usr/bin/python3 "$REACT" classify --print --event english --audience hanghang --timeout --rms 0)"
check I-scene "$(scene_of "$t")" timeout
check I-speak "$(speak_of "$t")" False

# 判定顺序：不要叫了 = stop_today 不是 oppose
ord="$(classify hanghang play 不要叫了 2000)"
check order-stop "$(scene_of "$ord")" stop_today
ord2="$(classify hanghang play 知道了 2000)"
check order-noncoop "$(scene_of "$ord2")" noncoop
check order-noncoop-speak "$(speak_of "$ord2")" False

# 活回合：反对写账本并冷却下一次
out="$(TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="不要" \
  "$TURN" --force --follow english hanghang 2>&1)"
echo "$out" | grep -q oppose || { echo "fail live oppose: $out"; fail=1; }
/usr/bin/python3 -c "
import json
row=json.load(open('$tmp/cat-turn-ledger.json'))['turns'][-1]
assert row['scene']=='oppose'
assert row['audience']=='hanghang'
assert row['spoke_again'] is True
assert 'text' not in row and 'transcript' not in row
"
muted="$(/usr/bin/python3 "$REACT" muted english hanghang; echo $?)" || true
/usr/bin/python3 "$REACT" muted english hanghang >/dev/null && rc=0 || rc=$?
[ "$rc" = "0" ] || { echo "fail oppose should mute hanghang english"; fail=1; }
/usr/bin/python3 "$REACT" muted english qiaqia >/dev/null && { echo "fail oppose should not mute qiaqia"; fail=1; } || true

# 冷却后 remind 跳过（不开麦）
out="$(TANGTANG_FAKE_TIME=16:20 "$CAT/cat-remind.sh" english hanghang 2>&1)"
echo "$out" | grep -qE "先不说|SKIP|今天" || { echo "fail remind skip: $out"; fail=1; }
echo "$out" | grep -qE "开麦 [0-9]+s" && { echo "fail muted remind opened mic"; fail=1; }

# 连续两次沉默 → 今天跳过
tmp2="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-react-s.XXXXXX")"
out="$(TANGTANG_DATA_DIR="$tmp2" TANGTANG_TURN_PCM="$silent" TANGTANG_TURN_STT=0 \
  TANGTANG_FAKE_TIME=16:20 "$TURN" --follow english hanghang 2>&1)"
echo "$out" | grep -qE "silent|timeout" || { echo "fail silent1: $out"; fail=1; }
out="$(TANGTANG_DATA_DIR="$tmp2" TANGTANG_TURN_PCM="$silent" TANGTANG_TURN_STT=0 \
  TANGTANG_FAKE_TIME=16:21 "$TURN" --follow english hanghang 2>&1)"
echo "$out" | grep -qE "silent|timeout" || { echo "fail silent2: $out"; fail=1; }
TANGTANG_DATA_DIR="$tmp2" TANGTANG_FAKE_TIME=16:22 /usr/bin/python3 "$REACT" muted english hanghang >/dev/null && rc=0 || rc=$?
[ "$rc" = "0" ] || { echo "fail two silents should mute"; fail=1; }
out="$(TANGTANG_DATA_DIR="$tmp2" TANGTANG_FAKE_TIME=16:22 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="好" \
  "$TURN" --follow english hanghang 2>&1)"
echo "$out" | grep -qE "SKIP|muted|cool|silent" || { echo "fail silent cooldown skip: $out"; fail=1; }
echo "$out" | grep -qE "开麦 [0-9]+s" && { echo "fail silent cooldown opened mic"; fail=1; }
# 兄妹隔离
out="$(TANGTANG_DATA_DIR="$tmp2" TANGTANG_FAKE_TIME=19:10 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="好啊" \
  "$TURN" --follow english qiaqia 2>&1)"
echo "$out" | grep -q joined || { echo "fail sibling still open: $out"; fail=1; }
echo "$out" | grep -q 航航 && { echo "fail named sibling"; fail=1; }
rm -rf "$tmp2"

# 反对两次隔天：第二天也跳过
tmp3="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-react-o2.XXXXXX")"
export TANGTANG_DATA_DIR="$tmp3"
export TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20
TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="不要" "$TURN" --force --follow english hanghang >/dev/null
export TANGTANG_FAKE_TODAY=2026-09-02
TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="不要" "$TURN" --force --follow english hanghang >/dev/null
/usr/bin/python3 "$REACT" muted english hanghang >/dev/null && rc=0 || rc=$?
[ "$rc" = "0" ] || { echo "fail twice oppose should skip tomorrow"; fail=1; }
export TANGTANG_FAKE_TODAY=2026-09-03 TANGTANG_FAKE_TIME=16:20
/usr/bin/python3 "$REACT" muted english hanghang >/dev/null && rc=0 || rc=$?
[ "$rc" = "0" ] || { echo "fail 9/3 still skipped after twice oppose"; fail=1; }
export TANGTANG_FAKE_TODAY=2026-09-04 TANGTANG_FAKE_TIME=16:20
/usr/bin/python3 "$REACT" muted english hanghang >/dev/null && { echo "fail 9/4 should be open"; fail=1; } || true
rm -rf "$tmp3"

# preview / dry-run 不开麦、不写这个夹具账本
pre="$(mktemp -d)"
out="$(TANGTANG_DATA_DIR="$pre" "$TURN" --print english hanghang 不要 2>&1)"
echo "$out" | grep -qE "oppose|不要" || { echo "fail dry-run scene: $out"; fail=1; }
echo "$out" | grep -qE "开麦 [0-9]+s" && { echo "fail dry-run mic"; fail=1; }
[ -f "$pre/cat-turn-ledger.json" ] && { echo "fail dry-run wrote ledger"; fail=1; }
rm -rf "$pre"

# features / help
"$CAT/cat.sh" features | grep -q "小朋友反应" || { echo "fail features"; fail=1; }
bash "$CAT/cat-lib.sh" help | grep -q "小朋友反应" || { echo "fail cat-lib help"; fail=1; }

rm -rf "$tmp"
if [ "$fail" = "0" ]; then
  echo "test-child-reactions ok"
  exit 0
fi
echo "test-child-reactions failed"
exit 1
