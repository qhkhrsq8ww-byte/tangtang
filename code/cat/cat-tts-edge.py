#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
糖糖正式音色：微软 Edge Neural TTS。
用法: cat-tts-edge.py "文本" [rate_delta] [pitch_delta]
  rate_delta: 整数，如 -5(慢5%) / 3(快3%)，默认 -5
  pitch_delta: 整数，如 0(原始音高) / -2(-2Hz)，默认 0
  TANGTANG_TTS_VOICE: 可选音色名；默认 zh-CN-XiaoxiaoNeural
输出: /tmp/cat_tts.mp3
"""
import sys
import os
import asyncio

TEXT = sys.argv[1] if len(sys.argv) > 1 else "汪汪"
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


def selected_voice():
    """Keep Xiaoxiao as the production default; allow explicit local A/B testing."""
    return (os.environ.get("TANGTANG_TTS_VOICE") or "").strip() or DEFAULT_VOICE


# rate: 整数 → 转成 "+5%" 或 "-10%"
r_raw = int(sys.argv[2]) if len(sys.argv) > 2 else -5
RATE = f"{'+' if r_raw >= 0 else ''}{r_raw}%"

# pitch: 整数 → 转成 "+5Hz" 或 "-5Hz"
p_raw = int(sys.argv[3]) if len(sys.argv) > 3 else 0
PITCH = f"{'+' if p_raw >= 0 else ''}{p_raw}Hz"

OUT = "/tmp/cat_tts.mp3"


async def main():
    import edge_tts
    tts = edge_tts.Communicate(TEXT, selected_voice(), rate=RATE, pitch=PITCH)
    await tts.save(OUT)
    print(f"OK {OUT} ({os.path.getsize(OUT)}B) voice={selected_voice()} rate={RATE} pitch={PITCH}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"ERR {e}", file=sys.stderr)
        sys.exit(1)
