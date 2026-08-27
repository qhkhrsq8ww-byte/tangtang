#!/bin/bash
# 糖糖 · 声纹特征提取（ffmpeg 频段能量，无需 numpy）
# 用法: ./cat-vp-feature.sh <pcm文件>  →  输出 8 维特征向量（JSON 单行）
# 特征: 低频300/中频700/中高频1500/高频3000 能量 + RMS + Peak + LRA + 过零率
FF=/Users/lv/.qclaw/workspace/cat/bin/ffmpeg
PCM="${1:?用法: cat-vp-feature.sh <pcm文件>}"
[ -f "$PCM" ] || { echo "{\"error\":\"文件不存在: $PCM\"}"; exit 1; }

# 1) 频段平均能量 (dB)，输出形如 "mean_volume: -36.6 dB" → 取 -36.6
get_vol() { # $1=filter
  "$FF" -hide_banner -loglevel info -f s16le -ar 16000 -ac 1 -i "$PCM" -af "$1,volumedetect" -f null - 2>&1 \
    | grep "mean_volume" | tail -1 | sed -E 's/.*mean_volume: (-?[0-9.]+) dB.*/\1/'
}
LOW=$(get_vol "lowpass=f=300")
MID=$(get_vol "bandpass=f=700:w=600")
MIDHI=$(get_vol "bandpass=f=1500:w=1000")
HIGH=$(get_vol "highpass=f=3000")
[ -z "$LOW" ] && LOW=-99

# 2) 总 RMS / Peak (dB)
RMS=$(get_vol "anull")
[ -z "$RMS" ] && RMS=-99
PEAK=$("$FF" -hide_banner -loglevel info -f s16le -ar 16000 -ac 1 -i "$PCM" -af "volumedetect" -f null - 2>&1 | grep "max_volume" | tail -1 | sed -E 's/.*max_volume: (-?[0-9.]+) dB.*/\1/')
[ -z "$PEAK" ] && PEAK=-99

# 3) LRA 响度范围（loudnorm JSON）
LRA=$("$FF" -hide_banner -loglevel info -f s16le -ar 16000 -ac 1 -i "$PCM" -af "loudnorm=print_format=json" -f null - 2>&1 | grep '"input_lra"' | head -1 | sed 's/.*"input_lra"[[:space:]]*:[[:space:]]*"\([0-9.]*\)".*/\1/')
[ -z "$LRA" ] && LRA=0

# 4) 过零率（astats: "Zero crossings rate: 0.062500"）
ZCR=$("$FF" -hide_banner -loglevel info -f s16le -ar 16000 -ac 1 -i "$PCM" -af "astats=metadata=1:reset=1" -f null - 2>&1 | grep "Zero crossings rate" | tail -1 | awk '{print $7}')
[ -z "$ZCR" ] && ZCR=0

# 输出 JSON
/usr/bin/python3 -c "
import json
feat={'low':float('$LOW'),'mid':float('$MID'),'midhi':float('$MIDHI'),'high':float('$HIGH'),'rms':float('$RMS'),'peak':float('$PEAK'),'lra':float('$LRA'),'zcr':float('$ZCR')}
print(json.dumps(feat))
"
