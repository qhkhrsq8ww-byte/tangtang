#!/bin/bash
# ============================================================
# 糖糖 · OpenClaw 客厅下午实测（2013 MacBook Air）
#
# 默认：休息日 · 航航 · 2026-08-28 客厅
#   14:00 问糖糖 → 15:00 英语 → 16:00 锻炼 → 17:00 休息
# 每步：出声一句 → 一个听窗 → 最多回一句。沉默不追问。
# 账本只写标签，不写小朋友原话。
#
# 用法:
#   ./cat.sh openclaw              今天下午依次：点到了就做，没到点就等到那个整点
#   ./cat.sh openclaw --now        已是下午、一次跑完四步（步间 3–8 秒）
#   ./cat.sh openclaw --preview    只打印计划与四句，不开麦、不发声
#   ./cat.sh openclaw --who qiaqia
#   ./cat.sh hwcheck               先查麦/音箱（非 Darwin 跳过硬件，不失败）
#   ./cat.sh today-report          只打标签
#
# 也可：./openclaw-today.sh …
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

export TZ="${TANGTANG_TZ:-Asia/Shanghai}"

PREVIEW=0
NOW=0
WHO="hanghang"
CMD="run"
# --now 步间间隔：未设则 3–8 秒。测试可 TANGTANG_OPENCLAW_GAP=0
GAP="${TANGTANG_OPENCLAW_GAP:-}"
# 等到整点的上限（秒）。超过则现在做，不睡整夜。
WAIT_CAP="${TANGTANG_OPENCLAW_WAIT_CAP:-7200}"
MIC_DEV="${TANGTANG_MIC_AVFOUNDATION:-:2}"

usage() {
  sed -n '2,24p' "$0"
}

while [ $# -gt 0 ]; do
  case "$1" in
    hwcheck) CMD="hwcheck"; shift;;
    today-report|report) CMD="report"; shift;;
    selftest|--selftest) CMD="selftest"; shift;;
    --preview|-n) PREVIEW=1; export TANGTANG_TTS=0; shift;;
    --now) NOW=1; shift;;
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
export TANGTANG_MEMBER_ID="$WHO"
export TANGTANG_SPEAKER="$WHO"
export TANGTANG_PROFILE="$PROFILE"
export TANGTANG_CHILD_NAME="$DISPLAY"
export TANGTANG_REQUIRE_PRESENCE=0
export TANGTANG_TURN_EVENTS="ask,english,move,rest"

if [ "$(uname -s)" != "Darwin" ]; then
  export TANGTANG_TTS="${TANGTANG_TTS:-0}"
fi

PLAN="$(tangtang_today_plan_file)" || {
  echo "[openclaw] 找不到 data/today_plan.json" >&2
  exit 1
}

tool_path() {
  command -v "$1" 2>/dev/null || true
}

print_hwcheck_tool() {
  local name="$1" path="$2"
  if [ -n "$path" ] && [ -x "$path" ]; then
    echo "  $name  $path"
    return 0
  fi
  echo "  $name  没有"
  return 1
}

