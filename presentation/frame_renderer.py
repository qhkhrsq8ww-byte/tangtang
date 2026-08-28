"""FrameRenderer: resolve PNG paths and blit onto a cleared buffer.

Missing frames never throw. Visible pixels are never destination-over'd
onto leftover RGBA — every paint starts from a transparent clear.
"""
from __future__ import annotations

from pathlib import Path

from presentation.asset_manifest import AssetManifest

# Cross-fade previous clip at most this opacity so it cannot read as a second dog.
FADE_OPACITY_CAP = 0.4
DEFAULT_SIZE = 512


class PixelBuffer:
    """Minimal RGBA canvas used by tests and Python compositing."""

    def __init__(self, width: int = DEFAULT_SIZE, height: int = DEFAULT_SIZE) -> None:
        self.width = int(width)
        self.height = int(height)
        self.pixels = bytearray(self.width * self.height * 4)

    def clear(self) -> None:
        """Wipe every pixel to transparent. Call before every draw."""
        self.pixels[:] = b"\x00" * len(self.pixels)

    def clearRect(self, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None) -> None:
        width = self.width if w is None else int(w)
        height = self.height if h is None else int(h)
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(self.width, x0 + width)
        y1 = min(self.height, y0 + height)
        for row in range(y0, y1):
            start = (row * self.width + x0) * 4
            stop = (row * self.width + x1) * 4
            self.pixels[start:stop] = b"\x00" * (stop - start)

    def _src_over_pixel(self, di: int, sr: int, sg: int, sb: int, sa: int) -> None:
        if sa <= 0:
            return
        dr = self.pixels[di]
        dg = self.pixels[di + 1]
        db = self.pixels[di + 2]
        da = self.pixels[di + 3]
        inv = 255 - sa
        self.pixels[di] = (sr * sa + dr * da * inv // 255) // 255
        self.pixels[di + 1] = (sg * sa + dg * da * inv // 255) // 255
        self.pixels[di + 2] = (sb * sa + db * da * inv // 255) // 255
        self.pixels[di + 3] = sa + da * inv // 255

    def blit(self, src: bytes | bytearray, *, alpha: float = 1.0) -> None:
        """Source-over `src` (RGBA bytes, same size). Does not clear."""
        if alpha <= 0:
            return
        cap = 1.0 if alpha >= 1.0 else max(0.0, min(1.0, float(alpha)))
        n = self.width * self.height
        mv = memoryview(src)
        for i in range(n):
            o = i * 4
            sa = int(mv[o + 3] * cap)
            if sa <= 0:
                continue
            self._src_over_pixel(o, mv[o], mv[o + 1], mv[o + 2], sa)

    def pixel(self, x: int, y: int) -> tuple[int, int, int, int]:
        i = (int(y) * self.width + int(x)) * 4
        p = self.pixels
        return (p[i], p[i + 1], p[i + 2], p[i + 3])


def composite_frame(
    current: bytes | bytearray,
    previous: bytes | bytearray | None = None,
    fade_t: float = 1.0,
    *,
    width: int = DEFAULT_SIZE,
    height: int = DEFAULT_SIZE,
    fade_cap: float = FADE_OPACITY_CAP,
) -> PixelBuffer:
    """Draw `current` onto a freshly cleared buffer.

    Cross-fade (0 < fade_t < 1) still clears first, then draws previous at
    min(fade_cap, 1 - fade_t) and current at fade_t. Never leaves the old
    frame on the visible buffer.
    """
    buf = PixelBuffer(width, height)
    buf.clear()
    fading = previous is not None and 0.0 < float(fade_t) < 1.0
    if fading:
        prev_a = min(float(fade_cap), max(0.0, 1.0 - float(fade_t)))
        buf.blit(previous, alpha=prev_a)
        buf.blit(current, alpha=max(float(fade_t), 1.0 - prev_a))
    else:
        buf.blit(current, alpha=1.0)
    return buf


class FrameRenderer:
    """AssetManifest → on-disk PNG, then blit onto a cleared PixelBuffer."""

    def __init__(self, manifest: AssetManifest | None = None, root: Path | str | None = None) -> None:
        self.manifest = manifest or AssetManifest(root)
        self.root = Path(root) if root is not None else self.manifest.root
        self.buffer = PixelBuffer(DEFAULT_SIZE, DEFAULT_SIZE)
        self._last_rgba: bytes | None = None

    def path(self, animation: str, index: int) -> Path:
        files = self.manifest.files(animation)
        if not files:
            return self._idle_or_empty()
        n = len(files)
        if n <= 0:
            return self._idle_or_empty()
        if self.manifest.loop(animation):
            idx = index % n
        else:
            idx = min(max(0, index), n - 1)
        candidate = self.root / files[idx]
        if candidate.is_file():
            return candidate
        return self._idle_or_empty()

    def paths(self, animation: str) -> list[Path]:
        out: list[Path] = []
        for rel in self.manifest.files(animation):
            p = self.root / rel
            if p.is_file():
                out.append(p)
        if out:
            return out
        idle = self._idle_or_empty()
        return [idle] if idle.is_file() else []

    def paint(
        self,
        rgba: bytes | bytearray,
        *,
        fade_t: float = 1.0,
        previous: bytes | bytearray | None = None,
        fade_cap: float = FADE_OPACITY_CAP,
    ) -> PixelBuffer:
        """Clear the visible buffer, then draw. Consecutive paints do not keep old RGBA."""
        prev = previous if previous is not None else None
        painted = composite_frame(
            rgba,
            prev,
            fade_t,
            width=self.buffer.width,
            height=self.buffer.height,
            fade_cap=fade_cap,
        )
        self.buffer = painted
        self._last_rgba = bytes(rgba)
        return self.buffer

    def paint_png(self, path: Path | str, *, fade_t: float = 1.0) -> PixelBuffer:
        rgba = _png_rgba_bytes(Path(path), self.buffer.width, self.buffer.height)
        painted = self.paint(rgba, fade_t=fade_t, previous=None)
        return painted

    def _idle_or_empty(self) -> Path:
        idle_files = self.manifest.files(self.manifest.fallback)
        if idle_files:
            p = self.root / idle_files[0]
            if p.is_file():
                return p
        fallback = self.root / "animations" / "idle" / "idle_01.png"
        if fallback.is_file():
            return fallback
        return self.root / "missing.png"


def _png_rgba_bytes(path: Path, width: int, height: int) -> bytes:
    try:
        from PIL import Image
    except ImportError:
        return bytes(width * height * 4)
    if not path.is_file():
        return bytes(width * height * 4)
    im = Image.open(path).convert("RGBA")
    if im.size != (width, height):
        im = im.resize((width, height), Image.Resampling.NEAREST)
    return im.tobytes()
