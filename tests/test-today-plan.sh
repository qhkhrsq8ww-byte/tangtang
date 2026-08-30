#!/bin/bash
# 今日休息四步：preview 顺序、休息日不禁童、--who 换听众、preview 不录音
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CAT="$ROOT/code/cat"
# shellcheck source=../code/cat/cat-lib.sh
. "$CAT/cat-lib.sh"

fail=0
ok() { echo "ok  $1"; }
bad() { echo "fail  $1"; fail=1; }

unset CAT_CHILD_HOME TANGTANG_CHILD_HOME
export TANGTANG_TTS=0
export TANGTANG_TURN_STT=0
export TANGTANG_TURN_LLM=0
export TANGTANG_TURN_GAP=0
export TANGTANG_SCHOOL_START=2026-09-01
unset TANGTANG_CALENDAR TANGTANG_REST_DAYS TANGTANG_TODAY_PLAN

bash -n "$CAT/cat-today.sh" || bad "bash -n cat-today.sh"
bash -n "$CAT/cat.sh" || bad "bash -n cat.sh"
bash -n "$CAT/cat-lib.sh" || bad "bash -n cat-lib.sh"

# 1) preview 四步顺序，打印谁/何时，不开麦不发声
out="$(TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=10:00 \
  "$CAT/cat.sh" today --preview hanghang 2>&1)" || { bad "preview hanghang exit"; out=""; }
echo "$out" | grep -q "今天休息 · 航航 · 问糖糖 → 学英语 → 锻炼 → 休息" \
  || bad "banner hanghang"
echo "$out" | grep -q "2026-08-28 10:00" || bad "preview missing when"
echo "$out" | grep -q "preview 不开客厅麦，也不发声" || bad "preview should say 不开客厅麦"
echo "$out" | grep -q "开麦 " && bad "preview claimed 开麦"
echo "$out" | grep -qi "录音" && bad "preview claimed 录音"
echo "$out" | grep -q "按回车" && bad "preview should not wait 回车"
ask_n="$(echo "$out" | grep -n "^1\\. 问糖糖" | head -n 1 | cut -d: -f1)"
eng_n="$(echo "$out" | grep -n "^2\\. 学英语" | head -n 1 | cut -d: -f1)"
move_n="$(echo "$out" | grep -n "^3\\. 锻炼身体" | head -n 1 | cut -d: -f1)"
rest_n="$(echo "$out" | grep -n "^4\\. 注意休息" | head -n 1 | cut -d: -f1)"
[ -n "$ask_n" ] && [ -n "$eng_n" ] && [ -n "$move_n" ] && [ -n "$rest_n" ] \
  || bad "preview missing step labels"
if [ -n "$ask_n" ] && [ -n "$eng_n" ] && [ -n "$move_n" ] && [ -n "$rest_n" ]; then
  [ "$ask_n" -lt "$eng_n" ] && [ "$eng_n" -lt "$move_n" ] && [ "$move_n" -lt "$rest_n" ] \
    || bad "preview step order $ask_n $eng_n $move_n $rest_n"
fi
echo "$out" | grep -q "汪汪～ 航航" || bad "play ask line"
echo "$out" | grep -q "你也动一动" || bad "move line missing 动一动"
echo "$out" | grep -q "躺一躺" || bad "rest line missing 躺一躺"
# 英语走译林小伴读，中英夹一句
echo "$out" | grep -Eq "aunt|dog|rabbit|tail|autumn|juice|school|clean|doctor|water" \
  || bad "english buddy line missing English word"
echo "$out" | grep -q "现在开始测试" && bad "should not sound like a test supervisor"
echo "$out" | grep -c "下一步：" | grep -qx "0" || bad "preview repeated CTA"
# 问糖糖 play 句有航航；banner 也有。friend 专属「洽洽要是想聊」不应出现
echo "$out" | grep -q "洽洽要是想聊" && bad "hanghang preview used friend ask"
ok "preview hanghang order"

# 2) --who / qiaqia 换听众：friend 口吻，不汪汪
out_q="$(TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=10:00 \
  "$CAT/cat.sh" today --preview --who qiaqia 2>&1)" || { bad "preview qiaqia exit"; out_q=""; }
echo "$out_q" | grep -q "今天休息 · 洽洽 · 问糖糖 → 学英语 → 锻炼 → 休息" \
  || bad "banner qiaqia"
