"""Fund intelligence persistence access."""

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    MetaData,
    String,
    Table,
    and_,
    delete,
    insert,
    select,
    update,
)

from core.contracts.funds import FundHolding, FundManagerProfile, FundMaster, FundNavPoint
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository

logger = get_logger(__name__)

fund_metadata = MetaData()

fund_master_table = Table(
    "fund_master",
    fund_metadata,
    Column("symbol", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("fund_type", String),
    Column("management_company", String),
    Column("inception_date", Date),
    Column("benchmark", String),
    Column("latest_size", Float),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

fund_nav_daily_table = Table(
    "fund_nav_daily",
    fund_metadata,
    Column("symbol", String, primary_key=True),
    Column("trading_day", Date, primary_key=True),
    Column("unit_nav", Float, nullable=False),
    Column("accumulated_nav", Float),
    Column("daily_return", Float),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

fund_holding_stock_table = Table(
    "fund_holding_stock",
    fund_metadata,
    Column("symbol", String, primary_key=True),
    Column("report_date", Date, primary_key=True),
    Column("stock_symbol", String, primary_key=True),
    Column("stock_name", String),
    Column("industry", String),
    Column("theme", String),
    Column("weight", Float, nullable=False),
    Column("market_value", Float),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

fund_manager_tenure_table = Table(
    "fund_manager_tenure",
    fund_metadata,
    Column("symbol", String, primary_key=True),
    Column("manager_id", String, primary_key=True),
    Column("manager_name", String, nullable=False),
    Column("institution_name", String),
    Column("tenure_start", Date),
    Column("tenure_end", Date),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FundRepository(BaseRepository):
    """Repository for fund master data, NAVs, holdings, and managers."""

    def ensure_schema(self) -> None:
        """Create fund intelligence tables for the configured database bind."""
        try:
            fund_metadata.create_all(bind=self.db.get_bind())
            logger.info("fund repository schema ensured")
        except Exception as exc:
            logger.error("failed to ensure fund schema", error=str(exc))
            raise

    def upsert_fund_master(self, fund: FundMaster) -> None:
        """Insert or update one fund master record."""
        payload = fund.model_dump()
        payload["updated_at"] = _utc_now()
        try:
            existing = self.db.execute(
                select(fund_master_table.c.symbol).where(fund_master_table.c.symbol == fund.symbol)
            ).first()
            if existing:
                self.db.execute(
                    update(fund_master_table)
                    .where(fund_master_table.c.symbol == fund.symbol)
                    .values(**payload)
                )
            else:
                self.db.execute(insert(fund_master_table).values(**payload))
            self.db.flush()
            logger.info("fund master upserted", symbol=fund.symbol)
        except Exception as exc:
            logger.error("failed to upsert fund master", symbol=fund.symbol, error=str(exc))
            raise

    def upsert_nav_points(self, nav_points: Iterable[FundNavPoint]) -> None:
        """Insert or update NAV points."""
        try:
            for nav in nav_points:
                payload = nav.model_dump()
                payload["updated_at"] = _utc_now()
                condition = and_(
                    fund_nav_daily_table.c.symbol == nav.symbol,
                    fund_nav_daily_table.c.trading_day == nav.trading_day,
                )
                existing = self.db.execute(
                    select(fund_nav_daily_table.c.symbol).where(condition)
                ).first()
                if existing:
                    self.db.execute(update(fund_nav_daily_table).where(condition).values(**payload))
                else:
                    self.db.execute(insert(fund_nav_daily_table).values(**payload))
            self.db.flush()
            logger.info("fund nav points upserted")
        except Exception as exc:
            logger.error("failed to upsert fund nav points", error=str(exc))
            raise

    def upsert_holdings(self, holdings: Iterable[FundHolding]) -> None:
        """Replace disclosed holdings for each fund/report-date pair in the input."""
        holdings_list = list(holdings)
        grouped: dict[tuple[str, date], list[FundHolding]] = defaultdict(list)
        for holding in holdings_list:
            grouped[(holding.symbol, holding.report_date)].append(holding)

        try:
            for (symbol, report_date), group in grouped.items():
                self.db.execute(
                    delete(fund_holding_stock_table).where(
                        and_(
                            fund_holding_stock_table.c.symbol == symbol,
                            fund_holding_stock_table.c.report_date == report_date,
                        )
                    )
                )
                for holding in group:
                    payload = holding.model_dump()
                    payload["updated_at"] = _utc_now()
                    self.db.execute(insert(fund_holding_stock_table).values(**payload))
            self.db.flush()
            logger.info("fund holdings upserted", count=len(holdings_list))
        except Exception as exc:
            logger.error("failed to upsert fund holdings", error=str(exc))
            raise

    def upsert_manager_tenures(self, symbol: str, managers: Iterable[FundManagerProfile]) -> None:
        """Replace manager tenures for one fund."""
        managers_list = list(managers)
        try:
            self.db.execute(
                delete(fund_manager_tenure_table).where(
                    fund_manager_tenure_table.c.symbol == symbol
                )
            )
            for manager in managers_list:
                payload = manager.model_dump()
                payload["symbol"] = symbol
                payload["updated_at"] = _utc_now()
                self.db.execute(insert(fund_manager_tenure_table).values(**payload))
            self.db.flush()
            logger.info("fund manager tenures upserted", symbol=symbol, count=len(managers_list))
        except Exception as exc:
            logger.error("failed to upsert fund manager tenures", symbol=symbol, error=str(exc))
            raise

    def get_fund_master(self, symbol: str) -> Optional[FundMaster]:
        """Return one fund master record."""
        try:
            row = (
                self.db.execute(
                    select(fund_master_table).where(fund_master_table.c.symbol == symbol)
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            return FundMaster(**{key: row[key] for key in FundMaster.model_fields})
        except Exception as exc:
            logger.error("failed to get fund master", symbol=symbol, error=str(exc))
            raise

    def get_nav_history(self, symbol: str) -> list[FundNavPoint]:
        """Return NAV history ordered by trading day."""
        try:
            rows = (
                self.db.execute(
                    select(fund_nav_daily_table)
                    .where(fund_nav_daily_table.c.symbol == symbol)
                    .order_by(fund_nav_daily_table.c.trading_day.asc())
                )
                .mappings()
                .all()
            )
            return [
                FundNavPoint(**{key: row[key] for key in FundNavPoint.model_fields}) for row in rows
            ]
        except Exception as exc:
            logger.error("failed to get nav history", symbol=symbol, error=str(exc))
            raise

    def get_latest_holdings(self, symbol: str) -> list[FundHolding]:
        """Return holdings for the latest report date."""
        try:
            latest_report = self.db.execute(
                select(fund_holding_stock_table.c.report_date)
                .where(fund_holding_stock_table.c.symbol == symbol)
                .order_by(fund_holding_stock_table.c.report_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest_report is None:
                return []
            rows = (
                self.db.execute(
                    select(fund_holding_stock_table)
                    .where(
                        and_(
                            fund_holding_stock_table.c.symbol == symbol,
                            fund_holding_stock_table.c.report_date == latest_report,
                        )
                    )
                    .order_by(fund_holding_stock_table.c.weight.desc())
                )
                .mappings()
                .all()
            )
            return [
                FundHolding(**{key: row[key] for key in FundHolding.model_fields}) for row in rows
            ]
        except Exception as exc:
            logger.error("failed to get latest holdings", symbol=symbol, error=str(exc))
            raise

    def get_manager_profiles(self, symbol: str) -> list[FundManagerProfile]:
        """Return manager profiles for one fund."""
        try:
            rows = (
                self.db.execute(
                    select(fund_manager_tenure_table)
                    .where(fund_manager_tenure_table.c.symbol == symbol)
                    .order_by(fund_manager_tenure_table.c.tenure_start.desc())
                )
                .mappings()
                .all()
            )
            return [
                FundManagerProfile(**{key: row[key] for key in FundManagerProfile.model_fields})
                for row in rows
            ]
        except Exception as exc:
            logger.error("failed to get manager profiles", symbol=symbol, error=str(exc))
            raise
