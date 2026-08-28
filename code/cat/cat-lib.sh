#!/bin/bash
# 糖糖 · 公共函数（被其它脚本 source，不要直接执行）
CAT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$CAT_DIR/tangtang-config.sh" ]; then
  # shellcheck disable=SC1091
  . "$CAT_DIR/tangtang-config.sh"
fi

: "${TANGTANG_PROFILE:=play}"
: "${TANGTANG_CHILD_NAME:=小朋友}"
: "${TANGTANG_PROJECTOR_IP:=192.168.31.104}"
: "${TANGTANG_AIRPLAY_PORT:=61949}"
: "${TANGTANG_REQUIRE_PRESENCE:=1}"
: "${TANGTANG_SCHOOL_START:=2026-09-01}"
: "${TANGTANG_ALARM_DOW:=1-5}"
: "${TANGTANG_SCHOOL_LEAVE:=07:30}"
: "${TANGTANG_HOME_HANGHANG:=16:00}"
: "${TANGTANG_HOME_QIAQIA:=18:00}"
: "${TANGTANG_TURN_EVENTS:=english}"
: "${TANGTANG_TURN_SECONDS:=5}"
: "${TANGTANG_TURN_RMS:=300}"
: "${TANGTANG_TURN_GAP:=0.5}"
: "${TANGTANG_TURN_ALL:=0}"
: "${TANGTANG_TURN_RMS_CLEAR:=800}"
export TANGTANG_PROFILE TANGTANG_CHILD_NAME
export TANGTANG_PROJECTOR_IP TANGTANG_AIRPLAY_PORT
export TANGTANG_REQUIRE_PRESENCE
export TANGTANG_HOST_QIAQIA TANGTANG_HOST_HANGHANG
export TANGTANG_SCHOOL_START TANGTANG_ALARM_DOW
export TANGTANG_SCHOOL_LEAVE TANGTANG_HOME_HANGHANG TANGTANG_HOME_QIAQIA
export TANGTANG_TURN_EVENTS TANGTANG_TURN_SECONDS TANGTANG_TURN_RMS
export TANGTANG_TURN_GAP TANGTANG_TURN_ALL TANGTANG_TURN_RMS_CLEAR

# 记忆只写本机硬盘（Mac Air: ~/Library/Application Support/Tangtang）
# 现在不要指向路由器 Samba。未设置时由 tangtang_paths.py 解析并迁移旧文件。
if [ -z "${TANGTANG_DATA_DIR:-}" ]; then
  TANGTANG_DATA_DIR="$(/usr/bin/python3 "$CAT_DIR/tangtang_paths.py" 2>/dev/null || true)"
  [ -n "$TANGTANG_DATA_DIR" ] || TANGTANG_DATA_DIR="$CAT_DIR"
fi
export TANGTANG_DATA_DIR
TANGTANG_REMIND_LOG="${TANGTANG_DATA_DIR}/cat-remind-log.txt"
export TANGTANG_REMIND_LOG

# 手机是否在客厅网段（Mac 在客厅）。ICMP 不通时再看 ARP，兼容 iPhone 省电不回 ping。
tangtang_host_on_lan() {
  local host="$1"
  [ -n "$host" ] || return 1
  if [ "$(uname -s)" = "Darwin" ]; then
    ping -c 1 -t 1 "$host" >/dev/null 2>&1 && return 0
  else
    ping -c 1 -W 1 "$host" >/dev/null 2>&1 && return 0
  fi
  if command -v arp >/dev/null 2>&1; then
    if arp -an 2>/dev/null | grep -F "($host)" | grep -vi incomplete | grep -Eq '([0-9a-fA-F]{1,2}:){5}'; then
      return 0
    fi
    if arp -n "$host" 2>/dev/null | grep -vi incomplete | grep -Eq '([0-9a-fA-F]{1,2}:){5}'; then
      return 0
    fi
  fi
  return 1
}

