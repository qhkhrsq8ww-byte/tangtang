#!/bin/bash
# 糖糖 · 语音转文字（百度语音识别 REST API）
# 用法: ./cat-stt-baidu.sh <pcm文件>
# Key 优先环境变量 BAIDU_STT_API_KEY / BAIDU_STT_SECRET_KEY
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

WAV="${1:-/tmp/cat_voice.wav}"
if [ -z "${BAIDU_STT_API_KEY:-}" ] || [ -z "${BAIDU_STT_SECRET_KEY:-}" ]; then
  if [ -f "$CAT_DIR/cat-stt-config.sh" ]; then
    # shellcheck disable=SC1091
    . "$CAT_DIR/cat-stt-config.sh"
  fi
fi
API_KEY="${BAIDU_STT_API_KEY:-}"
SECRET="${BAIDU_STT_SECRET_KEY:-}"
if [ -z "$API_KEY" ] || [ -z "$SECRET" ]; then
  echo "[STT] 未配置百度 key，无法识别" >&2
  exit 1
fi
TOKEN=$(curl -s --max-time 10 "https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=$API_KEY&client_secret=$SECRET" | /usr/bin/python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('access_token',''))" 2>/dev/null)
if [ -z "$TOKEN" ]; then echo "[STT] token 获取失败" >&2; exit 1; fi
PCM="$WAV"
RESULT=$(curl -s --max-time 15 -X POST \
  "https://vop.baidubce.com/server_api?dev_pid=1537&cuid=tangtang&token=$TOKEN" \
  -H "Content-Type: audio/pcm;rate=16000" \
  --data-binary @"$PCM" 2>/dev/null)
echo "$RESULT" | /usr/bin/python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('result',[''])[0] if d.get('err_no',1)==0 else '[STT错误]'+str(d))" 2>/dev/null
rm -f "$PCM"
