"""Bounded, strict and atomic storage for the Dollar snapshot."""

from pathlib import Path

from ..storage import AtomicSnapshotStore
from .contracts import DollarSnapshot
from .seed import build_seed


class DollarSnapshotStore(AtomicSnapshotStore[DollarSnapshot]):
    def __init__(self, root: Path):
        super().__init__(
            root,
            model=DollarSnapshot,
            seed_factory=build_seed,
            schema_version=1,
            framework_label="美元流动性",
        )
