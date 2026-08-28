#!/bin/bash
# 复制为 tangtang-config.sh 后按家庭填写。tangtang-config.sh 不入库。
#   cp tangtang-config.example.sh tangtang-config.sh

# play=约9岁玩伴模式；friend=约12岁朋友模式
export TANGTANG_PROFILE="play"

# 糖糖口头称呼。不要把真实姓名提交到 Git。
export TANGTANG_CHILD_NAME="小朋友"

# 投影 AirPlay（按家里局域网修改）
export TANGTANG_PROJECTOR_IP="192.168.31.104"
export TANGTANG_AIRPLAY_PORT="61949"

# 百度语音识别（优先环境变量；也可放在 gitignore 的 cat-stt-config.sh）
# export BAIDU_STT_API_KEY=""
# export BAIDU_STT_SECRET_KEY=""
