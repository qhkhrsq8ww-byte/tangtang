#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate randomized, blind-labeled Mandarin voice samples for TangTang.

Run with the same Python interpreter that production uses for Edge TTS:
  /usr/bin/python3 code/cat/cat-voice-lab.py
Add --play on macOS to play each sample in sequence after generating it.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_TEXT = "你回来啦！糖糖在呢。看了好久啦，要不要陪我起来走两步？"
RATE = "-5%"
PITCH = "+0Hz"
PREFERRED_VOICES = (
    "zh-CN-XiaoxiaoNeural",  # production default
    "zh-CN-XiaoyiNeural",
    "zh-CN-XiaohanNeural",
    "zh-CN-XiaomengNeural",
    "zh-CN-XiaomoNeural",
    "zh-CN-XiaorouNeural",
    "zh-CN-XiaoxuanNeural",
    "zh-CN-XiaoyanNeural",
)


def choose_voices(voices: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    """Pick currently available zh-CN female neural voices, preserving a shortlist order."""
    if limit < 2:
        raise ValueError("至少需要 2 个音色才能做对比")
    available: dict[str, dict[str, Any]] = {}
    for voice in voices:
        if not isinstance(voice, dict):
            continue
        name = str(voice.get("ShortName") or "").strip()
        locale = str(voice.get("Locale") or "").strip().lower()
        gender = str(voice.get("Gender") or "").strip().lower()
        if (
            name
            and locale == "zh-cn"
            and gender == "female"
            and "Neural" in name
            and "Multilingual" not in name
            and "Dragon" not in name
        ):
            available[name] = voice

    ordered_names = [name for name in PREFERRED_VOICES if name in available]
    ordered_names.extend(sorted(name for name in available if name not in ordered_names))
    chosen = [available[name] for name in ordered_names[:limit]]
    if len(chosen) < 2:
        raise RuntimeError(
            "Edge TTS 当前返回的可用普通话女声音色少于 2 个；请更新 edge-tts 后重试。"
        )
    return chosen


def make_output_dir(requested: str | None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if requested:
        root = Path(requested).expanduser()
    else:
        desktop = Path.home() / "Desktop"
        root = desktop if desktop.is_dir() else Path.home()
        root = root / f"TangTangVoiceLab-{stamp}"
    samples = root / "盲听样本"
    if samples.exists() and any(samples.iterdir()):
        raise FileExistsError(f"样本目录非空，为避免覆盖文件已停止：{samples}")
    samples.mkdir(parents=True, exist_ok=True)
    return root


async def generate(text: str, output_root: Path, limit: int) -> list[tuple[str, str, Path]]:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError(
            f"当前 Python ({sys.executable}) 没装 edge-tts。请用生产环境正在使用的 Python 安装后重试。"
        ) from exc

    voices = choose_voices(await edge_tts.list_voices(), limit=limit)
    # Random order prevents the first label from always revealing the production voice.
    random.SystemRandom().shuffle(voices)
    samples = output_root / "盲听样本"
    result: list[tuple[str, str, Path]] = []
    for index, voice in enumerate(voices):
        label = chr(ord("A") + index)
        name = str(voice["ShortName"])
        path = samples / f"{label}.mp3"
        try:
            speaker = edge_tts.Communicate(text, name, rate=RATE, pitch=PITCH)
            await speaker.save(str(path))
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError("生成文件为空")
        except Exception as exc:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            print(f"[跳过] {label} 音色生成失败：{name} ({type(exc).__name__})", file=sys.stderr)
            continue
        result.append((label, name, path))

    if len(result) < 2:
        raise RuntimeError("成功生成的样本少于 2 个，请检查网络和 Edge TTS 服务。")

    key_file = output_root / "答案-听完后再看.txt"
    lines = [
        "糖糖声音盲听答案（建议先听 A/B/C，再打开本文件）",
        f"统一测试文本：{text}",
        f"统一参数：rate={RATE}, pitch={PITCH}",
        "",
    ]
    lines.extend(f"{label} = {name}" for label, name, _ in result)
    key_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    score_file = output_root / "盲听评分.txt"
    score_file.write_text(
        "听完样本再填，先不要看答案文件。每项 1–5 分，5 分最好。\n"
        "样本 | 自然程度 | 温柔亲切 | 像糖糖 | 听久不累 | 备注\n"
        + "".join(f"{label} |  |  |  |  | \n" for label, _, _ in result)
        + "\n选音色时优先考虑自然、耐听、像家庭伙伴，不要只按可爱程度选。\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="为糖糖生成中文女声音色盲听样本")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="统一试听句；所有候选使用同一句")
    parser.add_argument("--output-dir", default=None, help="输出目录；默认放桌面并使用新目录")
    parser.add_argument("--limit", type=int, default=6, help="候选数，2–8，默认 6")
    parser.add_argument("--play", action="store_true", help="生成后在 macOS 逐个播放样本")
    args = parser.parse_args()
    if args.limit < 2 or args.limit > 8:
        parser.error("--limit 必须在 2 到 8 之间")

    try:
        output_root = make_output_dir(args.output_dir)
        result = asyncio.run(generate(args.text, output_root, args.limit))
    except Exception as exc:
        print(f"声音盲听准备失败：{exc}", file=sys.stderr)
        return 1

    print(f"已生成 {len(result)} 个样本：{output_root / '盲听样本'}")
    print(f"评分表：{output_root / '盲听评分.txt'}")
    print("请先按 A、B、C……试听并评分，最后再打开“答案-听完后再看.txt”。")
    if args.play:
        player = shutil.which("afplay") if sys.platform == "darwin" else None
        if not player:
            print("--play 仅在装有 afplay 的 macOS 上可用；样本已生成。", file=sys.stderr)
        else:
            for label, _name, path in result:
                print(f"正在播放样本 {label}……")
                completed = subprocess.run([player, str(path)], check=False)
                if completed.returncode != 0:
                    print(f"样本 {label} 播放失败；文件仍保留：{path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
