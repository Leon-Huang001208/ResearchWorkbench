"""FactorStore — 动态因子持久化服务层

FactorStore 将 FactorRepository 与 Pydantic 契约桥接，提供：
- 因子定义注册与查询
- 点时因子值的批量保存与加载
- 因子评估指标的持久化
- 动态权重的快照存取
"""
from __future__ import annotations

from datetime import date, datetime

from core.contracts.factors import (
    DynamicFactorWeights,
    FactorDefinition,
    FactorEvaluation,
    FactorValue,
)
from core.observability import get_logger
from data_layer.repositories.factor_repository import FactorRepository

logger = get_logger(__name__)


class FactorStore:
    """动态因子持久化服务

    用法::

        store = FactorStore()
        store.register_definitions([definition1, definition2])
        store.store_values([value1, value2, ...])
        values = store.load_values(as_of_date=date.today())
    """

    def __init__(self, repository: FactorRepository | None = None):
        self._repo = repository or FactorRepository()

    @property
    def repo(self) -> FactorRepository:
        return self._repo

    # ─── Factor Definitions ────────────────────────────────

    def register_definitions(self, definitions: list[FactorDefinition]) -> int:
        """注册或更新因子定义"""
        if not definitions:
            return 0
        records = [_definition_to_record(d) for d in definitions]
        return self.repo.save_definitions(records)

    def get_definitions(
        self,
        factor_ids: list[str] | None = None,
        category: str | None = None,
    ) -> list[FactorDefinition]:
        """查询因子定义"""
        rows = self.repo.get_definitions(factor_ids=factor_ids, category=category)
        return [_definition_from_row(r) for r in rows]

    def get_all_categories(self) -> list[str]:
        """获取所有已注册的因子类别"""
        return self.repo.get_all_categories()

    # ─── Factor Values ─────────────────────────────────────

    def store_values(self, values: list[FactorValue]) -> int:
        """批量持久化点时因子值"""
        if not values:
            return 0
        records = [_value_to_record(v) for v in values]
        return self.repo.save_values(records)

    def load_values(
        self,
        as_of_date: date,
        factor_ids: list[str] | None = None,
    ) -> list[FactorValue]:
        """加载指定日期的因子值（用于构建横截面矩阵）"""
        rows = self.repo.get_values_for_date(
            as_of_date=as_of_date,
            factor_ids=factor_ids,
        )
        return [_value_from_row(r) for r in rows]

    def load_values_range(
        self,
        factor_ids: list[str] | None = None,
        subject_ids: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50000,
    ) -> list[FactorValue]:
        """加载时间范围内的因子值"""
        rows = self.repo.get_values(
            factor_ids=factor_ids,
            subject_ids=subject_ids,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return [_value_from_row(r) for r in rows]

    def get_available_dates(
        self,
        factor_id: str | None = None,
        limit: int = 500,
    ) -> list[date]:
        """获取有因子值可用的日期列表"""
        return self.repo.get_available_dates(factor_id=factor_id, limit=limit)

    # ─── Factor Evaluations ────────────────────────────────

    def store_evaluations(self, evaluations: list[FactorEvaluation]) -> int:
        """批量持久化因子评估指标"""
        if not evaluations:
            return 0
        records = [_evaluation_to_record(e) for e in evaluations]
        return self.repo.save_evaluations(records)

    def load_evaluations(
        self,
        factor_ids: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 1000,
    ) -> list[FactorEvaluation]:
        """加载因子评估记录"""
        rows = self.repo.get_evaluations(
            factor_ids=factor_ids,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return [_evaluation_from_row(r) for r in rows]

    def load_latest_evaluations(
        self,
        factor_ids: list[str] | None = None,
        horizon_days: int = 20,
        limit_dates: int = 60,
    ) -> list[FactorEvaluation]:
        """加载最近评估记录（用于拟合动态权重）"""
        rows = self.repo.get_latest_evaluations(
            factor_ids=factor_ids,
            horizon_days=horizon_days,
            limit_dates=limit_dates,
        )
        return [_evaluation_from_row(r) for r in rows]

    # ─── Dynamic Weights ───────────────────────────────────

    def store_weights(self, weights: DynamicFactorWeights) -> int:
        """持久化动态因子权重快照"""
        record = _weights_to_record(weights)
        return self.repo.save_weights(record)

    def load_latest_weights(self, metric: str = "rank_ic") -> DynamicFactorWeights | None:
        """加载最新的动态权重"""
        row = self.repo.get_latest_weights(metric=metric)
        if row is None:
            return None
        return _weights_from_row(row)

    def load_weights_history(
        self,
        metric: str = "rank_ic",
        limit: int = 50,
    ) -> list[DynamicFactorWeights]:
        """加载权重历史快照"""
        rows = self.repo.get_weights_history(metric=metric, limit=limit)
        return [_weights_from_row(r) for r in rows]

    # ─── Lifecycle ─────────────────────────────────────────

    def close(self):
        """释放数据库连接"""
        self.repo.close()


# ─── Record ↔ Contract converters ─────────────────────────


def _definition_to_record(d: FactorDefinition) -> dict:
    return {
        "factor_id": d.factor_id,
        "name": d.name,
        "category": d.category.value,
        "direction": d.direction,
        "description": d.description,
        "version": d.version,
        "horizon_days": d.horizon_days,
        "refresh_frequency": d.refresh_frequency,
        "meta": d.metadata,
    }


def _definition_from_row(r) -> FactorDefinition:
    from core.contracts.factors import FactorCategory

    return FactorDefinition(
        factor_id=r.factor_id,
        name=r.name,
        category=FactorCategory(r.category),
        direction=r.direction,
        description=r.description or "",
        version=r.version or "v1",
        horizon_days=r.horizon_days,
        refresh_frequency=r.refresh_frequency or "1d",
        metadata=r.meta or {},
    )


def _value_to_record(v: FactorValue) -> dict:
    return {
        "factor_id": v.factor_id,
        "subject_id": v.subject_id,
        "as_of_date": v.as_of_date,
        "value": v.value,
        "available_at": v.available_at or datetime.utcnow(),
        "source": v.source,
        "meta": v.metadata,
    }


def _value_from_row(r) -> FactorValue:
    return FactorValue(
        factor_id=r.factor_id,
        subject_id=r.subject_id,
        as_of_date=r.as_of_date,
        value=float(r.value) if r.value is not None else None,
        available_at=r.available_at,
        source=r.source,
        metadata=r.meta or {},
    )


def _evaluation_to_record(e: FactorEvaluation) -> dict:
    return {
        "factor_id": e.factor_id,
        "as_of_date": e.as_of_date,
        "horizon_days": e.horizon_days,
        "sample_size": e.sample_size,
        "coverage": e.coverage,
        "ic": e.ic,
        "rank_ic": e.rank_ic,
        "decile_spread": e.decile_spread,
        "meta": e.metadata,
    }


def _evaluation_from_row(r) -> FactorEvaluation:
    return FactorEvaluation(
        factor_id=r.factor_id,
        as_of_date=r.as_of_date,
        horizon_days=r.horizon_days or 20,
        sample_size=r.sample_size or 0,
        coverage=float(r.coverage or 0.0),
        ic=float(r.ic or 0.0),
        rank_ic=float(r.rank_ic or 0.0),
        decile_spread=float(r.decile_spread or 0.0),
        metadata=r.meta or {},
    )


def _weights_to_record(w: DynamicFactorWeights) -> dict:
    return {
        "as_of_date": w.as_of_date,
        "lookback_periods": w.lookback_periods,
        "metric": w.metric,
        "weights": w.weights,
        "raw_scores": w.raw_scores,
    }


def _weights_from_row(r) -> DynamicFactorWeights:
    return DynamicFactorWeights(
        as_of_date=r.as_of_date,
        lookback_periods=r.lookback_periods or 12,
        metric=r.metric or "rank_ic",
        weights=r.weights or {},
        raw_scores=r.raw_scores or {},
    )
