"""Embedded framework package."""

from .context import build_context
from .contracts import EmbeddedSnapshot
from .definition import DEFINITION
from .seed import build_seed
from .store import EmbeddedSnapshotStore

__all__ = ["DEFINITION", "EmbeddedSnapshot", "EmbeddedSnapshotStore", "build_context", "build_seed"]
