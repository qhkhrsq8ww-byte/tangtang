"""V4 integration adapters.

These wrap existing V3 / living-room functions. They do not rewrite
voiceprint, do not dump-merge the living-room cat stack, and they never
let LLM code call TTS, projection, shell, or files.

Core still emits Event / PresentationAction only. Adapters execute sinks.
"""
from core.adapters.animation import (
    ANIMATION_NAMES,
    AnimationAction,
    AnimationController,
)
from core.adapters.chat_adapter import ChatAdapter
from core.adapters.event_store import JsonlEventStore
from core.adapters.family_loader import load_family_document, load_members
from core.adapters.living_room_adapter import (
    LIVING_ROOM_EVENT_TYPES,
    LivingRoomAdapter,
)
from core.adapters.observation import Observation, voice_observation
from core.adapters.projection_adapter import ProjectionAdapter
from core.adapters.tts_adapter import TTSAdapter
from core.adapters.voice_adapter import VoiceAdapter

__all__ = [
    "ANIMATION_NAMES",
    "AnimationAction",
    "AnimationController",
    "ChatAdapter",
    "JsonlEventStore",
    "LIVING_ROOM_EVENT_TYPES",
    "LivingRoomAdapter",
    "Observation",
    "ProjectionAdapter",
    "TTSAdapter",
    "VoiceAdapter",
    "load_family_document",
    "load_members",
    "voice_observation",
]
