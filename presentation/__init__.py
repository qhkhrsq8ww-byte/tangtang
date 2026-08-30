"""Presentation layer: TangTang character animation (V10).

Brain emits PresentationAction. This package maps that to PNG frames.
Do not import this package from core/.
"""
from presentation.animation_controller import AnimationClip, AnimationController
from presentation.asset_manifest import AssetManifest
from presentation.frame_renderer import FrameRenderer
from presentation.mapping import AnimationAction, plan_actions
from presentation.state_machine import AnimationStateMachine

__all__ = [
    "AnimationAction",
    "AnimationClip",
    "AnimationController",
    "AnimationStateMachine",
    "AssetManifest",
    "FrameRenderer",
    "plan_actions",
]
