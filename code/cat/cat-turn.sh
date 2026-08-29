#!/bin/bash
# ============================================================
# 糖糖 · 客厅语音小回合（只在客厅，不开第二只音箱）
#
# 麦：客厅 Mac 旁 MAONO AU-BM10（cat-listen.sh :2 + 30dB）
# 嘴：Mac 默认音频输出。客厅互动时蓝牙音箱应设为默认输出；
#     若音箱仍在儿童房，客厅听不见糖糖回话。不要做双音箱。
#
# 流程：出声完成（等 afplay）→ 短窗录音 → 能量 + 可选百度听写
#       → 关键词分类（配合/反对/沉默/不会/听不清/到此为止）
#       → 糖糖最多回一句，然后结束。沉默合法。反对不加重。
# 儿童原话不进账本、不进家庭共享、不写路由器盘；回合结束删除 PCM。
# 远程智能体不对孩子出声。听写只用于本机关键词，不走长篇 LLM。
#
# 用法:
#   ./cat-turn.sh                 客厅试听：说一句 → 开窗 → 回或不回
#   ./cat-turn.sh english hanghang
#   ./cat-turn.sh --follow english hanghang   提醒已说完，只开窗
#   ./cat-turn.sh --print english hanghang    预览各场景反应，不开麦
#   ./cat-turn.sh --force ...                 跳过作息/降温闸门（仍等出声再开麦）
#   ./cat-turn.sh selftest
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

PRINT=0
FORCE=0
FOLLOW=0
TURN_SECS="${TANGTANG_TURN_SECONDS:-5}"
PCM=""

cleanup_pcm() {
  if [ -n "${PCM:-}" ]; then
    rm -f "$PCM"
  fi
}
trap cleanup_pcm EXIT

turn_log() {
  echo "[turn] $*"
}

profile_for_who() {
  case "$1" in
    qiaqia|洽洽) printf '%s\n' "friend" ;;
    hanghang|航航) printf '%s\n' "play" ;;
    grandpa|grandma|爷爷|奶奶) printf '%s\n' "elder" ;;
    *) printf '%s\n' "${TANGTANG_PROFILE:-play}" ;;
  esac
}

display_for_who() {
  case "$1" in
    qiaqia|洽洽) printf '%s\n' "洽洽" ;;
    hanghang|航航) printf '%s\n' "航航" ;;
    *) printf '%s\n' "${TANGTANG_CHILD_NAME:-小朋友}" ;;
  esac
}

write_ledger() {
  local result="$1" stt="$2" presence="$3" rms="$4" speak="${5:-0}"
  /usr/bin/python3 "$CAT_DIR/cat-turn.py" ledger \
    "$EVENT" "$WHO" "$result" "$stt" "$presence" "$TURN_SECS" "$rms" "$speak" >/dev/null
}

speak_prompt() {
  local text
  if [ "$EVENT" = "turn" ] || [ -z "$EVENT" ]; then
    text="糖糖在客厅听你说一句。不说也没关系。"
    "$CAT_DIR/cat-talk.sh" say "$text" >/dev/null || true
    echo "$text"
    return
  fi
  if [ -n "$ARG" ]; then
    "$CAT_DIR/cat-talk.sh" "$EVENT" "$ARG"
  else
    "$CAT_DIR/cat-talk.sh" "$EVENT"
  fi
}

record_window() {
  PCM="${TMPDIR:-/tmp}/tangtang_turn_$$.pcm"
  if [ -n "${TANGTANG_TURN_PCM:-}" ] && [ -f "${TANGTANG_TURN_PCM}" ]; then
    cp "${TANGTANG_TURN_PCM}" "$PCM"
    return 0
  fi
  if [ "$(uname -s)" != "Darwin" ]; then
    turn_log "无麦环境，不开客厅麦"
    rm -f "$PCM"
    PCM=""
    return 1
  fi
  turn_log "开麦 ${TURN_SECS}s 客厅 MAONO AU-BM10"
  if ! "$CAT_DIR/cat-listen.sh" "$TURN_SECS" "$PCM" >/dev/null 2>&1; then
    turn_log "客厅麦没录上"
    rm -f "$PCM"
    PCM=""
    return 1
  fi
  return 0
}

