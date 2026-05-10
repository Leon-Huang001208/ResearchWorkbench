"""资产分析快照仓储实现"""
from typing import List, Optional

from core.contracts import AssetAnalysisSnapshot
from core.interfaces import AssetSnapshotRepository
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import AssetSnapshot as AssetSnapshotModel

logger = get_logger(__name__)


class AssetSnapshotRepositoryImpl(BaseRepository, AssetSnapshotRepository):
    """资产分析快照仓储实现"""

    def _to_domain(self, model: AssetSnapshotModel) -> AssetAnalysisSnapshot:
        """转换为领域模型"""
        from datetime import timezone

        as_of = model.as_of
        # 确保 as_of 带有 UTC 时区信息（SQLite 可能丢失时区）
        if as_of is not None and as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)

        return AssetAnalysisSnapshot(
            canonical_id=model.canonical_id,
            as_of=as_of,
            financial=model.financial,
            fund_flow=model.fund_flow,
            price_volume=model.price_volume,
            valuation=model.valuation,
            shareholder=model.shareholder,
            industry=model.industry,
            event_impact=model.event_impact,
            macro_exposure=model.macro_exposure,
            evidence_refs=model.evidence_refs,
        )

    def _to_model(self, domain: AssetAnalysisSnapshot) -> AssetSnapshotModel:
        """转换为数据库模型"""
        import uuid

        return AssetSnapshotModel(
            snapshot_id=str(uuid.uuid4()),
            canonical_id=domain.canonical_id,
            as_of=domain.as_of,
            financial=domain.financial,
            fund_flow=domain.fund_flow,
            price_volume=domain.price_volume,
            valuation=domain.valuation,
            shareholder=domain.shareholder,
            industry=domain.industry,
            event_impact=domain.event_impact,
            macro_exposure=domain.macro_exposure,
            evidence_refs=domain.evidence_refs,
        )

    def save(self, entity: AssetAnalysisSnapshot) -> AssetAnalysisSnapshot:
        """保存快照"""
        # 检查是否已存在相同时间点的快照
        existing = (
            self.db.query(AssetSnapshotModel)
            .filter_by(canonical_id=entity.canonical_id, as_of=entity.as_of)
            .first()
        )

        if existing:
            existing.financial = entity.financial
            existing.fund_flow = entity.fund_flow
            existing.price_volume = entity.price_volume
            existing.valuation = entity.valuation
            existing.shareholder = entity.shareholder
            existing.industry = entity.industry
            existing.event_impact = entity.event_impact
            existing.macro_exposure = entity.macro_exposure
            existing.evidence_refs = entity.evidence_refs
            model = existing
        else:
            model = self._to_model(entity)
            self.db.add(model)

        self.db.flush()
        logger.debug("asset snapshot saved", canonical_id=entity.canonical_id, as_of=entity.as_of)
        return self._to_domain(model)

    def get(self, id: str) -> Optional[AssetAnalysisSnapshot]:
        """根据 ID 获取快照"""
        model = self.db.query(AssetSnapshotModel).filter_by(snapshot_id=id).first()
        return self._to_domain(model) if model else None

    def list(self, limit: int = 100, offset: int = 0) -> List[AssetAnalysisSnapshot]:
        """列出快照"""
        models = self.db.query(AssetSnapshotModel).limit(limit).offset(offset).all()
        return [self._to_domain(m) for m in models]

    def delete(self, id: str) -> bool:
        """删除快照"""
        count = self.db.query(AssetSnapshotModel).filter_by(snapshot_id=id).delete()
        return count > 0

    def get_latest_by_canonical_id(self, canonical_id: str) -> Optional[AssetAnalysisSnapshot]:
        """获取某资产的最新快照"""
        model = (
            self.db.query(AssetSnapshotModel)
            .filter_by(canonical_id=canonical_id)
            .order_by(AssetSnapshotModel.as_of.desc())
            .first()
        )
        return self._to_domain(model) if model else None

    def get_by_canonical_id_and_time_range(
        self, canonical_id: str, start_time: str, end_time: str
    ) -> List[AssetAnalysisSnapshot]:
        """获取某资产在时间范围内的快照"""
        from datetime import datetime

        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)

        models = (
            self.db.query(AssetSnapshotModel)
            .filter(
                AssetSnapshotModel.canonical_id == canonical_id,
                AssetSnapshotModel.as_of >= start_dt,
                AssetSnapshotModel.as_of <= end_dt,
            )
            .order_by(AssetSnapshotModel.as_of.desc())
            .all()
        )
        return [self._to_domain(m) for m in models]
