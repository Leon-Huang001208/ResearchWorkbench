"""PostgreSQL 资产分析快照仓库"""
from typing import Optional

from sqlalchemy.orm import Session

from core.contracts.assets import AssetAnalysisSnapshot
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import AssetSnapshotModel


class PostgresAssetSnapshotRepository(BaseRepository):
    """PostgreSQL 实现资产快照持久化"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def save(self, snapshot: AssetAnalysisSnapshot) -> AssetAnalysisSnapshot:
        """保存资产分析快照"""
        model = AssetSnapshotModel.from_contract(snapshot)
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model.to_contract()

    def get_latest_by_canonical_id(self, canonical_id: str) -> Optional[AssetAnalysisSnapshot]:
        """查询最新快照"""
        model = (
            self.db.query(AssetSnapshotModel)
            .filter(AssetSnapshotModel.canonical_id == canonical_id)
            .order_by(AssetSnapshotModel.created_at.desc())
            .first()
        )
        if not model:
            return None
        return model.to_contract()
