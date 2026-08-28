#!/bin/bash
# ============================================================
# 糖糖 · 客厅语音小回合（只在客厅，不开第二只音箱）
#
# 麦：客厅 Mac 旁 MAONO AU-BM10（cat-listen.sh :2 + 30dB）
# 嘴：Mac 默认音频输出。客厅互动时蓝牙音箱应设为默认输出；
#     若音箱仍在儿童房，客厅听不见糖糖回话。不要做双音箱。
#
# 流程：出声完成（等 afplay）→ 短窗录音 → 本机能量 joined/silent
#       → joined 时可按次百度听写 → 糖糖最多回一句 → 结束
# 沉默合法，不追问。儿童原话不进账本、不进家庭共享、不写路由器盘；
# 回合结束删除 PCM。远程智能体不对孩子出声。
#
# 用法:
#   ./cat-turn.sh                 客厅试听：说一句 → 开窗 → 回或不回
#   ./cat-turn.sh english hanghang
#   ./cat-turn.sh --follow english hanghang   提醒已说完，只开窗
#   ./cat-turn.sh --print english hanghang    预览，不开麦
#   ./cat-turn.sh --force ...                 跳过作息闸门（仍等出声再开麦）
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
WINDOW_KIND="unknown"
SPOKE=0

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
  local result="$1" stt="$2" presence="$3" rms="$4" spoke="${5:-0}"
  local window="${WINDOW_KIND:-unknown}"
  local persona="${TANGTANG_PROFILE:-play}"
  /usr/bin/python3 "$CAT_DIR/cat-turn.py" ledger \
    "$EVENT" "$WHO" "$result" "$stt" "$presence" "$TURN_SECS" "$rms" \
    "$spoke" "$window" "$persona" "$result" >/dev/null
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
  WINDOW_KIND="unknown"
  if [ -n "${TANGTANG_TURN_PCM:-}" ] && [ -f "${TANGTANG_TURN_PCM}" ]; then
    cp "${TANGTANG_TURN_PCM}" "$PCM"
    WINDOW_KIND="${TANGTANG_TURN_WINDOW:-fixture}"
    turn_log "stub 听窗 fixture （夹具 PCM，不调用 avfoundation）"
    return 0
  fi
  listen="${TANGTANG_TURN_LISTEN:-}"
  case "$listen" in
    silent|joined|tone)
      kind="silent"
      [ "$listen" = "silent" ] || kind="tone"
      /usr/bin/python3 "$CAT_DIR/cat-turn.py" pcm "$kind" "$PCM" >/dev/null
      WINDOW_KIND="stub"
      turn_log "stub 听窗 $listen （无客厅麦/音箱，不调用 avfoundation）"
      return 0
      ;;
  esac
  if [ "$(uname -s)" != "Darwin" ]; then
    /usr/bin/python3 "$CAT_DIR/cat-turn.py" pcm silent "$PCM" >/dev/null
    WINDOW_KIND="stub"
    turn_log "stub 听窗 silent （云上无客厅麦，跳过实声）"
    return 0
  fi
  turn_log "开麦 ${TURN_SECS}s 客厅 MAONO AU-BM10"
  WINDOW_KIND="live"
  if ! "$CAT_DIR/cat-listen.sh" "$TURN_SECS" "$PCM" >/dev/null 2>&1; then
    turn_log "客厅麦没录上"
    rm -f "$PCM"
    PCM=""
    WINDOW_KIND="live"
    return 1
  fi
  return 0
}

reply_once() {
  local text="$1"
  local reply=""
  if [ "${TANGTANG_TURN_LLM:-1}" = "1" ]; then
    reply="$(TANGTANG_PROFILE="$TANGTANG_PROFILE" \
      TANGTANG_SPEAKER="$WHO" \
      TANGTANG_MEMBER_ID="$WHO" \
      TANGTANG_CHILD_NAME="$TANGTANG_CHILD_NAME" \
      /usr/bin/python3 "$CAT_DIR/cat-chat.py" "$text" 2>/dev/null | tr '\n' ' ')"
  fi
  reply="$(/usr/bin/python3 "$CAT_DIR/cat-turn.py" sentence "$reply")"
  if [ -z "$reply" ]; then
    reply="$(/usr/bin/python3 "$CAT_DIR/cat-turn.py" canned "$TANGTANG_PROFILE")"
  fi
  turn_log "joined 糖糖回一句"
  echo "$reply"
  if [ "${TANGTANG_TTS:-1}" != "0" ]; then
    "$CAT_DIR/cat-say.sh" "$reply" cute
  fi
  SPOKE=1
}

