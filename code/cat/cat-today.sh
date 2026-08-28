#!/bin/bash
# ============================================================
# 糖糖 · 今日休息四步（只在客厅）
#
# 问糖糖 → 学英语 → 锻炼身体 → 注意休息
# 每步：出声一句 → 最多一个听窗 → 最多回一句 → 停。不连着念完。
#
# 用法:
#   ./cat.sh today                 默认航航，按回车测下一步（家长节奏）
#   ./cat.sh today hanghang
#   ./cat.sh today qiaqia
#   ./cat.sh today --who qiaqia
#   ./cat.sh today --preview       只打印四句，不开麦、不发声
#   ./cat.sh today --auto          无人值守；自测间隔 2–5 秒（TANGTANG_TODAY_GAP）
#   ./cat.sh today --auto --now    用 CAT_NOW / 墙上钟注入 14/15/16/17，四步立刻跑完
#   ./cat.sh today-selftest        云上自测：夹具听窗 silent+joined，不按回车
#   ./cat.sh today-report          打印账本标签摘要（无原话）
#   ./cat.sh today --home          等同 CAT_CHILD_HOME=1
#
# 真机下午（Asia/Shanghai）按 14:00 问糖糖 / 15:00 英语 / 16:00 锻炼 / 17:00 休息。
# 云上自测把钟拨到这些点，步间隔 3 秒，不假装客厅麦/音箱。
# 休息日计划由家长点名，白天也可以跟小朋友说。不关爷爷奶奶提醒。
# 麦：客厅 Mac 旁 MAONO AU-BM10。音箱：Mac 默认输出，放客厅。
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

PREVIEW=0
AUTO=0
CRON=0
NOW_FLAG=0
SELFTEST=0
DO_REPORT=0
WHO="hanghang"
# 自测默认 3 秒；真机 --auto 仍可用 TANGTANG_TODAY_GAP=105 拉开步距
GAP="${TANGTANG_TODAY_GAP:-}"

usage() {
  sed -n '2,28p' "$0"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --preview|-n) PREVIEW=1; export TANGTANG_TTS=0; shift;;
    --auto) AUTO=1; shift;;
    --now) NOW_FLAG=1; shift;;
    --home) export CAT_CHILD_HOME=1; export TANGTANG_CHILD_HOME=1; shift;;
    --crontab) CRON=1; shift;;
    selftest|--selftest|today-selftest)
      SELFTEST=1
      AUTO=1
      NOW_FLAG=1
      shift
      ;;
    report|--report|today-report)
      DO_REPORT=1
      shift
      ;;
    --who)
      if [ -z "${2:-}" ]; then
        echo "用法: --who hanghang|qiaqia" >&2
        exit 1
      fi
      WHO="$2"
      shift 2
      ;;
    hanghang|航航) WHO="hanghang"; shift;;
    qiaqia|洽洽) WHO="qiaqia"; shift;;
    -h|--help) usage; exit 0;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

case "$WHO" in
  qiaqia|洽洽|6|grade6)
    WHO="qiaqia"
    PROFILE="friend"
    DISPLAY="洽洽"
    ;;
  *)
    WHO="hanghang"
    PROFILE="play"
    DISPLAY="航航"
    ;;
esac

export CAT_CHILD_HOME=1
export TANGTANG_CHILD_HOME=1
export TANGTANG_REST_DAY=1
export TANGTANG_MEMBER_ID="$WHO"
export TANGTANG_SPEAKER="$WHO"
export TANGTANG_PROFILE="$PROFILE"
export TANGTANG_CHILD_NAME="$DISPLAY"
export TANGTANG_REQUIRE_PRESENCE=0
export TANGTANG_TURN_EVENTS="ask,english,move,rest"
export TANGTANG_TURN_LLM="${TANGTANG_TURN_LLM:-0}"

PLAN="$(tangtang_today_plan_file)" || {
  echo "[today] 找不到 data/today_plan.json" >&2
  exit 1
}

if [ "$SELFTEST" = "1" ]; then
  [ -n "$GAP" ] || GAP=3
  export TANGTANG_FIXTURE=1
  export TANGTANG_TURN_STT=0
  export TANGTANG_TURN_GAP=0
  if [ "$(uname -s)" != "Darwin" ]; then
    export TANGTANG_TTS=dry
  fi
elif [ "$AUTO" = "1" ] && [ "$NOW_FLAG" = "1" ]; then
  [ -n "$GAP" ] || GAP=3
elif [ "$AUTO" = "1" ]; then
  [ -n "$GAP" ] || GAP=105
fi
[ -n "$GAP" ] || GAP=105

