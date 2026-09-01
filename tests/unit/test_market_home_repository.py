from __future__ import annotations

from datetime import UTC, date, datetime

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
    ThemeObservationDB,
)

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
                    unit="ratio",
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

        candidates = MarketHomeRepository(session).read_mainline_candidates(date(2026, 9, 1))

        assert len(candidates) == 1
        assert candidates[0].theme_key == "gold"
        assert candidates[0].label == "黄金"
        assert candidates[0].turnover_change == 1.4
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
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
