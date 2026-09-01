"""Persistence adapter for canonical assets, watchlists, alerts, and notifications.

The repository owns no asset facts.  It reads the existing stock/index/ETF/fund
tables and writes only the personal-observation tables introduced by migration
018.  Transaction commit/rollback remains owned by ``get_db``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, inspect, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from core.contracts.asset_observation import (
    AlertEvent,
    AlertEventStatus,
    AlertRule,
    AlertRuleStatus,
    Notification,
    NotificationStatus,
    Watchlist,
    WatchlistItem,
)
from core.contracts.platform_shared import AssetRef, FreshnessStatus
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.fund_repository import (
    fund_master_table,
    fund_nav_daily_table,
)
from data_layer.repositories.models import (
    AlertEventDB,
    AlertRuleDB,
    AssetIdentifierDB,
    AssetRegistryDB,
    ETFDailyMetricDB,
    ETFMasterDB,
    IndexETFLinkDB,
    IndexMasterDB,
    NotificationDB,
    StockDailyBarDB,
    StockMasterDB,
    StockQuoteSnapshotDB,
    WatchlistDB,
    WatchlistItemDB,
)

logger = get_logger(__name__)

_IDENTIFIER_SCHEME_PRIORITY = {
    "wind": 0,
    "official": 1,
    "exchange": 2,
    "symbol": 3,
    "provider": 4,
    "alias": 100,
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None, *, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return _aware(value, fallback=_utc_now()).isoformat()
    return value


def _source_ref(source: str, identity: str) -> dict[str, Any]:
    digest = hashlib.sha256(f"{source}:{identity}".encode()).hexdigest()
    return {
        "source_id": source or "database",
        "name": source or "Database",
        "tier": "licensed" if source.lower() in {"wind", "ifind"} else "public",
        "content_hash": f"sha256:{digest}",
    }


class AssetObservationRepository(BaseRepository):
    """Request-scoped repository; methods flush but never commit."""

    def get_asset_projection(
        self,
        asset_id: str,
        *,
        as_of: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Read one canonical asset and its existing type-specific facts."""

        point_in_time = _aware(as_of, fallback=_utc_now()) if as_of else _utc_now()
        try:
            registry = self.db.get(AssetRegistryDB, asset_id)
            if registry is None:
                return None
            identifier_records = self._current_identifiers(asset_id, point_in_time)
            identifiers = [row.value for row in identifier_records]
            projection = self._empty_projection(registry, identifiers, point_in_time)
            if registry.asset_type == "stock":
                self._load_stock_projection(projection, identifier_records, point_in_time)
            elif registry.asset_type == "index":
                self._load_index_projection(projection, asset_id, identifiers, point_in_time)
            elif registry.asset_type == "etf":
                self._load_etf_projection(projection, identifier_records, point_in_time)
            elif registry.asset_type == "active_fund":
                self._load_fund_projection(projection, identifier_records, point_in_time)
            else:
                projection["quality_flags"].append("unsupported_asset_type")
            return projection
        except SQLAlchemyError as exc:
            logger.error(
                "asset projection query failed",
                asset_id=asset_id,
                error_type=type(exc).__name__,
            )
            raise

    def list_peer_assets(
        self,
        *,
        asset_id: str,
        asset_type: str,
        dimension: str,
        value: str,
    ) -> list[AssetRef]:
        """Return canonical peers selected by an explicit fact dimension."""

        try:
            rows = self.db.scalars(
                select(AssetRegistryDB)
                .where(
                    and_(
                        AssetRegistryDB.asset_type == asset_type,
                        AssetRegistryDB.status == "active",
                    )
                )
                .order_by(AssetRegistryDB.asset_id)
            ).all()
            peers: list[AssetRef] = []
            for row in rows:
                projection = self.get_asset_projection(row.asset_id)
                if projection is None:
                    continue
                if self._peer_dimension_matches(projection["type_payload"], dimension, value):
                    peers.append(
                        AssetRef(
                            asset_id=row.asset_id,
                            asset_type=row.asset_type,
                            display_name=row.canonical_name,
                        )
                    )
            return peers
        except SQLAlchemyError as exc:
            logger.error(
                "peer asset query failed",
                asset_id=asset_id,
                asset_type=asset_type,
                error_type=type(exc).__name__,
            )
            raise

    def create_watchlist(self, *, profile_id: str, name: str, position: int = 0) -> WatchlistDB:
        now = _utc_now()
        row = WatchlistDB(
            watchlist_id=f"watchlist-{uuid4()}",
            profile_id=profile_id,
            name=name,
            position=position,
            created_at=now,
            updated_at=now,
        )
        try:
            self.db.add(row)
            self.db.flush()
            logger.info(
                "watchlist created",
                profile_id=profile_id,
                watchlist_id=row.watchlist_id,
            )
            return row
        except SQLAlchemyError as exc:
            logger.warning(
                "watchlist create failed",
                profile_id=profile_id,
                error_type=type(exc).__name__,
            )
            raise

    def list_watchlists(self, profile_id: str) -> list[WatchlistDB]:
        try:
            return list(
                self.db.scalars(
                    select(WatchlistDB)
                    .where(WatchlistDB.profile_id == profile_id)
                    .order_by(WatchlistDB.position, WatchlistDB.created_at)
                ).all()
            )
        except SQLAlchemyError as exc:
            logger.error(
                "watchlist query failed",
                profile_id=profile_id,
                error_type=type(exc).__name__,
            )
            raise

    def add_watchlist_item(
        self,
        *,
        watchlist_id: str,
        asset_id: str,
        position: int,
        note: str | None,
    ) -> WatchlistItemDB:
        """Idempotently add a canonical asset to a watchlist."""

        try:
            existing = self.db.scalar(
                select(WatchlistItemDB).where(
                    and_(
                        WatchlistItemDB.watchlist_id == watchlist_id,
                        WatchlistItemDB.asset_id == asset_id,
                    )
                )
            )
            if existing is not None:
                existing.position = position
                existing.note = note
                self.db.flush()
                return existing
            row = WatchlistItemDB(
                item_id=f"watchlist-item-{uuid4()}",
                watchlist_id=watchlist_id,
                asset_id=asset_id,
                position=position,
                note=note,
                created_at=_utc_now(),
            )
            self.db.add(row)
            self.db.flush()
            logger.info(
                "watchlist item added",
                watchlist_id=watchlist_id,
                asset_id=asset_id,
                item_id=row.item_id,
            )
            return row
        except SQLAlchemyError as exc:
            logger.warning(
                "watchlist item write failed",
                watchlist_id=watchlist_id,
                asset_id=asset_id,
                error_type=type(exc).__name__,
            )
            raise

    def get_watchlist(self, watchlist_id: str) -> WatchlistDB | None:
        return self.db.get(WatchlistDB, watchlist_id)

    def get_asset(self, asset_id: str) -> AssetRegistryDB | None:
        return self.db.get(AssetRegistryDB, asset_id)

    def create_alert_rule(self, rule: AlertRule, *, state: dict[str, Any]) -> AlertRuleDB:
        row = AlertRuleDB(
            rule_id=rule.rule_id,
            asset_id=rule.asset_id,
            metric_type=rule.metric_type,
            metric_key=rule.metric_key,
            operator=rule.operator.value,
            threshold=rule.threshold,
            unit=rule.unit,
            required_freshness=rule.required_freshness.value,
            cooldown_seconds=rule.cooldown_seconds,
            status=rule.status.value,
            state=state,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        try:
            self.db.add(row)
            self.db.flush()
            logger.info("alert rule created", rule_id=row.rule_id, asset_id=row.asset_id)
            return row
        except SQLAlchemyError as exc:
            logger.warning(
                "alert rule create failed",
                rule_id=row.rule_id,
                asset_id=row.asset_id,
                error_type=type(exc).__name__,
            )
            raise

    def list_alert_rules(self, asset_id: str | None = None) -> list[AlertRuleDB]:
        statement = select(AlertRuleDB).order_by(AlertRuleDB.created_at.desc())
        if asset_id is not None:
            statement = statement.where(AlertRuleDB.asset_id == asset_id)
        return list(self.db.scalars(statement).all())

    def get_alert_rule(self, rule_id: str) -> AlertRuleDB | None:
        return self.db.get(AlertRuleDB, rule_id)

    def update_alert_rule_status(
        self,
        rule_id: str,
        status: AlertRuleStatus,
    ) -> AlertRuleDB | None:
        row = self.db.get(AlertRuleDB, rule_id)
        if row is None:
            return None
        row.status = status.value
        row.updated_at = _utc_now()
        self.db.flush()
        return row

    def get_rule_state(self, rule_id: str) -> dict[str, Any]:
        row = self.db.get(AlertRuleDB, rule_id)
        return dict(row.state or {}) if row is not None else {}

    def lock_rule_state(self, rule_id: str) -> dict[str, Any]:
        """Lock and re-read mutable rule state for the caller's transaction."""

        try:
            row = self.db.scalar(
                select(AlertRuleDB).where(AlertRuleDB.rule_id == rule_id).with_for_update()
            )
            if row is None:
                raise LookupError("alert rule not found")
            self.db.refresh(row, attribute_names=["state"])
            return dict(row.state or {})
        except SQLAlchemyError as exc:
            logger.error(
                "alert rule state lock failed",
                rule_id=rule_id,
                error_type=type(exc).__name__,
            )
            raise

    def update_rule_state(self, rule_id: str, state: dict[str, Any]) -> None:
        row = self.db.get(AlertRuleDB, rule_id)
        if row is None:
            raise LookupError("alert rule not found")
        row.state = dict(state)
        row.updated_at = _utc_now()
        self.db.flush()

    def create_alert_event(self, **values: Any) -> AlertEventDB | None:
        """Create an edge in a savepoint, returning ``None`` on active-edge conflict."""

        row = AlertEventDB(**values)
        try:
            with self.db.begin_nested():
                self.db.add(row)
                self.db.flush()
            logger.info(
                "alert event persisted",
                event_id=row.event_id,
                rule_id=row.rule_id,
                observation_id=row.observation_id,
            )
            return row
        except IntegrityError as exc:
            active_event = self.get_active_alert_event(str(values.get("rule_id", "")))
            if active_event is None:
                logger.warning(
                    "alert event integrity failure was not an active-edge conflict",
                    rule_id=values.get("rule_id"),
                    observation_id=values.get("observation_id"),
                    error_type=type(exc).__name__,
                )
                raise
            logger.info(
                "alert event deduplicated by active edge constraint",
                rule_id=values.get("rule_id"),
                observation_id=values.get("observation_id"),
            )
            return None
        except SQLAlchemyError as exc:
            logger.warning(
                "alert event persistence failed",
                rule_id=values.get("rule_id"),
                observation_id=values.get("observation_id"),
                error_type=type(exc).__name__,
            )
            raise

    def get_active_alert_event(self, rule_id: str) -> AlertEventDB | None:
        return self.db.scalar(
            select(AlertEventDB)
            .where(
                and_(
                    AlertEventDB.rule_id == rule_id,
                    AlertEventDB.status.in_(
                        [
                            AlertEventStatus.OPEN.value,
                            AlertEventStatus.ACKNOWLEDGED.value,
                        ]
                    ),
                )
            )
            .order_by(AlertEventDB.triggered_at.desc())
            .limit(1)
        )

    def create_notification(self, **values: Any) -> NotificationDB:
        row = NotificationDB(**values)
        try:
            self.db.add(row)
            self.db.flush()
            logger.info(
                "in-app notification persisted",
                notification_id=row.notification_id,
                alert_event_id=row.alert_event_id,
                notification_channel="in_app",
            )
            return row
        except SQLAlchemyError as exc:
            logger.warning(
                "notification persistence failed",
                alert_event_id=values.get("alert_event_id"),
                error_type=type(exc).__name__,
            )
            raise

    def list_alert_events(self, rule_id: str | None = None) -> list[AlertEventDB]:
        statement = select(AlertEventDB).order_by(AlertEventDB.triggered_at.desc())
        if rule_id is not None:
            statement = statement.where(AlertEventDB.rule_id == rule_id)
        return list(self.db.scalars(statement).all())

    def acknowledge_alert_event(
        self,
        event_id: str,
        acknowledged_at: datetime,
    ) -> AlertEventDB | None:
        row = self.db.get(AlertEventDB, event_id)
        if row is None:
            return None
        if row.status != AlertEventStatus.RESOLVED.value:
            row.status = AlertEventStatus.ACKNOWLEDGED.value
            row.acknowledged_at = acknowledged_at
            self.db.flush()
        return row

    def resolve_alert_event(
        self,
        event_id: str,
        resolved_at: datetime,
    ) -> AlertEventDB | None:
        row = self.db.get(AlertEventDB, event_id)
        if row is None:
            return None
        row.status = AlertEventStatus.RESOLVED.value
        row.resolved_at = resolved_at
        self.db.flush()
        return row

    def list_notifications(
        self,
        profile_id: str,
        *,
        unread_only: bool = False,
        status: NotificationStatus | None = None,
    ) -> list[NotificationDB]:
        statement = (
            select(NotificationDB)
            .where(NotificationDB.profile_id == profile_id)
            .order_by(NotificationDB.created_at.desc())
        )
        if unread_only:
            statement = statement.where(NotificationDB.read_at.is_(None))
        if status is not None:
            statement = statement.where(NotificationDB.status == status.value)
        return list(self.db.scalars(statement).all())

    def mark_notification_delivery(
        self,
        notification_id: str,
        status: NotificationStatus,
        delivered_at: datetime,
    ) -> NotificationDB | None:
        row = self.db.get(NotificationDB, notification_id)
        if row is None:
            return None
        row.status = status.value
        row.delivered_at = delivered_at
        self.db.flush()
        return row

    @staticmethod
    def to_watchlist(row: WatchlistDB) -> Watchlist:
        return Watchlist(
            watchlist_id=row.watchlist_id,
            profile_id=row.profile_id,
            name=row.name,
            created_at=_aware(row.created_at, fallback=_utc_now()),
            updated_at=_aware(row.updated_at, fallback=_utc_now()),
        )

    @staticmethod
    def to_watchlist_item(row: WatchlistItemDB) -> WatchlistItem:
        return WatchlistItem(
            item_id=row.item_id,
            watchlist_id=row.watchlist_id,
            asset_id=row.asset_id,
            position=row.position,
            note=row.note,
            created_at=_aware(row.created_at, fallback=_utc_now()),
        )

    @staticmethod
    def to_alert_rule(row: AlertRuleDB) -> AlertRule:
        return AlertRule(
            rule_id=row.rule_id,
            asset_id=row.asset_id,
            metric_type=row.metric_type,
            metric_key=row.metric_key,
            operator=row.operator,
            threshold=row.threshold,
            unit=row.unit,
            required_freshness=row.required_freshness,
            cooldown_seconds=row.cooldown_seconds,
            status=row.status,
        )

    @staticmethod
    def to_alert_event(row: AlertEventDB) -> AlertEvent:
        return AlertEvent(
            event_id=row.event_id,
            rule_id=row.rule_id,
            observation_id=row.observation_id,
            dedupe_key=row.dedupe_key,
            status=row.status,
            triggered_at=_aware(row.triggered_at, fallback=_utc_now()),
            acknowledged_at=(
                _aware(row.acknowledged_at, fallback=_utc_now())
                if row.acknowledged_at is not None
                else None
            ),
            resolved_at=(
                _aware(row.resolved_at, fallback=_utc_now())
                if row.resolved_at is not None
                else None
            ),
        )

    @staticmethod
    def to_notification(row: NotificationDB) -> Notification:
        return Notification(
            notification_id=row.notification_id,
            alert_event_id=row.alert_event_id,
            profile_id=row.profile_id,
            title=row.title,
            body=row.body,
            status=row.status,
            created_at=_aware(row.created_at, fallback=_utc_now()),
            delivered_at=(
                _aware(row.delivered_at, fallback=_utc_now())
                if row.delivered_at is not None
                else None
            ),
        )

    def _current_identifiers(
        self,
        asset_id: str,
        as_of: datetime,
    ) -> list[AssetIdentifierDB]:
        rows = self.db.scalars(
            select(AssetIdentifierDB)
            .where(
                and_(
                    AssetIdentifierDB.asset_id == asset_id,
                    AssetIdentifierDB.valid_from <= as_of,
                    or_(
                        AssetIdentifierDB.valid_to.is_(None),
                        AssetIdentifierDB.valid_to > as_of,
                    ),
                )
            )
            .order_by(AssetIdentifierDB.scheme, AssetIdentifierDB.value)
        ).all()
        return list(rows)

    @staticmethod
    def _fact_candidate_values(identifiers: list[AssetIdentifierDB]) -> list[str]:
        """Prioritize explicit schemes while retaining all validated candidates."""

        ordered = sorted(
            identifiers,
            key=lambda row: (
                _IDENTIFIER_SCHEME_PRIORITY.get(row.scheme.lower(), 50),
                row.scheme,
                row.market or "",
                row.value,
            ),
        )
        return list(dict.fromkeys(row.value for row in ordered))

    @staticmethod
    def _empty_projection(
        registry: AssetRegistryDB,
        identifiers: list[str],
        point_in_time: datetime,
    ) -> dict[str, Any]:
        return {
            "asset": AssetRef(
                asset_id=registry.asset_id,
                asset_type=registry.asset_type,
                display_name=registry.canonical_name,
            ),
            "identifiers": identifiers,
            "market_data": {},
            "history": [],
            "events": [],
            "themes": [],
            "type_payload": {},
            "as_of": point_in_time,
            "observed_at": _aware(registry.updated_at, fallback=point_in_time),
            "available_at": _aware(registry.updated_at, fallback=point_in_time),
            "source_refs": [_source_ref("asset_registry", registry.asset_id)],
            "freshness_status": FreshnessStatus.UNAVAILABLE,
            "quality_flags": ["market_data_unavailable"],
        }

    def _load_stock_projection(
        self,
        projection: dict[str, Any],
        identifiers: list[AssetIdentifierDB],
        as_of: datetime,
    ) -> None:
        if not identifiers:
            projection["quality_flags"].append("identifier_unavailable")
            return
        symbol = next(
            (
                candidate
                for candidate in self._fact_candidate_values(identifiers)
                if self.db.get(StockMasterDB, candidate) is not None
                or self.db.scalar(
                    select(StockQuoteSnapshotDB.symbol)
                    .where(StockQuoteSnapshotDB.symbol == candidate)
                    .limit(1)
                )
                is not None
            ),
            None,
        )
        if symbol is None:
            projection["quality_flags"].append("identifier_fact_unmatched")
            return
        master = self.db.get(StockMasterDB, symbol)
        quote = self.db.scalar(
            select(StockQuoteSnapshotDB)
            .where(
                and_(
                    StockQuoteSnapshotDB.symbol == symbol,
                    StockQuoteSnapshotDB.quote_time <= as_of,
                )
            )
            .order_by(StockQuoteSnapshotDB.quote_time.desc())
            .limit(1)
        )
        bars: list[StockDailyBarDB] = []
        if inspect(self.db.get_bind()).has_table(StockDailyBarDB.__tablename__):
            bars = list(
                self.db.scalars(
                    select(StockDailyBarDB)
                    .where(
                        and_(
                            StockDailyBarDB.symbol == symbol,
                            StockDailyBarDB.trade_date <= as_of,
                        )
                    )
                    .order_by(StockDailyBarDB.trade_date.desc())
                    .limit(60)
                ).all()
            )
        if master is not None:
            projection["type_payload"] = {
                "exchange": master.exchange,
                "market": master.market,
                "industry_level1": master.industry_level1,
                "industry_level2": master.industry_level2,
                "industry_level3": master.industry_level3,
            }
        if quote is not None:
            observed = _aware(quote.quote_time, fallback=as_of)
            projection["market_data"] = {
                "last": _json_value(quote.last_price),
                "change_pct": _json_value(quote.change_pct),
                "volume": _json_value(quote.volume),
                "amount": _json_value(quote.amount),
                "turnover": _json_value(quote.turnover),
                "pe": _json_value(quote.pe),
                "pb": _json_value(quote.pb),
            }
            projection["observed_at"] = observed
            projection["available_at"] = _aware(quote.created_at, fallback=observed)
            projection["source_refs"] = [_source_ref(quote.source, f"{symbol}:{observed}")]
            projection["freshness_status"] = self._freshness(observed, as_of, timedelta(minutes=1))
            projection["quality_flags"] = []
        projection["history"] = [
            {
                "as_of": _aware(bar.trade_date, fallback=as_of).isoformat(),
                "open": _json_value(bar.open),
                "high": _json_value(bar.high),
                "low": _json_value(bar.low),
                "close": _json_value(bar.close),
                "volume": _json_value(bar.volume),
                "source": bar.source,
            }
            for bar in reversed(bars)
        ]

    def _load_index_projection(
        self,
        projection: dict[str, Any],
        asset_id: str,
        identifiers: list[str],
        as_of: datetime,
    ) -> None:
        master = self.db.scalar(
            select(IndexMasterDB).where(
                or_(
                    IndexMasterDB.index_id == asset_id,
                    IndexMasterDB.official_code.in_(identifiers or [""]),
                    IndexMasterDB.wind_code.in_(identifiers or [""]),
                )
            )
        )
        if master is None:
            return
        observed = _aware(master.updated_at, fallback=as_of)
        projection["type_payload"] = {
            "provider_code": master.provider_code,
            "category": master.category,
            "market": master.market,
            "currency": master.currency,
        }
        projection["observed_at"] = observed
        projection["available_at"] = observed
        projection["source_refs"] = [_source_ref("index_master", f"{master.index_id}:{observed}")]
        projection["quality_flags"] = ["index_quote_unavailable"]

    def _load_etf_projection(
        self,
        projection: dict[str, Any],
        identifiers: list[AssetIdentifierDB],
        as_of: datetime,
    ) -> None:
        if not identifiers:
            return
        symbol = next(
            (
                candidate
                for candidate in self._fact_candidate_values(identifiers)
                if self.db.get(ETFMasterDB, candidate) is not None
                or self.db.scalar(
                    select(ETFDailyMetricDB.etf_symbol)
                    .where(ETFDailyMetricDB.etf_symbol == candidate)
                    .limit(1)
                )
                is not None
            ),
            None,
        )
        if symbol is None:
            projection["quality_flags"].append("identifier_fact_unmatched")
            return
        master = self.db.get(ETFMasterDB, symbol)
        metric = self.db.scalar(
            select(ETFDailyMetricDB)
            .where(
                and_(
                    ETFDailyMetricDB.etf_symbol == symbol,
                    ETFDailyMetricDB.trade_date <= as_of,
                )
            )
            .order_by(ETFDailyMetricDB.trade_date.desc())
            .limit(1)
        )
        link = self.db.scalar(
            select(IndexETFLinkDB)
            .where(IndexETFLinkDB.etf_symbol == symbol)
            .order_by(IndexETFLinkDB.updated_at.desc())
            .limit(1)
        )
        if master is not None:
            projection["type_payload"] = {
                "exchange": master.exchange,
                "market": master.market,
                "tracking_index": link.index_id if link is not None else None,
                "theme": (master.raw_payload or {}).get("theme"),
            }
        if metric is not None:
            observed = _aware(metric.trade_date, fallback=as_of)
            projection["market_data"] = {
                "nav": _json_value(metric.nav),
                "close": _json_value(metric.close),
                "aum": _json_value(metric.aum),
                "net_flow_amount": _json_value(metric.net_flow_amount),
                "premium_discount_pct": _json_value(metric.premium_discount_pct),
            }
            projection["observed_at"] = observed
            projection["available_at"] = _aware(metric.created_at, fallback=observed)
            projection["source_refs"] = [_source_ref(metric.source, f"{symbol}:{observed}")]
            projection["freshness_status"] = self._freshness(observed, as_of, timedelta(days=2))
            projection["quality_flags"] = []

    def _load_fund_projection(
        self,
        projection: dict[str, Any],
        identifiers: list[AssetIdentifierDB],
        as_of: datetime,
    ) -> None:
        if not identifiers or not inspect(self.db.get_bind()).has_table(fund_master_table.name):
            return
        symbol = None
        master = None
        for candidate in self._fact_candidate_values(identifiers):
            candidate_master = (
                self.db.execute(
                    select(fund_master_table).where(fund_master_table.c.symbol == candidate)
                )
                .mappings()
                .first()
            )
            if candidate_master is not None:
                symbol = candidate
                master = candidate_master
                break
        if master is None:
            projection["quality_flags"].append("identifier_fact_unmatched")
            return
        projection["type_payload"] = {
            "fund_type": master["fund_type"],
            "benchmark": master["benchmark"],
            "management_company": master["management_company"],
        }
        if not inspect(self.db.get_bind()).has_table(fund_nav_daily_table.name):
            return
        nav = (
            self.db.execute(
                select(fund_nav_daily_table)
                .where(fund_nav_daily_table.c.symbol == symbol)
                .order_by(fund_nav_daily_table.c.trading_day.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if nav is None:
            return
        observed = datetime.combine(nav["trading_day"], datetime.min.time(), tzinfo=UTC)
        projection["market_data"] = {
            "unit_nav": nav["unit_nav"],
            "accumulated_nav": nav["accumulated_nav"],
            "daily_return": nav["daily_return"],
        }
        projection["observed_at"] = observed
        projection["available_at"] = _aware(nav["updated_at"], fallback=observed)
        projection["source_refs"] = [_source_ref("fund_nav_daily", f"{symbol}:{observed}")]
        projection["freshness_status"] = self._freshness(observed, as_of, timedelta(days=3))
        projection["quality_flags"] = []

    @staticmethod
    def _freshness(observed_at: datetime, as_of: datetime, sla: timedelta) -> FreshnessStatus:
        return FreshnessStatus.FRESH if as_of - observed_at <= sla else FreshnessStatus.STALE

    @staticmethod
    def _peer_dimension_matches(
        payload: dict[str, Any],
        dimension: str,
        value: str,
    ) -> bool:
        if dimension == "tracking_index_or_theme":
            return value in {payload.get("tracking_index"), payload.get("theme")}
        if dimension == "classification_and_benchmark":
            return value == f"{payload.get('fund_type')}|{payload.get('benchmark')}"
        return payload.get(dimension) == value
