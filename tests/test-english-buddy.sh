#!/bin/bash
# 英语弱伴读：选人、口吻、作息+在场闸门。不测验、不改号。
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CAT="$ROOT/code/cat"
# shellcheck source=../code/cat/cat-lib.sh
. "$CAT/cat-lib.sh"

fail=0
ok() { echo "ok  $1"; }
bad() { echo "fail  $1"; fail=1; }

export TANGTANG_TTS=0
export TANGTANG_TURN_STT=0
export TANGTANG_TURN_LLM=0
export TANGTANG_TURN_GAP=0
export TANGTANG_SCHOOL_START=2026-09-01
unset TANGTANG_HOST_HANGHANG TANGTANG_HOST_QIAQIA
unset TANGTANG_MEMBER_ID TANGTANG_SPEAKER
unset CAT_CHILD_HOME TANGTANG_CHILD_HOME

bash -n "$CAT/cat-lib.sh" || bad "bash -n cat-lib.sh"
bash -n "$CAT/cat-remind.sh" || bad "bash -n cat-remind.sh"
/usr/bin/python3 "$CAT/cat-english.py" --selftest >/tmp/en-self.txt || bad "cat-english selftest"

# 1) 选人：洽洽参数 / MEMBER_ID 不被默认航航盖掉
[ "$(tangtang_english_who qiaqia)" = "qiaqia" ] || bad "english_who qiaqia"
[ "$(tangtang_english_who 洽洽)" = "qiaqia" ] || bad "english_who 洽洽"
[ "$(tangtang_english_who g6)" = "qiaqia" ] || bad "english_who g6"
[ "$(tangtang_turn_who english qiaqia)" = "qiaqia" ] || bad "turn_who qiaqia"
[ "$(TANGTANG_MEMBER_ID=qiaqia tangtang_turn_who english "")" = "qiaqia" ] \
  || bad "turn_who MEMBER_ID qiaqia"
[ "$(TANGTANG_MEMBER_ID=hanghang TANGTANG_PROFILE=friend tangtang_english_who "")" = "hanghang" ] \
  || bad "friend mouth remapped hanghang"
ok "who picker"

tmp="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-en.XXXXXX")"
export TANGTANG_DATA_DIR="$tmp"

# 2) 口吻：print 不是测验；兄妹句不同
out_h="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 \
  "$CAT/cat-remind.sh" --print english hanghang 2>&1)" || true
out_q="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=19:10 \
  "$CAT/cat-remind.sh" --print english qiaqia 2>&1)" || true
[ -n "$out_h" ] && [ -n "$out_q" ] && [ "$out_h" != "$out_q" ] \
  || bad "print who did not switch: [$out_h] [$out_q]"
echo "$out_h" | grep -qE "测验|正确|打分|跟我读|repeat after" && bad "hanghang quiz tone"
echo "$out_q" | grep -qE "测验|正确|打分|跟我读|repeat after" && bad "qiaqia quiz tone"
echo "$out_q" | grep -q "航航" && bad "qiaqia print named 航航"
ok "tone + who print"

# 3) 闸门：上学未归；配了 Wi‑Fi 却不在网则跳过（不改成另一个孩子）
out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=12:00 TANGTANG_TTS=0 \
  "$CAT/cat-remind.sh" english qiaqia 2>&1)" || true
echo "$out" | grep -q "洽洽还没到家" || bad "noon qiaqia should skip school: $out"
echo "$out" | grep -qE "开麦 [0-9]+s" && bad "noon qiaqia opened mic"

out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=19:10 TANGTANG_TTS=0 \
  TANGTANG_HOST_QIAQIA=203.0.113.9 \
  "$CAT/cat-remind.sh" english qiaqia 2>&1)" || true
echo "$out" | grep -q "客厅没检测到洽洽" || bad "away qiaqia should skip wifi: $out"
echo "$out" | grep -qE "开麦 [0-9]+s" && bad "away qiaqia opened mic"
echo "$out" | grep -q "航航还没到家" && bad "away qiaqia remapped to hanghang school skip"

out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_TTS=0 \
  TANGTANG_HOST_HANGHANG=203.0.113.9 \
  "$CAT/cat-turn.sh" --follow english hanghang 2>&1)" || true
echo "$out" | grep -q "客厅未检测到" || bad "away hanghang turn should skip: $out"
echo "$out" | grep -qE "开麦 [0-9]+s" && bad "away hanghang opened mic"
ok "school + presence gate"

rm -rf "$tmp"
if [ "$fail" = "0" ]; then
  echo "test-english-buddy ok"
  exit 0
fi
echo "test-english-buddy failed"
exit 1
