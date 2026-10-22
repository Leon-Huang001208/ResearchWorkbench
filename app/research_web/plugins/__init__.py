"""Inert, reviewed ecosystem packages projected into the sole DSH runtime."""

from .packages import PluginError
from .service import PluginService

__all__ = ["PluginError", "PluginService"]
