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


def _column_runs(mask: Image.Image, min_mass: int = 8) -> list[tuple[int, int]]:
    """Occupied x-ranges of a binary mask (0 / 255)."""
    pix = mask.load()
    w, h = mask.size
    occupied: list[bool] = []
    for x in range(w):
        mass = 0
        for y in range(h):
            if pix[x, y]:
                mass += 1
                if mass >= min_mass:
                    break
        occupied.append(mass >= min_mass)
    runs: list[tuple[int, int]] = []
    x = 0
    while x < w:
        if occupied[x]:
            x1 = x
            while x1 < w and occupied[x1]:
                x1 += 1
            runs.append((x, x1 - 1))
            x = x1
        else:
            x += 1
    return runs


def _mask_blobs(mask: Image.Image, min_pixels: int = 800) -> list[tuple[int, int, int, int, int]]:
    """Bounding boxes of connected opaque islands on a binary mask."""
    pix = mask.load()
    w, h = mask.size
    seen = bytearray(w * h)
    blobs: list[tuple[int, int, int, int, int]] = []

    def at(x: int, y: int) -> int:
        return y * w + x

    for y in range(h):
        for x in range(w):
            if seen[at(x, y)] or not pix[x, y]:
                continue
            stack = [x, y]
            seen[at(x, y)] = 1
            pixels = 0
            minx, miny, maxx, maxy = x, y, x, y
            while stack:
                cy = stack.pop()
                cx = stack.pop()
                pixels += 1
                if cx < minx:
                    minx = cx
                if cy < miny:
                    miny = cy
                if cx > maxx:
                    maxx = cx
                if cy > maxy:
                    maxy = cy
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[at(nx, ny)] and pix[nx, ny]:
                        seen[at(nx, ny)] = 1
                        stack.append(nx)
                        stack.append(ny)
            if pixels >= min_pixels:
                blobs.append((minx, miny, maxx, maxy, pixels))
    blobs.sort(key=lambda b: b[0])
    return blobs


