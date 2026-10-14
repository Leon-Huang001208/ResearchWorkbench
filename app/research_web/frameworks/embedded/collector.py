"""No-op collector for embedded frameworks; the app runs standalone."""

from core.observability import get_logger

from .store import EmbeddedSnapshotStore

log = get_logger(__name__)


class EmbeddedCollector:
    def __init__(self, store: EmbeddedSnapshotStore) -> None:
        self.store = store

    async def ping(self) -> None:
        """Optional: could health-check external URL in the future."""
        log.info("framework_static_collection_not_supported")
