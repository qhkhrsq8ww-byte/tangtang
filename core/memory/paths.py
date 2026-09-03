"""Keep MemoryStore / habit / private files under TANGTANG_HOME."""
from __future__ import annotations

import os
import re
from pathlib import Path

from core.errors import PathError

_MEMBER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_FORBIDDEN_PARTS = frozenset({".", ".."})


def tangtang_home(override: str | os.PathLike[str] | None = None) -> Path:
    raw = override if override is not None else (
        os.environ.get("TANGTANG_HOME") or os.environ.get("TANGTANG_DATA_DIR")
    )
    if raw is None or str(raw).strip() == "":
        raise PathError("TANGTANG_HOME is required")
    text = str(raw)
    if ".." in Path(text).parts:
        raise PathError("path traversal rejected")
    return Path(text).expanduser().resolve()


def sanitize_member_id(member_id: str | None) -> str:
    text = (member_id or "").strip()
    if not _MEMBER_ID_RE.fullmatch(text):
        raise PathError("illegal member_id for file path")
    return text


def resolve_under(root: str | os.PathLike[str], *parts: str) -> Path:
    """Join parts under root. Reject `../`, absolute, and NUL."""
    base = Path(root).resolve()
    if not parts:
        raise PathError("path is required")
    for part in parts:
        if part is None or str(part) == "":
            raise PathError("empty path part")
        text = str(part)
        if "\x00" in text:
            raise PathError("nul in path")
        if text.startswith("~"):
            raise PathError("absolute path rejected")
        # Windows drive / POSIX absolute
        if os.path.isabs(text) or (len(text) >= 2 and text[1] == ":"):
            raise PathError("absolute path rejected")
        if "\\" in text:
            raise PathError("path traversal rejected")
        candidate = Path(text)
        if candidate.is_absolute():
            raise PathError("absolute path rejected")
        for piece in candidate.parts:
            if piece in _FORBIDDEN_PARTS or piece == "..":
                raise PathError("path traversal rejected")
            if piece.startswith(".."):
                raise PathError("path traversal rejected")
    joined = base.joinpath(*parts)
    resolved = joined.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise PathError("path escapes TANGTANG_HOME") from exc
    return resolved


def private_file(home: str | os.PathLike[str], member_id: str, name: str = "memories.json") -> Path:
    mid = sanitize_member_id(member_id)
    return resolve_under(home, "private", mid, name)


def family_file(home: str | os.PathLike[str], name: str = "family-memory.json") -> Path:
    return resolve_under(home, "family", name)


def habit_file(home: str | os.PathLike[str], name: str = "cat-habits.json") -> Path:
    return resolve_under(home, "habits", name)


def living_room_file(home: str | os.PathLike[str], name: str = "cat-habits.json") -> Path:
    """V3 living-room JSON at the Application Support root (same TANGTANG_HOME)."""
    return resolve_under(home, name)


def family_state_file(home: str | os.PathLike[str], name: str = "family-state.json") -> Path:
    """Derived Family Memory 2.0 snapshot. Tags only; not a third event store."""
    return resolve_under(home, name)


def emotion_state_file(home: str | os.PathLike[str], name: str = "emotion-state.json") -> Path:
    """Live emotion vector for 糖糖 (no utterances)."""
    return resolve_under(home, "memory", name)


def emotion_snapshot_file(home: str | os.PathLike[str], name: str = "emotion-snapshots.jsonl") -> Path:
    """Daily emotion snapshots (one line per day)."""
    return resolve_under(home, "memory", name)


def habit_trends_file(home: str | os.PathLike[str], name: str = "habit-trends.json") -> Path:
    """Day ledger + 7d rollup + 14d stable habit tags (no child raw speech)."""
    return resolve_under(home, "habits", name)