# 打印在场小朋友名字（空格分隔）。0=有人 1=没人 2=没配置手机 IP
tangtang_kids_present() {
  local names=()
  local ip
  ip="${TANGTANG_HOST_QIAQIA:-}"
  if [ -n "$ip" ] && tangtang_host_on_lan "$ip"; then
    names+=("洽洽")
  fi
  ip="${TANGTANG_HOST_HANGHANG:-}"
  if [ -n "$ip" ] && tangtang_host_on_lan "$ip"; then
    names+=("航航")
  fi
  if [ ${#names[@]} -gt 0 ]; then
    printf '%s\n' "${names[*]}"
    return 0
  fi
  if [ -z "${TANGTANG_HOST_QIAQIA:-}" ] && [ -z "${TANGTANG_HOST_HANGHANG:-}" ]; then
    return 2
  fi
  printf '\n'
  return 1
}

tangtang_today() {
  printf '%s\n' "${TANGTANG_FAKE_TODAY:-$(date +%F)}"
}

# 1=周一 ... 7=周日
tangtang_weekday() {
  local d="${TANGTANG_FAKE_TODAY:-}"
  if [ -z "$d" ]; then
    date +%u
  elif [ "$(uname -s)" = "Darwin" ]; then
    date -j -f "%Y-%m-%d" "$d" +%u
  else
    date -d "$d" +%u
  fi
}

tangtang_cron_to_iso() {
  local n="$1"
  if [ "$n" = "0" ]; then
    n=7
  fi
  printf '%s\n' "$n"
}

# spec: * / 1-5 / 0,6 （crontab 星期，0和7都是周日）
tangtang_dow_match() {
  local spec="${1:-*}"
  local u="${2:-}"
  [ -n "$u" ] || u="$(tangtang_weekday)"
  [ "$spec" = "*" ] && return 0
  local part lo hi t
  local IFS=','
  for part in $spec; do
    if [ "${part%-*}" != "$part" ] && [ "${part#*-}" != "$part" ]; then
      lo="$(tangtang_cron_to_iso "${part%-*}")"
      hi="$(tangtang_cron_to_iso "${part#*-}")"
      if [ "$lo" -le "$hi" ] && [ "$u" -ge "$lo" ] && [ "$u" -le "$hi" ]; then
        return 0
      fi
    else
      t="$(tangtang_cron_to_iso "$part")"
      [ "$t" = "$u" ] && return 0
    fi
  done
  return 1
}

tangtang_date_in_window() {
  local today from until
  today="$(tangtang_today)"
  from="${1:-}"
  until="${2:-}"
  if [ -n "$from" ] && [ "$today" \< "$from" ]; then
    return 1
  fi
  if [ -n "$until" ] && [ "$today" \> "$until" ]; then
    return 1
  fi
  return 0
}

tangtang_calendar_file() {
  local p
  for p in \
    "${TANGTANG_CALENDAR:-}" \
    "${TANGTANG_DATA_DIR:-}/school_calendar.txt" \
    "$CAT_DIR/school_calendar.txt" \
    "$CAT_DIR/../../data/school_calendar.txt"
  do
    [ -n "$p" ] && [ -f "$p" ] && printf '%s\n' "$p" && return 0
  done
  return 1
}

tangtang_now_hm() {
  printf '%s\n' "${TANGTANG_FAKE_TIME:-$(date +%H:%M)}"
}

# HH:MM -> 分钟
tangtang_hm_min() {
  local hm="$1"
  local h="${hm%%:*}"
  local m="${hm##*:}"
  h=$((10#$h))
  m=$((10#$m))
  printf '%s\n' $((h * 60 + m))
}

# 当前时刻是否在 [start, end) ，HH:MM
tangtang_time_in_away() {
  local start="$1" end="$2"
  local now
  now="$(tangtang_now_hm)"
  local n s e
  n="$(tangtang_hm_min "$now")"
  s="$(tangtang_hm_min "$start")"
  e="$(tangtang_hm_min "$end")"
  [ "$n" -ge "$s" ] && [ "$n" -lt "$e" ]
}

tangtang_date_between() {
  local day="$1" from="$2" to="$3"
  [ "$day" \> "$from" ] || [ "$day" = "$from" ] || return 1
  [ "$day" \< "$to" ] || [ "$day" = "$to" ] || return 1
  return 0
}

# 0=今天放假（小朋友在家）
tangtang_is_holiday() {
  local cal day line kind span from to
  day="$(tangtang_today)"
  cal="$(tangtang_calendar_file)" || return 1
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%#*}"
    line="$(printf '%s' "$line" | awk '{$1=$1};1')"
    [ -n "$line" ] || continue
    kind="${line%% *}"
    span="${line#* }"
    span="${span%% *}"
    [ "$kind" = "holiday" ] || continue
    if [ "${span#*..}" != "$span" ]; then
      from="${span%%..*}"
      to="${span#*..}"
    else
      from="$span"
      to="$span"
    fi
    if tangtang_date_between "$day" "$from" "$to"; then
      return 0
    fi
  done < "$cal"
  return 1
}

# 0=调休上课日（周末也上学）
tangtang_is_makeup_school() {
  local cal day line kind span
  day="$(tangtang_today)"
  cal="$(tangtang_calendar_file)" || return 1
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%#*}"
    line="$(printf '%s' "$line" | awk '{$1=$1};1')"
    [ -n "$line" ] || continue
    kind="${line%% *}"
    span="${line#* }"
    span="${span%% *}"
    [ "$kind" = "school" ] || continue
    [ "$span" = "$day" ] && return 0
  done < "$cal"
  return 1
}

# 0=今天要上学（非节假日的工作日，或调休上课）
tangtang_is_school_day() {
  tangtang_date_in_window "${TANGTANG_SCHOOL_START:-2026-09-01}" "" || return 1
  tangtang_is_holiday && return 1
  tangtang_is_makeup_school && return 0
  tangtang_dow_match "${TANGTANG_ALARM_DOW:-1-5}"
}

# 0=这个小朋友按作息正在上学、不在家
# 参数: qiaqia|hanghang|洽洽|航航|member_id
tangtang_child_at_school() {
  local who="$1"
  local home leave
  leave="${TANGTANG_SCHOOL_LEAVE:-07:30}"
  case "$who" in
    qiaqia|洽洽) home="${TANGTANG_HOME_QIAQIA:-18:00}" ;;
    hanghang|航航) home="${TANGTANG_HOME_HANGHANG:-16:00}" ;;
    *) return 1 ;;
  esac
  tangtang_is_school_day || return 1
  tangtang_time_in_away "$leave" "$home"
}

# 现在可以互动的小朋友名字（空格分隔）。上学时段即使手机在家也不算。
# 0=有人 1=没人 2=没配置且不是上学日（沿用手机检测）
tangtang_kids_interactable() {
  local names=()
  if tangtang_is_school_day; then
    if ! tangtang_child_at_school hanghang; then
      names+=("航航")
    fi
    if ! tangtang_child_at_school qiaqia; then
      names+=("洽洽")
    fi
    if [ ${#names[@]} -gt 0 ]; then
      printf '%s\n' "${names[*]}"
      return 0
    fi
    printf '\n'
    return 1
  fi
  tangtang_kids_present
}

# 解析时刻表一行，结果放 TANGTANG_SCHED_* 
tangtang_parse_schedule_line() {
  local line="$1"
  local -a f
  local tok
  read -r -a f <<< "$line"
  TANGTANG_SCHED_MIN="${f[0]:-}"
  TANGTANG_SCHED_HOUR="${f[1]:-}"
  TANGTANG_SCHED_EVENT="${f[2]:-}"
  TANGTANG_SCHED_ARG=""
  TANGTANG_SCHED_DOW="*"
  TANGTANG_SCHED_FROM=""
  TANGTANG_SCHED_UNTIL=""
  TANGTANG_SCHED_PRESENCE=""
  local i=3
  while [ "$i" -lt "${#f[@]}" ]; do
    tok="${f[$i]}"
    case "$tok" in
      dow=*) TANGTANG_SCHED_DOW="${tok#dow=}" ;;
      from=*) TANGTANG_SCHED_FROM="${tok#from=}" ;;
      until=*) TANGTANG_SCHED_UNTIL="${tok#until=}" ;;
      presence=*) TANGTANG_SCHED_PRESENCE="${tok#presence=}" ;;
      *)
        if [ -z "$TANGTANG_SCHED_ARG" ]; then
          TANGTANG_SCHED_ARG="$tok"
        fi
        ;;
    esac
    i=$((i + 1))
  done
}

tangtang_alarm_chime() {
  [ "$(uname -s)" = "Darwin" ] || return 0
  local s="/System/Library/Sounds/Glass.aiff"
  [ -f "$s" ] || return 0
  afplay "$s" >/dev/null 2>&1 || true
  afplay "$s" >/dev/null 2>&1 || true
}

tangtang_ffmpeg() {
  if [ -x "$CAT_DIR/bin/ffmpeg" ]; then
    printf '%s\n' "$CAT_DIR/bin/ffmpeg"
  elif command -v ffmpeg >/dev/null 2>&1; then
    command -v ffmpeg
  else
    printf '%s\n' "$CAT_DIR/bin/ffmpeg"
  fi
}

# 客厅互动：蓝牙音箱应作为 Mac 默认输出，回话才能在客厅听见。
# 不要做第二只音箱。若音箱仍在儿童房，客厅听不见糖糖回话。
# 播放音频；按真实秒数超时，避免 sleep 0.3 却 +3 导致约 12 秒被掐断
tangtang_play_audio() {
  local f="$1"
  local limit="${2:-40}"
  [ -f "$f" ] || return 1
  afplay "$f" >/dev/null 2>&1 &
  local ap=$!
  local start now
  start=$(date +%s)
  while kill -0 "$ap" 2>/dev/null; do
    sleep 0.3
    now=$(date +%s)
    if [ $((now - start)) -ge "$limit" ]; then
      kill -9 "$ap" 2>/dev/null
      break
    fi
  done
  wait "$ap" 2>/dev/null
  return 0
}

tangtang_ensure_server() {
  if ! curl -s -o /dev/null --max-time 3 "http://127.0.0.1:8080/cat-stage.html"; then
    nohup /usr/bin/python3 -m http.server 8080 --bind 127.0.0.1 --directory "$CAT_DIR" >/tmp/cathttp.log 2>&1 &
    sleep 2
  fi
}

tangtang_ensure_stage() {
  tangtang_ensure_server
  if ! pgrep -f "Safari.*cat-stage" >/dev/null 2>&1; then
    open "http://127.0.0.1:8080/cat-stage.html"
    ( osascript -e "tell application \"Safari\" to if (count of windows) > 0 then set URL of front document to \"http://127.0.0.1:8080/cat-stage.html\"" 2>/dev/null & )
  fi
}

tangtang_projector_on() {
  nc -z -w 3 "$TANGTANG_PROJECTOR_IP" "$TANGTANG_AIRPLAY_PORT" 2>/dev/null
}

# 时刻表默认只给 english 开客厅录音窗；其它提醒仍单向。TANGTANG_TURN_ALL=1 才全部开窗。
tangtang_turn_event_enabled() {
  local event="$1"
  [ -n "$event" ] || return 1
  if [ "${TANGTANG_TURN_ALL:-0}" = "1" ]; then
    return 0
  fi
  local allow=",${TANGTANG_TURN_EVENTS:-english},"
  case "$allow" in
    *",$event,"*) return 0 ;;
  esac
  return 1
}

