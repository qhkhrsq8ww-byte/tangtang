#!/bin/bash
# ============================================================
# 糖糖 · 客厅软硬件自检
#
# 云上 Linux 不能验证 MAONO AU-BM10、蓝牙音箱、avfoundation :2。
# 不要假装测过。Linux 打印「云上无客厅麦/音箱，跳过实声」并 exit 0（skip-not-fail）。
#
# 用法: ./cat.sh hwcheck
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

OS="$(uname -s)"
echo "糖糖硬件自检"
echo "os	$OS"

have() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "tool	$1	ok"
    return 0
  fi
  echo "tool	$1	missing"
  return 1
}

have sox || true
have ffmpeg || true
have python3 || true
if command -v say >/dev/null 2>&1; then
  echo "tool	say	ok"
else
  echo "tool	say	missing"
fi

if [ "$OS" != "Darwin" ]; then
  echo "hw	mic	skip"
  echo "hw	speaker	skip"
  echo "hw	avfoundation	skip"
  echo "云上无客厅麦/音箱，跳过实声"
  echo "skip-not-fail"
  exit 0
fi

echo "hw	platform	darwin"
if command -v ffmpeg >/dev/null 2>&1; then
  echo "avfoundation 设备："
  ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | sed -n 's/^/[avfoundation] /p' || true
fi
if command -v osascript >/dev/null 2>&1; then
  out="$(osascript -e 'output volume of (get volume settings)' 2>/dev/null || true)"
  [ -n "$out" ] && echo "volume	$output"
fi
tmp="/tmp/tangtang-hwcheck-$$.wav"
if command -v ffmpeg >/dev/null 2>&1; then
  if ffmpeg -hide_banner -loglevel error -f avfoundation -i ":2" -t 0.3 -y "$tmp" 2>/dev/null; then
    echo "hw	record0.3s	ok"
  else
    echo "hw	record0.3s	fail"
  fi
  rm -f "$tmp"
else
  echo "hw	record0.3s	skip"
fi
echo "darwin-hwcheck-done"
exit 0
