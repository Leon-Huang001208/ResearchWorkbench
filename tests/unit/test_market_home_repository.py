from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.contracts.market_home import MarketHomeSectionKey, MarketHomeSnapshot
from core.contracts.platform_shared import FreshnessStatus, SourceRef, SourceTier
from data_layer.repositories.base import Base
from data_layer.repositories.market_home_repository import MarketHomeRepository
from data_layer.repositories.models import (
    DocumentEventV1DB,
    DocumentV1DB,
    DomainEventDB,
    ScheduledJobDB,
    StockMasterDB,
    StockQuoteSnapshotDB,
    ThemeObservationDB,
)
from services.market_home_service import MarketHomeService

NOW = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
SOURCE = SourceRef(
    source_id="repo-test",
    name="Repository test",
    tier=SourceTier.OFFICIAL,
    content_hash="sha256:repo-test",
)


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)()


def test_repository_round_trips_immutable_close_rows_without_commit() -> None:
    engine, session = _session()
    try:
        repo = MarketHomeRepository(session)
        rows = [
            MarketHomeSnapshot(
                snapshot_id=f"snapshot-{key.value}",
                trading_day=date(2026, 9, 1),
                snapshot_kind="close",
                section_key=key,
                formula_version="mainline-v1",
                payload={"section": key.value},
                input_fact_refs=[SOURCE.source_id],
                as_of=NOW,
                observed_at=NOW,
                available_at=NOW,
                source_refs=[SOURCE],
                freshness_status=FreshnessStatus.FRESH,
                quality_flags=[],
            )
            for key in MarketHomeSectionKey
        ]

        repo.insert_close_snapshots(rows)
        actual = repo.get_close_snapshots(date(2026, 9, 1))

        assert [item.section_key for item in actual] == list(MarketHomeSectionKey)
        assert session.in_transaction()
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_repository_builds_mainline_candidates_only_from_complete_facts() -> None:
    engine, session = _session()
    try:
        for pack_key, metric_key, value in [
            ("gold", "return", 2.5),
            ("gold", "turnover_vs_20d_median", 1.4),
            ("gold", "breadth", 0.7),
            ("gold", "verified_event_density", 0.2),
            ("solar", "return", -1.0),
        ]:
            session.add(
                ThemeObservationDB(
                    observation_id=f"{pack_key}-{metric_key}",
                    pack_key=pack_key,
                    dataset_key="market_home_mainline",
                    row_identity=f"{pack_key}-{metric_key}",
                    subject_ref=pack_key,
                    metric_key=metric_key,
                    value=value,
                    unit={
                        "return": "pct",
                        "turnover_vs_20d_median": "ratio",
                        "breadth": "ratio",
                        "verified_event_density": "events_per_asset",
                    }[metric_key],
                    as_of=NOW,
                    observed_at=NOW,
                    available_at=NOW,
                    source_refs=[SOURCE.model_dump(mode="json")],
                    freshness_status="fresh",
                    quality_flags=[],
                    source_hash=f"hash-{pack_key}-{metric_key}",
                    payload={"label": "黄金" if pack_key == "gold" else "光伏"},
                )
            )
        session.flush()

        batch = MarketHomeRepository(session).read_mainline_candidates(date(2026, 9, 1), as_of=NOW)

        assert len(batch.candidates) == 1
        assert batch.candidates[0].theme_key == "gold"
        assert batch.candidates[0].label == "黄金"
        assert batch.candidates[0].turnover_change == 1.4
        assert batch.missing_components == [
            "solar:breadth:missing",
            "solar:turnover_vs_20d_median:missing",
            "solar:verified_event_density:missing",
        ]
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_repository_resumes_durable_invalidation_events_after_last_event_id() -> None:
    engine, session = _session()
    try:
        for index, section_key in enumerate(
            [MarketHomeSectionKey.A_SHARE_STATUS, MarketHomeSectionKey.IMPORTANT_EVENTS],
            start=1,
        ):
            session.add(
                DomainEventDB(
                    event_id=f"event-{index}",
                    event_type="market_home.section_invalidated",
                    aggregate_type="market_home",
                    aggregate_id=section_key.value,
                    sequence=index,
                    occurred_at=NOW.replace(microsecond=index),
                    payload_ref=f"market-home:{section_key.value}",
                    payload={
                        "section_key": section_key.value,
                        "as_of": NOW.isoformat(),
                        "private_fact_payload": {"must_not_escape": True},
                    },
                    idempotency_key=f"event-{index}",
                )
            )
        session.flush()

        events = MarketHomeRepository(session).list_invalidation_events("event-1")

        assert len(events) == 1
        assert events[0].event_id == "event-2"
        assert events[0].section_key == MarketHomeSectionKey.IMPORTANT_EVENTS
        assert set(events[0].model_dump()) == {
            "event_id",
            "section_key",
            "as_of",
        }
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_repository_initial_sse_read_returns_latest_window_in_order() -> None:
    engine, session = _session()
    try:
        for index in range(1, 102):
            session.add(
                DomainEventDB(
                    event_id=f"event-{index:03d}",
                    event_type="market_home.section_invalidated",
                    aggregate_type="market_home",
                    aggregate_id=MarketHomeSectionKey.A_SHARE_STATUS.value,
                    sequence=index,
                    occurred_at=NOW.replace(microsecond=index),
                    payload_ref="market-home:a_share_status",
                    payload={
                        "section_key": MarketHomeSectionKey.A_SHARE_STATUS.value,
                        "as_of": NOW.isoformat(),
                    },
                    idempotency_key=f"latest-window-{index}",
                )
            )
        session.flush()

        events = MarketHomeRepository(session).list_invalidation_events(limit=100)

        assert len(events) == 100
        assert events[0].event_id == "event-002"
        assert events[-1].event_id == "event-101"
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_repository_important_events_keep_original_document_provenance() -> None:
    engine, session = _session()
    try:
        session.add(
            DocumentV1DB(
                doc_id="doc-1",
                doc_type="news",
                source_type="web",
                title="事件来源",
                content="source-backed event",
                doc_metadata={},
                source_metadata={},
                classification={},
                quality={},
                evidence_profile={},
                timeliness={},
                processing={},
                review={},
                extra={},
                source_name="Exchange Bulletin",
                source_url="https://example.com/bulletin/1",
                content_hash="sha256:document-1",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            DocumentEventV1DB(
                event_id="important-1",
                doc_id="doc-1",
                event_type="announcement",
                event_time=NOW,
                event_summary="可追溯事件",
                confidence=0.9,
                extra={},
                created_at=NOW,
            )
        )
        session.flush()

        section = MarketHomeRepository(session).read_live_section(
            MarketHomeSectionKey.IMPORTANT_EVENTS,
            date(2026, 9, 1),
            as_of=NOW,
        )

        assert section.source_refs == [
            SourceRef(
                source_id="document:doc-1",
                name="Exchange Bulletin",
                tier=SourceTier.PUBLIC,
                content_hash="sha256:document-1",
                source_url="https://example.com/bulletin/1",
            )
        ]
        event_payload = section.payload["events"][0]
        assert event_payload == {
            "event_id": "important-1",
            "source_document_id": "doc-1",
            "title": "事件来源",
            "source_name": "Exchange Bulletin",
            "source_url": "https://example.com/bulletin/1",
            "content_hash": "sha256:document-1",
            "document_created_at": NOW.isoformat(),
        }
        assert "可追溯事件" not in str(event_payload)
        assert not {"summary", "impact_direction", "confidence"} & set(event_payload)
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _add_mainline_observation(
    session,
    *,
    theme: str,
    metric: str,
    value: float,
    unit: str,
    as_of: datetime,
    available_at: datetime | None = None,
    freshness: str = "fresh",
    quality_flags: list[str] | None = None,
) -> None:
    session.add(
        ThemeObservationDB(
            observation_id=f"{theme}-{metric}-{as_of.isoformat()}",
            pack_key=theme,
            dataset_key="market_home_mainline",
            row_identity=f"{theme}-{metric}-{as_of.isoformat()}",
            subject_ref=theme,
            metric_key=metric,
            value=value,
            unit=unit,
            as_of=as_of,
            observed_at=as_of,
            available_at=available_at or as_of,
            source_refs=[SOURCE.model_dump(mode="json")],
            freshness_status=freshness,
            quality_flags=quality_flags or [],
            source_hash=f"hash-{theme}-{metric}-{as_of.isoformat()}",
            payload={"label": theme},
        )
    )


def test_mainline_batch_blocks_bad_freshness_units_flags_future_and_mixed_watermarks() -> None:
    engine, session = _session()
    try:
        metrics = {
            "return": (2.5, "pct"),
            "turnover_vs_20d_median": (1.4, "ratio"),
            "breadth": (0.7, "ratio"),
            "verified_event_density": (0.2, "events_per_asset"),
        }
        for metric, (value, unit) in metrics.items():
            _add_mainline_observation(
                session, theme="gold", metric=metric, value=value, unit=unit, as_of=NOW
            )
            _add_mainline_observation(
                session,
                theme="solar",
                metric=metric,
                value=value,
                unit=unit,
                as_of=NOW,
                freshness="quarantined",
            )
            _add_mainline_observation(
                session,
                theme="aero",
                metric=metric,
                value=value,
                unit="pct" if metric == "breadth" else unit,
                as_of=NOW,
            )
            _add_mainline_observation(
                session,
                theme="flagged",
                metric=metric,
                value=value,
                unit=unit,
                as_of=NOW,
                quality_flags=["source_conflict"] if metric == "return" else [],
            )
            _add_mainline_observation(
                session,
                theme="mixed",
                metric=metric,
                value=value,
                unit=unit,
                as_of=NOW if metric != "breadth" else NOW - timedelta(seconds=1),
            )
            _add_mainline_observation(
                session,
                theme="future",
                metric=metric,
                value=value,
                unit=unit,
                as_of=NOW,
                available_at=(
                    NOW + timedelta(seconds=1) if metric == "verified_event_density" else NOW
                ),
            )
        session.flush()

        batch = MarketHomeRepository(session).read_mainline_candidates(date(2026, 9, 1), as_of=NOW)

        assert [item.theme_key for item in batch.candidates] == ["gold"]
        missing = set(batch.missing_components)
        assert "solar:return:freshness:quarantined" in missing
        assert "aero:breadth:unit_mismatch" in missing
        assert "flagged:return:quality_flags" in missing
        assert "mixed:breadth:watermark_conflict" in missing
        assert "future:verified_event_density:future_available_at" in missing
        assert batch.as_of == NOW
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_quote_projection_uses_latest_per_symbol_at_or_before_as_of() -> None:
    engine, session = _session()
    try:
        for symbol in ("600001.SH", "600002.SH"):
            session.add(
                StockMasterDB(
                    symbol=symbol,
                    raw_code=symbol.split(".")[0],
                    name=symbol,
                    source="test",
                )
            )
        session.add_all(
            [
                StockQuoteSnapshotDB(
                    symbol="600001.SH",
                    quote_time=NOW,
                    last_price=10,
                    change_pct=1,
                    source="test",
                    created_at=NOW,
                ),
                StockQuoteSnapshotDB(
                    symbol="600002.SH",
                    quote_time=NOW + timedelta(seconds=1),
                    last_price=20,
                    change_pct=-1,
                    source="test",
                    created_at=NOW + timedelta(seconds=1),
                ),
            ]
        )
        session.flush()

        section = MarketHomeRepository(session).read_live_section(
            MarketHomeSectionKey.A_SHARE_STATUS,
            date(2026, 9, 1),
            as_of=NOW + timedelta(seconds=2),
        )

        assert section.payload["quote_count"] == 2
        assert section.payload["coverage_ratio"] == 1.0
        assert section.payload["watermark_min"] == NOW.isoformat()
        assert section.payload["watermark_max"] == (NOW + timedelta(seconds=1)).isoformat()
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_snapshot_unique_conflict_returns_existing_rows_without_breaking_transaction() -> None:
    engine, session = _session()
    try:
        repo = MarketHomeRepository(session)
        first = [
            MarketHomeSnapshot(
                snapshot_id=f"first-{key.value}",
                trading_day=date(2026, 9, 1),
                snapshot_kind="close",
                section_key=key,
                formula_version="mainline-v1",
                payload={},
                input_fact_refs=[SOURCE.source_id],
                as_of=NOW,
                observed_at=NOW,
                available_at=NOW,
                source_refs=[SOURCE],
                freshness_status=FreshnessStatus.FRESH,
                quality_flags=[],
            )
            for key in MarketHomeSectionKey
        ]
        repo.insert_close_snapshots(first)
        second = [
            item.model_copy(update={"snapshot_id": f"second-{item.section_key.value}"})
            for item in first
        ]

        actual = repo.insert_close_snapshots(second)

        assert [item.snapshot_id for item in actual] == [item.snapshot_id for item in first]
        assert session.in_transaction()
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_fact_update_writes_idempotent_outbox_and_registers_close_job() -> None:
    engine, session = _session()
    try:
        repo = MarketHomeRepository(session)
        service = MarketHomeService(repo, now_provider=lambda: NOW)

        first = service.record_fact_update(
            MarketHomeSectionKey.A_SHARE_STATUS,
            as_of=NOW,
            idempotency_key="quote-batch-1",
        )
        duplicate = service.record_fact_update(
            MarketHomeSectionKey.A_SHARE_STATUS,
            as_of=NOW,
            idempotency_key="quote-batch-1",
        )
        first_job = service.schedule_close_snapshot(date(2026, 9, 1))
        duplicate_job = service.schedule_close_snapshot(date(2026, 9, 1))

        assert first.event_id == duplicate.event_id
        assert session.query(DomainEventDB).count() == 1
        assert first_job.job_id == duplicate_job.job_id
        assert session.query(ScheduledJobDB).count() == 1
        assert first_job.job_type == "market_home.close_snapshot"
        assert first_job.allow_concurrent is False
        assert first_job.coalesce_policy == "latest"
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
