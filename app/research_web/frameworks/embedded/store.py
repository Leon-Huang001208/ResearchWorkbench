"""Bounded storage for embedded framework snapshots."""

from pathlib import Path

from ..storage import AtomicSnapshotStore
from .contracts import EmbeddedSnapshot
from .seed import build_seed


class EmbeddedSnapshotStore(AtomicSnapshotStore[EmbeddedSnapshot]):
    def __init__(self, root: Path):
        super().__init__(
            root,
            model=EmbeddedSnapshot,
            seed_factory=build_seed,
            schema_version=1,
            framework_label="嵌入式",
        )
