#!/bin/bash
# 糖糖本地习惯成长：标签进客厅 Mac，不记小朋友原话。
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CAT="$ROOT/code/cat"
fail=0
tmp="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-habit.XXXXXX")"
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

export TANGTANG_DATA_DIR="$tmp"
export TANGTANG_FAKE_TODAY=2026-09-01
export TANGTANG_FAKE_TIME=16:20
export TANGTANG_TTS=0
unset TANGTANG_HABIT_READONLY
unset TANGTANG_HABIT_SLOTS

H="$CAT/cat-habits.py"
speak() { /usr/bin/python3 "$H" should-speak "$1" "$2"; }
observe() { /usr/bin/python3 "$H" observe "$@"; }
prefer() { /usr/bin/python3 "$H" prefer-line "$1" "$2"; }

echo "== oppose mute survives fake reboot =="
observe hanghang english oppose >/dev/null
g1="$(speak english hanghang)"
echo "$g1" | grep -q '^skip' || { echo "fail oppose should skip: $g1"; fail=1; }
# fake reboot: new interpreter, same file
g2="$(/usr/bin/python3 "$H" should-speak english hanghang)"
echo "$g2" | grep -q '^skip' || { echo "fail reboot lost mute: $g2"; fail=1; }
test -f "$tmp/cat-habit-growth.json" || { echo "fail missing growth file"; fail=1; }

echo "== silent streak skips remaining today =="
tmp2="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-habit.XXXXXX")"
TANGTANG_DATA_DIR="$tmp2" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 \
  observe hanghang english silent >/dev/null
g="$(TANGTANG_DATA_DIR="$tmp2" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:21 \
  speak english hanghang)"
echo "$g" | grep -q '^speak' || { echo "fail first silent should still speak: $g"; fail=1; }
TANGTANG_DATA_DIR="$tmp2" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:22 \
  observe hanghang english silent >/dev/null
g="$(TANGTANG_DATA_DIR="$tmp2" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:23 \
  speak english hanghang)"
echo "$g" | grep -q '^skip' || { echo "fail silent streak should skip: $g"; fail=1; }
rm -rf "$tmp2"

echo "== defer retry at most once =="
tmp3="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-habit.XXXXXX")"
export TANGTANG_HABIT_SLOTS="16:20,20:00"
TANGTANG_DATA_DIR="$tmp3" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 \
  observe hanghang english defer >/dev/null
g="$(TANGTANG_DATA_DIR="$tmp3" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:21 \
  speak english hanghang)"
echo "$g" | grep -q '^skip' || { echo "fail defer same hour should skip: $g"; fail=1; }
g="$(TANGTANG_DATA_DIR="$tmp3" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=20:00 \
  speak english hanghang)"
echo "$g" | grep -q '^speak' || { echo "fail defer later slot should speak once: $g"; fail=1; }
g="$(TANGTANG_DATA_DIR="$tmp3" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=20:05 \
  speak english hanghang)"
echo "$g" | grep -q '^skip' || { echo "fail defer second retry should skip: $g"; fail=1; }
unset TANGTANG_HABIT_SLOTS
rm -rf "$tmp3"

echo "== joined prefers that line_id =="
tmp4="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-habit.XXXXXX")"
TANGTANG_DATA_DIR="$tmp4" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=15:30 \
  observe hanghang water joined water_play 1 home >/dev/null
got="$(TANGTANG_DATA_DIR="$tmp4" prefer water hanghang)"
[ "$got" = "water_play" ] || { echo "fail prefer line got '$got'"; fail=1; }
# oppose demotes
TANGTANG_DATA_DIR="$tmp4" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=15:31 \
  observe hanghang water oppose water_play 1 home >/dev/null
# still no crash; preferred may drop
TANGTANG_DATA_DIR="$tmp4" prefer water hanghang >/dev/null
rm -rf "$tmp4"

echo "== qiaqia oppose does not mute hanghang =="
tmp5="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-habit.XXXXXX")"
TANGTANG_DATA_DIR="$tmp5" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=19:10 \
  observe qiaqia english oppose >/dev/null
g_h="$(TANGTANG_DATA_DIR="$tmp5" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 \
  speak english hanghang)"