# 本地短回句，不把儿童原话送进 LLM / 家庭摘要
speak_reaction() {
  local reply="$1"
  [ -n "$reply" ] || return 0
  turn_log "回一句 $reply"
  echo "$reply"
  if [ "${TANGTANG_TTS:-1}" != "0" ]; then
    "$CAT_DIR/cat-say.sh" "$reply" cute
  fi
}

run_turn() {
  WHO="$(tangtang_turn_who "$EVENT" "$ARG")"
  export TANGTANG_MEMBER_ID="$WHO"
  export TANGTANG_SPEAKER="$WHO"
  export TANGTANG_PROFILE="$(profile_for_who "$WHO")"
  export TANGTANG_CHILD_NAME="$(display_for_who "$WHO")"

  if [ "$PRINT" = "1" ]; then
    turn_log "preview 不开麦 event=$EVENT who=$WHO"
    /usr/bin/python3 "$CAT_DIR/cat-turn.py" preview "$EVENT" "$WHO"
    return 0
  fi

  if [ "$FOLLOW" = "1" ] && [ "$FORCE" != "1" ]; then
    if ! tangtang_turn_event_enabled "$EVENT"; then
      turn_log "wont 此事件不开窗 event=$EVENT（默认只挂 english）"
      write_ledger wont 0 unknown 0 0
      return 0
    fi
  fi

  if [ "$FORCE" != "1" ] && tangtang_child_at_school "$WHO"; then
    turn_log "wont 上学未归 不开麦 who=$WHO event=$EVENT time=$(tangtang_now_hm)"
    write_ledger wont 0 unknown 0 0
    return 0
  fi

  if [ "$FORCE" != "1" ] && ! tangtang_turn_gate_open "$EVENT" "$WHO"; then
    return 0
  fi

  PRESENCE="$(tangtang_note_member_presence "$WHO" 2>/dev/null || true)"
  [ -n "$PRESENCE" ] || PRESENCE="unknown"

  if [ "$FOLLOW" != "1" ]; then
    speak_prompt
  fi
  if [ "${TANGTANG_TTS:-1}" != "0" ]; then
    sleep "${TANGTANG_TURN_GAP:-0.5}"
  fi

  if ! record_window; then
    # 超时 / 没录上 = silent，合法，不追问
    write_ledger silent 0 "$PRESENCE" 0 0
    turn_log "silent 未录到 不说话"
    return 0
  fi

  ENERGY="$(/usr/bin/python3 "$CAT_DIR/cat-turn.py" energy "$PCM" "${TANGTANG_TURN_RMS:-300}")"
  RMS="${ENERGY%%	*}"
  LABEL="${ENERGY#*	}"
  [ -n "$LABEL" ] || LABEL="silent"
  [ -n "$RMS" ] || RMS=0
  if [ "$LABEL" = "joined" ]; then
    ENERGY_KIND="voiced"
  else
    ENERGY_KIND="silent"
  fi

  TEXT=""
  DID_STT=0
  STT_STATUS="off"
  if [ "$ENERGY_KIND" = "voiced" ]; then
    if [ -n "${TANGTANG_TURN_TEXT:-}" ]; then
      TEXT="${TANGTANG_TURN_TEXT}"
      DID_STT=1
      STT_STATUS="ok"
    elif [ "${TANGTANG_TURN_STT:-1}" = "1" ]; then
      TEXT="$("$CAT_DIR/cat-stt-baidu.sh" "$PCM" 2>/dev/null | tr -d '\n')"
      DID_STT=1
      PCM=""
      STT_STATUS="ok"
    else
      STT_STATUS="off"
    fi
  fi
  case "$TEXT" in
    \[STT*) TEXT=""; STT_STATUS="fail" ;;
  esac
  if [ "$STT_STATUS" = "ok" ] && [ -z "$TEXT" ]; then
    STT_STATUS="empty"
  fi
  # 听写原文只用完即弃，不进账本；PCM 由 trap 删除

  DECIDE="$(/usr/bin/python3 "$CAT_DIR/cat-turn.py" decide \
    "$ENERGY_KIND" "$STT_STATUS" "$RMS" "$TANGTANG_PROFILE" "$WHO" "$TEXT")"
  RESULT="${DECIDE%%	*}"
  REST="${DECIDE#*	}"
  SPEAK_FLAG="${REST%%	*}"
  REPLY="${REST#*	}"
  [ -n "$RESULT" ] || RESULT="silent"
  [ -n "$SPEAK_FLAG" ] || SPEAK_FLAG="0"

  turn_log "$RESULT rms=$RMS stt=$STT_STATUS"
  if [ "$SPEAK_FLAG" = "1" ] && [ -n "$REPLY" ]; then
    speak_reaction "$REPLY"
  else
    turn_log "不说话 结束"
  fi
  write_ledger "$RESULT" "$DID_STT" "$PRESENCE" "$RMS" "$SPEAK_FLAG"
  return 0
}

