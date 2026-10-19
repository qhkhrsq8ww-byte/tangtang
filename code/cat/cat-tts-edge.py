#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
糖糖正式音色：微软晓晓（zh-CN-XiaoxiaoNeural）神经语音
用法: cat-tts-edge.py "文本" [rate_delta] [pitch_delta]
  rate_delta: 整数，如 -10(慢10%) / 5(快5%)，默认 -10
  pitch_delta: 整数，如 5(+5Hz) / -2(-2Hz)，默认 5
输出: /tmp/cat_tts.mp3
"""
import sys, os, asyncio

TEXT = sys.argv[1] if len(sys.argv) > 1 else "汪汪"

# rate: 整数 → 转成 "+5%" 或 "-10%"
r_raw = int(sys.argv[2]) if len(sys.argv) > 2 else -10
RATE = f"{'+' if r_raw >= 0 else ''}{r_raw}%"

# pitch: 整数 → 转成 "+5Hz" 或 "-5Hz"
p_raw = int(sys.argv[3]) if len(sys.argv) > 3 else 5
PITCH = f"{'+' if p_raw >= 0 else ''}{p_raw}Hz"

OUT = "/tmp/cat_tts.mp3"

async def main():
    import edge_tts
    tts = edge_tts.Communicate(TEXT, "zh-CN-XiaoxiaoNeural", rate=RATE, pitch=PITCH)
    await tts.save(OUT)
    print(f"OK {OUT} ({os.path.getsize(OUT)}B) rate={RATE} pitch={PITCH}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"ERR {e}", file=sys.stderr)
        sys.exit(1)
