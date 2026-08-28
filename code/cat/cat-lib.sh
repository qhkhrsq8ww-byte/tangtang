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
export TANGTANG_PROFILE TANGTANG_CHILD_NAME
export TANGTANG_PROJECTOR_IP TANGTANG_AIRPLAY_PORT
export TANGTANG_REQUIRE_PRESENCE
export TANGTANG_HOST_QIAQIA TANGTANG_HOST_HANGHANG
export TANGTANG_SCHOOL_START TANGTANG_ALARM_DOW

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