run_selftest() {
  local fail=0 tmp silent tone out last
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-turn-st.XXXXXX")"
  export TANGTANG_DATA_DIR="$tmp"
  export TANGTANG_TTS=0
  export TANGTANG_TURN_LLM=0
  export TANGTANG_TURN_STT=0
  export TANGTANG_TURN_GAP=0
  unset TANGTANG_HOST_HANGHANG TANGTANG_HOST_QIAQIA TANGTANG_TURN_PCM TANGTANG_TURN_TEXT
  export TANGTANG_SCHOOL_START=2026-09-01
  export TANGTANG_HOME_HANGHANG=16:00
  export TANGTANG_HOME_QIAQIA=18:00
  export TANGTANG_SCHOOL_LEAVE=07:30

  bash -n "$CAT_DIR/cat-turn.sh" || { echo "fail bash -n cat-turn.sh"; fail=1; }
  bash -n "$CAT_DIR/cat-lib.sh" || { echo "fail bash -n cat-lib.sh"; fail=1; }
  bash -n "$CAT_DIR/cat.sh" || { echo "fail bash -n cat.sh"; fail=1; }
  bash -n "$CAT_DIR/cat-remind.sh" || { echo "fail bash -n cat-remind.sh"; fail=1; }

  /usr/bin/python3 "$CAT_DIR/cat-turn.py" selftest || { echo "fail cat-turn.py"; fail=1; }

  silent="$tmp/silent.pcm"
  tone="$tmp/tone.pcm"
  /usr/bin/python3 "$CAT_DIR/cat-turn.py" pcm silent "$silent"
  /usr/bin/python3 "$CAT_DIR/cat-turn.py" pcm tone "$tone"

  # preview / --print 不开麦、不写账本，并列出各场景反应
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 \
    "$CAT_DIR/cat-turn.sh" --print english hanghang 2>&1)"
  echo "$out" | grep -q "preview 不开麦" || { echo "fail print should say 不开麦"; fail=1; }
  echo "$out" | grep -qE "开麦 [0-9]+s" && { echo "fail print opened mic log"; fail=1; }
  echo "$out" | grep -q "配合" || { echo "fail print missing 配合"; fail=1; }
  echo "$out" | grep -q "反对" || { echo "fail print missing 反对"; fail=1; }
  echo "$out" | grep -q "糖糖不吵你" || { echo "fail print missing play oppose"; fail=1; }
  echo "$out" | grep -q "糖糖不说了" || { echo "fail print missing friend oppose"; fail=1; }
  if [ -f "$tmp/cat-turn-ledger.json" ]; then
    echo "fail print should not write ledger"
    fail=1
  fi
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp" \
    "$CAT_DIR/cat-remind.sh" --print english hanghang 2>&1)"
  echo "$out" | grep -qE "开麦 [0-9]+s" && { echo "fail remind --print opened mic"; fail=1; }
  if [ -f "$tmp/cat-turn-ledger.json" ]; then
    echo "fail remind --print wrote ledger"
    fail=1
  fi

  # 上学日中午：english hanghang 不开窗
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=12:00 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "wont 上学未归 不开麦" || { echo "fail noon should wont: $out"; fail=1; }
  echo "$out" | grep -qE "开麦 [0-9]+s" && { echo "fail noon opened mic"; fail=1; }
  last="$(/usr/bin/python3 -c "import json;d=json.load(open('$tmp/cat-turn-ledger.json'));print(d['turns'][-1]['result'])")"
  [ "$last" = "wont" ] || { echo "fail noon ledger $last"; fail=1; }

  # 16:20 航航到家后：静音窗 → silent（mock 录音，不开真麦）
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$silent" TANGTANG_TURN_STT=0 \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "silent" || { echo "fail 16:20 silent: $out"; fail=1; }
  echo "$out" | grep -q "wont 上学未归" && { echo "fail 16:20 should open window"; fail=1; }
  echo "$out" | grep -q "再试一次" && { echo "fail silent should not retry"; fail=1; }
  last="$(/usr/bin/python3 -c "import json;d=json.load(open('$tmp/cat-turn-ledger.json'));print(d['turns'][-1]['result'])")"
  [ "$last" = "silent" ] || { echo "fail 16:20 silent ledger $last"; fail=1; }

  # 16:20 有能量、不听写 → joined_soft，不追问
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_STT=0 TANGTANG_TURN_LLM=0 \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "joined_soft" || { echo "fail 16:20 joined_soft: $out"; fail=1; }
  last="$(/usr/bin/python3 -c "import json;d=json.load(open('$tmp/cat-turn-ledger.json'));print(d['turns'][-1]['result'], d['turns'][-1].get('stt'))")"
  echo "$last" | grep -q "^joined_soft False$" || { echo "fail 16:20 joined_soft ledger $last"; fail=1; }

  # 16:20 有听写 mock → 配合，本地短回句，不走云
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="好啊" \
    TANGTANG_TURN_LLM=0 \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "joined" || { echo "fail joined: $out"; fail=1; }
  echo "$out" | grep -qE "糖糖听到|玩到这儿" || { echo "fail play joined reply: $out"; fail=1; }
  echo "$out" | grep -q "正确" && { echo "fail should not score: $out"; fail=1; }
  /usr/bin/python3 -c "
