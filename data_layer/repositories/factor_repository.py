"""FactorRepository — 动态因子持久化层

为动态多因子系统提供 FactorDefinition、FactorValue、FactorEvaluation
和 DynamicFactorWeight 的持久化能力。
"""
from datetime import date
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.observability import get_logger
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import (
    DynamicFactorWeightDB,
    FactorDefinitionDB,
    FactorEvaluationDB,
    FactorValueDB,
)

logger = get_logger(__name__)


class FactorRepository:
    """因子数据仓储 —— 基于 PostgreSQL upsert 的持久化层"""

    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    # ─── Generic upsert ────────────────────────────────────

    def _upsert(self, model, records: list[dict], key_cols: list[str]) -> int:
        """通用 upsert 实现"""
        if not records:
            return 0

        session = self.db
        saved = 0
        try:
            for record in records:
                stmt = pg_insert(model).values(**record)
                update_cols = {
                    k: stmt.excluded[k] for k in record if k not in key_cols and k != "id"
                }
                if update_cols:
                    stmt = stmt.on_conflict_do_update(
                        index_elements=key_cols,
                        set_=update_cols,
                    )
                else:
                    stmt = stmt.on_conflict_do_nothing(index_elements=key_cols)
                session.execute(stmt)
                saved += 1
            session.commit()
            logger.info(
                "FactorRepository: upserted %d records to %s",
                saved,
                model.__tablename__,
            )
        except Exception as e:
            session.rollback()
            logger.error(
                "FactorRepository upsert failed for %s: %s",
                model.__tablename__,
                e,
                exc_info=True,
            )
            raise
        return saved

    # ─── Factor Definitions ────────────────────────────────

    def save_definitions(self, records: list[dict]) -> int:
        """批量保存因子定义"""
        return self._upsert(FactorDefinitionDB, records, ["factor_id"])

    def get_definitions(
        self,
        factor_ids: Optional[list[str]] = None,
        category: Optional[str] = None,
    ) -> list[FactorDefinitionDB]:
        """查询因子定义"""
        query = self.db.query(FactorDefinitionDB)
        if factor_ids:
            query = query.filter(FactorDefinitionDB.factor_id.in_(factor_ids))
        if category:
            query = query.filter(FactorDefinitionDB.category == category)
        return query.all()

    def get_all_categories(self) -> list[str]:
        """获取所有已注册的因子类别"""
        results = (
            self.db.query(FactorDefinitionDB.category)
            .distinct()
            .order_by(FactorDefinitionDB.category)
            .all()
        )
        return [r[0] for r in results]

    # ─── Factor Values ─────────────────────────────────────

    def save_values(self, records: list[dict]) -> int:
        """批量保存点时因子值"""
        return self._upsert(
            FactorValueDB,
            records,
            ["factor_id", "subject_id", "as_of_date"],
        )

    def get_values(
        self,
        factor_ids: Optional[list[str]] = None,
        subject_ids: Optional[list[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50000,
    ) -> list[FactorValueDB]:
        """查询因子值"""
        query = self.db.query(FactorValueDB)
        if factor_ids:
            query = query.filter(FactorValueDB.factor_id.in_(factor_ids))
        if subject_ids:
            query = query.filter(FactorValueDB.subject_id.in_(subject_ids))
        if start_date:
            query = query.filter(FactorValueDB.as_of_date >= start_date)
        if end_date:
            query = query.filter(FactorValueDB.as_of_date <= end_date)
        return (
            query.order_by(FactorValueDB.as_of_date.desc(), FactorValueDB.factor_id)
            .limit(limit)
            .all()
        )

    def get_values_for_date(
        self,
        as_of_date: date,
        factor_ids: Optional[list[str]] = None,
    ) -> list[FactorValueDB]:
        """获取某一天的所有因子值（用于构建横截面矩阵）"""
        query = self.db.query(FactorValueDB).filter(FactorValueDB.as_of_date == as_of_date)
        if factor_ids:
            query = query.filter(FactorValueDB.factor_id.in_(factor_ids))
        return query.all()

    def get_available_dates(
        self,
        factor_id: Optional[str] = None,
        limit: int = 500,
    ) -> list[date]:
        """获取有因子值的日期列表（按日期降序）"""
        query = self.db.query(FactorValueDB.as_of_date).distinct()
        if factor_id:
            query = query.filter(FactorValueDB.factor_id == factor_id)
        results = query.order_by(FactorValueDB.as_of_date.desc()).limit(limit).all()
        return [r[0] for r in results]

    # ─── Factor Evaluations ────────────────────────────────

    def save_evaluations(self, records: list[dict]) -> int:
        """批量保存因子评估指标"""
        return self._upsert(
            FactorEvaluationDB,
            records,
            ["factor_id", "as_of_date", "horizon_days"],
        )

    def get_evaluations(
        self,
        factor_ids: Optional[list[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 1000,
    ) -> list[FactorEvaluationDB]:
        """查询因子评估记录"""
        query = self.db.query(FactorEvaluationDB)
        if factor_ids:
            query = query.filter(FactorEvaluationDB.factor_id.in_(factor_ids))
        if start_date:
            query = query.filter(FactorEvaluationDB.as_of_date >= start_date)
        if end_date:
            query = query.filter(FactorEvaluationDB.as_of_date <= end_date)
        return (
            query.order_by(
                FactorEvaluationDB.as_of_date.desc(),
                FactorEvaluationDB.factor_id,
            )
            .limit(limit)
            .all()
        )

    def get_latest_evaluations(
        self,
        factor_ids: Optional[list[str]] = None,
        horizon_days: int = 20,
        limit_dates: int = 60,
    ) -> list[FactorEvaluationDB]:
        """获取最近的评估记录（用于拟合动态权重）"""
        query = self.db.query(FactorEvaluationDB).filter(
            FactorEvaluationDB.horizon_days == horizon_days
        )
        if factor_ids:
            query = query.filter(FactorEvaluationDB.factor_id.in_(factor_ids))
        return (
            query.order_by(FactorEvaluationDB.as_of_date.desc())
            .limit(limit_dates * (len(factor_ids) if factor_ids else 10))
            .all()
        )

    # ─── Dynamic Weights ───────────────────────────────────

    def save_weights(self, record: dict) -> int:
        """保存动态因子权重快照"""
        try:
            session = self.db
            stmt = pg_insert(DynamicFactorWeightDB).values(**record)
            update_cols = {k: stmt.excluded[k] for k in record if k not in ("as_of_date", "metric")}
            if update_cols:
                stmt = stmt.on_conflict_do_update(
                    index_elements=["as_of_date", "metric"],
                    set_=update_cols,
                )
            else:
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["as_of_date", "metric"],
                )
            session.execute(stmt)
            session.commit()
            logger.info(
                "FactorRepository: saved weights for %s metric=%s",
                record.get("as_of_date"),
                record.get("metric"),
            )
            return 1
        except Exception as e:
            session.rollback()
            logger.error("FactorRepository save_weights failed: %s", e, exc_info=True)
            raise

    def get_latest_weights(self, metric: str = "rank_ic") -> Optional[DynamicFactorWeightDB]:
        """获取最新的动态权重"""
        return (
            self.db.query(DynamicFactorWeightDB)
            .filter(DynamicFactorWeightDB.metric == metric)
            .order_by(DynamicFactorWeightDB.as_of_date.desc())
            .first()
        )

    def get_weights_history(
        self,
        metric: str = "rank_ic",
        limit: int = 50,
    ) -> list[DynamicFactorWeightDB]:
        """获取权重历史记录"""
        return (
            self.db.query(DynamicFactorWeightDB)
            .filter(DynamicFactorWeightDB.metric == metric)
            .order_by(DynamicFactorWeightDB.as_of_date.desc())
            .limit(limit)
            .all()
        )

    def close(self):
        """关闭数据库会话"""
        if self._db:
            self._db.close()
            self._db = None
