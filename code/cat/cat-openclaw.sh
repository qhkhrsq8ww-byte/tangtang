#!/bin/bash
# ============================================================
# OpenClaw：四步自测 → 写成报告 → 推 GitHub（只含标签）
#
# 用法:
#   ./cat.sh openclaw --preview
#   ./cat.sh openclaw --now --submit
#   ./cat.sh openclaw --dry-run
#   ./cat.sh openclaw-report
#   ./cat.sh openclaw --submit
#
# 报告里只许标签，不许小朋友原话。
# 默认 --now 会提交（origin 在、工作区没有无关脏文件）。
# 脏工作区：仍写 reports/openclaw/DATE.json，跳过 push。
# 显式 --submit 只 git add 该报告文件。
# --dry-run 把 JSON 打到 stdout，不 git。
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

PREVIEW=0
NOW=0
SUBMIT=0
NOSUBMIT=0
DRY=0
REPORT_ONLY=0
WHO="hanghang"
HOUR="${TANGTANG_OPENCLAW_HOUR:-14}"
PY="$CAT_DIR/cat-openclaw-report.py"
STEPS_FILE=""
FAIL_FILE=""

usage() {
  sed -n '2,18p' "$0"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --preview|-n) PREVIEW=1; export TANGTANG_TTS=0; shift;;
    --now) NOW=1; shift;;
    --submit) SUBMIT=1; shift;;
    --no-submit) NOSUBMIT=1; shift;;
    --dry-run) DRY=1; export TANGTANG_TTS=0; shift;;
    --report-only|--report) REPORT_ONLY=1; shift;;
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
  qiaqia|洽洽) WHO="qiaqia"; PERSONA="friend";;
  *) WHO="hanghang"; PERSONA="play";;
esac

export CAT_CHILD_HOME=1
export TANGTANG_CHILD_HOME=1
export TANGTANG_MEMBER_ID="$WHO"
export TANGTANG_SPEAKER="$WHO"
export TANGTANG_PROFILE="$PERSONA"
export TANGTANG_REQUIRE_PRESENCE=0
export TANGTANG_TURN_EVENTS="${TANGTANG_TURN_EVENTS:-ask,english,move,rest}"
export TANGTANG_TODAY_GAP="${TANGTANG_TODAY_GAP:-0}"
export TANGTANG_OPENCLAW_HOUR="$HOUR"

REST_DAY=1
if command -v tangtang_is_rest_day >/dev/null 2>&1 || type tangtang_is_rest_day >/dev/null 2>&1; then
  if tangtang_is_rest_day; then
    REST_DAY=1
  else
    REST_DAY=0
  fi
fi
export TANGTANG_REST_DAY="$REST_DAY"

