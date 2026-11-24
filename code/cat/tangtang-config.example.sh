#!/bin/bash
# 复制为 tangtang-config.sh 后按家庭填写。tangtang-config.sh 不入库。
#   cp tangtang-config.example.sh tangtang-config.sh

# play=约9岁玩伴模式；friend=约12岁朋友模式
export TANGTANG_PROFILE="play"

# 糖糖口头称呼。不要把真实姓名提交到 Git。
export TANGTANG_CHILD_NAME="小朋友"

# 投影 AirPlay（按家里局域网修改）
export TANGTANG_PROJECTOR_IP="192.168.31.x"  # 替换为家中投影设备 IP，不要提交真实地址
export TANGTANG_AIRPLAY_PORT="61949"

# 百度语音识别（优先环境变量；也可放在 gitignore 的 cat-stt-config.sh）
# export BAIDU_STT_API_KEY=""
# export BAIDU_STT_SECRET_KEY=""

# V4 runtime is the default conversation path.
export TANGTANG_V4_PIPELINE=1

# Model backend: direct (default) or hermes. Hermes remains opt-in until M6 acceptance.
# export TANGTANG_LLM_BACKEND="hermes"
# export TANGTANG_HERMES_BASE_URL="http://127.0.0.1:8642"
# export TANGTANG_HERMES_API_KEY=""  # 与 Hermes API_SERVER_KEY 一致；只保存在本机配置
# export TANGTANG_HERMES_MODEL="hermes-agent"
# export TANGTANG_HERMES_TIMEOUT="15"
# Initial Hermes adapter has a zero-tool allowlist. Do not enable MCP tools before security review.
# TANGTANG_ALLOW_PRIVATE_LLM / TANGTANG_ALLOW_UNKNOWN_LLM remain separate privacy opt-ins.

# Optional alarm music override; defaults to bundled local audio.
# export TANGTANG_ALARM_MUSIC="/path/to/local/alarm-music.mp3"
# Bundled fallback includes assets/alarm_light.wav.
