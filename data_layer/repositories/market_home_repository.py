"""Persistence and facts-only read projection for the market home module."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.contracts.market_home import (
    MainlineCandidate,
    MainlineCandidateBatch,
    MarketHomeInvalidationEvent,
    MarketHomeSection,
    MarketHomeSectionKey,
    MarketHomeSnapshot,
    SectionStatus,
)
from core.contracts.platform_shared import (
    FreshnessStatus,
    ScheduledJob,
    ScheduledJobStatus,
    SourceRef,
    SourceTier,
)
from core.observability import get_logger
from data_layer.repositories.models import (
    DocumentEventV1DB,
    DocumentV1DB,
    DomainEventDB,
    MarketHomeSnapshotDB,
    ScheduledJobDB,
    StockMasterDB,
    StockQuoteSnapshotDB,
    ThemeObservationDB,
)

logger = get_logger(__name__)
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
MAINLINE_REQUIRED_UNITS: dict[str, set[str]] = {
    "return": {"pct", "percent"},
    "turnover_vs_20d_median": {"ratio", "x"},
    "breadth": {"ratio"},
    "verified_event_density": {"ratio", "events_per_asset"},
}


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
        try:
            with self.db.begin_nested():
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
                            source_refs=[
                                item.model_dump(mode="json") for item in snapshot.source_refs
                            ],
                            freshness_status=snapshot.freshness_status.value,
                            quality_flags=snapshot.quality_flags,
                            payload=snapshot.payload,
                            input_fact_refs=snapshot.input_fact_refs,
                        )
                    )
                self.db.flush()
        except IntegrityError:
            existing = self.get_close_snapshots(snapshots[0].trading_day)
            if len(existing) == len(MarketHomeSectionKey):
                logger.info(
                    "market home close snapshot won by concurrent writer",
                    trading_day=snapshots[0].trading_day.isoformat(),
                )
                return existing
            raise
        return snapshots

    def read_mainline_candidates(
        self, trading_day: date, *, as_of: datetime
    ) -> MainlineCandidateBatch:
        start, end = self._utc_day_bounds(trading_day)
        rows = (
            self.db.query(ThemeObservationDB)
            .filter(
                ThemeObservationDB.dataset_key == "market_home_mainline",
                ThemeObservationDB.as_of >= start,
                ThemeObservationDB.as_of < end,
                ThemeObservationDB.as_of <= as_of,
            )
            .order_by(ThemeObservationDB.as_of.desc(), ThemeObservationDB.observation_id.asc())
            .all()
        )
        if not rows:
            raise LookupError("no mainline facts")
        required = set(MAINLINE_REQUIRED_UNITS)
        grouped: dict[str, list[ThemeObservationDB]] = {}
        for row in rows:
            if row.metric_key not in required:
                continue
            grouped.setdefault(row.subject_ref, []).append(row)
        candidates: list[MainlineCandidate] = []
        missing_components: list[str] = []
        selected_rows: list[ThemeObservationDB] = []
        for theme_key in sorted(grouped):
            theme_rows = grouped[theme_key]
            watermark = max(_aware(row.as_of) for row in theme_rows)
            by_metric: dict[str, ThemeObservationDB] = {}
            for row in theme_rows:
                by_metric.setdefault(row.metric_key, row)
            valid: dict[str, ThemeObservationDB] = {}
            for metric in sorted(required):
                row = by_metric.get(metric)
                reason: str | None = None
                if row is None:
                    reason = "missing"
                elif _aware(row.as_of) != watermark:
                    reason = "watermark_conflict"
                elif _aware(row.available_at) > as_of:
                    reason = "future_available_at"
                elif row.freshness_status != FreshnessStatus.FRESH.value:
                    reason = f"freshness:{row.freshness_status}"
                elif row.quality_flags:
                    reason = "quality_flags"
                elif row.value is None:
                    reason = "missing_value"
                elif row.unit not in MAINLINE_REQUIRED_UNITS[metric]:
                    reason = "unit_mismatch"
                if reason:
                    missing_components.append(f"{theme_key}:{metric}:{reason}")
                else:
                    valid[metric] = row
            if set(valid) != required:
                logger.info(
                    "market mainline candidate rejected by quality gate",
                    theme_key=theme_key,
                    watermark=watermark.isoformat(),
                    missing_components=[
                        item for item in missing_components if item.startswith(f"{theme_key}:")
                    ],
                )
                continue
            try:
                candidates.append(
                    MainlineCandidate(
                        theme_key=theme_key,
                        label=str(valid["return"].payload.get("label") or theme_key),
                        return_value=float(valid["return"].value),
                        turnover_change=float(valid["turnover_vs_20d_median"].value),
                        breadth=float(valid["breadth"].value),
                        verified_event_density=float(valid["verified_event_density"].value),
                    )
                )
                selected_rows.extend(valid.values())
            except (TypeError, ValueError):
                missing_components.append(f"{theme_key}:numeric_value:invalid")
                logger.warning(
                    "market mainline candidate quarantined for non-numeric facts",
                    theme_key=theme_key,
                )
        provenance_rows = selected_rows or rows
        sources = self._observation_sources(provenance_rows)
        return MainlineCandidateBatch(
            candidates=candidates,
            missing_components=missing_components,
            as_of=max(_aware(row.as_of) for row in provenance_rows),
            observed_at=max(_aware(row.observed_at) for row in provenance_rows),
            available_at=max(_aware(row.available_at) for row in provenance_rows),
            source_refs=sources,
            freshness_status=FreshnessStatus.FRESH,
            quality_flags=["mainline_components_incomplete"] if missing_components else [],
        )

    def read_live_section(
        self,
        section_key: MarketHomeSectionKey,
        trading_day: date,
        *,
        as_of: datetime,
    ) -> MarketHomeSection:
        if section_key == MarketHomeSectionKey.GLOBAL_CONTEXT:
            return self._read_observation_section(
                section_key, "market_home_global", trading_day, as_of=as_of
            )
        if section_key == MarketHomeSectionKey.MARKET_MAINLINES:
            return self._read_observation_section(
                section_key, "market_home_mainline", trading_day, as_of=as_of
            )
        if section_key == MarketHomeSectionKey.A_SHARE_STATUS:
            return self._read_a_share_status(section_key, as_of=as_of)
        if section_key == MarketHomeSectionKey.ASSET_MOVES:
            return self._read_asset_moves(section_key, as_of=as_of)
        if section_key == MarketHomeSectionKey.IMPORTANT_EVENTS:
            return self._read_important_events(section_key, trading_day, as_of=as_of)
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
                    DomainEventDB.created_at > anchor.created_at,
                    and_(
                        DomainEventDB.created_at == anchor.created_at,
                        DomainEventDB.event_id > anchor.event_id,
                    ),
                )
            )
        if last_event_id:
            rows = (
                query.order_by(DomainEventDB.created_at.asc(), DomainEventDB.event_id.asc())
                .limit(limit)
                .all()
            )
        else:
            rows = list(
                reversed(
                    query.order_by(DomainEventDB.created_at.desc(), DomainEventDB.event_id.desc())
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

    def record_invalidation(
        self,
        section_key: MarketHomeSectionKey,
        *,
        as_of: datetime,
        idempotency_key: str,
    ) -> MarketHomeInvalidationEvent:
        """Persist one facts-update outbox event before SSE delivery."""

        durable_key = f"market-home:{section_key.value}:{idempotency_key}"
        existing = self.db.query(DomainEventDB).filter_by(idempotency_key=durable_key).one_or_none()
        if existing is not None:
            return self._to_invalidation_event(existing)
        aggregate_id = section_key.value
        sequence = (
            self.db.query(func.max(DomainEventDB.sequence))
            .filter_by(aggregate_type="market_home", aggregate_id=aggregate_id)
            .scalar()
            or 0
        ) + 1
        event_id = str(uuid5(NAMESPACE_URL, durable_key))
        try:
            with self.db.begin_nested():
                self.db.add(
                    DomainEventDB(
                        event_id=event_id,
                        event_type="market_home.section_invalidated",
                        aggregate_type="market_home",
                        aggregate_id=aggregate_id,
                        sequence=sequence,
                        occurred_at=as_of,
                        payload_ref=f"market-home:{aggregate_id}",
                        payload={"section_key": aggregate_id, "as_of": as_of.isoformat()},
                        idempotency_key=durable_key,
                    )
                )
                self.db.flush()
        except IntegrityError:
            existing = (
                self.db.query(DomainEventDB).filter_by(idempotency_key=durable_key).one_or_none()
            )
            if existing is None:
                raise
            return self._to_invalidation_event(existing)
        logger.info(
            "market home invalidation persisted",
            event_id=event_id,
            section_key=aggregate_id,
            sequence=sequence,
        )
        return MarketHomeInvalidationEvent(event_id=event_id, section_key=section_key, as_of=as_of)

    def ensure_close_snapshot_job(self, trading_day: date) -> ScheduledJob:
        """Register the durable single-flight close snapshot job idempotently."""

        durable_key = f"market-home-close:{trading_day.isoformat()}"
        existing = (
            self.db.query(ScheduledJobDB)
            .filter_by(owner="market_home", idempotency_key=durable_key)
            .one_or_none()
        )
        if existing is not None:
            return self._to_scheduled_job(existing)
        scheduled_local = datetime.combine(trading_day, time(15, 5), tzinfo=SHANGHAI_TZ)
        row = ScheduledJobDB(
            job_id=str(uuid5(NAMESPACE_URL, durable_key)),
            owner="market_home",
            job_type="market_home.close_snapshot",
            idempotency_key=durable_key,
            status=ScheduledJobStatus.IDLE.value,
            scheduled_for=scheduled_local.astimezone(UTC),
            allow_concurrent=False,
            coalesce_policy="latest",
            payload={"trading_day": trading_day.isoformat()},
        )
        try:
            with self.db.begin_nested():
                self.db.add(row)
                self.db.flush()
        except IntegrityError:
            existing = (
                self.db.query(ScheduledJobDB)
                .filter_by(owner="market_home", idempotency_key=durable_key)
                .one()
            )
            return self._to_scheduled_job(existing)
        logger.info(
            "market home close snapshot job registered",
            job_id=row.job_id,
            trading_day=trading_day.isoformat(),
        )
        return self._to_scheduled_job(row)

    def _read_observation_section(
        self,
        section_key: MarketHomeSectionKey,
        dataset_key: str,
        trading_day: date,
        *,
        as_of: datetime,
    ) -> MarketHomeSection:
        start, end = self._utc_day_bounds(trading_day)
        rows = (
            self.db.query(ThemeObservationDB)
            .filter(
                ThemeObservationDB.dataset_key == dataset_key,
                ThemeObservationDB.as_of >= start,
                ThemeObservationDB.as_of < end,
                ThemeObservationDB.as_of <= as_of,
                ThemeObservationDB.available_at <= as_of,
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

    def _read_a_share_status(
        self, section_key: MarketHomeSectionKey, *, as_of: datetime
    ) -> MarketHomeSection:
        rows, universe_size = self._latest_quote_rows(as_of)
        changes = [_number(row.change_pct) for row in rows if row.change_pct is not None]
        if not changes:
            raise LookupError("no usable A-share quote changes")
        payload: dict[str, Any] = {
            "quote_count": len(changes),
            "rising_count": sum(value > 0 for value in changes if value is not None),
            "falling_count": sum(value < 0 for value in changes if value is not None),
            "unchanged_count": sum(value == 0 for value in changes if value is not None),
        }
        self._add_quote_watermark(payload, rows, universe_size)
        amounts = [_number(row.amount) for row in rows if row.amount is not None]
        if amounts:
            payload["total_amount"] = sum(value for value in amounts if value is not None)
            payload["amount_unit"] = "CNY"
        return self._quote_section(section_key, rows, payload)

    def _read_asset_moves(
        self, section_key: MarketHomeSectionKey, *, as_of: datetime
    ) -> MarketHomeSection:
        rows, universe_size = self._latest_quote_rows(as_of)
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
        self._add_quote_watermark(payload, rows, universe_size)
        return self._quote_section(section_key, rows, payload)

    def _read_important_events(
        self,
        section_key: MarketHomeSectionKey,
        trading_day: date,
        *,
        as_of: datetime,
    ) -> MarketHomeSection:
        start, end = self._utc_day_bounds(trading_day)
        rows = (
            self.db.query(DocumentEventV1DB)
            .filter(
                func.coalesce(DocumentEventV1DB.event_time, DocumentEventV1DB.created_at) >= start,
                func.coalesce(DocumentEventV1DB.event_time, DocumentEventV1DB.created_at) < end,
                DocumentEventV1DB.created_at <= as_of,
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
        documents = {
            row.doc_id: row
            for row in self.db.query(DocumentV1DB)
            .filter(DocumentV1DB.doc_id.in_([event.doc_id for event in rows]))
            .all()
        }
        source_refs: list[SourceRef] = []
        traceable_doc_ids: set[str] = set()
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
                traceable_doc_ids.add(doc_id)
            except ValueError:
                logger.warning(
                    "important event source reference quarantined",
                    doc_id=doc_id,
                )
        if not source_refs:
            raise LookupError("important events have no traceable document sources")
        traceable_rows = [row for row in rows if row.doc_id in traceable_doc_ids]
        timestamps = [_aware(row.event_time or row.created_at) for row in traceable_rows]
        return MarketHomeSection(
            section_key=section_key,
            status=SectionStatus.READY,
            payload={
                "events": [
                    {
                        "event_id": row.event_id,
                        "source_document_id": row.doc_id,
                        "title": documents[row.doc_id].title,
                        "source_name": documents[row.doc_id].source_name,
                        "source_url": documents[row.doc_id].source_url,
                        "content_hash": documents[row.doc_id].content_hash,
                        "document_created_at": _aware(documents[row.doc_id].created_at).isoformat(),
                    }
                    for row in traceable_rows
                ]
            },
            as_of=max(timestamps),
            observed_at=max(timestamps),
            available_at=max(_aware(row.created_at) for row in traceable_rows),
            source_refs=source_refs,
            freshness_status=FreshnessStatus.FRESH,
            quality_flags=[],
        )

    def _latest_quote_rows(self, as_of: datetime) -> tuple[list[StockQuoteSnapshotDB], int]:
        per_symbol = (
            self.db.query(
                StockQuoteSnapshotDB.symbol.label("symbol"),
                func.max(StockQuoteSnapshotDB.quote_time).label("quote_time"),
            )
            .filter(
                StockQuoteSnapshotDB.quote_time <= as_of,
                StockQuoteSnapshotDB.created_at <= as_of,
            )
            .group_by(StockQuoteSnapshotDB.symbol)
            .subquery()
        )
        rows = (
            self.db.query(StockQuoteSnapshotDB)
            .join(
                per_symbol,
                and_(
                    StockQuoteSnapshotDB.symbol == per_symbol.c.symbol,
                    StockQuoteSnapshotDB.quote_time == per_symbol.c.quote_time,
                ),
            )
            .order_by(StockQuoteSnapshotDB.symbol.asc(), StockQuoteSnapshotDB.id.desc())
            .all()
        )
        deduplicated = list({row.symbol: row for row in reversed(rows)}.values())
        if not deduplicated:
            raise LookupError("no quote snapshots")
        universe_size = self.db.query(func.count(StockMasterDB.symbol)).scalar() or 0
        if universe_size == 0:
            universe_size = len(deduplicated)
        return deduplicated, universe_size

    @staticmethod
    def _add_quote_watermark(
        payload: dict[str, Any], rows: list[StockQuoteSnapshotDB], universe_size: int
    ) -> None:
        watermarks = [_aware(row.quote_time) for row in rows]
        payload.update(
            {
                "universe_size": universe_size,
                "coverage_ratio": round(len({row.symbol for row in rows}) / universe_size, 6),
                "watermark_min": min(watermarks).isoformat(),
                "watermark_max": max(watermarks).isoformat(),
            }
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

    @staticmethod
    def _to_invalidation_event(row: DomainEventDB) -> MarketHomeInvalidationEvent:
        payload = row.payload or {}
        return MarketHomeInvalidationEvent(
            event_id=row.event_id,
            section_key=MarketHomeSectionKey(payload["section_key"]),
            as_of=datetime.fromisoformat(str(payload["as_of"])),
        )

    @staticmethod
    def _to_scheduled_job(row: ScheduledJobDB) -> ScheduledJob:
        return ScheduledJob(
            job_id=row.job_id,
            owner=row.owner,
            job_type=row.job_type,
            idempotency_key=row.idempotency_key,
            status=ScheduledJobStatus(row.status),
            scheduled_for=_aware(row.scheduled_for),
            allow_concurrent=row.allow_concurrent,
            coalesce_policy=row.coalesce_policy,
            lease_owner=row.lease_owner,
            lease_expires_at=(_aware(row.lease_expires_at) if row.lease_expires_at else None),
            payload=dict(row.payload or {}),
            attempt=row.attempt,
            fencing_token=row.attempt,
        )
