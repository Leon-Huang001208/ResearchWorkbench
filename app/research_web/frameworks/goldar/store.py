"""Bounded, strict and atomic local storage for the Goldar snapshot."""

from pathlib import Path

from ..storage import AtomicSnapshotStore
from .contracts import GoldSnapshot
from .seed import build_seed


class GoldSnapshotStore(AtomicSnapshotStore[GoldSnapshot]):
    def __init__(self, root: Path):
        super().__init__(
            root,
            model=GoldSnapshot,
            seed_factory=build_seed,
            schema_version=2,
            framework_label="黄金",
        )
