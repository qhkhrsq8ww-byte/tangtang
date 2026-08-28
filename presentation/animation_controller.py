"""TangTang V10 AnimationController — presentation layer only.

Event -> Brain -> Response -> PresentationAction -> AnimationController -> PNG
Brain does not import this module and never receives image paths.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from core.runtime.isolate import isolate

from presentation.mapping import (
    AnimationAction,
    LOOPING,
    animation_from_response_action,
    is_night,
    plan_actions,
    soften_for_night,
)
from presentation.registry import (
    DEFAULT_ASSET_ROOT,
    animation_spec,
    frame_path,
    load_metadata,
)
from presentation.state_machine import ANIM_TO_STATE, MAX_FPS, SLEEP_MAX_FPS, AnimationStateMachine

DEFAULT_ANCHOR = {"x": 0.5, "y": 1.0}


@dataclass
class AnimationClip:
    name: str
    state: str
    frames: list[str]
    fps: int
    loop: bool
    anchor: dict[str, float]
    declared_frame_count: int
    resolved_frame_count: int
    fallback_used: bool = False
    scale: float = 1.0
    continuous: bool = False
    transition_from: str | None = None
    night_softened: bool = False
    interrupt_blocked: bool = False
    projection: dict[str, Any] = field(default_factory=dict)

    def timeline(self, ticks: int | None = None) -> list[str]:
        """Ordered frames. Index moves 0,1,2… never skips. Hold last if not looping."""
        if not self.frames:
            return []
        n = len(self.frames)
        count = ticks if ticks is not None else (n if not self.loop else n)
        out: list[str] = []
        for t in range(max(0, count)):
            if self.loop:
                out.append(self.frames[t % n])
            else:
                out.append(self.frames[min(t, n - 1)])
        return out


def _pngs_in_folder(root: Path, folder: str, size: int = 512) -> list[Path]:
    base = root / folder if size == 512 else root / folder / str(size)
    if not base.is_dir():
        return []
    files = sorted(
        p
        for p in base.iterdir()
        if p.is_file() and p.suffix.lower() == ".png" and p.stem.isdigit()
    )
    return files


def _cap_fps(name: str, fps: int) -> int:
    value = fps if isinstance(fps, int) and fps > 0 else 8
    value = min(value, MAX_FPS)
    if name == "sleep":
        value = min(value, SLEEP_MAX_FPS)
    return max(1, value)


class AnimationController:
    """Deterministic sprite sequencer. Missing frames fallback to idle. Never raises to Brain."""

    layer = "presentation"

    def __init__(
        self,
        root: Path | str | None = None,
        *,
        now: Callable[[], datetime] | None = None,
        size: int = 512,
    ) -> None:
        self.root = Path(root) if root is not None else DEFAULT_ASSET_ROOT
        self.size = 512 if size not in (512, 256, 128) else size
        self._now = now or datetime.now
        self.meta = load_metadata(self.root)
        self.machine = AnimationStateMachine("IDLE")
        self._last_clip: AnimationClip | None = None

    @property
    def projection(self) -> dict[str, Any]:
        proj = self.meta.get("projection") if isinstance(self.meta.get("projection"), dict) else {}
        return {
            "canvas": list(proj.get("canvas") or [1920, 1080]),
            "character": list(proj.get("character") or [512, 512]),
            "anchor": dict(proj.get("anchor") or DEFAULT_ANCHOR),
            "scale": 1.0,
        }

    def spec(self, name: str) -> dict[str, Any]:
        return animation_spec(self.meta, name)

    def resolve_frames(self, name: str) -> list[str]:
        spec = self.spec(name)
        folder = str(spec.get("folder") or name)
        declared = int(spec.get("frame_count") or 0)
        found = _pngs_in_folder(self.root, folder, self.size)
        if declared > 0:
            ordered: list[Path] = []
            for i in range(declared):
                path = frame_path(self.root, folder, i, self.size)
                if path.is_file():
                    ordered.append(path)
            if ordered:
                found = ordered
        return [str(p) for p in found]

    def _idle_clip(self, *, fallback_used: bool = True, transition_from: str | None = None) -> AnimationClip:
        spec = self.spec("idle")
        frames = self.resolve_frames("idle")
        if not frames:
            # Last-resort: any 512 still under base/, still no crash.
            base = self.root / "base" / "three_quarter_left.png"
            if not base.is_file():
                alt = sorted((self.root / "base").glob("*.png")) if (self.root / "base").is_dir() else []
                base = alt[0] if alt else self.root / "idle" / "00.png"
            frames = [str(base)] if base.is_file() else []
        fps = _cap_fps("idle", int(spec.get("fps") or 8))
        return AnimationClip(
            name="idle",
            state="IDLE",
            frames=frames,
            fps=fps,
            loop=True,
            anchor=dict(spec.get("anchor") or DEFAULT_ANCHOR),
            declared_frame_count=int(spec.get("frame_count") or 8),
            resolved_frame_count=len(frames),
            fallback_used=fallback_used,
            scale=1.0,
            continuous=False,
            transition_from=transition_from,
            projection=self.projection,
        )

    def play(self, action: AnimationAction | str | Any | None) -> AnimationClip:
        if action is not None and not isinstance(action, (AnimationAction, str)):
            action = AnimationAction(animation_from_response_action(action))
        if isinstance(action, str):
            action = AnimationAction(action)
        if action is None:
            action = AnimationAction("idle")

        night = is_night(self._now())
        wanted = soften_for_night(action.name, night)
        night_softened = wanted != action.name
        spec = self.spec(wanted) or self.spec("idle")
        priority = int(action.priority or spec.get("priority") or 0)
        interrupt = bool(action.interrupt)
        state = ANIM_TO_STATE.get(wanted, "IDLE")

        trans = self.machine.request(
            state,
            priority=priority,
            interrupt=interrupt,
            force=bool(action.force),
        )
        if not trans.accepted:
            # Sleep lock / ignored high-frequency request: keep current clip.
            current = self._last_clip or self._idle_clip(fallback_used=False)
            current.interrupt_blocked = True
            return current

        frames = self.resolve_frames(wanted)
        min_playable = int(spec.get("min_playable") or 1)
        continuous = bool(spec.get("continuous"))
        if continuous and len(frames) < min_playable:
            clip = self._idle_clip(fallback_used=True, transition_from=trans.from_state)
            clip.night_softened = night_softened
            self._last_clip = clip
            return clip
        if len(frames) < min_playable or not frames:
            clip = self._idle_clip(fallback_used=True, transition_from=trans.from_state)
            clip.night_softened = night_softened
            self._last_clip = clip
            return clip

        # Continuous clips must not be a 2-frame ping-pong fake.
        if continuous and _is_two_frame_pong(frames):
            clip = self._idle_clip(fallback_used=True, transition_from=trans.from_state)
            clip.night_softened = night_softened
            self._last_clip = clip
            return clip

        fps = _cap_fps(wanted, int(spec.get("fps") or 8))
        loop = bool(spec.get("loop")) if "loop" in spec else wanted in LOOPING
        clip = AnimationClip(
            name=wanted,
            state=state,
            frames=frames,
            fps=fps,
            loop=loop,
            anchor=dict(spec.get("anchor") or DEFAULT_ANCHOR),
            declared_frame_count=int(spec.get("frame_count") or len(frames)),
            resolved_frame_count=len(frames),
            fallback_used=False,
            scale=1.0,
            continuous=continuous,
            transition_from=trans.from_state if trans.hold_previous else None,
            night_softened=night_softened,
            projection=self.projection,
        )
        self._last_clip = clip
        return clip

    def play_safe(self, action: AnimationAction | str | Any | None) -> AnimationClip:
        result = isolate(lambda: self.play(action), fallback=None)
        if result.ok and isinstance(result.value, AnimationClip):
            return result.value
        return self._idle_clip(fallback_used=True)

    def apply(
        self,
        event: Any = None,
        response: Any = None,
        *,
        night: bool | None = None,
        now: datetime | None = None,
    ) -> list[AnimationClip]:
        """Presentation mapping: Event + Response → clips. Isolated from Brain."""

        def _run() -> list[AnimationClip]:
            specs = self.meta.get("animations") if isinstance(self.meta.get("animations"), dict) else {}
            planned = plan_actions(
                event,
                response,
                night=night,
                now=now or self._now(),
                specs=specs,  # type: ignore[arg-type]
            )
            clips: list[AnimationClip] = []
            for step in planned:
                clips.append(self.play(step))
            if not clips:
                clips.append(self.play(AnimationAction("idle")))
            return clips

        result = isolate(_run, fallback=None)
        if result.ok and isinstance(result.value, list) and result.value:
            return result.value
        return [self._idle_clip(fallback_used=True)]

    def project_safe(self, projector: Callable[[AnimationClip], Any], clip: AnimationClip) -> bool:
        """Projection failures never propagate."""
        result = isolate(lambda: projector(clip), fallback=None)
        return bool(result.ok)


def _is_two_frame_pong(frames: Iterable[str]) -> bool:
    seq = list(frames)
    if len(seq) < 4:
        return False
    uniq = []
    for item in seq:
        if item not in uniq:
            uniq.append(item)
        if len(uniq) > 2:
            return False
    if len(uniq) != 2:
        return False
    a, b = uniq
    expected = [a, b] * (len(seq) // 2)
    if len(seq) % 2:
        expected.append(a)
    return seq == expected[: len(seq)]
