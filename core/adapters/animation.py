"""Animation stays out of Family Brain.

Brain may emit AnimationAction. AnimationController turns it into frames.
Existing clips: 站立 / 眨眼 / 走路 / 跑步.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.runtime.isolate import isolate

ANIMATION_NAMES = ("站立", "眨眼", "走路", "跑步")

FRAMES: dict[str, tuple[str, ...]] = {
    "站立": ("stand_0", "stand_1", "blink_soft"),
    "眨眼": ("blink_0", "blink_1", "stand_0"),
    "走路": ("walk_0", "walk_1", "walk_2", "walk_3"),
    "跑步": ("run_0", "run_1", "run_2", "run_3"),
}


@dataclass(frozen=True)
class AnimationAction:
    name: str
    loops: int = 1

    def __post_init__(self) -> None:
        label = self.name if self.name in ANIMATION_NAMES else "站立"
        object.__setattr__(self, "name", label)
        loops = self.loops if isinstance(self.loops, int) and self.loops > 0 else 1
        object.__setattr__(self, "loops", loops)


class AnimationController:
    """Deterministic frames. No LLM, no Brain dependency the other way."""

    core_api_version = "4.0.0"

    def play(self, action: AnimationAction | str | None) -> list[str]:
        if isinstance(action, str):
            action = AnimationAction(action)
        if action is None:
            action = AnimationAction("站立")
        frames = list(FRAMES.get(action.name, FRAMES["站立"]))
        return frames * action.loops

    def play_safe(self, action: AnimationAction | str | None) -> list[str]:
        result = isolate(lambda: self.play(action), fallback=list(FRAMES["站立"]))
        return list(result.value or FRAMES["站立"])
