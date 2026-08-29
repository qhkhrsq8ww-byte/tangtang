"""Shared validation errors for V4 core. No I/O."""


class EventError(ValueError):
    """Illegal event construction or publish of a non-Event."""


class MemoryError(ValueError):
    """Illegal memory record or query scope."""


class ActionError(ValueError):
    """Illegal presentation action (orchestrator output)."""


class PrivacyError(ValueError):
    """Illegal privacy classification or store routing."""


class PathError(ValueError):
    """Path traversal or write outside TANGTANG_HOME."""


class ShellError(ValueError):
    """Event/LLM text must not reach a shell."""


class SinkError(Exception):
    """TTS / STT / projection failed. The Event must still be kept."""


class IsolationError(Exception):
    """Wrapped subsystem failure. Process continues."""


class CompatibilityError(ValueError):
    """Port is not V4-compatible. V5 must not silently smash V4."""
