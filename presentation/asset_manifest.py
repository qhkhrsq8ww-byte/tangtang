"""V10 AssetManifest. Presentation only — Brain never imports this."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
V10_ROOT = REPO_ROOT / "assets" / "character" / "tangtang" / "v10"
MANIFEST_NAME = "manifest.json"

DEFAULT_ANCHOR = {"x": 0.5, "y": 0.957}
DEFAULT_SIZE = 512


class AssetManifest:
    """frames / fps / loop / anchor / width / height per animation."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else V10_ROOT
        self.data: dict[str, Any] = {}
        path = self.root / MANIFEST_NAME
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data = loaded

    @property
    def animations(self) -> dict[str, dict[str, Any]]:
        raw = self.data.get("animations")
        return dict(raw) if isinstance(raw, dict) else {}

    @property
    def fallback(self) -> str:
        name = self.data.get("fallback") or "idle"
        return name if name in self.animations else "idle"

    def spec(self, name: str) -> dict[str, Any]:
        spec = self.animations.get(name)
        if not isinstance(spec, dict):
            spec = self.animations.get(self.fallback) or {}
        return dict(spec)

    def width(self, name: str) -> int:
        spec = self.spec(name)
        return int(spec.get("width") or self.data.get("width") or DEFAULT_SIZE)

    def height(self, name: str) -> int:
        spec = self.spec(name)
        return int(spec.get("height") or self.data.get("height") or DEFAULT_SIZE)

    def fps(self, name: str) -> int:
        value = int(self.spec(name).get("fps") or 12)
        return max(1, min(value, 30))

    def loop(self, name: str) -> bool:
        return bool(self.spec(name).get("loop", True))

    def anchor(self, name: str) -> dict[str, float]:
        raw = self.spec(name).get("anchor") or self.data.get("anchor") or DEFAULT_ANCHOR
        if not isinstance(raw, Mapping):
            return dict(DEFAULT_ANCHOR)
        return {"x": float(raw.get("x", 0.5)), "y": float(raw.get("y", 0.957))}

    def frame_count(self, name: str) -> int:
        spec = self.spec(name)
        files = spec.get("files")
        if isinstance(files, list) and files:
            return len(files)
        return int(spec.get("frames") or 0)

    def files(self, name: str) -> list[str]:
        spec = self.spec(name)
        files = spec.get("files")
        if isinstance(files, list) and files:
            return [str(item) for item in files]
        count = int(spec.get("frames") or 0)
        return [f"animations/{name}/{name}_{i:02d}.png" for i in range(1, count + 1)]
