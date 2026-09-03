"""Behavior layer: Character State Engine + interrupt / speak gates (V3 facade)."""

from __future__ import annotations

from behavior.character_state import (
    CharacterStateDecision,
    CharacterStateEngine,
    CharacterStateResolver,
)
from core.policy.interrupt_policy import InterruptPolicy, infer_scene
from core.policy.speak_gate import decide as speak_gate_decide
from core.policy.speak_gate import may_call_llm

# Spec name alias used in docs/15
ShouldInterrupt = InterruptPolicy

__all__ = [
    "CharacterStateDecision",
    "CharacterStateEngine",
    "CharacterStateResolver",
    "InterruptPolicy",
    "ShouldInterrupt",
    "infer_scene",
    "speak_gate_decide",
    "may_call_llm",
]
