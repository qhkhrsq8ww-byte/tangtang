#!/bin/bash
# 复制为 tangtang-config.sh 后按家庭填写。tangtang-config.sh 不入库。
#   cp tangtang-config.example.sh tangtang-config.sh

# play=航航对话；friend=洽洽对话。语音识别成功后按名册覆盖。
export TANGTANG_PROFILE="play"

# 房间定时提醒默认 friend（少卖萌，全家都能听）
export TANGTANG_REMIND_PROFILE="friend"

# 上学闹铃：2026-09-01 起，上学日 06:30；周末/节假日休息
export TANGTANG_SCHOOL_START="2026-09-01"
export TANGTANG_ALARM_DOW="1-5"
# 白天上学：约 07:30 后不跟小朋友互动。航航 16:00 到家，洽洽 18:00 到家。
export TANGTANG_SCHOOL_LEAVE="07:30"
export TANGTANG_HOME_HANGHANG="16:00"
export TANGTANG_HOME_QIAQIA="18:00"
# 放假日历：仓库 data/school_calendar.txt （寒假暑假按学校通知追加）
# 小朋友临时在家：data/rest_days.txt 写日期，或 CAT_CHILD_HOME=1 / ./cat.sh today --home
# 不是每周五都休息。./cat.sh today 会当作今天在家，不关爷爷奶奶提醒，不改开学闹铃。
# OpenClaw 下午实测：./cat.sh openclaw（--preview / --now）。音箱=系统默认输出且放客厅。
# 麦 MAONO AU-BM10，ffmpeg avfoundation :2。先 ./cat.sh hwcheck。

# 英语小伴读：译林牛津。航航二年级、洽洽六年级。上学日到家后各一句。
# 说完一句后在客厅开约 5 秒麦（见 cat-turn.sh）。其它提醒默认仍单向。
# export TANGTANG_ENGLISH_FILE="/absolute/path/to/english_jiangsu.json"
# export TANGTANG_TURN_EVENTS="english"
# export TANGTANG_TURN_SECONDS="5"
# 若希望喝水/吃饭等提醒也开窗（不建议）：export TANGTANG_TURN_ALL=1

# 客厅互动：蓝牙音箱应作为 Mac 默认音频输出（系统设置 → 声音 → 输出）。
# 麦在客厅 Mac 旁（MAONO AU-BM10）。不要做第二只音箱。
# 若音箱仍放在儿童房，客厅听不见糖糖回话。

# 糖糖口头称呼。语音识别到家人后会改成对方的 display_name。
export TANGTANG_CHILD_NAME="小朋友"

# 家庭名册：仓库 data/family.json（爷爷/奶奶/爸爸/洽洽/航航）
# export TANGTANG_FAMILY_FILE="/absolute/path/to/family.json"

# 小朋友手机 IP（客厅 Mac 同一网段）。任一台在线才播定时语音。
# 路由器里绑死 DHCP。iPhone 可能不回 ping，脚本会再看 ARP。
# 查 IP：手机连家里 Wi-Fi 后，在 Mac 上 arp -a
export TANGTANG_HOST_QIAQIA=""
export TANGTANG_HOST_HANGHANG=""
export TANGTANG_REQUIRE_PRESENCE=1

# 投影 AirPlay（按家里局域网修改；这轮语音提醒不用）
export TANGTANG_PROJECTOR_IP="192.168.31.104"
export TANGTANG_AIRPLAY_PORT="61949"

# 记忆目录：先只写客厅 Mac Air 本机硬盘，不写路由器硬盘。
# 不填则默认：~/Library/Application Support/Tangtang
# 以后要备份到路由器盘再单独做，现在不要填 /Volumes/ 或 smb://
# export TANGTANG_DATA_DIR="$HOME/Library/Application Support/Tangtang"

# 百度语音识别（优先环境变量；也可放在 gitignore 的 cat-stt-config.sh）
# export BAIDU_STT_API_KEY=""
# export BAIDU_STT_SECRET_KEY=""
