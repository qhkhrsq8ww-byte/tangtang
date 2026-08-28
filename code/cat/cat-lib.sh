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
export TANGTANG_PROFILE TANGTANG_CHILD_NAME
export TANGTANG_PROJECTOR_IP TANGTANG_AIRPLAY_PORT
export TANGTANG_REQUIRE_PRESENCE
export TANGTANG_HOST_QIAQIA TANGTANG_HOST_HANGHANG

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