# Linux 或 --now / --preview / --dry-run：不等 14:00。Darwin 且未加 --now 才等到下午。
wait_until_afternoon() {
  if [ "$NOW" = "1" ] || [ "$PREVIEW" = "1" ] || [ "$DRY" = "1" ] || [ "$REPORT_ONLY" = "1" ]; then
    return 0
  fi
  if [ "$(uname -s)" != "Darwin" ]; then
    echo "[openclaw] 非 Darwin，不等 14:00（加 --now 同效）"
    return 0
  fi
  local hm hour
  while :; do
    hm="$(TZ=Asia/Shanghai date +%H:%M)"
    hour="${hm%%:*}"
    hour=$((10#$hour))
    if [ "$hour" -ge "$HOUR" ]; then
      echo "[openclaw] ${hm} 到点，开始四步"
      return 0
    fi
    echo "[openclaw] 等到 ${HOUR}:00（上海），现在 ${hm}。加 --now 立刻跑。"
    sleep 30
  done
}

tmpd="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-openclaw.XXXXXX")"
STEPS_FILE="$tmpd/steps.json"
FAIL_FILE="$tmpd/failures.json"
printf '%s\n' '[]' > "$FAIL_FILE"
trap 'rm -rf "$tmpd"' EXIT

append_fail() {
  local cmd="$1" err="$2"
  /usr/bin/python3 - "$FAIL_FILE" "$cmd" "$err" <<'PY'
import json, sys
path, cmd, err = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    data = json.load(open(path, encoding="utf-8"))
except Exception:
    data = []
if not isinstance(data, list):
    data = []
data.append({"command": cmd[:80], "stderr": (err or "")[:200]})
json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
PY
}

run_hwcheck() {
  echo "[openclaw] hwcheck host=$(uname -s)"
}

# 内置四步：无 cat-today.sh 时仍能跑完并写 skip。日志只给 ingest，JSON 只有标签。
builtin_four_steps() {
  local sid logf
  logf="$tmpd/builtin.log"
  : > "$logf"
  for sid in ask english move rest; do
    echo "[openclaw] step ${sid}" | tee -a "$logf"
    if [ "$PREVIEW" = "1" ]; then
      echo "[openclaw] preview ${sid} 不开麦 不发声" | tee -a "$logf"
    elif [ -x "$CAT_DIR/cat-turn.sh" ] && [ "$(uname -s)" = "Darwin" ]; then
      "$CAT_DIR/cat-turn.sh" --follow --force "$sid" "$WHO" 2>&1 | tee -a "$logf" || true
    else
      echo "[openclaw] 无麦，跳过听窗 ${sid}" | tee -a "$logf"
    fi
  done
  /usr/bin/python3 "$PY" ingest-log --who "$WHO" --log "$logf" --out "$STEPS_FILE"
}

run_today_four_steps() {
  local rc=0 args logf
  logf="$tmpd/today.log"
  if [ "$PREVIEW" = "1" ]; then
    args="--preview"
  else
    args="--auto"
  fi
  echo "[openclaw] today $args $WHO"
  "$CAT_DIR/cat-today.sh" $args "$WHO" > "$logf" 2>&1 || rc=$?
  cat "$logf"
  if [ "$rc" != "0" ]; then
    append_fail "cat-today.sh" "exit $rc"
  fi
  /usr/bin/python3 "$PY" ingest-log --who "$WHO" --log "$logf" --out "$STEPS_FILE"
}

run_four_steps() {
  if [ -x "$CAT_DIR/cat-today.sh" ]; then
    run_today_four_steps
  else
    echo "[openclaw] 无 today，走内置四步"
    builtin_four_steps
  fi
  if [ ! -s "$STEPS_FILE" ]; then
    builtin_four_steps
  fi
}

do_report() {
  local extra="" mode
  extra=""
  if [ "$REST_DAY" != "1" ]; then
    extra="$extra --no-rest-day"
  fi
  export TANGTANG_OPENCLAW_STEPS="$STEPS_FILE"
  export TANGTANG_OPENCLAW_FAILURES="$FAIL_FILE"
  if [ "$DRY" = "1" ]; then
    /usr/bin/python3 "$PY" dry-run --who "$WHO" --steps-file "$STEPS_FILE" $extra
    return $?
  fi
  if [ "$PREVIEW" = "1" ]; then
    echo "[openclaw] preview 不写报告 不 push。田间提交请用 --now --submit"
    return 0
  fi
  if [ "$NOSUBMIT" = "1" ]; then
    /usr/bin/python3 "$PY" write --who "$WHO" --steps-file "$STEPS_FILE" $extra
    echo "[openclaw] --no-submit 只写文件"
    return 0
  fi
  # 显式 --submit：只 add 报告文件，即使工作区有其它脏文件。
  if [ "$SUBMIT" = "1" ]; then
    /usr/bin/python3 "$PY" submit --who "$WHO" --steps-file "$STEPS_FILE" --allow-dirty $extra
    return $?
  fi
  # 默认 --now 提交；脏工作区则写文件并跳过 push。
  /usr/bin/python3 "$PY" submit --who "$WHO" --steps-file "$STEPS_FILE" $extra
}

if [ "$REPORT_ONLY" = "1" ]; then
  day="$(tangtang_today)"
  existing=""
  root="$(cd "$CAT_DIR/../.." && pwd)"
  if [ -f "$root/reports/openclaw/${day}.json" ]; then
    existing="$root/reports/openclaw/${day}.json"
  fi
  if [ "$DRY" = "1" ]; then
    if [ -n "$existing" ]; then
      cat "$existing"
      exit 0
    fi
    builtin_four_steps
    /usr/bin/python3 "$PY" dry-run --who "$WHO" --steps-file "$STEPS_FILE"
    exit $?
  fi
  if [ -n "$existing" ]; then
    echo "[openclaw] 使用已有 $existing"
    /usr/bin/python3 "$PY" push-existing
    exit $?
  fi
  echo "[openclaw] 尚无今日报告，先跑四步"
  run_hwcheck
  run_four_steps
  /usr/bin/python3 "$PY" submit --who "$WHO" --steps-file "$STEPS_FILE" --allow-dirty
  exit $?
fi

echo "[openclaw] who=$WHO rest_day=$REST_DAY host=$(uname -s)"
run_hwcheck
wait_until_afternoon
run_four_steps
# 成功或失败都写报告
do_report
exit $?
