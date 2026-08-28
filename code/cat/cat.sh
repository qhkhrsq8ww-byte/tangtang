#!/bin/bash
# ============================================================
# 糖糖统一入口（自动适配投影状态，走智能大脑）
# 用法:
#   ./cat.sh                  # 上糖糖（投影开着->全屏舞台；没开->语音报平安）
#   ./cat.sh "想说的话"       # 说一句话（带人设语气包装）
#   ./cat.sh -f               # 强制仅声音（不管投影）
#   ./cat.sh -p               # 强制透明宠物浮现
#   ./cat.sh -s               # 强制全屏舞台
#   ./cat.sh status           # 查看糖糖当前心情状态
#   ./cat.sh habits [成员]    # 查看五口之家习惯摘要（不投屏）
#   ./cat.sh preview          # 打印今日语音提醒文案（不发声）
#   ./cat.sh today            # 今日休息四步（问糖糖→学英语→锻炼→休息）
#   ./cat.sh today --preview  # 只看四句话，不开麦不发声
#   ./cat.sh openclaw --preview
#   ./cat.sh openclaw --now --submit   # 四步自测并提交 GitHub 报告
#   ./cat.sh openclaw-report
#   ./cat.sh schedule         # 今天时刻表会响哪些
#   ./cat.sh features         # 糖糖有哪些功能
#   ./cat.sh alarm            # 立刻试上学闹铃（跳过日期）
#   ./cat.sh english          # 试航航二年级英语小伴读
#   ./cat.sh english qiaqia   # 试洽洽六年级英语小伴读
#   ./cat.sh turn             # 客厅试听：说一句 → 录音窗 → 回或不回
#   ./cat.sh presence         # 看洽洽/航航是否在客厅网段
#   ./cat.sh data             # 看记忆文件写在本机哪
#   ./cat.sh chat "想聊的"     # 云端真对话
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

MOOD_FILE="$CAT_DIR/cat-mood.txt"
TEXT=""
STATUS_REQ=0
CHAT_REQ=0
FORCE_VOICE=0
FORCE_STAGE=0
FORCE_PET=0
while [ $# -gt 0 ]; do
  case "$1" in
    -f) FORCE_VOICE=1; shift;;
    -s) FORCE_STAGE=1; shift;;
    -p) FORCE_PET=1; shift;;
    status) STATUS_REQ=1; shift;;
    habits)
      shift
      /usr/bin/python3 "$CAT_DIR/cat-family.py" summary "$@"
      exit 0
      ;;
    preview)
      "$CAT_DIR/cat-schedule.sh" preview
      exit 0
      ;;
    today)
      shift
      exec "$CAT_DIR/cat-today.sh" "$@"
      ;;
    openclaw)
      shift
      exec "$CAT_DIR/cat-openclaw.sh" "$@"
      ;;
    openclaw-report)
      shift
      exec "$CAT_DIR/cat-openclaw.sh" --report-only "$@"
      ;;
    schedule)
      shift
      if [ $# -eq 0 ]; then
        exec "$CAT_DIR/cat-schedule.sh" today
      fi
      exec "$CAT_DIR/cat-schedule.sh" "$@"
      ;;
    features)
      cat <<'EOF'
糖糖现在有这些功能（客厅 Mac Air 出声，先不上投影）

1. 说话陪伴
   比熊糖糖口吻。航航用玩伴，洽洽用朋友。
   上学日白天只跟爷爷奶奶说，不跟小朋友互动。
   ./cat.sh "想说的话"    ./cat.sh chat "聊几句"

2. 认人与习惯
   声纹只回答「是谁」；习惯按爷爷/奶奶/爸爸/洽洽/航航分开记。
   儿童原话不进家庭共享。  ./cat.sh habits

3. 定时语音提醒
   喝水、吃饭、休息、照顾糖糖（加水/出门/吃饭/梳毛）。
   上学日白天只跟爷爷奶奶说（航航16:00到、洽洽18:00到）。
   周末/晚上才看出门。  ./cat.sh preview    ./cat.sh presence

4. 上学闹铃
   上学日 06:30 铃+说话；周末和节假日休息；调休上课日也响。
   卧室也要听到，不看出门检测。开学前 07:30 仍用普通早安。
   试听：./cat.sh alarm

5. 本机记性
   状态/习惯/声纹/对话只写 Mac Air 硬盘，不写路由器盘。
   ./cat.sh data

6. 英语小伴读（译林牛津·江苏）
   航航小学二年级，洽洽小学六年级。英语偏弱：中英夹一句，给选择，不督学。
   上学日航航 16:20、洽洽 19:10；周末放假休息。
   试听：./cat.sh english    ./cat.sh english qiaqia

7. 客厅语音小回合（只在客厅）
   英语小伴读说完一句、等音箱播完，再开约 5 秒麦。有人应就听一句，糖糖最多回一句；没人应就算了，不追问。
   麦是客厅 Mac 旁的 MAONO AU-BM10。音箱要设成 Mac 默认输出；若还在儿童房，客厅听不见回话。
   试：./cat.sh turn    ./cat.sh turn english hanghang
   预览不开麦：./cat.sh preview

