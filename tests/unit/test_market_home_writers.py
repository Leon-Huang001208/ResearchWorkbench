"""Authoritative fact writers must persist market-home outbox rows atomically."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api.routes.market_home import get_market_home_service
from core.contracts import DocumentEventV1
from core.contracts.market_home import MarketHomeSectionKey
from data_layer.repositories.base import Base
from data_layer.repositories.documents_v1 import DocumentEventV1Repository
from data_layer.repositories.market_data_repository import MarketDataRepository
from data_layer.repositories.market_home_repository import MarketHomeRepository
from data_layer.repositories.models import DocumentEventV1DB, DomainEventDB
from services.market_home_service import MarketHomeService

NOW = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


def _session() -> tuple[object, Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)()


def _quote(symbol: str, *, seconds: int = 0) -> dict:
    quote_time = NOW.replace(second=seconds)
    return {
        "symbol": symbol,
        "quote_time": quote_time,
        "last_price": 10,
        "change_pct": 1,
        "source": "writer-test",
        "created_at": quote_time,
    }


def _document_event(event_id: str = "event-writer-1") -> DocumentEventV1:
    return DocumentEventV1(
        event_id=event_id,
        doc_id="doc-writer-1",
        event_type="announcement",
        event_time=NOW,
        event_summary="model enrichment must stay outside market home",
        confidence=0.9,
        created_at=NOW,
    )


def test_quote_writer_flushes_two_idempotent_invalidations_before_outer_commit() -> None:
    engine, session = _session()
    try:
        writer = MarketDataRepository(session)

        writer.insert_quote_snapshots([_quote("600001.SH"), _quote("600002.SH", seconds=1)])
        writer.insert_quote_snapshots([_quote("600001.SH"), _quote("600002.SH", seconds=1)])

        rows = session.query(DomainEventDB).order_by(DomainEventDB.created_at).all()
        assert session.in_transaction()
        assert len(rows) == 2
        assert {row.payload["section_key"] for row in rows} == {
            MarketHomeSectionKey.A_SHARE_STATUS.value,
            MarketHomeSectionKey.ASSET_MOVES.value,
        }
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_document_event_writer_has_outbox_row_before_its_legacy_commit() -> None:
    engine, session = _session()
    outbox_counts_at_commit: list[int] = []
    original_commit = session.commit

    def observed_commit() -> None:
        session.flush()
        outbox_counts_at_commit.append(session.query(DomainEventDB).count())
        original_commit()

    session.commit = observed_commit  # type: ignore[method-assign]
    try:
        saved = DocumentEventV1Repository(session).create(_document_event())

        assert saved.event_id == "event-writer-1"
        assert outbox_counts_at_commit == [1]
        assert session.query(DocumentEventV1DB).count() == 1
        assert session.query(DomainEventDB).count() == 1
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_actual_quote_and_document_writers_resume_over_http_last_event_id() -> None:
    engine, session = _session()
    try:
        MarketDataRepository(session).insert_quote_snapshots([_quote("600001.SH")])
        quote_events = MarketHomeRepository(session).list_invalidation_events()
        anchor = quote_events[-1]
        DocumentEventV1Repository(session).create(_document_event("event-writer-http"))
        service = MarketHomeService(MarketHomeRepository(session), now_provider=lambda: NOW)
        app.dependency_overrides[get_market_home_service] = lambda: service
        client = TestClient(app)

        response = client.get(
            "/api/market-home/events?replay_only=true",
            headers={"Last-Event-ID": anchor.event_id},
        )

        assert response.status_code == 200
        assert '"section_key":"important_events"' in response.text
        assert f"id: {anchor.event_id}" not in response.text
    finally:
        app.dependency_overrides.pop(get_market_home_service, None)
        session.close()
        Base.metadata.drop_all(bind=engine)