tangtang_turn_who() {
  local event="${1:-}"
  local arg="${2:-}"
  case "$event" in
    english)
      case "$arg" in
        qiaqia|洽洽|6|grade6) printf '%s\n' "qiaqia" ;;
        *) printf '%s\n' "hanghang" ;;
      esac
      return 0
      ;;
  esac
  case "${TANGTANG_MEMBER_ID:-${TANGTANG_SPEAKER:-}}" in
    qiaqia|洽洽) printf '%s\n' "qiaqia"; return 0 ;;
    hanghang|航航) printf '%s\n' "hanghang"; return 0 ;;
  esac
  if ! tangtang_child_at_school hanghang; then
    printf '%s\n' "hanghang"
    return 0
  fi
  if ! tangtang_child_at_school qiaqia; then
    printf '%s\n' "qiaqia"
    return 0
  fi
  printf '%s\n' "hanghang"
}

# 用客厅 Wi‑Fi/ARP 记一笔在场（home/away）。只在回合/提醒时调用，不要 24 小时 ping。
# 打印 home|away|unknown；0=在网 1=不在网 2=没配 IP
tangtang_note_member_presence() {
  local who="$1"
  local ip="" mid=""
  case "$who" in
    hanghang|航航) ip="${TANGTANG_HOST_HANGHANG:-}"; mid="hanghang" ;;
    qiaqia|洽洽) ip="${TANGTANG_HOST_QIAQIA:-}"; mid="qiaqia" ;;
    *) printf '%s\n' "unknown"; return 2 ;;
  esac
  if [ -z "$ip" ]; then
    printf '%s\n' "unknown"
    return 2
  fi
  if tangtang_host_on_lan "$ip"; then
    /usr/bin/python3 "$CAT_DIR/cat-family.py" log "$mid" home wifi >/dev/null 2>&1 || true
    printf '%s\n' "home"
    return 0
  fi
  /usr/bin/python3 "$CAT_DIR/cat-family.py" log "$mid" away wifi >/dev/null 2>&1 || true
  printf '%s\n' "away"
  return 1
}

