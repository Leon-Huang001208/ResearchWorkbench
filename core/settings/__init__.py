"""Core settings public exports with lazy initialization."""

from __future__ import annotations

from typing import Any

__all__ = ["settings"]


def __getattr__(name: str) -> Any:
    """Load Settings only when a consumer explicitly requests the singleton."""
    if name == "settings":
        from .config import settings

        return settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