echo "$out_q" | grep -q "糖糖在客厅。洽洽要是想聊" || bad "friend ask line"
echo "$out_q" | grep -q "汪汪" && bad "friend should not 汪汪"
echo "$out_q" | grep -q "汪汪～ 航航" && bad "qiaqia preview used play ask"
echo "$out_q" | grep -q "开麦 " && bad "qiaqia preview claimed 开麦"
# 同一天 hanghang / qiaqia 英语句应不同（年级不同）
line_h="$(echo "$out" | awk '/^2\. 学英语$/{getline; print; exit}')"
line_q="$(echo "$out_q" | awk '/^2\. 学英语$/{getline; print; exit}')"
[ -n "$line_h" ] && [ -n "$line_q" ] && [ "$line_h" != "$line_q" ] \
  || bad "english who did not switch: [$line_h] [$line_q]"
ok "who switches audience"

# 3) 休息日 / CAT_CHILD_HOME 绕过上学日白天禁童；不把周五都当休息
unset CAT_CHILD_HOME TANGTANG_CHILD_HOME
TANGTANG_FAKE_TODAY=2026-09-01
TANGTANG_FAKE_TIME=12:00
tangtang_is_school_day || bad "Sep1 is school day"
tangtang_child_at_school hanghang || bad "Sep1 noon hanghang at school"
tangtang_child_at_school qiaqia || bad "Sep1 noon qiaqia at school"

CAT_CHILD_HOME=1
if tangtang_child_at_school hanghang; then
  bad "CAT_CHILD_HOME should let hanghang talk at noon"
fi
if tangtang_child_at_school qiaqia; then
  bad "CAT_CHILD_HOME should let qiaqia talk at noon"
fi
tangtang_is_school_day || bad "CAT_CHILD_HOME must not cancel school day / alarm"
unset CAT_CHILD_HOME

TANGTANG_FAKE_TODAY=2026-08-28
TANGTANG_FAKE_TIME=12:00
tangtang_is_rest_day || bad "Aug28 should be rest day"
if tangtang_child_at_school hanghang; then
  bad "Aug28 rest day hanghang should be home"
fi
if tangtang_is_school_day; then
  bad "Aug28 is before school start, not a school day"
fi

# rest_days.txt 单独一天，不是周五通配
tmpd="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-rest.XXXXXX")"
printf '%s\n' "2026-09-01  临时在家" > "$tmpd/rest_days.txt"
TANGTANG_FAKE_TODAY=2026-09-01
TANGTANG_FAKE_TIME=12:00
TANGTANG_REST_DAYS="$tmpd/rest_days.txt"
tangtang_is_rest_day || bad "rest_days.txt Sep1"
if tangtang_child_at_school hanghang; then
  bad "rest_days.txt should bypass child mute"
fi
unset TANGTANG_REST_DAYS
# 2026-09-04 周五，未写入 rest，中午仍禁童
TANGTANG_FAKE_TODAY=2026-09-04
TANGTANG_FAKE_TIME=12:00
if tangtang_is_rest_day; then
  bad "must not mark every Friday as rest"
fi
tangtang_is_school_day || bad "Sep4 Friday is school day"
tangtang_child_at_school hanghang || bad "Sep4 noon hanghang at school"
rm -rf "$tmpd"
ok "rest-day bypasses school-hours child mute"

# 4) ./cat.sh today 在上学日中午仍出儿童句（计划内绕过），preview 不录音
out_home="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=12:00 \
  "$CAT/cat.sh" today --preview hanghang 2>&1)" || { bad "today preview on school noon"; out_home=""; }
echo "$out_home" | grep -q "上学期间不跟小朋友互动" && bad "today plan should bypass child mute"
echo "$out_home" | grep -q "汪汪～ 航航" || bad "today noon still greet hanghang"
echo "$out_home" | grep -q "开麦 " && bad "school-noon preview claimed 开麦"
echo "$out_home" | grep -q "爷爷奶奶" && bad "today plan should not switch to elder"
ok "today command home bypass"

# 5) --auto 无麦不录音；features 提到 today
out_auto="$(TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=10:00 \
  TANGTANG_TTS=0 TANGTANG_TODAY_GAP=0 \
  "$CAT/cat.sh" today --auto hanghang 2>&1)" || { bad "auto exit"; out_auto=""; }
echo "$out_auto" | grep -q "1. 问糖糖" || bad "auto missing step 1"
echo "$out_auto" | grep -q "4. 注意休息" || bad "auto missing step 4"
echo "$out_auto" | grep -q "开麦 " && bad "auto no-mic claimed 开麦"
echo "$out_auto" | grep -q "录音" && bad "auto no-mic claimed 录音"
echo "$out_auto" | grep -q "按回车" && bad "auto should not wait 回车"
feat="$("$CAT/cat.sh" features 2>&1)"
echo "$feat" | grep -q "今日休息四步" || bad "features missing today"
echo "$feat" | grep -q "./cat.sh today" || bad "features missing ./cat.sh today"
ok "auto skip mic + features"

if [ "$fail" = "0" ]; then
  echo "test-today-plan ok"
  exit 0
fi
echo "test-today-plan failed"
exit 1
