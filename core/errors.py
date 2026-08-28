"""Shared validation errors for V4 core. No I/O."""


class EventError(ValueError):
    """Illegal event construction or publish of a non-Event."""


class MemoryError(ValueError):
    """Illegal memory record or query scope."""


class ActionError(ValueError):
    """Illegal presentation action (orchestrator output)."""
