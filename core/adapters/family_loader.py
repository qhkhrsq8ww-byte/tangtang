"""Load family.json. Core must not hardcode members or overwrite names."""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.errors import PathError
from core.memory.paths import tangtang_home
from core.runtime.isolate import isolate

_REPO_FAMILY = Path(__file__).resolve().parents[2] / "data" / "family.json"


def _read_json(path: Path) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    loaded = isolate(lambda: json.loads(path.read_text(encoding="utf-8")))
    if loaded.ok and isinstance(loaded.value, Mapping):
        return loaded.value
    return None


def family_json_path(override: str | os.PathLike[str] | None = None) -> Path | None:
    """Resolve family.json. Never the hardcoded Mac cat home."""
    if override is not None:
        return Path(override).expanduser()
    env = (os.environ.get("TANGTANG_FAMILY_FILE") or "").strip()
    if env:
        return Path(env).expanduser()
    home_try = isolate(lambda: tangtang_home() / "family.json")
    if home_try.ok and isinstance(home_try.value, Path) and home_try.value.is_file():
        return home_try.value
    if _REPO_FAMILY.is_file():
        return _REPO_FAMILY
    return None


def load_family_document(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Return the family.json document. Empty members if missing — never invent people."""
    resolved = family_json_path(path)
    if resolved is None:
        return {"version": "2.0", "members": []}
    doc = _read_json(Path(resolved))
    if not isinstance(doc, Mapping):
        return {"version": "2.0", "members": []}
    members = doc.get("members")
    if not isinstance(members, list):
        members = []
    return {
        "version": str(doc.get("version") or "2.0"),
        "family_id": doc.get("family_id"),
        "members": members,
    }


def load_members(path: str | os.PathLike[str] | None = None) -> dict[str, dict[str, Any]]:
    """member_id → record. Keys come from the file, not a hardcoded roster."""
    out: dict[str, dict[str, Any]] = {}
    for row in load_family_document(path).get("members") or []:
        if not isinstance(row, Mapping):
            continue
        mid = str(row.get("member_id") or "").strip()
        if not mid:
            continue
        out[mid] = dict(row)
    return out


def require_members(path: str | os.PathLike[str] | None = None) -> dict[str, dict[str, Any]]:
    members = load_members(path)
    if not members:
        raise PathError("family.json has no members")
    return members