# 从 JSON 取一步的口吻文案。英语步优先走译林小伴读。
today_step_line() {
  local step_id="$1"
  local text=""
  if [ "$step_id" = "english" ] && [ -f "$CAT_DIR/cat-english.py" ]; then
    text="$(/usr/bin/python3 "$CAT_DIR/cat-english.py" "$WHO" 2>/dev/null | tr -d '\r')"
  fi
  if [ -z "$text" ]; then
    text="$(/usr/bin/python3 - "$PLAN" "$WHO" "$step_id" <<'PY'
import json, sys
plan = json.load(open(sys.argv[1], encoding="utf-8"))
who = sys.argv[2]
step_id = sys.argv[3]
profile = "friend" if who == "qiaqia" else "play"
for step in plan.get("steps") or []:
    if step.get("id") == step_id:
        text = (step.get(profile) or step.get("play") or "").strip()
        sys.stdout.write(text)
        break
PY
)"
  fi
  printf '%s\n' "$text"
}

today_steps_meta() {
  /usr/bin/python3 - "$PLAN" <<'PY'
import json, sys
plan = json.load(open(sys.argv[1], encoding="utf-8"))
for step in plan.get("steps") or []:
    sid = step.get("id") or ""
    label = step.get("label") or sid
    nxt = step.get("next") or ""
    event = step.get("event") or sid
    at = step.get("at") or ""
    fixture = step.get("selftest_listen") or ""
    print("|".join([sid, label, nxt or "-", event, at, fixture or "-"]))
PY
}

print_banner() {
  local when
  when="$(tangtang_today) $(tangtang_now_hm)"
  echo "今天休息 · ${DISPLAY} · 问糖糖 → 学英语 → 锻炼 → 休息"
  echo "客厅 ${when} · ${PROFILE}口吻 · 一步一句"
}

print_optional_cron() {
  echo
  echo "# 可选：仅今天无人值守（自己 crontab -e，不要 sudo）"
  echo "# 主路径仍是客厅终端：./cat.sh today hanghang"
  echo "# 真机下午按 14/15/16/17；云上自测：./cat.sh today-selftest"
  echo "0 14 28 8 * cd $CAT_DIR && CAT_NOW='2026-08-28 14:05:00' ./cat.sh today --now hanghang"
}

today_report() {
  /usr/bin/python3 - "$TANGTANG_DATA_DIR" "$(tangtang_today)" <<'PY'
import json, os, sys
root = sys.argv[1]
day = sys.argv[2]
path = os.path.join(root, "cat-turn-ledger.json")
print("糖糖今日账本（只标签，无原话） %s" % day)
print("step\taudience\tpersona\tspoke\twindow\tscene")
if not os.path.isfile(path):
    print("（还没有回合）")
    sys.exit(0)
data = json.load(open(path, encoding="utf-8"))
want = ("ask", "english", "move", "rest")
n = 0
for row in data.get("turns") or []:
    if not isinstance(row, dict):
        continue
    ts = str(row.get("ts") or "")
    if ts[:10] != day:
        continue
    ev = row.get("event") or ""
    if ev not in want:
        continue
    for bad in ("text", "transcript", "utterance", "pcm", "words", "say", "stt_text", "child_text"):
        if bad in row:
            print("ledger leaked %s" % bad, file=sys.stderr)
            sys.exit(2)
    n += 1
    spoke = row.get("spoke")
    if spoke is None:
        spoke = row.get("spoke_again")
    spoke_s = "1" if spoke else "0"
    print("\t".join([
        ev,
        str(row.get("audience") or row.get("who") or ""),
        str(row.get("persona") or ""),
        spoke_s,
        str(row.get("window") or ""),
        str(row.get("scene") or row.get("result") or ""),
    ]))
if n == 0:
    print("（今天四步还没有标签）")
PY
}

if [ "$DO_REPORT" = "1" ]; then
  today_report
  exit $?
fi

speak_line() {
  local text="$1"
  [ -n "$text" ] || return 0
  echo "$text"
  if [ "$PREVIEW" = "1" ] || [ "${TANGTANG_TTS:-1}" = "0" ]; then
    return 0
  fi
  "$CAT_DIR/cat-say.sh" "$text" cute
}

