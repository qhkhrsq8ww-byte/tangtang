"""Write PresentationAction for the desktop pet. cat-mood.txt is legacy only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.presentation.action import PresentationAction


def write_presentation_action(action: PresentationAction, directory: str | Path) -> Path:
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "cat-presentation-action.json"
    payload: dict[str, Any] = action.to_dict()
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # Legacy transport — desktop pet must not treat this as the source of truth.
    legacy = folder / "cat-mood.txt"
    line = f"[{action.state}] {action.text if action.speak else ''}".rstrip()
    legacy.write_text(line + "\n", encoding="utf-8")
    return target
