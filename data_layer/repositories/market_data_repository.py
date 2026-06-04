"""MarketDataRepository — 市场结构化数据的 upsert/查询层

为 stock_master, stock_daily_bar 等表提供幂等写入方法。
PostgreSQL 使用 on_conflict_do_update，SQLite fallback 用 check-then-update-or-insert。
"""
from typing import Any, Optional, cast

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import (
    IndexComponentDB,
    StockDailyBarDB,
    StockFinancialMetricDB,
    StockMasterDB,
    StockQuoteSnapshotDB,
    StockShareholderDB,
    StockValuationDB,
)

logger = get_logger(__name__)


def _is_postgresql(db: Session) -> bool:
    """检测当前数据库是否为 PostgreSQL"""
    return bool(db.bind and db.bind.dialect.name == "postgresql")


class MarketDataRepository(BaseRepository):
    """市场数据仓储"""

    # ── StockMaster ──────────────────────────────────────────────

    def upsert_stock_master(self, item: dict) -> None:
        """插入或更新单条股票基本信息"""
        self.upsert_stock_master_many([item])

    def upsert_stock_master_many(self, items: list[dict]) -> int:
        """批量插入或更新股票基本信息，返回实际写入行数"""
        if not items:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                StockMasterDB,
                items,
                constraint="stock_master_pkey",
                update_cols=[
                    "raw_code",
                    "name",
                    "exchange",
                    "market",
                    "industry_level1",
                    "industry_level2",
                    "industry_level3",
                    "list_date",
                    "source",
                    "updated_at",
                ],
            )
        else:
            return self._upsert_sqlite(StockMasterDB, items, key_cols=["symbol"])

    def get_stock_master(self, symbol: str) -> Optional[StockMasterDB]:
        """按 symbol 查询股票基本信息"""
        return self.db.query(StockMasterDB).filter(StockMasterDB.symbol == symbol).first()

    def get_all_stock_symbols(self, limit: int = 5000) -> list[str]:
        """获取所有股票 symbol"""
        rows = self.db.query(StockMasterDB.symbol).order_by(StockMasterDB.symbol).limit(limit).all()
        return [r[0] for r in rows]

    # ── StockDailyBar ────────────────────────────────────────────

    def upsert_daily_bars(self, bars: list[dict]) -> int:
        """批量插入或更新日行情数据"""
        if not bars:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                StockDailyBarDB,
                bars,
                constraint="uq_stock_daily_bar_symbol_date_source",
                update_cols=[
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "amount",
                    "turnover",
                    "raw_payload",
                ],
            )
        else:
            return self._upsert_sqlite(
                StockDailyBarDB, bars, key_cols=["symbol", "trade_date", "source"]
            )

    def get_daily_bars(
        self, symbol: str, start_date=None, end_date=None, limit: int = 500
    ) -> list[StockDailyBarDB]:
        """按股票查询日行情"""
        q = (
            self.db.query(StockDailyBarDB)
            .filter(StockDailyBarDB.symbol == symbol)
            .order_by(StockDailyBarDB.trade_date.desc())
        )
        if start_date:
            q = q.filter(StockDailyBarDB.trade_date >= start_date)
        if end_date:
            q = q.filter(StockDailyBarDB.trade_date <= end_date)
        return q.limit(limit).all()

    def get_latest_daily_bar(self, symbol: str) -> Optional[StockDailyBarDB]:
        """获取最新一条日行情"""
        return (
            self.db.query(StockDailyBarDB)
            .filter(StockDailyBarDB.symbol == symbol)
            .order_by(StockDailyBarDB.trade_date.desc())
            .first()
        )

    # ── StockQuoteSnapshot ───────────────────────────────────────

    def insert_quote_snapshots(self, quotes: list[dict]) -> int:
        """批量插入实时行情快照（通常不需要 upsert）"""
        if not quotes:
            return 0
        self.db.execute(text(""), {})  # no-op, placeholder for batch insert
        self.db.bulk_insert_mappings(cast(Any, StockQuoteSnapshotDB), quotes)
        self.db.flush()
        return len(quotes)

    # ── StockFinancialMetric ─────────────────────────────────────

    def upsert_financial_metrics(self, metrics: list[dict]) -> int:
        """批量插入或更新财务指标"""
        if not metrics:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                StockFinancialMetricDB,
                metrics,
                constraint="stock_financial_metric_pkey",
                update_cols=[
                    "report_type",
                    "total_revenue",
                    "net_profit",
                    "total_assets",
                    "total_liabilities",
                    "equity",
                    "roe",
                    "roa",
                    "gross_margin",
                    "net_margin",
                    "debt_ratio",
                    "source",
                    "raw_payload",
                ],
            )
        else:
            return self._upsert_sqlite(
                StockFinancialMetricDB, metrics, key_cols=["symbol", "report_date", "source"]
            )

    def get_latest_financial(self, symbol: str) -> Optional[StockFinancialMetricDB]:
        """获取最新一条财务指标"""
        return (
            self.db.query(StockFinancialMetricDB)
            .filter(StockFinancialMetricDB.symbol == symbol)
            .order_by(StockFinancialMetricDB.report_date.desc())
            .first()
        )

    # ── StockValuation ───────────────────────────────────────────

    def upsert_valuations(self, valuations: list[dict]) -> int:
        """批量插入或更新估值指标"""
        if not valuations:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                StockValuationDB,
                valuations,
                constraint="stock_valuation_pkey",
                update_cols=[
                    "pe_ttm",
                    "pe_dynamic",
                    "pb",
                    "ps",
                    "market_cap",
                    "float_market_cap",
                    "source",
                    "raw_payload",
                ],
            )
        else:
            return self._upsert_sqlite(
                StockValuationDB, valuations, key_cols=["symbol", "as_of", "source"]
            )

    def get_latest_valuation(self, symbol: str) -> Optional[StockValuationDB]:
        """获取最新一条估值指标"""
        return (
            self.db.query(StockValuationDB)
            .filter(StockValuationDB.symbol == symbol)
            .order_by(StockValuationDB.as_of.desc())
            .first()
        )

    # ── StockShareholder ─────────────────────────────────────────

    def upsert_shareholders(self, holders: list[dict]) -> int:
        """批量插入或更新股东信息"""
        if not holders:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                StockShareholderDB,
                holders,
                constraint="stock_shareholder_pkey",
                update_cols=[
                    "holder_rank",
                    "shares",
                    "holding_pct",
                    "holder_type",
                    "source",
                    "raw_payload",
                ],
            )
        else:
            return self._upsert_sqlite(
                StockShareholderDB,
                holders,
                key_cols=["symbol", "report_date", "holder_name", "source"],
            )

    def get_latest_shareholders(self, symbol: str, limit: int = 10) -> list[StockShareholderDB]:
        """获取最新一期股东信息"""
        return (
            self.db.query(StockShareholderDB)
            .filter(StockShareholderDB.symbol == symbol)
            .order_by(StockShareholderDB.report_date.desc(), StockShareholderDB.holder_rank)
            .limit(limit)
            .all()
        )

    # ── IndexComponent ───────────────────────────────────────────

    def upsert_index_components(self, components: list[dict]) -> int:
        """批量插入或更新指数成分"""
        if not components:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                IndexComponentDB,
                components,
                constraint="index_component_pkey",
                update_cols=["component_name", "weight", "source", "raw_payload"],
            )
        else:
            return self._upsert_sqlite(
                IndexComponentDB,
                components,
                key_cols=["index_symbol", "component_symbol", "as_of", "source"],
            )

    # ── Internal helpers ─────────────────────────────────────────

    def _upsert_postgres(
        self, model, items: list[dict], constraint: str, update_cols: list[str]
    ) -> int:
        """PostgreSQL: INSERT ... ON CONFLICT DO UPDATE"""
        stmt = insert(model).values(items)
        stmt = stmt.on_conflict_do_update(
            constraint=constraint,
            set_={col: getattr(stmt.excluded, col) for col in update_cols},
        )
        self.db.execute(stmt)
        self.db.flush()
        return len(items)

    def _upsert_sqlite(self, model, items: list[dict], key_cols: list[str]) -> int:
        """SQLite fallback: check-then-update-or-insert"""
        count = 0
        for item in items:
            filters = {col: item[col] for col in key_cols if col in item}
            existing = self.db.query(model).filter_by(**filters).first()
            if existing:
                for k, v in item.items():
                    if k not in key_cols:
                        setattr(existing, k, v)
            else:
                self.db.add(model(**item))
            count += 1
        self.db.flush()
        return count
