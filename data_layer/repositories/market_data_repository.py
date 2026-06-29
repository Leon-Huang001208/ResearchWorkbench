"""MarketDataRepository — 市场结构化数据的 upsert/查询层

为 stock_master, stock_daily_bar 等表提供幂等写入方法。
PostgreSQL 使用 on_conflict_do_update，SQLite fallback 用 check-then-update-or-insert。
"""
from datetime import date, datetime
from typing import Any, Optional, cast

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import (
    ETFDailyMetricDB,
    ETFMasterDB,
    IndexComponentSnapshotDB,
    IndexETFLinkDB,
    IndexMasterDB,
    IndexProviderDB,
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

    def get_existing_trade_dates(
        self,
        symbol: str,
        source: str,
        start_date: str | date | datetime,
        end_date: str | date | datetime,
    ) -> set[date]:
        """查询某证券在指定来源和日期范围内已有的交易日集合"""
        start_dt = self._coerce_datetime(start_date)
        end_dt = self._coerce_datetime(end_date)
        rows = (
            self.db.query(StockDailyBarDB.trade_date)
            .filter(StockDailyBarDB.symbol == symbol)
            .filter(StockDailyBarDB.source == source)
            .filter(StockDailyBarDB.trade_date >= start_dt)
            .filter(StockDailyBarDB.trade_date <= end_dt)
            .all()
        )
        return {
            value.date() if isinstance(value, datetime) else value
            for (value,) in rows
            if value is not None
        }

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

    # ── Index structure ──────────────────────────────────────────

    def upsert_index_providers(self, providers: list[dict]) -> int:
        """批量插入或更新指数发布方"""
        if not providers:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                IndexProviderDB,
                providers,
                constraint="index_provider_pkey",
                update_cols=["name", "official_site", "source_priority", "raw_payload", "updated_at"],
            )
        return self._upsert_sqlite(IndexProviderDB, providers, key_cols=["provider_code"])

    def upsert_index_master_many(self, indices: list[dict]) -> int:
        """批量插入或更新指数主数据"""
        if not indices:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                IndexMasterDB,
                indices,
                constraint="index_master_pkey",
                update_cols=[
                    "provider_code",
                    "official_code",
                    "wind_code",
                    "name_cn",
                    "name_en",
                    "market",
                    "currency",
                    "category",
                    "launch_date",
                    "base_date",
                    "base_value",
                    "is_active",
                    "raw_payload",
                    "updated_at",
                ],
            )
        return self._upsert_sqlite(IndexMasterDB, indices, key_cols=["index_id"])

    def upsert_index_components(self, components: list[dict]) -> int:
        """批量插入或更新指数成分权重快照"""
        if not components:
            return 0

        normalized = [self._normalize_index_component(item) for item in components]

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                IndexComponentSnapshotDB,
                normalized,
                constraint="uq_index_component_snapshot_identity",
                update_cols=[
                    "index_symbol",
                    "provider_code",
                    "component_name",
                    "market",
                    "weight",
                    "weight_pct",
                    "rank",
                    "as_of",
                    "source_scope",
                    "raw_payload",
                ],
            )
        return self._upsert_sqlite(
            IndexComponentSnapshotDB,
            normalized,
            key_cols=["index_id", "trade_date", "component_symbol", "source"],
        )

    def get_index_components(
        self,
        index_id: str,
        trade_date=None,
        source: str | None = None,
        limit: int = 1000,
    ) -> list[IndexComponentSnapshotDB]:
        """按指数查询成分权重快照"""
        q = (
            self.db.query(IndexComponentSnapshotDB)
            .filter(IndexComponentSnapshotDB.index_id == index_id)
            .order_by(IndexComponentSnapshotDB.rank.asc(), IndexComponentSnapshotDB.weight_pct.desc())
        )
        if trade_date:
            q = q.filter(IndexComponentSnapshotDB.trade_date == trade_date)
        if source:
            q = q.filter(IndexComponentSnapshotDB.source == source)
        return q.limit(limit).all()

    def get_stock_index_memberships(
        self,
        component_symbol: str,
        trade_date=None,
        source: str | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """反查个股所属指数及权重"""
        q = self.db.query(IndexComponentSnapshotDB).filter(
            IndexComponentSnapshotDB.component_symbol == component_symbol
        )
        if trade_date:
            q = q.filter(IndexComponentSnapshotDB.trade_date == trade_date)
        if source:
            q = q.filter(IndexComponentSnapshotDB.source == source)

        rows = q.order_by(IndexComponentSnapshotDB.weight_pct.desc()).limit(limit).all()
        index_ids = [row.index_id for row in rows]
        masters = {}
        if index_ids:
            master_rows = self.db.query(IndexMasterDB).filter(IndexMasterDB.index_id.in_(index_ids)).all()
            masters = {row.index_id: row for row in master_rows}

        memberships = []
        for row in rows:
            master = masters.get(row.index_id)
            memberships.append(
                {
                    "index_id": row.index_id,
                    "index_symbol": row.index_symbol,
                    "provider_code": row.provider_code,
                    "index_name": master.name_cn if master else row.index_symbol,
                    "component_symbol": row.component_symbol,
                    "component_name": row.component_name,
                    "trade_date": row.trade_date,
                    "weight_pct": row.weight_pct,
                    "source": row.source,
                }
            )
        return memberships

    # ── ETF structure ────────────────────────────────────────────

    def upsert_etf_master_many(self, etfs: list[dict]) -> int:
        """批量插入或更新 ETF 主数据"""
        if not etfs:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                ETFMasterDB,
                etfs,
                constraint="etf_master_pkey",
                update_cols=[
                    "name",
                    "exchange",
                    "market",
                    "fund_manager",
                    "listed_date",
                    "currency",
                    "status",
                    "raw_payload",
                    "updated_at",
                ],
            )
        return self._upsert_sqlite(ETFMasterDB, etfs, key_cols=["etf_symbol"])

    def upsert_index_etf_links(self, links: list[dict]) -> int:
        """批量插入或更新指数与 ETF 跟踪关系"""
        if not links:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                IndexETFLinkDB,
                links,
                constraint="uq_index_etf_link_identity",
                update_cols=["tracking_role", "confidence", "raw_payload", "updated_at"],
            )
        return self._upsert_sqlite(
            IndexETFLinkDB,
            links,
            key_cols=["index_id", "etf_symbol", "link_source"],
        )

    def upsert_etf_daily_metrics(self, metrics: list[dict]) -> int:
        """批量插入或更新 ETF 日度规模与资金流指标"""
        if not metrics:
            return 0

        if _is_postgresql(self.db):
            return self._upsert_postgres(
                ETFDailyMetricDB,
                metrics,
                constraint="uq_etf_daily_metric_symbol_date_source",
                update_cols=[
                    "nav",
                    "close",
                    "shares_outstanding",
                    "aum",
                    "turnover",
                    "premium_discount_pct",
                    "net_flow_amount",
                    "raw_payload",
                ],
            )
        return self._upsert_sqlite(
            ETFDailyMetricDB,
            metrics,
            key_cols=["etf_symbol", "trade_date", "source"],
        )

    def get_index_etfs(self, index_id: str, limit: int = 500) -> list[dict]:
        """查询跟踪某指数的 ETF 产品"""
        links = (
            self.db.query(IndexETFLinkDB)
            .filter(IndexETFLinkDB.index_id == index_id)
            .order_by(IndexETFLinkDB.confidence.desc())
            .limit(limit)
            .all()
        )
        symbols = [link.etf_symbol for link in links]
        etf_map = {}
        if symbols:
            etfs = self.db.query(ETFMasterDB).filter(ETFMasterDB.etf_symbol.in_(symbols)).all()
            etf_map = {etf.etf_symbol: etf for etf in etfs}

        results = []
        for link in links:
            etf = etf_map.get(link.etf_symbol)
            results.append(
                {
                    "index_id": link.index_id,
                    "etf_symbol": link.etf_symbol,
                    "name": etf.name if etf else link.etf_symbol,
                    "exchange": etf.exchange if etf else None,
                    "tracking_role": link.tracking_role,
                    "link_source": link.link_source,
                    "confidence": link.confidence,
                }
            )
        return results

    def get_etf_daily_metrics(
        self,
        etf_symbol: str,
        start_date=None,
        end_date=None,
        limit: int = 500,
    ) -> list[ETFDailyMetricDB]:
        """查询 ETF 日度规模与资金流指标"""
        q = (
            self.db.query(ETFDailyMetricDB)
            .filter(ETFDailyMetricDB.etf_symbol == etf_symbol)
            .order_by(ETFDailyMetricDB.trade_date.desc())
        )
        if start_date:
            q = q.filter(ETFDailyMetricDB.trade_date >= start_date)
        if end_date:
            q = q.filter(ETFDailyMetricDB.trade_date <= end_date)
        return q.limit(limit).all()

    # ── Internal helpers ─────────────────────────────────────────

    @staticmethod
    def _normalize_index_component(item: dict) -> dict:
        """兼容旧 index_component 入参并补齐新快照字段"""
        normalized = dict(item)
        index_symbol = str(normalized.get("index_symbol") or normalized.get("index_id") or "")
        provider_code = str(normalized.get("provider_code") or normalized.get("source") or "unknown")
        normalized.setdefault("index_id", f"{provider_code}:{index_symbol}")
        normalized.setdefault("index_symbol", index_symbol)
        normalized.setdefault("provider_code", provider_code)
        normalized.setdefault("trade_date", normalized.get("as_of"))
        normalized.setdefault("weight_pct", normalized.get("weight"))
        normalized.setdefault("weight", normalized.get("weight_pct"))
        normalized.setdefault("source_scope", "full")
        normalized.setdefault("raw_payload", {})
        return normalized

    @staticmethod
    def _coerce_datetime(value: str | date | datetime) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        return datetime.fromisoformat(str(value))

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
