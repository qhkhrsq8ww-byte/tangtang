#!/bin/bash
# ============================================================
# 糖糖 · 今日休息四步（只在客厅）
#
# 问糖糖 → 学英语 → 锻炼身体 → 注意休息
# 每步：出声一句 → 最多一个听窗 → 最多回一句 → 停。不连着念完。
#
# 用法:
#   ./cat.sh today                 默认航航，按回车测下一步
#   ./cat.sh today hanghang
#   ./cat.sh today qiaqia
#   ./cat.sh today --who qiaqia
#   ./cat.sh today --preview       只打印四句，不开麦、不发声
#   ./cat.sh today --auto          步与步间隔约 90–120 秒；无麦则跳过听窗
#   ./cat.sh today --home          等同 CAT_CHILD_HOME=1
#
# 休息日计划由家长点名，白天也可以跟小朋友说。不关爷爷奶奶提醒。
# 麦：客厅 Mac 旁 MAONO AU-BM10。音箱：Mac 默认输出，放客厅。
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

PREVIEW=0
AUTO=0
CRON=0
WHO="hanghang"
GAP="${TANGTANG_TODAY_GAP:-105}"

usage() {
  sed -n '2,22p' "$0"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --preview|-n) PREVIEW=1; export TANGTANG_TTS=0; shift;;
    --auto) AUTO=1; shift;;
    --home) export CAT_CHILD_HOME=1; shift;;
    --crontab) CRON=1; shift;;
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
  qiaqia|洽洽|6|grade6|g6|姐姐)
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
export TANGTANG_MEMBER_ID="$WHO"
export TANGTANG_SPEAKER="$WHO"
export TANGTANG_PROFILE="$PROFILE"
export TANGTANG_CHILD_NAME="$DISPLAY"
export TANGTANG_REQUIRE_PRESENCE=0
export TANGTANG_TURN_EVENTS="ask,english,move,rest"

PLAN="$(tangtang_today_plan_file)" || {
  echo "[today] 找不到 data/today_plan.json" >&2
  exit 1
}

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
    print("\t".join([sid, label, nxt, event]))
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
  echo "# ${GAP} 秒一步；无麦会跳过听窗"
  echo "0 10 28 8 * cd $CAT_DIR && ./cat.sh today --auto hanghang"
}

speak_line() {
  local text="$1"
  [ -n "$text" ] || return 0
  echo "$text"
  if [ "$PREVIEW" = "1" ] || [ "${TANGTANG_TTS:-1}" = "0" ]; then
    return 0
  fi
  "$CAT_DIR/cat-say.sh" "$text" cute
}

# 出声完成后再开客厅短窗。preview 不开麦。无麦（含 --auto 非 Darwin）跳过。
listen_after_speak() {
  local event="$1"
  if [ "$PREVIEW" = "1" ]; then
    return 0
  fi
  if [ ! -x "$CAT_DIR/cat-turn.sh" ]; then
    # 客厅听窗脚本若缺失，本步只出声，不假装录音。
    echo "[today] 尚无客厅听窗，本步只出声"
    return 0
  fi
  if [ "$AUTO" = "1" ] && [ "$(uname -s)" != "Darwin" ]; then
    echo "[today] 无麦，跳过听窗"
    return 0
  fi
  # --follow：提醒已说完，只开窗。--force：休息日计划由家长点名，仍开窗。
  # 有人应就最多回一句；沉默不追问。儿童原话不进账本。
  "$CAT_DIR/cat-turn.sh" --follow --force "$event" "$WHO"
}

wait_next() {
  local next_label="$1"
  [ -n "$next_label" ] || return 0
  if [ "$PREVIEW" = "1" ]; then
    return 0
  fi
  if [ "$AUTO" = "1" ]; then
    if [ "${GAP:-0}" != "0" ]; then
      echo "[today] 下一项：${next_label}。先歇 ${GAP} 秒"
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

if [ "$CRON" = "1" ]; then
  print_banner
  print_optional_cron
  exit 0
fi

print_banner
if [ "$PREVIEW" = "1" ]; then
  echo "preview 不开客厅麦，也不发声"
fi

step_n=0
while IFS="$(printf '\t')" read -r sid label nxt event; do
  [ -n "$sid" ] || continue
  step_n=$((step_n + 1))
  if [ "$step_n" -gt 1 ] && [ "$PREVIEW" != "1" ]; then
    echo
  fi
  echo "${step_n}. ${label}"
  line="$(today_step_line "$sid")"
  speak_line "$line"
  listen_after_speak "${event:-$sid}"
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
