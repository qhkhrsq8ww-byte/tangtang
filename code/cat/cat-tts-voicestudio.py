#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional VoiceStudio OpenAI-compatible TTS client for TangTang.

Synthesis only: cat-say.sh/cat-talk.sh own playback and fallback policy.
Never log spoken text or credentials.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

OUTPUT = Path("/tmp/cat_tts.mp3")
DEFAULT_URL = "http://127.0.0.1:3900/v1/audio/speech"
MAX_AUDIO_BYTES = 20 * 1024 * 1024


def _speed(rate_arg: str) -> float:
    """Convert the legacy shell rate delta (e.g. -10) to a TTS multiplier."""
    try:
        rate = int(rate_arg)
    except (TypeError, ValueError):
        rate = -10
    return max(0.25, min(4.0, (100 + rate) / 100.0))


def make_request(text: str, rate_arg: str = "-10") -> tuple[str, bytes, dict[str, str]]:
    text = str(text or "").strip()
    if not text:
        raise ValueError("empty text")
    if len(text) > 4096:
        raise ValueError("text exceeds VoiceStudio's 4096-character API limit")

    url = os.environ.get("TANGTANG_VOICESTUDIO_URL", DEFAULT_URL).strip()
    if not url.startswith(("https://", "http://")) or any(ch in url for ch in "\r\n"):
        raise ValueError("VoiceStudio URL must be a valid HTTP(S) endpoint")

    payload = {
        "model": os.environ.get("TANGTANG_VOICESTUDIO_MODEL", "tts-1").strip() or "tts-1",
        "input": text,
        "voice": os.environ.get("TANGTANG_VOICESTUDIO_VOICE", "default").strip() or "default",
        "response_format": "mp3",
        "speed": _speed(rate_arg),
    }
    instructions = os.environ.get("TANGTANG_VOICESTUDIO_INSTRUCTIONS", "").strip()
    if instructions:
        payload["instructions"] = instructions

    headers = {"Content-Type": "application/json", "Accept": "audio/mpeg"}
    api_key = os.environ.get("TANGTANG_VOICESTUDIO_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return url, json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers


def synthesize(text: str, rate_arg: str = "-10") -> Path:
    url, body, headers = make_request(text, rate_arg)
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    timeout = float(os.environ.get("TANGTANG_VOICESTUDIO_TIMEOUT", "18"))
    try:
        with urllib.request.urlopen(request, timeout=max(1.0, min(timeout, 60.0))) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            audio = response.read(MAX_AUDIO_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"VoiceStudio HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError(f"VoiceStudio request failed ({type(exc).__name__})") from None

    if len(audio) > MAX_AUDIO_BYTES:
        raise RuntimeError("VoiceStudio response exceeded 20 MiB")
    if not audio or "json" in content_type or len(audio) < 200:
        raise RuntimeError("VoiceStudio returned no usable audio")
    # Confirm that the MP3 response is not an HTML/JSON error body.
    if not (audio.startswith(b"ID3") or (len(audio) >= 2 and audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0)):
        raise RuntimeError("VoiceStudio response is not recognisable MP3 audio")

    OUTPUT.write_bytes(audio)
    return OUTPUT


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else ""
    rate = sys.argv[2] if len(sys.argv) > 2 else "-10"
    try:
        path = synthesize(text, rate)
    except Exception as exc:
        print(f"VoiceStudio TTS unavailable: {exc}", file=sys.stderr)
        return 1
    print(f"OK {path} ({path.stat().st_size}B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