# 小朋友反应冷却：反对/今天别叫/连续沉默 → 这条提醒先不说。不加大音量。
# 0=可以开  1=先不说。打印 [turn] SKIP ...
tangtang_turn_gate_open() {
  local event="${1:-english}"
  local who="${2:-}"
  local out rc=0
  [ -n "$who" ] || who="$(tangtang_turn_who "$event" "")"
  out="$(/usr/bin/python3 "$CAT_DIR/cat-react.py" muted "$event" "$who" 2>/dev/null)" || rc=$?
  if [ "$rc" != "0" ]; then
    return 0
  fi
  echo "[turn] SKIP ${out:-muted	cool}"
  return 1
}

tangtang_note_presence_for_event() {
  local event="${1:-}" arg="${2:-}"
  case "$event" in
    english|turn)
      tangtang_note_member_presence "$(tangtang_turn_who "$event" "$arg")"
      ;;
    *)
      if [ -n "${TANGTANG_HOST_HANGHANG:-}" ]; then
        tangtang_note_member_presence hanghang >/dev/null || true
      fi
      if [ -n "${TANGTANG_HOST_QIAQIA:-}" ]; then
        tangtang_note_member_presence qiaqia >/dev/null || true
      fi
      printf '%s\n' "unknown"
      ;;
  esac
}

tangtang_help() {
  cat <<'EOF'
糖糖公共函数（被其它脚本 source）

小朋友反应（客厅短窗，见 data/child_reactions.json）
  配合 joined    回一句暖的，然后停。不连着夸。
  反对 oppose    轻轻让开，这条今天不再叫这个孩子。不争、不加大声音。
  沉默 silent    合法。不追问。同一事件连续两次，今天先跳过。
  推迟 defer     回一句好，晚上同事件若还有档才再试一次。
  不会 wont      帮一小下就停。英语只说这句的意思。
  听不清 unclear 不让人家重复。比熊可回一声汪汪，朋友不回。
  今天别叫 stop_today  让开，今天这条不再叫。
  敷衍 perfunctory     当沉默，不当成配合。
  超时 timeout         同沉默，不回。

  一轮最多再回一句。儿童原话不进账本。
  预览：./cat-turn.sh --print english hanghang 不要
EOF
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  case "${1:-help}" in
    help|-h|--help) tangtang_help; exit 0 ;;
    *) tangtang_help; exit 1 ;;
  esac
fi
