#!/bin/bash
# 糖糖 · 客厅在场检测（小朋友手机是否在家里 Wi-Fi / 客厅网段）
# 用法: ./cat-presence.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

echo "客厅在场检测（Mac 在客厅，看手机是否连着家里网）"
if [ -z "${TANGTANG_HOST_QIAQIA:-}" ] && [ -z "${TANGTANG_HOST_HANGHANG:-}" ]; then
  echo "未配置。在 tangtang-config.sh 里填写："
  echo "  export TANGTANG_HOST_QIAQIA=\"洽洽手机IP\""
  echo "  export TANGTANG_HOST_HANGHANG=\"航航手机IP\""
  echo "路由器里给两部手机绑死 IP 更稳。iPhone 可能不回 ping，会再用 ARP 判断。"
  exit 2
fi

check_one() {
  local name="$1" ip="$2"
  if [ -z "$ip" ]; then
    echo "  $name  未填 IP"
    return
  fi
  if tangtang_host_on_lan "$ip"; then
    echo "  $name  在（$ip）"
  else
    echo "  $name  不在（$ip）"
  fi
}

check_one "洽洽" "${TANGTANG_HOST_QIAQIA:-}"
check_one "航航" "${TANGTANG_HOST_HANGHANG:-}"

names="$(tangtang_kids_present)"
rc=$?
echo
if [ "$rc" = "0" ]; then
  echo "结论：客厅这边检测到 $names，可以播报。"
  exit 0
fi
echo "结论：没检测到小朋友，定时提醒会静音跳过。"
exit 1
