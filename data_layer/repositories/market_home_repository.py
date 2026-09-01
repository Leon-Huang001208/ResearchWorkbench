"""Persistence and facts-only read projection for the market home module."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.contracts.market_home import (
    MainlineCandidate,
    MarketHomeInvalidationEvent,
    MarketHomeSection,
    MarketHomeSectionKey,
    MarketHomeSnapshot,
    SectionStatus,
)
from core.contracts.platform_shared import FreshnessStatus, SourceRef, SourceTier
from core.observability import get_logger
from data_layer.repositories.models import (
    DocumentEventV1DB,
    DocumentV1DB,
    DomainEventDB,
    MarketHomeSnapshotDB,
    StockQuoteSnapshotDB,
    ThemeObservationDB,
)

logger = get_logger(__name__)
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _aware(value: datetime) -> datetime:
    """Restore UTC awareness lost by SQLite while retaining PostgreSQL offsets."""

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value


def _number(value: Decimal | float | None) -> float | None:
    return float(value) if value is not None else None


class MarketHomeRepository:
    """Own snapshots/events and query only existing authoritative fact tables."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_close_snapshots(self, trading_day: date) -> list[MarketHomeSnapshot]:
        rows = (
            self.db.query(MarketHomeSnapshotDB)
            .filter_by(trading_day=trading_day, snapshot_kind="close")
            .order_by(MarketHomeSnapshotDB.section_key.asc())
            .all()
        )
        by_key = {row.section_key: self._to_snapshot(row) for row in rows}
        return [by_key[key.value] for key in MarketHomeSectionKey if key.value in by_key]

    def insert_close_snapshots(
        self, snapshots: list[MarketHomeSnapshot]
    ) -> list[MarketHomeSnapshot]:
        for snapshot in snapshots:
            self.db.add(
                MarketHomeSnapshotDB(
                    snapshot_id=snapshot.snapshot_id,
                    trading_day=snapshot.trading_day,
                    snapshot_kind=snapshot.snapshot_kind,
                    section_key=snapshot.section_key.value,
                    formula_version=snapshot.formula_version,
                    as_of=snapshot.as_of,
                    observed_at=snapshot.observed_at,
                    available_at=snapshot.available_at,
                    source_refs=[item.model_dump(mode="json") for item in snapshot.source_refs],
                    freshness_status=snapshot.freshness_status.value,
                    quality_flags=snapshot.quality_flags,
                    payload=snapshot.payload,
                    input_fact_refs=snapshot.input_fact_refs,
                )
            )
        self.db.flush()
        return snapshots

    def read_mainline_candidates(self, trading_day: date) -> list[MainlineCandidate]:
        start, end = self._utc_day_bounds(trading_day)
        rows = (
            self.db.query(ThemeObservationDB)
            .filter(
                ThemeObservationDB.dataset_key == "market_home_mainline",
                ThemeObservationDB.as_of >= start,
                ThemeObservationDB.as_of < end,
            )
            .order_by(ThemeObservationDB.as_of.desc(), ThemeObservationDB.observation_id.asc())
            .all()
        )
        required = {
            "return",
            "turnover_vs_20d_median",
            "breadth",
            "verified_event_density",
        }
        grouped: dict[str, dict[str, ThemeObservationDB]] = {}
        for row in rows:
            if row.metric_key not in required or row.value is None:
                continue
            metrics = grouped.setdefault(row.subject_ref, {})
            metrics.setdefault(row.metric_key, row)
        candidates: list[MainlineCandidate] = []
        for theme_key, metrics in grouped.items():
            if set(metrics) != required:
                logger.info(
                    "market mainline candidate skipped for missing facts",
                    theme_key=theme_key,
                    missing_components=sorted(required - set(metrics)),
                )
                continue
            try:
                candidates.append(
                    MainlineCandidate(
                        theme_key=theme_key,
                        label=str(metrics["return"].payload.get("label") or theme_key),
                        return_value=float(metrics["return"].value),
                        turnover_change=float(metrics["turnover_vs_20d_median"].value),
                        breadth=float(metrics["breadth"].value),
                        verified_event_density=float(metrics["verified_event_density"].value),
                    )
                )
            except (TypeError, ValueError):
                logger.warning(
                    "market mainline candidate quarantined for non-numeric facts",
                    theme_key=theme_key,
                )
        return candidates

    def read_live_section(
        self, section_key: MarketHomeSectionKey, trading_day: date
    ) -> MarketHomeSection:
        if section_key == MarketHomeSectionKey.GLOBAL_CONTEXT:
            return self._read_observation_section(section_key, "market_home_global", trading_day)
        if section_key == MarketHomeSectionKey.MARKET_MAINLINES:
            return self._read_observation_section(section_key, "market_home_mainline", trading_day)
        if section_key == MarketHomeSectionKey.A_SHARE_STATUS:
            return self._read_a_share_status(section_key)
        if section_key == MarketHomeSectionKey.ASSET_MOVES:
            return self._read_asset_moves(section_key)
        if section_key == MarketHomeSectionKey.IMPORTANT_EVENTS:
            return self._read_important_events(section_key, trading_day)
        raise ValueError(f"unsupported market home section: {section_key.value}")

    def list_invalidation_events(
        self, last_event_id: str | None = None, *, limit: int = 100
    ) -> list[MarketHomeInvalidationEvent]:
        query = self.db.query(DomainEventDB).filter(
            DomainEventDB.event_type == "market_home.section_invalidated",
            DomainEventDB.aggregate_type == "market_home",
        )
        if last_event_id:
            anchor = self.db.get(DomainEventDB, last_event_id)
            if anchor is None or anchor.aggregate_type != "market_home":
                raise KeyError(last_event_id)
            query = query.filter(
                or_(
                    DomainEventDB.occurred_at > anchor.occurred_at,
                    and_(
                        DomainEventDB.occurred_at == anchor.occurred_at,
                        DomainEventDB.event_id > anchor.event_id,
                    ),
                )
            )
        if last_event_id:
            rows = (
                query.order_by(DomainEventDB.occurred_at.asc(), DomainEventDB.event_id.asc())
                .limit(limit)
                .all()
            )
        else:
            rows = list(
                reversed(
                    query.order_by(DomainEventDB.occurred_at.desc(), DomainEventDB.event_id.desc())
                    .limit(limit)
                    .all()
                )
            )
        events: list[MarketHomeInvalidationEvent] = []
        for row in rows:
            payload = row.payload or {}
            as_of_value = payload.get("as_of")
            if not as_of_value:
                logger.warning(
                    "market home invalidation skipped without as_of", event_id=row.event_id
                )
                continue
            try:
                as_of = datetime.fromisoformat(str(as_of_value))
                events.append(
                    MarketHomeInvalidationEvent(
                        event_id=row.event_id,
                        section_key=MarketHomeSectionKey(payload["section_key"]),
                        as_of=as_of,
                    )
                )
            except (KeyError, ValueError, TypeError):
                logger.warning("invalid market home invalidation skipped", event_id=row.event_id)
        return events

    def _read_observation_section(
        self, section_key: MarketHomeSectionKey, dataset_key: str, trading_day: date
    ) -> MarketHomeSection:
        start, end = self._utc_day_bounds(trading_day)
        rows = (
            self.db.query(ThemeObservationDB)
            .filter(
                ThemeObservationDB.dataset_key == dataset_key,
                ThemeObservationDB.as_of >= start,
                ThemeObservationDB.as_of < end,
            )
            .order_by(ThemeObservationDB.available_at.desc())
            .all()
        )
        if not rows:
            raise LookupError(f"no facts for {section_key.value}")
        latest_by_identity: dict[tuple[str, str], ThemeObservationDB] = {}
        for row in rows:
            latest_by_identity.setdefault((row.subject_ref, row.metric_key), row)
        selected = list(latest_by_identity.values())
        sources = self._observation_sources(selected)
        latest = max(selected, key=lambda row: _aware(row.available_at))
        return MarketHomeSection(
            section_key=section_key,
            status=SectionStatus.READY,
            payload={
                "observations": [
                    {
                        "subject_ref": row.subject_ref,
                        "metric_key": row.metric_key,
                        "value": row.value,
                        "unit": row.unit,
                        "missing_reason": row.missing_reason,
                    }
                    for row in selected
                ]
            },
            as_of=max(_aware(row.as_of) for row in selected),
            observed_at=max(_aware(row.observed_at) for row in selected),
            available_at=_aware(latest.available_at),
            source_refs=sources,
            freshness_status=FreshnessStatus(latest.freshness_status),
            quality_flags=sorted({flag for row in selected for flag in (row.quality_flags or [])}),
        )

    def _read_a_share_status(self, section_key: MarketHomeSectionKey) -> MarketHomeSection:
        rows = self._latest_quote_rows()
        changes = [_number(row.change_pct) for row in rows if row.change_pct is not None]
        if not changes:
            raise LookupError("no usable A-share quote changes")
        payload: dict[str, Any] = {
            "quote_count": len(changes),
            "rising_count": sum(value > 0 for value in changes if value is not None),
            "falling_count": sum(value < 0 for value in changes if value is not None),
            "unchanged_count": sum(value == 0 for value in changes if value is not None),
        }
        amounts = [_number(row.amount) for row in rows if row.amount is not None]
        if amounts:
            payload["total_amount"] = sum(value for value in amounts if value is not None)
            payload["amount_unit"] = "CNY"
        return self._quote_section(section_key, rows, payload)

    def _read_asset_moves(self, section_key: MarketHomeSectionKey) -> MarketHomeSection:
        rows = self._latest_quote_rows()
        usable = [row for row in rows if row.change_pct is not None]
        if not usable:
            raise LookupError("no usable asset moves")
        usable.sort(key=lambda row: (-abs(float(row.change_pct)), row.symbol))
        payload = {
            "moves": [
                {
                    "symbol": row.symbol,
                    "last_price": _number(row.last_price),
                    "change_pct": _number(row.change_pct),
                    "quote_time": _aware(row.quote_time).isoformat(),
                }
                for row in usable[:20]
            ]
        }
        return self._quote_section(section_key, usable, payload)

    def _read_important_events(
        self, section_key: MarketHomeSectionKey, trading_day: date
    ) -> MarketHomeSection:
        start, end = self._utc_day_bounds(trading_day)
        rows = (
            self.db.query(DocumentEventV1DB)
            .filter(
                func.coalesce(DocumentEventV1DB.event_time, DocumentEventV1DB.created_at) >= start,
                func.coalesce(DocumentEventV1DB.event_time, DocumentEventV1DB.created_at) < end,
            )
            .order_by(
                func.coalesce(DocumentEventV1DB.event_time, DocumentEventV1DB.created_at).desc(),
                DocumentEventV1DB.event_id.asc(),
            )
            .limit(20)
            .all()
        )
        if not rows:
            raise LookupError("no verified events")
        timestamps = [_aware(row.event_time or row.created_at) for row in rows]
        documents = {
            row.doc_id: row
            for row in self.db.query(DocumentV1DB)
            .filter(DocumentV1DB.doc_id.in_([event.doc_id for event in rows]))
            .all()
        }
        source_refs: list[SourceRef] = []
        for doc_id in sorted(documents):
            document = documents[doc_id]
            try:
                source_refs.append(
                    SourceRef(
                        source_id=f"document:{doc_id}",
                        name=document.source_name or document.source_type,
                        tier=SourceTier.PUBLIC,
                        content_hash=document.content_hash,
                        source_url=document.source_url,
                    )
                )
            except ValueError:
                logger.warning(
                    "important event source reference quarantined",
                    doc_id=doc_id,
                )
        if not source_refs:
            raise LookupError("important events have no traceable document sources")
        return MarketHomeSection(
            section_key=section_key,
            status=SectionStatus.READY,
            payload={
                "events": [
                    {
                        "event_id": row.event_id,
                        "event_type": row.event_type,
                        "event_time": _aware(row.event_time or row.created_at).isoformat(),
                        "summary": row.event_summary,
                        "subject_entity": row.subject_entity,
                        "impact_direction": row.impact_direction,
                        "confidence": _number(row.confidence),
                    }
                    for row in rows
                ]
            },
            as_of=max(timestamps),
            observed_at=max(timestamps),
            available_at=max(_aware(row.created_at) for row in rows),
            source_refs=source_refs,
            freshness_status=FreshnessStatus.FRESH,
            quality_flags=[],
        )

    def _latest_quote_rows(self) -> list[StockQuoteSnapshotDB]:
        latest = self.db.query(func.max(StockQuoteSnapshotDB.quote_time)).scalar()
        if latest is None:
            raise LookupError("no quote snapshots")
        return (
            self.db.query(StockQuoteSnapshotDB)
            .filter(StockQuoteSnapshotDB.quote_time == latest)
            .order_by(StockQuoteSnapshotDB.symbol.asc())
            .all()
        )

    def _quote_section(
        self,
        section_key: MarketHomeSectionKey,
        rows: list[StockQuoteSnapshotDB],
        payload: dict[str, Any],
    ) -> MarketHomeSection:
        quote_time = max(_aware(row.quote_time) for row in rows)
        created_at = max(_aware(row.created_at) for row in rows)
        source_names = sorted({row.source for row in rows})
        source_refs = [
            SourceRef(
                source_id=f"quote:{source}",
                name=source,
                tier=SourceTier.LICENSED,
                content_hash=f"quote-set:{source}:{quote_time.isoformat()}",
            )
            for source in source_names
        ]
        return MarketHomeSection(
            section_key=section_key,
            status=SectionStatus.READY,
            payload=payload,
            as_of=quote_time,
            observed_at=quote_time,
            available_at=created_at,
            source_refs=source_refs,
            freshness_status=FreshnessStatus.FRESH,
            quality_flags=[],
        )

    @staticmethod
    def _observation_sources(rows: list[ThemeObservationDB]) -> list[SourceRef]:
        unique: dict[str, SourceRef] = {}
        for row in rows:
            for item in row.source_refs or []:
                source = SourceRef.model_validate(item)
                unique.setdefault(source.source_id, source)
        if not unique:
            raise LookupError("observation facts have no source refs")
        return list(unique.values())

    @staticmethod
    def _utc_day_bounds(trading_day: date) -> tuple[datetime, datetime]:
        start_local = datetime.combine(trading_day, time.min, tzinfo=SHANGHAI_TZ)
        return start_local.astimezone(UTC), (start_local + timedelta(days=1)).astimezone(UTC)

    @staticmethod
    def _to_snapshot(row: MarketHomeSnapshotDB) -> MarketHomeSnapshot:
        return MarketHomeSnapshot(
            snapshot_id=row.snapshot_id,
            trading_day=row.trading_day,
            snapshot_kind=row.snapshot_kind,
            section_key=MarketHomeSectionKey(row.section_key),
            formula_version=row.formula_version,
            payload=dict(row.payload or {}),
            input_fact_refs=list(row.input_fact_refs or []),
            as_of=_aware(row.as_of),
            observed_at=_aware(row.observed_at),
            available_at=_aware(row.available_at),
            source_refs=[SourceRef.model_validate(item) for item in row.source_refs or []],
            freshness_status=FreshnessStatus(row.freshness_status),
            quality_flags=list(row.quality_flags or []),
        )