# Darwin：列 avfoundation、默认输出、0.3 秒录完即删、查 sox/ffmpeg/say。
# 麦/音箱没有则失败。非 Darwin：跳过硬件，不失败。
run_hwcheck() {
  local ff sox_bin say_bin os_name tmp wav devices outvol
  os_name="$(uname -s)"
  echo "=== hwcheck ==="
  echo "系统  $os_name  TZ=$TZ  $(tangtang_today) $(tangtang_now_hm)"
  ff="$(tangtang_ffmpeg)"
  sox_bin="$(tool_path sox)"
  say_bin="$(tool_path say)"
  print_hwcheck_tool ffmpeg "$ff" || true
  print_hwcheck_tool sox "$sox_bin" || true
  print_hwcheck_tool say "$say_bin" || true

  if [ "$os_name" != "Darwin" ]; then
    echo "非 Darwin：跳过麦/音箱实测（云端不失败）"
    echo "客厅 Mac 请用 MAONO AU-BM10 avfoundation ${MIC_DEV}；音箱必须是系统默认输出且放客厅。"
    echo "=== hwcheck skip ==="
    return 0
  fi

  if [ -z "$ff" ] || [ ! -x "$ff" ]; then
    echo "失败：找不到 ffmpeg。客厅 Mac 没法开麦。" >&2
    echo "=== hwcheck fail ==="
    return 1
  fi
  if [ -z "$say_bin" ]; then
    echo "失败：找不到 say。没有系统朗读。" >&2
    echo "=== hwcheck fail ==="
    return 1
  fi
  if [ -z "$sox_bin" ]; then
    echo "提示：没有 sox（本轮用 ffmpeg 录音，不算失败）"
  fi

  echo "avfoundation 设备："
  devices="$("$ff" -hide_banner -f avfoundation -list_devices true -i "" 2>&1 || true)"
  echo "$devices" | sed -n '1,80p'
  echo "$devices" | grep -qi "AVFoundation" || {
    echo "失败：ffmpeg 列不出 avfoundation 设备。" >&2
    echo "=== hwcheck fail ==="
    return 1
  }
  if ! echo "$devices" | grep -qiE "audio|麦克风|Microphone|MAONO|BM10"; then
    echo "失败：没有音频输入。客厅麦应是 MAONO AU-BM10，avfoundation ${MIC_DEV}。" >&2
    echo "=== hwcheck fail ==="
    return 1
  fi

  outvol="$(osascript -e 'output volume of (get volume settings)' 2>/dev/null || true)"
  if [ -z "$outvol" ]; then
    echo "失败：读不到系统默认输出。音箱要设成 Mac 默认输出，并放客厅。" >&2
    echo "=== hwcheck fail ==="
    return 1
  fi
  echo "默认输出音量  $outvol"
  echo "音箱必须是系统默认输出且放客厅。不要第二只音箱。"

  tmp="$(mktemp "${TMPDIR:-/tmp}/tangtang_hwcheck.XXXXXX")"
  wav="${tmp}.wav"
  echo "试录 0.3s  ${MIC_DEV} （录完即删）"
  if ! "$ff" -hide_banner -loglevel error -f avfoundation -i "$MIC_DEV" \
      -t 0.3 -ar 16000 -ac 1 -y "$wav" 2>/tmp/tangtang_hwcheck_ff.err; then
    echo "失败：avfoundation ${MIC_DEV} 录不上。查 MAONO AU-BM10 是否插在客厅 Mac。" >&2
    sed -n '1,20p' /tmp/tangtang_hwcheck_ff.err 2>/dev/null || true
    rm -f "$wav" "$tmp"
    echo "=== hwcheck fail ==="
    return 1
  fi
  if [ ! -s "$wav" ]; then
    echo "失败：试录文件是空的。麦没声。" >&2
    rm -f "$wav" "$tmp"
    echo "=== hwcheck fail ==="
    return 1
  fi
  rm -f "$wav" "$tmp"
  echo "试录完成，已删除。"
  echo "=== hwcheck ok ==="
  return 0
}

