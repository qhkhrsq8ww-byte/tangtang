#!/bin/bash
# 糖糖 · 客厅在场检测（作息 + 小朋友手机）
# 用法: ./cat-presence.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

echo "客厅在场（$(tangtang_today) $(tangtang_now_hm)）"
echo "作息：上学日 07:30 后小朋友不在家；航航 ${TANGTANG_HOME_HANGHANG:-16:00} 到，洽洽 ${TANGTANG_HOME_QIAQIA:-18:00} 到。"

if tangtang_is_holiday; then
  echo "今天：放假，小朋友在家，可以互动。"
elif tangtang_is_makeup_school; then
  echo "今天：调休上课。"
elif tangtang_is_school_day; then
  echo "今天：上学日。"
else
  echo "今天：不上学（周末或未开学）。"
fi

echo
echo "作息判断："
if tangtang_child_at_school hanghang; then
  echo "  航航  上学未归（${TANGTANG_HOME_HANGHANG:-16:00} 到家）"
else
  echo "  航航  按作息在家（可互动）"
fi
if tangtang_child_at_school qiaqia; then
  echo "  洽洽  上学未归（${TANGTANG_HOME_QIAQIA:-18:00} 到家）"
else
  echo "  洽洽  按作息在家（可互动）"
fi

echo
echo "手机网段："
if [ -z "${TANGTANG_HOST_QIAQIA:-}" ] && [ -z "${TANGTANG_HOST_HANGHANG:-}" ]; then
  echo "  未配置手机 IP。周末提醒仍需要填写才能看出门。"
else
  check_one() {
    local name="$1" ip="$2"
    if [ -z "$ip" ]; then
      echo "  $name  未填 IP"
      return
    fi
    if tangtang_host_on_lan "$ip"; then
      echo "  $name  手机在网（$ip）"
    else
      echo "  $name  手机不在网（$ip）"
    fi
  }
  check_one "洽洽" "${TANGTANG_HOST_QIAQIA:-}"
  check_one "航航" "${TANGTANG_HOST_HANGHANG:-}"
fi

echo
kids="$(tangtang_kids_interactable)"
rc=$?
if tangtang_is_school_day && [ "$rc" != "0" ]; then
  echo "结论：小朋友上学未归。白天只跟爷爷奶奶说话，不跟洽洽航航互动。"
  exit 1
fi
if [ "$rc" = "0" ]; then
  echo "结论：现在可以跟 $kids 互动。"
  exit 0
fi
if [ "$rc" = "2" ]; then
  echo "结论：未配置手机 IP，周末/晚上的出门检测不可用。"
  exit 2
fi
echo "结论：没检测到可互动的小朋友，针对小朋友的提醒会跳过。"
exit 1