run_turn() {
  WHO="$(tangtang_turn_who "$EVENT" "$ARG")"
  export TANGTANG_MEMBER_ID="$WHO"
  export TANGTANG_SPEAKER="$WHO"
  export TANGTANG_PROFILE="$(profile_for_who "$WHO")"
  export TANGTANG_CHILD_NAME="$(display_for_who "$WHO")"

  if [ "$PRINT" = "1" ]; then
    WINDOW_KIND="preview"
    turn_log "preview 不开麦 event=$EVENT who=$WHO persona=$TANGTANG_PROFILE"
    return 0
  fi

  if [ "$FOLLOW" = "1" ] && [ "$FORCE" != "1" ]; then
    if ! tangtang_turn_event_enabled "$EVENT"; then
      turn_log "wont 此事件不开窗 event=$EVENT（默认只挂 english）"
      WINDOW_KIND="skip"
      write_ledger wont 0 unknown 0 0
      return 0
    fi
  fi

  if [ "$FORCE" != "1" ] && tangtang_child_at_school "$WHO"; then
    turn_log "wont 上学未归 不开麦 who=$WHO event=$EVENT time=$(tangtang_now_hm)"
    WINDOW_KIND="skip"
    write_ledger wont 0 unknown 0 0
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
    write_ledger silent 0 "$PRESENCE" 0 0
    turn_log "silent 未录到"
    return 0
  fi

  ENERGY="$(/usr/bin/python3 "$CAT_DIR/cat-turn.py" energy "$PCM" "${TANGTANG_TURN_RMS:-300}")"
  RMS="${ENERGY%%|*}"
  LABEL="${ENERGY#*|}"
  [ -n "$LABEL" ] || LABEL="silent"
  [ -n "$RMS" ] || RMS=0

  if [ "$LABEL" != "joined" ]; then
    turn_log "silent rms=$RMS 不追问"
    write_ledger silent 0 "$PRESENCE" "$RMS" 0
    return 0
  fi

  TEXT=""
  DID_STT=0
  if [ -n "${TANGTANG_TURN_TEXT:-}" ]; then
    TEXT="${TANGTANG_TURN_TEXT}"
    DID_STT=1
  elif [ "${TANGTANG_TURN_STT:-1}" = "1" ]; then
    TEXT="$("$CAT_DIR/cat-stt-baidu.sh" "$PCM" 2>/dev/null | tr -d '\n')"
    DID_STT=1
    PCM=""
  fi
  case "$TEXT" in
    \[STT*) TEXT="" ;;
  esac

  if [ -z "$TEXT" ]; then
    turn_log "joined rms=$RMS 无听写，不追问"
    write_ledger joined "$DID_STT" "$PRESENCE" "$RMS" 0
    return 0
  fi

  reply_once "$TEXT"
  write_ledger joined 1 "$PRESENCE" "$RMS" 1
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

  /usr/bin/python3 "$CAT_DIR/cat-turn.py" selftest || { echo "fail cat-turn.py"; fail=1; }

  silent="$tmp/silent.pcm"
  tone="$tmp/tone.pcm"
  /usr/bin/python3 "$CAT_DIR/cat-turn.py" pcm silent "$silent"
  /usr/bin/python3 "$CAT_DIR/cat-turn.py" pcm tone "$tone"

  opened_real_mic() {
    printf '%s\n' "$1" | grep -q "客厅 MAONO"
  }

  # preview / --print 不开麦、不写账本（单独目录，避免污染后面的大脑冷却）
  print_dir="$tmp/print"
  mkdir -p "$print_dir"
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$print_dir" \
    "$CAT_DIR/cat-turn.sh" --print english hanghang 2>&1)"
  echo "$out" | grep -q "preview 不开麦" || { echo "fail print should say 不开麦"; fail=1; }
  opened_real_mic "$out" && { echo "fail print opened mic log"; fail=1; }
  if [ -f "$print_dir/cat-turn-ledger.json" ] || [ -f "$tmp/cat-turn-ledger.json" ]; then
    echo "fail print should not write ledger"
    fail=1
  fi
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$print_dir" \
    "$CAT_DIR/cat-remind.sh" --print english hanghang 2>&1)"
  opened_real_mic "$out" && { echo "fail remind --print opened mic"; fail=1; }
  if [ -f "$print_dir/cat-turn-ledger.json" ]; then
    echo "fail remind --print wrote ledger"
    fail=1
  fi

  # 上学日中午：english hanghang 不开窗
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=12:00 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "wont 上学未归 不开麦" || { echo "fail noon should wont: $out"; fail=1; }
  opened_real_mic "$out" && { echo "fail noon opened mic"; fail=1; }
  last="$(/usr/bin/python3 -c "import json;d=json.load(open('$tmp/cat-turn-ledger.json'));print(d['turns'][-1]['result'])")"
  [ "$last" = "wont" ] || { echo "fail noon ledger $last"; fail=1; }

  # 16:20 航航到家后：静音窗 → silent（mock 录音，不开真麦）
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$silent" TANGTANG_TURN_STT=0 \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "silent" || { echo "fail 16:20 silent: $out"; fail=1; }
  echo "$out" | grep -q "wont 上学未归" && { echo "fail 16:20 should open window"; fail=1; }
  last="$(/usr/bin/python3 -c "import json;d=json.load(open('$tmp/cat-turn-ledger.json'));print(d['turns'][-1]['result'])")"
  [ "$last" = "silent" ] || { echo "fail 16:20 silent ledger $last"; fail=1; }

  # 16:20 有能量、不听写 → joined，不追问
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_STT=0 TANGTANG_TURN_LLM=0 \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "joined" || { echo "fail 16:20 joined: $out"; fail=1; }
  last="$(/usr/bin/python3 -c "import json;d=json.load(open('$tmp/cat-turn-ledger.json'));print(d['turns'][-1]['result'], d['turns'][-1].get('stt'))")"
  echo "$last" | grep -q "^joined False$" || { echo "fail 16:20 joined ledger $last"; fail=1; }

  # 16:20 有听写 mock → 最多回一句（本地 canned，不走云）
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" TANGTANG_TURN_TEXT="糖糖你好" \
    TANGTANG_TURN_LLM=0 \
    "$CAT_DIR/cat-turn.sh" --follow english hanghang 2>&1)"
  echo "$out" | grep -q "糖糖听到" || { echo "fail reply: $out"; fail=1; }
  /usr/bin/python3 -c "
import json
d=json.load(open('$tmp/cat-turn-ledger.json'))
row=d['turns'][-1]
assert row['result']=='joined' and row['stt'] is True
assert 'text' not in row and 'transcript' not in row
print('ledger json ok', row['who'], row['event'])
" || { echo "fail ledger json"; fail=1; }

  # 其它提醒默认不开窗
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" \
    "$CAT_DIR/cat-turn.sh" --follow water 2>&1)"
  echo "$out" | grep -q "wont 此事件不开窗" || { echo "fail water should not open: $out"; fail=1; }

  # 洽洽 19:10 开窗；中午不开
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=12:00 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" \
    "$CAT_DIR/cat-turn.sh" --follow english qiaqia 2>&1)"
  echo "$out" | grep -q "wont 上学未归" || { echo "fail qiaqia noon: $out"; fail=1; }
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=19:10 TANGTANG_DATA_DIR="$tmp" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$silent" TANGTANG_TURN_STT=0 \
    "$CAT_DIR/cat-turn.sh" --follow english qiaqia 2>&1)"
  echo "$out" | grep -q "silent" || { echo "fail qiaqia 19:10: $out"; fail=1; }

  # remind 上学日中午整段跳过，不开窗
  mkdir -p "$tmp/noon"
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=12:00 TANGTANG_DATA_DIR="$tmp/noon" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$tone" \
    "$CAT_DIR/cat-remind.sh" english hanghang 2>&1)"
  echo "$out" | grep -q "航航还没到家" || { echo "fail remind noon skip: $out"; fail=1; }
  opened_real_mic "$out" && { echo "fail remind noon opened mic"; fail=1; }

  # remind 16:20 挂钩：出声后开静音窗
  mkdir -p "$tmp/hook"
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp/hook" \
    TANGTANG_TTS=0 TANGTANG_TURN_PCM="$silent" TANGTANG_TURN_STT=0 TANGTANG_TURN_LLM=0 \
    TANGTANG_TURN_GAP=0 \
    "$CAT_DIR/cat-remind.sh" english hanghang 2>&1)"
  echo "$out" | grep -q "silent" || { echo "fail remind 16:20 hook: $out"; fail=1; }
  opened_real_mic "$out" && { echo "fail remind hook used real mic log"; fail=1; }
  /usr/bin/python3 -c "
import json,os
p='$tmp/hook/cat-turn-ledger.json'
assert os.path.isfile(p), p
row=json.load(open(p))['turns'][-1]
assert row['result']=='silent' and row['event']=='english' and row['who']=='hanghang'
assert 'text' not in row
" || { echo "fail remind hook ledger"; fail=1; }

  # schedule preview 不开麦
  mkdir -p "$tmp/preview"
  out="$(TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 TANGTANG_DATA_DIR="$tmp/preview" \
    "$CAT_DIR/cat-schedule.sh" preview 2>&1)"
  echo "$out" | grep -q "客厅 MAONO" && { echo "fail schedule preview opened mic"; fail=1; }

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
      sed -n '2,22p' "$0"
      exit 0
      ;;
    *) break;;
  esac
done

EVENT="${1:-turn}"
ARG="${2:-}"
run_turn
exit 0