g_q="$(TANGTANG_DATA_DIR="$tmp5" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=19:10 \
  speak english qiaqia)"
echo "$g_h" | grep -q '^speak' || { echo "fail hanghang leaked qiaqia mute: $g_h"; fail=1; }
echo "$g_q" | grep -q '^skip' || { echo "fail qiaqia should be muted: $g_q"; fail=1; }
rm -rf "$tmp5"

echo "== habits file contains no transcript-like fields =="
/usr/bin/python3 -c "
import json, os, sys, importlib.util
spec = importlib.util.spec_from_file_location('tangtang_habits', '$CAT/cat-habits.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ok, bad = mod.dump_ok('$tmp')
assert ok, bad
raw = open('$tmp/cat-habit-growth.json', encoding='utf-8').read()
for k in ('transcript', 'utterance', 'pcm', 'audio', 'embedding', 'voiceprint'):
    assert k not in raw, k
data = json.load(open('$tmp/cat-habit-growth.json'))
assert '\"text\"' not in json.dumps(data)
print('no transcript fields ok')
" || { echo "fail transcript fields"; fail=1; }

echo "== decay/cap empty ledger =="
tmp6="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-habit.XXXXXX")"
out="$(TANGTANG_DATA_DIR="$tmp6" /usr/bin/python3 "$H" decay)"
echo "$out" | grep -q 'decay ok' || { echo "fail empty decay: $out"; fail=1; }
out="$(TANGTANG_DATA_DIR="$tmp6" /usr/bin/python3 "$H" ingest)"
echo "$out" | grep -q 'ingested 0' || { echo "fail empty ingest: $out"; fail=1; }
rm -rf "$tmp6"

echo "== ledger adapter (stub oppose / stop_today, no child text) =="
tmp7="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-habit.XXXXXX")"
mkdir -p "$tmp7"
cat > "$tmp7/cat-turn-ledger.json" <<'JSON'
{"version":1,"turns":[
  {"ts":"2026-09-01T16:20:00","event":"english","who":"hanghang","result":"oppose","stt":false,"presence":"home","seconds":5,"rms":800,"spoke":true},
  {"ts":"2026-09-01T16:21:00","event":"english","who":"hanghang","result":"stop_today","stt":false,"presence":"home","seconds":5,"rms":400,"spoke":true}
]}
JSON
out="$(TANGTANG_DATA_DIR="$tmp7" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:22 \
  /usr/bin/python3 "$H" ingest)"
echo "$out" | grep -q 'ingested 2' || { echo "fail ingest stub ledger: $out"; fail=1; }
g="$(TANGTANG_DATA_DIR="$tmp7" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:22 \
  speak english hanghang)"
echo "$g" | grep -q '^skip' || { echo "fail ingested oppose/stop mute: $g"; fail=1; }
if grep -E 'transcript|"text"' "$tmp7/cat-habit-growth.json" >/dev/null; then
  echo "fail growth copied text"; fail=1
fi
rm -rf "$tmp7"

echo "== features / help mention local habits, no child speech =="
feat="$("$CAT/cat.sh" features)"
echo "$feat" | grep -q '习惯会记在客厅 Mac，不记小朋友原话' || { echo "fail features missing habit line"; fail=1; }
echo "$feat" | grep -q '不上传训练' || { echo "fail features missing no-train"; fail=1; }

echo "== remind --print dry-run shows mute reason =="
tmp8="$(mktemp -d "${TMPDIR:-/tmp}/tangtang-habit.XXXXXX")"
TANGTANG_DATA_DIR="$tmp8" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 \
  observe hanghang english oppose >/dev/null
out="$(TANGTANG_DATA_DIR="$tmp8" TANGTANG_FAKE_TODAY=2026-09-01 TANGTANG_FAKE_TIME=16:20 \
  TANGTANG_TTS=0 "$CAT/cat-remind.sh" --print english hanghang 2>/dev/null)"
echo "$out" | grep -q '这次不说（习惯：' || { echo "fail remind print mute: $out"; fail=1; }
rm -rf "$tmp8"

if [ "$fail" = "0" ]; then
  echo "test-habit-growth ok"
  exit 0
fi
echo "test-habit-growth failed"
exit 1