8. 今日休息四步（问糖糖 → 学英语 → 锻炼 → 休息）
   小朋友在家时，客厅依次完成四项：打招呼听一句、译林英语一句、动一动、歇一会儿。
   一步一句，再听窗，不连着念。默认航航玩伴；洽洽用 --who qiaqia。
   试：./cat.sh today    ./cat.sh today hanghang    ./cat.sh today --preview

9. OpenClaw 田间报告（只含标签，不含小朋友原话）
   客厅 2013 Mac 跑四步，写成 reports/openclaw/日期.json 并推 GitHub。
   ./cat.sh openclaw --preview
   ./cat.sh openclaw --now --submit
   ./cat.sh openclaw-report
EOF
      exit 0
      ;;
    alarm)
      exec "$CAT_DIR/cat-schedule.sh" fire --force alarm school
      ;;
    english)
      shift
      who="${1:-hanghang}"
      exec "$CAT_DIR/cat-schedule.sh" fire --force english "$who"
      ;;
    turn)
      shift
      exec "$CAT_DIR/cat-turn.sh" "$@"
      ;;
    presence)
      exec "$CAT_DIR/cat-presence.sh"
      ;;
    data)
      echo "记忆目录（Mac Air 本机硬盘，不写路由器）"
      echo "$TANGTANG_DATA_DIR"
      ls -1 "$TANGTANG_DATA_DIR" 2>/dev/null | grep -E 'cat-(state|memory|habits|voiceprints|chat-history|remind-log|turn-ledger)' || true
      exit 0
      ;;
    chat) CHAT_REQ=1; shift;;
    *) TEXT="$1"; shift;;
  esac
done

brain_say(){
  local event="$1"; local arg="${2:-}"
  if [ -n "$arg" ]; then
    "$CAT_DIR/cat-talk.sh" "$event" "$arg"
  else
    "$CAT_DIR/cat-talk.sh" "$event"
  fi
}

if [ "$STATUS_REQ" = "1" ]; then
  /usr/bin/python3 "$CAT_DIR/cat-brain.py" status
  exit 0
fi

# 上学日白天不跟洽洽航航互动（他们不在家）；客厅里按爷爷奶奶说
if [ -n "${TANGTANG_MEMBER_ID:-${TANGTANG_SPEAKER:-}}" ] \
   && tangtang_child_at_school "${TANGTANG_MEMBER_ID:-${TANGTANG_SPEAKER:-}}"; then
  echo "[糖糖] 上学期间不跟小朋友互动（按作息还没到家）"
  exit 0
fi
if tangtang_is_school_day && tangtang_child_at_school hanghang && tangtang_child_at_school qiaqia; then
  export TANGTANG_PROFILE=elder
  export TANGTANG_CHILD_NAME="${TANGTANG_CHILD_NAME:-爷爷奶奶}"
fi

if [ "$CHAT_REQ" = "1" ]; then
  if tangtang_projector_on; then
    tangtang_ensure_stage
  fi
  if [ -z "$TEXT" ]; then
    TEXT="糖糖，我来啦"
  fi
  reply="$(/usr/bin/python3 "$CAT_DIR/cat-chat.py" "$TEXT")"
  echo "[idle] $reply" > "$MOOD_FILE"
  "$CAT_DIR/cat-say.sh" "$reply" cute
  echo "[糖糖·云端对话] 回复：$reply"
  exit 0
fi

if [ "$FORCE_VOICE" = "1" ]; then
  MODE="voice"
elif [ "$FORCE_STAGE" = "1" ]; then
  MODE="stage"
elif [ "$FORCE_PET" = "1" ]; then
  MODE="pet"
elif tangtang_projector_on; then
  MODE="stage"
else
  MODE="voice"
fi

case "$MODE" in
  stage)
    tangtang_ensure_stage
    if ! system_profiler SPDisplaysDataType 2>/dev/null | grep -q "Mirror: On"; then
      echo "提示：未检测到镜像。点菜单栏『屏幕镜像』选投影；连上后糖糖舞台自动上屏，点画面可进全屏。"
    fi
    if [ -n "$TEXT" ]; then
      brain_say "say" "$TEXT"
    else
      brain_say "greet"
    fi
    echo "[糖糖] 投影在线 → 全屏舞台 + 智能说话"
    ;;
  pet)
    tangtang_ensure_server
    open "http://127.0.0.1:8080/cat-pet.html"
    osascript -e "tell application \"Safari\" to if (count of windows) > 0 then set URL of front document to \"http://127.0.0.1:8080/cat-pet.html\"" 2>/dev/null
    if ! system_profiler SPDisplaysDataType 2>/dev/null | grep -q "Mirror: On"; then
      echo "提示：未检测到镜像。点菜单栏『屏幕镜像』选投影；连上后糖糖自动上屏，不弹窗遮挡。"
    fi
    if [ -n "$TEXT" ]; then
      brain_say "say" "$TEXT"
    else
      brain_say "greet"
    fi
    echo "[糖糖] 投影在线 → 透明浮现宠物 + 智能说话"
    ;;
  voice)
    if [ -n "$TEXT" ]; then
      brain_say "say" "$TEXT"
    else
      brain_say "greet"
    fi
    echo "[糖糖] 投影离线 → 仅声音(智能)"
    ;;
esac
exit 0
