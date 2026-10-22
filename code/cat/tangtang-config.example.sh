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

# V4 runtime is the default conversation path.
export TANGTANG_V4_PIPELINE=1

# Optional VoiceStudio TTS (disabled by default; existing fallback chain remains active).
# Use a private/TLS-protected endpoint for remote servers; do not expose an unauthenticated API.
# export TANGTANG_VOICESTUDIO_ENABLED="1"
# export TANGTANG_VOICESTUDIO_URL="https://your-private-host.example/v1/audio/speech"
# export TANGTANG_VOICESTUDIO_API_KEY=""  # matches OMNIVOICE_API_KEY on the backend
# export TANGTANG_VOICESTUDIO_MODEL="tts-1"  # aliases VoiceStudio's active engine
# export TANGTANG_VOICESTUDIO_VOICE="default"
# export TANGTANG_VOICESTUDIO_TIMEOUT="18"
# export TANGTANG_VOICESTUDIO_INSTRUCTIONS="温柔、自然、亲切，像陪伴孩子的生活伙伴；语速适中，不要刻意装幼稚。"

# Optional alarm music override; defaults to bundled local audio.
# export TANGTANG_ALARM_MUSIC="/path/to/local/alarm-music.mp3"
# Bundled fallback includes assets/alarm_light.wav.