# 出声完成后再开客厅短窗。preview 不开麦。
# 云上无麦：走 stub 听窗（silent / joined 夹具），不调用 avfoundation，不假装实声。
listen_after_speak() {
  local event="$1"
  local fixture="$2"
  if [ "$PREVIEW" = "1" ]; then
    return 0
  fi
  if [ ! -x "$CAT_DIR/cat-turn.sh" ]; then
    echo "[today] 尚无客厅听窗，本步只出声"
    return 0
  fi
  if [ -n "$fixture" ]; then
    export TANGTANG_TURN_LISTEN="$fixture"
    export TANGTANG_TURN_WINDOW="stub"
    export TANGTANG_FIXTURE=1
    if [ "$fixture" = "joined" ]; then
      # 只用于本机关键词分类；不进账本、不进家庭习惯
      export TANGTANG_TURN_TEXT="${TANGTANG_TURN_TEXT_JOINED:-好啊}"
      export TANGTANG_TURN_STT=0
      export TANGTANG_TURN_LLM=0
    else
      unset TANGTANG_TURN_TEXT
    fi
  elif [ "$(uname -s)" != "Darwin" ]; then
    export TANGTANG_TURN_LISTEN="${TANGTANG_TURN_LISTEN:-silent}"
    export TANGTANG_TURN_WINDOW="stub"
  fi
  # --follow：提醒已说完，只开窗。--force：休息日计划由家长点名，仍开窗。
  # 有人应就最多回一句；沉默不追问。儿童原话不进账本。
  "$CAT_DIR/cat-turn.sh" --follow --force "$event" "$WHO"
  unset TANGTANG_TURN_LISTEN TANGTANG_TURN_TEXT TANGTANG_TURN_WINDOW
}

wait_next() {
  local next_label="$1"
  [ -n "$next_label" ] || return 0
  if [ "$PREVIEW" = "1" ]; then
    return 0
  fi
  if [ "$AUTO" = "1" ]; then
    if [ "${GAP:-0}" != "0" ]; then
      echo "[today] 下一项：${next_label}。先歇 ${GAP} 秒（真机下午用 14/15/16/17，自测用 2–5 秒）"
      sleep "$GAP"
    fi
    return 0
  fi
  if [ ! -t 0 ]; then
    echo "[today] 非交互，停在这一项。客厅请开终端，或加 --auto / --preview"
    return 2
  fi
  printf '下一步：%s。按回车继续，或 Ctrl-C 结束' "$next_label"
  echo
  read -r _ || return 2
  return 0
}

step_clock() {
  local at="$1"
  local day
  day="$(tangtang_today)"
  [ -n "$at" ] || return 0
  # at=14:00 → 注入 14:05，落在该小时内
  local hm="$at"
  case "$hm" in
    *:*) ;;
    *) return 0 ;;
  esac
  local h="${hm%%:*}"
  tangtang_set_now "${day} ${h}:05:00"
}

if [ "$CRON" = "1" ]; then
  print_banner
  print_optional_cron
  exit 0
fi

if [ "$NOW_FLAG" = "1" ]; then
  tangtang_apply_clock
fi

print_banner
if [ "$PREVIEW" = "1" ]; then
  echo "preview 不开麦 不发声"
fi
if [ "$SELFTEST" = "1" ]; then
  echo "selftest 无人值守 · 听窗夹具 silent/joined · 不按回车"
fi
if [ "$AUTO" = "1" ] && [ "$PREVIEW" != "1" ]; then
  echo "auto 不按回车 · 步间隔 ${GAP}s"
fi

step_n=0
SELF_I=0
while IFS='|' read -r sid label nxt event at fixture; do
  [ -n "$sid" ] || continue
  [ "$nxt" = "-" ] && nxt=""
  [ "$fixture" = "-" ] && fixture=""
  step_n=$((step_n + 1))
  SELF_I=$((SELF_I + 1))
  if [ "$NOW_FLAG" = "1" ] || [ "$SELFTEST" = "1" ]; then
    step_clock "$at"
  fi
  if [ "$SELFTEST" = "1" ]; then
    case "$SELF_I" in
      1) fixture="silent" ;;
      2) fixture="joined" ;;
      3) fixture="silent" ;;
      4) fixture="joined" ;;
    esac
  fi
  if [ "$step_n" -gt 1 ] && [ "$PREVIEW" != "1" ]; then
    echo
  fi
  echo "${step_n}. ${label}"
  echo "[today] should_speak=yes persona=${PROFILE} audience=${WHO} clock=$(tangtang_today) $(tangtang_now_hm)"
  line="$(today_step_line "$sid")"
  speak_line "$line"
  listen_after_speak "${event:-$sid}" "$fixture"
  if [ -n "$nxt" ]; then
    wait_next "$nxt" || break
  fi
done <<EOF
$(today_steps_meta)
EOF

if [ "$PREVIEW" != "1" ] && [ "$step_n" -ge 4 ]; then
  echo "[today] 今天四步走完了。糖糖去趴着。"
fi
exit 0
