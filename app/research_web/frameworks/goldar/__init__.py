"""Goldar's domain-specific definition, snapshot and scoring package."""

from .context import build_context
from .contracts import GoldSnapshot
from .definition import DEFINITION
from .store import GoldSnapshotStore

__all__ = ["DEFINITION", "GoldSnapshot", "GoldSnapshotStore", "build_context"]