import json
d=json.load(open('$tmp/cat-turn-ledger.json'))
row=d['turns'][-1]
assert row['result']=='joined' and row['stt'] is True
assert 'text' not in row and 'transcript' not in row
print('ledger json ok', row['who'], row['event'])
" || { echo "fail ledger json"; fail=1; }

  # 反对：温和收场，不加重（--force 避免前面的账本触发降温）
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:25 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="不要" \
    "$CAT_DIR/cat-turn.sh" --force --follow english hanghang 2>&1)"
  echo "$out" | grep -q "oppose" || { echo "fail oppose: $out"; fail=1; }
  echo "$out" | grep -q "再试一次" && { echo "fail oppose retry: $out"; fail=1; }
  echo "$out" | grep -qE "不吵你|先去趴着" || { echo "fail play oppose reply: $out"; fail=1; }

  # 滚：温和，不当攻击升级
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:26 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="滚" \
    "$CAT_DIR/cat-turn.sh" --force --follow english hanghang 2>&1)"
  echo "$out" | grep -q "oppose" || { echo "fail 滚: $out"; fail=1; }
  echo "$out" | grep -qiE "滚|骂|警告" && { echo "fail 滚 escalated: $out"; fail=1; }

  # 不会
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:27 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="好难" \
    "$CAT_DIR/cat-turn.sh" --force --follow english hanghang 2>&1)"
  echo "$out" | grep -q "wont" || { echo "fail wont: $out"; fail=1; }
  echo "$out" | grep -qE "没学会|也不会" || { echo "fail wont reply: $out"; fail=1; }

  # 听不清：有声 + STT 失败标记
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:28 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="[STT错误]" \
    "$CAT_DIR/cat-turn.sh" --force --follow english hanghang 2>&1)"
  echo "$out" | grep -q "unclear" || { echo "fail unclear: $out"; fail=1; }
  echo "$out" | grep -q "再说" && { echo "fail unclear should not chase: $out"; fail=1; }

  # 敷衍：极短无效应 → silent
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:29 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="啊" \
    "$CAT_DIR/cat-turn.sh" --force --follow english hanghang 2>&1)"
  echo "$out" | grep -q "silent" || { echo "fail scratch silent: $out"; fail=1; }

  # 其它提醒默认不开窗
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" \
    "$CAT_DIR/cat-turn.sh" --follow water 2>&1)"
  echo "$out" | grep -q "wont 此事件不开窗" || { echo "fail water should not open: $out"; fail=1; }

  # 洽洽 19:10 开窗；中午不开。friend 回句与 play 不同
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=12:00 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" \
    "$CAT_DIR/cat-turn.sh" --follow english qiaqia 2>&1)"
  echo "$out" | grep -q "wont 上学未归" || { echo "fail qiaqia noon: $out"; fail=1; }
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=19:10 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$silent" TANGTANG_TURN_STT=0 \
    "$CAT_DIR/cat-turn.sh" --follow english qiaqia 2>&1)"
  echo "$out" | grep -q "silent" || { echo "fail qiaqia 19:10: $out"; fail=1; }
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=19:11 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="好啊" \
    "$CAT_DIR/cat-turn.sh" --follow english qiaqia 2>&1)"
  echo "$out" | grep -qE "糖糖听到了|就这样" || { echo "fail friend joined: $out"; fail=1; }
  echo "$out" | grep -q "汪汪" && { echo "fail friend should not 汪汪: $out"; fail=1; }
  echo "$out" | grep -q "航航" && { echo "fail should not mention 航航: $out"; fail=1; }

  # stop 当天关窗
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=19:12 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="今天别叫我" \
    "$CAT_DIR/cat-turn.sh" --follow english qiaqia 2>&1)"
  echo "$out" | grep -q "stop" || { echo "fail stop: $out"; fail=1; }
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=19:40 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="好啊" \
    "$CAT_DIR/cat-turn.sh" --follow english qiaqia 2>&1)"
  echo "$out" | grep -q "stop" || { echo "fail stop gate: $out"; fail=1; }
  echo "$out" | grep -qE "开麦 [0-9]+s" && { echo "fail stop should not open mic"; fail=1; }

  # 连续沉默降温：今晚不再开（用干净账本）
  local tmp2
  tmp2="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-turn-cool.XXXXXX")"
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp2" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$silent" TANGTANG_TURN_STT=0 \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "silent" || { echo "fail cool1: $out"; fail=1; }
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:21 TANGTANG_DATA_DIR="$tmp2" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$silent" TANGTANG_TURN_STT=0 \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "silent" || { echo "fail cool2: $out"; fail=1; }
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:22 TANGTANG_DATA_DIR="$tmp2" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="好啊" \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "cool" || { echo "fail cool gate: $out"; fail=1; }
  echo "$out" | grep -qE "开麦 [0-9]+s" && { echo "fail cool should not open mic"; fail=1; }
  # 洽洽不受航航降温影响
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=19:10 TANGTANG_DATA_DIR="$tmp2" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="好啊" \
    "$CAT_DIR/cat-turn.sh" --follow english qiaqia 2>&1)"
  echo "$out" | grep -q "joined" || { echo "fail sibling isolation: $out"; fail=1; }
  echo "$out" | grep -q "航航" && { echo "fail qiaqia reply mentioned 航航: $out"; fail=1; }
  rm -rf "$tmp2"

  # remind --print 文案仍在，且不碰麦
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp" \
    "$CAT_DIR/cat-schedule.sh" preview 2>&1)"
  echo "$out" | grep -qE "开麦 [0-9]+s" && { echo "fail schedule preview opened mic"; fail=1; }

  rm -rf "$tmp"
  if [ "$fail" = "0" ]; then
    echo "cat-turn selftest ok"
    exit 0
  fi
  echo "cat-turn selftest failed"
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --print|-n) PRINT=1; export TANGTANG_TTS=0; shift;;
    --force) FORCE=1; shift;;
    --follow) FOLLOW=1; shift;;
    selftest|--selftest)
      run_selftest
      exit $?
      ;;
    -h|--help)
      sed -n '2,24p' "$0"
      exit 0
      ;;
    *) break;;
  esac
done

EVENT="${1:-turn}"
ARG="${2:-}"
run_turn
exit 0
