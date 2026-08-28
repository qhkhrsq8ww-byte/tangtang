#!/usr/bin/env python3
"""One-shot packer: chroma-key V10 stills/strips into assets/character/tangtang.

Does not invent new dogs. Only keys, crops, resizes, and slices existing renders.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "assets" / "character" / "tangtang"
SRC = Path("/opt/cursor/artifacts/assets")
SHEET = DEST / "TangTang-V10-character-design-sheet.png"

SIZES = (512, 256, 128)
MAGENTA = (255, 0, 255)
ANCHOR = {"x": 0.5, "y": 1.0}


def is_screen(r: int, g: int, b: int) -> bool:
    # Magenta screen: high R+B, low G. Protect blue bandana (G is high) and gold.
    mag = (r + b) / 2 - g
    return mag > 48 and g < 170 and r > 90 and b > 90


def key_and_despill(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    pix = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pix[x, y]
            if is_screen(r, g, b):
                pix[x, y] = (0, 0, 0, 0)
                continue
            # Magenta fringe on white fur: pull green up, kill leftover magenta.
            mag = (r + b) / 2 - g
            if mag > 18 and g < 220:
                t = min(1.0, (mag - 18) / 80.0)
                g2 = min(255, int(g + (mag * 0.55 * t)))
                r2 = max(0, int(r - 40 * t))
                b2 = max(0, int(b - 40 * t))
                alpha = max(0, min(255, int(255 * (1.0 - t * 0.85))))
                pix[x, y] = (r2, g2, b2, alpha)
    return im


def bbox_opaque(im: Image.Image, alpha_min: int = 24) -> tuple[int, int, int, int] | None:
    a = im.split()[-1]
    box = a.point(lambda p: 255 if p >= alpha_min else 0).getbbox()
    return box


def fit_square(im: Image.Image, size: int = 512, margin: float = 0.06) -> Image.Image:
    """Pad to square with feet on the bottom (anchor y=1, x=0.5)."""
    im = im.convert("RGBA")
    box = bbox_opaque(im)
    if box is None:
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        return canvas
    cropped = im.crop(box)
    cw, ch = cropped.size
    inner = int(size * (1.0 - 2 * margin))
    scale = min(inner / max(cw, 1), inner / max(ch, 1))
    nw = max(1, int(cw * scale))
    nh = max(1, int(ch * scale))
    fitted = cropped.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - nw) // 2
    y = size - nh - int(size * margin * 0.35)
    canvas.paste(fitted, (x, y), fitted)
    return canvas


def save_sizes(im512: Image.Image, dest_512: Path) -> None:
    dest_512.parent.mkdir(parents=True, exist_ok=True)
    im512.save(dest_512, "PNG", optimize=True)
    for side in (256, 128):
        out = dest_512.parent / str(side) / dest_512.name
        out.parent.mkdir(parents=True, exist_ok=True)
        im512.resize((side, side), Image.Resampling.LANCZOS).save(out, "PNG", optimize=True)


def process_still(src: Path) -> Image.Image:
    keyed = key_and_despill(Image.open(src))
    return fit_square(keyed, 512)


def slice_strip(src: Path, count: int) -> list[Image.Image]:
    raw = Image.open(src).convert("RGBA")
    keyed = key_and_despill(raw)
    w, h = keyed.size
    cell = w / count
    frames: list[Image.Image] = []
    for i in range(count):
        x0 = int(round(i * cell))
        x1 = int(round((i + 1) * cell))
        cell_im = keyed.crop((x0, 0, x1, h))
        frames.append(fit_square(cell_im, 512))
    return frames


def slice_effects(src: Path) -> dict[str, Image.Image]:
    keyed = key_and_despill(Image.open(src))
    w, h = keyed.size
    quads = {
        "paw": (0, 0, w // 2, h // 2),
        "heart": (w // 2, 0, w, h // 2),
        "star": (0, h // 2, w // 2, h),
        "bone": (w // 2, h // 2, w, h),
    }
    out = {}
    for name, box in quads.items():
        out[name] = fit_square(keyed.crop(box), 512, margin=0.18)
    return out


def living_room_bg() -> Image.Image:
    im = Image.new("RGB", (1920, 1080), (255, 248, 240))
    draw = ImageDraw.Draw(im)
    for y in range(1080):
        t = y / 1079
        # cream wall into warmer floor
        r = int(255 - 12 * t)
        g = int(246 - 28 * t)
        b = int(236 - 40 * t)
        draw.line([(0, y), (1919, y)], fill=(r, g, b))
    # soft floor band
    for y in range(780, 1080):
        t = (y - 780) / 300
        r = int(232 - 18 * t)
        g = int(210 - 16 * t)
        b = int(188 - 14 * t)
        draw.line([(0, y), (1919, y)], fill=(r, g, b))
    im = ImageEnhance.Color(im).enhance(1.02)
    return im.filter(ImageFilter.GaussianBlur(0.4))


def copy_named(im: Image.Image, rel: str) -> None:
    save_sizes(im, DEST / rel)


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    stills = {
        "front": SRC / "tangtang-v10-front.png",
        "qleft": SRC / "tangtang-v10-qleft.png",
        "side": SRC / "tangtang-v10-side-left.png",
        "back": SRC / "tangtang-v10-back.png",
        "qright": SRC / "tangtang-v10-qright.png",
        "happy": SRC / "tangtang-v10-happy.png",
        "blink": SRC / "tangtang-v10-blink.png",
        "listen": SRC / "tangtang-v10-listen.png",
        "encourage": SRC / "tangtang-v10-encourage.png",
        "sad": SRC / "tangtang-v10-sad.png",
        "sit": SRC / "tangtang-v10-sit.png",
        "lie": SRC / "tangtang-v10-lie.png",
        "sleep": SRC / "tangtang-v10-sleep.png",
        "expectant": SRC / "tangtang-v10-expectant.png",
        "walk_pose": SRC / "tangtang-v10-walk-pose.png",
        "run_pose": SRC / "tangtang-v10-run-pose.png",
    }
    packed = {k: process_still(p) for k, p in stills.items() if p.exists()}

    # Base + angles (same five camera views)
    copy_named(packed["front"], "base/front.png")
    copy_named(packed["qleft"], "base/three_quarter_left.png")
    copy_named(packed["side"], "base/side_left.png")
    copy_named(packed["back"], "base/back.png")
    copy_named(packed["qright"], "base/three_quarter_right.png")
    for name in ("front", "three_quarter_left", "side_left", "back", "three_quarter_right"):
        src = DEST / "base" / f"{name}.png"
        dst = DEST / "angles" / f"{name}.png"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        for side in (256, 128):
            sdir = DEST / "angles" / str(side)
            sdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DEST / "base" / str(side) / f"{name}.png", sdir / f"{name}.png")

    # Expressions
    expr = {
        "default": packed["front"],
        "happy": packed["happy"],
        "blink": packed["blink"],
        "tilt": packed["listen"],
        "encourage": packed["encourage"],
        "expectant": packed["expectant"],
        "sad": packed["sad"],
        "sleepy": packed["sleep"],
    }
    for name, im in expr.items():
        copy_named(im, f"expressions/{name}.png")

    # Preferred idle uses 3/4 left so she is not always staring.
    copy_named(packed["qleft"], "idle/00.png")
    copy_named(packed["blink"], "blink/00.png")
    copy_named(packed["listen"], "listen/00.png")
    copy_named(packed["happy"], "happy/00.png")
    copy_named(packed["encourage"], "encourage/00.png")
    copy_named(packed["sad"], "sad/00.png")
    copy_named(packed["sit"], "sit/00.png")
    copy_named(packed["lie"], "lie/00.png")
    copy_named(packed["sleep"], "sleep/00.png")

    walk_frames = slice_strip(SRC / "tangtang-v10-walk-strip.png", 12)
    for i, im in enumerate(walk_frames):
        copy_named(im, f"walk/{i:02d}.png")

    run_frames = slice_strip(SRC / "tangtang-v10-run-strip.png", 8)
    for i, im in enumerate(run_frames):
        copy_named(im, f"run/{i:02d}.png")

    copy_named(packed["listen"], "interactive/turn_to_voice.png")
    copy_named(packed["expectant"], "interactive/wait.png")
    copy_named(packed["happy"], "interactive/tail_wag.png")
    copy_named(packed["qright"], "interactive/look_around.png")

    for name, im in slice_effects(SRC / "tangtang-v10-effects.png").items():
        copy_named(im, f"effects/{name}.png")

    bg = living_room_bg()
    bg_dir = DEST / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)
    bg.save(bg_dir / "living_room_cream.png", "PNG", optimize=True)

    pngs = list(DEST.rglob("*.png"))
    print("packed pngs", len(pngs))
    print("walk", len(walk_frames), "run", len(run_frames))


if __name__ == "__main__":
    main()
