"""FrameRenderer: resolve PNG paths. Missing frames never throw."""
from __future__ import annotations

from pathlib import Path

from presentation.asset_manifest import AssetManifest


class FrameRenderer:
    """AssetManifest → on-disk PNG. No TTS, no Brain, no projection."""

    def __init__(self, manifest: AssetManifest | None = None, root: Path | str | None = None) -> None:
        self.manifest = manifest or AssetManifest(root)
        self.root = Path(root) if root is not None else self.manifest.root

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
