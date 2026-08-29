"""Map presentation state → video file. Presentation layer only."""
from __future__ import annotations

from pathlib import Path

from core.presentation.action import PRESENTATION_STATES

REPO_ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = REPO_ROOT / "code" / "cat" / "assets" / "video"

STATE_FILES = {
    "idle": ("v2/tangtang-idle.mp4", "tangtang-idle.mp4"),
    "talk": ("v2/tangtang-talk.mp4", "tangtang-talk.mp4"),
    "happy": ("v2/tangtang-happy.mp4", "tangtang-happy.mp4"),
    "curious": ("v2/tangtang-curious.mp4", "tangtang-curious.mp4"),
    "thinking": ("v2/tangtang-thinking.mp4", "tangtang-thinking.mp4"),
    "caring": ("tangtang-caring.mp4",),
    "encouraging": ("tangtang-encouraging.mp4",),
    "walking": ("tangtang-walking.mp4",),
    "running": ("tangtang-running.mp4",),
    "sitting": ("tangtang-sitting.mp4",),
    "lying": ("tangtang-lying.mp4",),
    "sleepy": ("tangtang-sleepy.mp4",),
    "sleeping": ("v2/tangtang-sleeping.mp4", "tangtang-sleeping.mp4"),
    "welcome": ("tangtang-welcome.mp4",),
    "accompany": ("tangtang-accompany.mp4",),
    "wakeup": ("tangtang-wakeup.mp4",),
    "night": ("tangtang-night.mp4",),
}


class AssetRegistry:
    """CharacterStateEngine must not import this."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else VIDEO_DIR

    def filename(self, state: str) -> str:
        key = state if state in PRESENTATION_STATES else "idle"
        candidates = STATE_FILES.get(key) or STATE_FILES["idle"]
        for rel in candidates:
            if (self.root / rel).is_file():
                return rel
        return candidates[0]

    def path(self, state: str) -> Path:
        return self.root / self.filename(state)

    def exists(self, state: str) -> bool:
        return self.path(state).is_file()

    def missing(self) -> list[str]:
        return [name for name in sorted(PRESENTATION_STATES) if not self.exists(name)]
