"""内存资产快照仓储 — 无 DB 依赖，用于测试和 API 默认"""
from datetime import datetime
from typing import Dict, List, Optional

from core.contracts import AssetAnalysisSnapshot
from core.interfaces import AssetSnapshotRepository


class InMemoryAssetSnapshotRepository(AssetSnapshotRepository):
    """内存资产快照仓储"""

    def __init__(self) -> None:
        self._store: Dict[str, AssetAnalysisSnapshot] = {}

    def save(self, entity: AssetAnalysisSnapshot) -> AssetAnalysisSnapshot:
        key = f"{entity.canonical_id}:{entity.as_of.isoformat()}"
        self._store[key] = entity
        return entity

    def get(self, id: str) -> Optional[AssetAnalysisSnapshot]:
        return self._store.get(id)

    def list(self, limit: int = 100, offset: int = 0) -> List[AssetAnalysisSnapshot]:
        items = list(self._store.values())
        return items[offset : offset + limit]

    def delete(self, id: str) -> bool:
        if id in self._store:
            del self._store[id]
            return True
        return False

    def get_latest_by_canonical_id(self, canonical_id: str) -> Optional[AssetAnalysisSnapshot]:
        snapshots = [s for s in self._store.values() if s.canonical_id == canonical_id]
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.as_of)

    def get_by_canonical_id_and_time_range(
        self, canonical_id: str, start_time: str, end_time: str
    ) -> List[AssetAnalysisSnapshot]:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        return [
            s
            for s in self._store.values()
            if s.canonical_id == canonical_id and start_dt <= s.as_of <= end_dt
        ]
