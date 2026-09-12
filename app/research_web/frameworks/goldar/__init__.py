"""Goldar's domain-specific definition, snapshot and scoring package."""

from .definition import DEFINITION
from .store import GoldSnapshotStore

__all__ = ["DEFINITION", "GoldSnapshotStore"]
