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
export TANGTANG_PROFILE TANGTANG_CHILD_NAME
export TANGTANG_PROJECTOR_IP TANGTANG_AIRPLAY_PORT

tangtang_ffmpeg() {
  if [ -x "$CAT_DIR/bin/ffmpeg" ]; then
    printf '%s\n' "$CAT_DIR/bin/ffmpeg"
  elif command -v ffmpeg >/dev/null 2>&1; then
    command -v ffmpeg
  else
    printf '%s\n' "$CAT_DIR/bin/ffmpeg"
  fi
}

# 播放音频：保留播放器真实退出状态，超时则终止并返回失败
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
      kill -TERM "$ap" 2>/dev/null || true
      wait "$ap" 2>/dev/null || true
      return 124
    fi
  done
  wait "$ap"
  return $?
}

TANGTANG_TTS_LOCK_DIR=""
tangtang_tts_unlock() {
  local lock="${TANGTANG_TTS_LOCK_DIR:-${TMPDIR:-/tmp}/tangtang-tts-output.lock}"
  if [ -d "$lock" ]; then
    local lock_pid=""
    [ -f "$lock/pid" ] && lock_pid="$(cat "$lock/pid" 2>/dev/null || true)"
    if [ "$lock_pid" = "$$" ]; then
      rm -rf "$lock"
    fi
  fi
}
tangtang_tts_lock() {
  local lock="${TMPDIR:-/tmp}/tangtang-tts-output.lock"
  if mkdir "$lock" 2>/dev/null; then
    TANGTANG_TTS_LOCK_DIR="$lock"
    printf '%s\n' "$$" > "$lock/pid"
    trap tangtang_tts_unlock EXIT
    return 0
  fi
  local lock_pid=""
  [ -f "$lock/pid" ] && lock_pid="$(cat "$lock/pid" 2>/dev/null || true)"
  if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
    echo "糖糖语音正在播放，避免重叠播放" >&2
    return 75
  fi
  local stale_dir="$lock.stale.$$"
  if mv "$lock" "$stale_dir" 2>/dev/null; then rm -rf "$stale_dir"; fi
  if mkdir "$lock" 2>/dev/null; then
    TANGTANG_TTS_LOCK_DIR="$lock"
    printf '%s\n' "$$" > "$lock/pid"
    trap tangtang_tts_unlock EXIT
    return 0
  fi
  echo "糖糖语音正在播放，避免重叠播放" >&2
  return 75
}

tangtang_ensure_server() {
  local url="http://127.0.0.1:8080/cat-stage.html"
  if curl -fsS -o /dev/null --max-time 3 "$url"; then
    return 0
  fi
  nohup python3 -m http.server 8080 --bind 127.0.0.1 --directory "$CAT_DIR" >/tmp/cathttp.log 2>&1 &
  local attempt
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    sleep 0.5
    if curl -fsS -o /dev/null --max-time 3 "$url"; then
      return 0
    fi
  done
  echo "糖糖本地页面服务启动失败" >&2
  return 1
}

tangtang_ensure_stage() {
  tangtang_ensure_server || return $?
  if ! pgrep -f "Safari.*cat-stage" >/dev/null 2>&1; then
    open "http://127.0.0.1:8080/cat-stage.html" || return $?
    ( osascript -e "tell application \\"Safari\\" to if (count of windows) > 0 then set URL of front document to \\"http://127.0.0.1:8080/cat-stage.html\\"" 2>/dev/null & )
  fi
  return 0
}

tangtang_ensure_pet() {
  tangtang_ensure_server || return $?
  if ! pgrep -f "Safari.*cat-desktop-pet" >/dev/null 2>&1; then
    open "http://127.0.0.1:8080/cat-desktop-pet.html" || return $?
    ( osascript -e "tell application \\"Safari\\" to if (count of windows) > 0 then set URL of front document to \\"http://127.0.0.1:8080/cat-desktop-pet.html\\"" 2>/dev/null & )
  fi
  return 0
}

tangtang_alarm_music_path() {
  local candidate="${TANGTANG_ALARM_MUSIC:-}"
  if [ -n "$candidate" ] && [ -f "$candidate" ]; then
    printf '%s\n' "$candidate"
  elif [ -f "$CAT_DIR/assets/wake_music_3min.mp3" ]; then
    printf '%s\n' "$CAT_DIR/assets/wake_music_3min.mp3"
  elif [ -f "$CAT_DIR/assets/alarm_light.wav" ]; then
    printf '%s\n' "$CAT_DIR/assets/alarm_light.wav"
  else
    return 1
  fi
}

tangtang_alarm_chime() {
  local chime="/System/Library/Sounds/Glass.aiff"
  if [ -f "$chime" ] && command -v afplay >/dev/null 2>&1; then
    afplay "$chime"
    return $?
  fi
  return 0
}

tangtang_alarm_music() {
  local music
  music="$(tangtang_alarm_music_path)" || return 0
  tangtang_play_audio "$music" "${TANGTANG_ALARM_MUSIC_SECONDS:-30}"
}

tangtang_projector_on() {
  nc -z -w 3 "$TANGTANG_PROJECTOR_IP" "$TANGTANG_AIRPLAY_PORT" 2>/dev/null
}

# Local-only fallback for direct file opening.
tangtang_open_local_pet() { open "file://$CAT_DIR/cat-desktop-pet.html"; }