def crop_subjects(keyed: Image.Image, expand: int = 8) -> list[Image.Image]:
    """Split a keyed strip into one crop per dog.

    Equal-width cells wrap when dogs sit closer than cell width (walk strip:
    11 touching poses sliced as 12 cells → two dogs / cut-off tails).
    Erode until 2D blobs separate, then crop the uneroded keyed pixels using
    neighbor midpoints as hard x bounds so fur never includes the next dog.
    """
    keyed = keyed.convert("RGBA")
    mask = keyed.split()[-1].point(lambda p: 255 if p >= 24 else 0)
    eroded = mask
    best: list[tuple[int, int, int, int, int]] = []
    for _ in range(14):
        eroded = eroded.filter(ImageFilter.MinFilter(3))
        blobs = _mask_blobs(eroded, min_pixels=800)
        if not blobs:
            continue
        widths = [b[2] - b[0] + 1 for b in blobs]
        med = sorted(widths)[len(widths) // 2]
        compact = all(w <= med * 1.55 for w in widths)
        if 8 <= len(blobs) <= 12 and compact:
            best = blobs
            break
        if compact and len(blobs) > len(best) and len(blobs) <= 16:
            best = blobs
        elif not best and len(blobs) > 1:
            best = blobs
    if len(best) < 2:
        return [keyed]
    w, h = keyed.size
    crops: list[Image.Image] = []
    for i, (x0, y0, x1, y1, _n) in enumerate(best):
        if i == 0:
            gx0 = max(0, x0 - expand)
        else:
            prev_x1 = best[i - 1][2]
            gx0 = max(0, (prev_x1 + x0) // 2 + 2)
        if i == len(best) - 1:
            gx1 = min(w, x1 + 1 + expand)
        else:
            next_x0 = best[i + 1][0]
            gx1 = min(w, (x1 + next_x0) // 2 - 1)
        gy0 = max(0, y0 - expand)
        gy1 = min(h, y1 + 1 + expand)
        if gx1 - gx0 < 8 or gy1 - gy0 < 8:
            continue
        crop = keyed.crop((gx0, gy0, gx1, gy1))
        crops.append(keep_largest_blob(crop, min_pixels=200))
    return crops or [keyed]


def keep_largest_blob(im: Image.Image, alpha_min: int = 24, min_pixels: int = 400) -> Image.Image:
    """Zero every opaque island except the largest (drops sheet-wrap slivers)."""
    im = im.convert("RGBA")
    pix = im.load()
    w, h = im.size
    seen = bytearray(w * h)
    blobs: list[list[int]] = []  # flattened (x,y) pairs per blob

    def idx(x: int, y: int) -> int:
        return y * w + x

    for y in range(h):
        for x in range(w):
            if seen[idx(x, y)] or pix[x, y][3] < alpha_min:
                continue
            stack = [x, y]
            seen[idx(x, y)] = 1
            coords: list[int] = []
            while stack:
                cy = stack.pop()
                cx = stack.pop()
                coords.append(cx)
                coords.append(cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[idx(nx, ny)]:
                        if pix[nx, ny][3] >= alpha_min:
                            seen[idx(nx, ny)] = 1
                            stack.append(nx)
                            stack.append(ny)
            if len(coords) >= min_pixels * 2:
                blobs.append(coords)
    if len(blobs) <= 1:
        return im
    blobs.sort(key=len, reverse=True)
    keep = set(zip(blobs[0][0::2], blobs[0][1::2]))
    out = im.copy()
    opix = out.load()
    for blob in blobs[1:]:
        for i in range(0, len(blob), 2):
            x, y = blob[i], blob[i + 1]
            if (x, y) not in keep:
                opix[x, y] = (0, 0, 0, 0)
    return out


def slice_strip(src: Path, count: int, extra: Path | None = None) -> list[Image.Image]:
    raw = Image.open(src).convert("RGBA")
    keyed = key_and_despill(raw)
    crops = crop_subjects(keyed)
    frames = [fit_square(c, 512, margin=0.12) for c in crops]
    if extra is not None and extra.is_file() and len(frames) < count:
        extra_im = key_and_despill(Image.open(extra))
        frames.append(fit_square(extra_im, 512, margin=0.12))
    if len(frames) > count:
        frames = frames[:count]
    # Equal-width cells wrap on touching strips. Only use them if blob
    # detection failed almost completely.
    if len(frames) < max(3, min(count, 8)):
        w, h = keyed.size
        cell = w / count
        frames = []
        for i in range(count):
            x0 = int(round(i * cell))
            x1 = int(round((i + 1) * cell))
            cell_im = keep_largest_blob(keyed.crop((x0, 0, x1, h)))
            frames.append(fit_square(cell_im, 512))
    return [keep_largest_blob(frame) for frame in frames]


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


def recrop_gait_from_strip(src: Path, count: int, extra: Path | None = None) -> list[Image.Image]:
    return slice_strip(src, count, extra=extra)


def recrop_packed_gait() -> None:
    """Re-slice walk/run only. Does not touch idle/expressions/Brain."""
    walk_src = SRC / "tangtang-v10-walk-strip.png"
    run_src = SRC / "tangtang-v10-run-strip.png"
    if not walk_src.is_file() or not run_src.is_file():
        raise SystemExit(f"missing source strips under {SRC}")
    walk_frames = recrop_gait_from_strip(
        walk_src, 12, extra=SRC / "tangtang-v10-walk-pose.png"
    )
    for i, im in enumerate(walk_frames):
        copy_named(im, f"walk/{i:02d}.png")
    run_frames = recrop_gait_from_strip(run_src, 8)
    for i, im in enumerate(run_frames):
        copy_named(im, f"run/{i:02d}.png")
    print("recropped walk", len(walk_frames), "run", len(run_frames))


def wipe_secondary_blobs(folder: Path) -> int:
    """Keep the largest opaque island on already-packed 512 frames."""
    changed = 0
    for path in sorted(folder.glob("*.png")):
        im = Image.open(path).convert("RGBA")
        cleaned = keep_largest_blob(im)
        if cleaned is not im:
            save_sizes(cleaned, path)
            changed += 1
    return changed


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

    walk_frames = recrop_gait_from_strip(
        SRC / "tangtang-v10-walk-strip.png",
        12,
        extra=SRC / "tangtang-v10-walk-pose.png",
    )
    for i, im in enumerate(walk_frames):
        copy_named(im, f"walk/{i:02d}.png")

    run_frames = recrop_gait_from_strip(SRC / "tangtang-v10-run-strip.png", 8)
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
    import sys

    if "--gait-only" in sys.argv:
        recrop_packed_gait()
    else:
        main()
