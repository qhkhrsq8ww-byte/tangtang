"""Load TangTang V10 animation metadata. Presentation only — Brain never imports this."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ASSET_ROOT = REPO_ROOT / "assets" / "character" / "tangtang"
METADATA_NAME = "metadata.json"

REQUIRED_FIELDS = (
    "animation_name",
    "frame_count",
    "fps",
    "loop",
    "anchor",
    "preferred_state",
    "fallback_state",
)


def asset_root(root: Path | str | None = None) -> Path:
    return Path(root) if root is not None else DEFAULT_ASSET_ROOT


def load_metadata(root: Path | str | None = None) -> dict[str, Any]:
    path = asset_root(root) / METADATA_NAME
    if not path.is_file():
        return {"animations": {}, "projection": {}, "states": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"animations": {}, "projection": {}, "states": []}
    return data


def animation_spec(meta: Mapping[str, Any], name: str) -> dict[str, Any]:
    anims = meta.get("animations") if isinstance(meta.get("animations"), dict) else {}
    spec = anims.get(name) if isinstance(anims, dict) else None
    if not isinstance(spec, dict):
        return {}
    return dict(spec)


def frame_path(root: Path, folder: str, index: int, size: int = 512) -> Path:
    name = f"{index:02d}.png"
    if size == 512:
        return root / folder / name
    return root / folder / str(size) / name