step_line() {
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

# id label at event
steps_meta() {
  /usr/bin/python3 - "$PLAN" <<'PY'
import json, sys
plan = json.load(open(sys.argv[1], encoding="utf-8"))
fallback = {"ask": "14:00", "english": "15:00", "move": "16:00", "rest": "17:00"}
for step in plan.get("steps") or []:
    sid = step.get("id") or ""
    label = step.get("label") or sid
    at = step.get("at") or fallback.get(sid) or ""
    event = step.get("event") or sid
    print("\t".join([sid, label, at, event]))
PY
}

print_plan_once() {
  echo "休息日 · ${DISPLAY} · 14:00问糖糖 → 15:00英语 → 16:00锻炼 → 17:00休息"
  echo "客厅 2013 MacBook Air · $(tangtang_today) $(tangtang_now_hm) · ${PROFILE}口吻"
  echo "麦 MAONO AU-BM10 avfoundation ${MIC_DEV} · 音箱系统默认输出且放客厅"
  echo "一步一句；沉默不追问；账本只写标签，不写小朋友原话。"
}

append_label() {
  local event="$1" result="$2"
  /usr/bin/python3 "$CAT_DIR/cat-turn.py" ledger \
    "$event" "$WHO" "$result" 0 unknown 0 0 >/dev/null
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

# 一个听窗。非 Darwin / preview：记 skip，不开麦。沉默不追问。
listen_after_speak() {
  local event="$1"
  if [ "$PREVIEW" = "1" ]; then
    append_label "$event" skip
    echo "[openclaw] $event skip  preview 不开麦"
    return 0
  fi
  if [ "$(uname -s)" != "Darwin" ]; then
    append_label "$event" skip
    echo "[openclaw] $event skip  无麦环境"
    return 0
  fi
  if [ ! -x "$CAT_DIR/cat-turn.sh" ]; then
    append_label "$event" skip
    echo "[openclaw] $event skip  没有听窗脚本"
    return 0
  fi
  # --follow：这句已经说过。--force：休息日家长点名，仍开窗。
  "$CAT_DIR/cat-turn.sh" --follow --force "$event" "$WHO"
}

gap_now() {
  local n
  if [ "$PREVIEW" = "1" ]; then
    return 0
  fi
  if [ -n "$GAP" ]; then
    n="$GAP"
  else
    n=$((3 + RANDOM % 6))
  fi
  if [ "$n" = "0" ] || [ -z "$n" ]; then
    return 0
  fi
  echo "[openclaw] 歇 ${n}s"
  sleep "$n"
}

# 没到点就等到那个整点；已经过了就现在做。上限 WAIT_CAP，不睡整夜。
# FAKE_TIME 不会自己走，测试里不真睡。
wait_until_hm() {
  local target="$1"
  local now_m tgt_m remain
  [ -n "$target" ] || return 0
  if [ "$NOW" = "1" ] || [ "$PREVIEW" = "1" ]; then
    return 0
  fi
  now_m="$(tangtang_hm_min "$(tangtang_now_hm)")"
  tgt_m="$(tangtang_hm_min "$target")"
  if [ "$now_m" -ge "$tgt_m" ]; then
    echo "[openclaw] ${target} 已过，现在做"
    return 0
  fi
  remain=$(( (tgt_m - now_m) * 60 ))
  # 深夜/凌晨：不要睡到下午
  if [ "$now_m" -lt 480 ] || [ "$now_m" -ge 1320 ]; then
    echo "[openclaw] 现在 $(tangtang_now_hm) 不睡到 ${target}，现在做"
    return 0
  fi
  if [ "$remain" -gt "$WAIT_CAP" ]; then
    echo "[openclaw] 距 ${target} 超过等待上限 ${WAIT_CAP}s，现在做"
    return 0
  fi
  if [ -n "${TANGTANG_FAKE_TIME:-}" ]; then
    echo "[openclaw] FAKE_TIME=${TANGTANG_FAKE_TIME} 早于 ${target}，测试不睡，现在做"
    return 0
  fi
  echo "[openclaw] 等到 ${target}（约 ${remain}s，上限 ${WAIT_CAP}s）"
  while :; do
    now_m="$(tangtang_hm_min "$(tangtang_now_hm)")"
    if [ "$now_m" -ge "$tgt_m" ]; then
      return 0
    fi
    remain=$(( (tgt_m - now_m) * 60 ))
    if [ "$remain" -le 0 ]; then
      return 0
    fi
    if [ "$remain" -gt "$WAIT_CAP" ]; then
      echo "[openclaw] 等待超过上限，现在做"
      return 0
    fi
    if [ "$remain" -gt 15 ]; then
      sleep 15
    else
      sleep "$remain"
    fi
  done
}

print_report() {
  /usr/bin/python3 "$CAT_DIR/cat-turn.py" today-report "$WHO" "$(tangtang_today)"
}

run_afternoon() {
  local step_n=0 sid label at event line
  print_plan_once
  if [ "$PREVIEW" = "1" ]; then
    echo "preview 不开麦 不发声"
  elif [ "$NOW" = "1" ]; then
    echo "--now 一次跑完四步，不再等整点"
  else
    echo "今天下午依次：没到点等到那个整点；过了就现在做"
  fi

  if [ "$PREVIEW" != "1" ]; then
    run_hwcheck || {
      echo "[openclaw] hwcheck 失败，停。请先把客厅麦和默认音箱弄好。"
      print_report
      return 1
    }
  fi

  step_n=0
  while IFS="$(printf '\t')" read -r sid label at event; do
    [ -n "$sid" ] || continue
    step_n=$((step_n + 1))
    if [ "$step_n" -gt 1 ]; then
      echo
      if [ "$NOW" = "1" ]; then
        gap_now
      fi
    fi
    wait_until_hm "$at"
    echo "${at}  ${step_n}. ${label}"
    line="$(step_line "$sid")"
    speak_line "$line"
    listen_after_speak "${event:-$sid}"
  done <<EOF
$(steps_meta)
EOF

  echo
  print_report
  if [ "$PREVIEW" != "1" ]; then
    echo "[openclaw] 四步走完了。糖糖去趴着。汪汪～"
  fi
  return 0
}

if [ "$CMD" = "hwcheck" ]; then
  run_hwcheck
  exit $?
fi
if [ "$CMD" = "report" ]; then
  print_report
  exit 0
fi
if [ "$CMD" = "selftest" ]; then
  exec "$CAT_DIR/../../tests/test-openclaw-plan.sh"
fi

run_afternoon
exit $?
