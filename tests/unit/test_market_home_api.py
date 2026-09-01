from __future__ import annotations

import json
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes.market_home import (
    _format_market_home_sse_event,
    get_market_home_service,
)
from core.contracts.market_home import (
    MarketHomeEnvelope,
    MarketHomeInvalidationEvent,
    MarketHomeSection,
    MarketHomeSectionKey,
    MarketHomeSnapshot,
    SectionStatus,
    TradingStatus,
)
from core.contracts.platform_shared import FreshnessStatus, SourceRef, SourceTier
from services.market_home_service import SnapshotConflictError, SnapshotNotFoundError

NOW = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
SOURCE = SourceRef(
    source_id="api-test",
    name="API test",
    tier=SourceTier.OFFICIAL,
    content_hash="sha256:api-test",
)


def _envelope() -> MarketHomeEnvelope:
    return MarketHomeEnvelope(
        trading_day=date(2026, 9, 1),
        trading_status=TradingStatus.OPEN,
        sections=[
            MarketHomeSection(
                section_key=key,
                status=SectionStatus.READY,
                payload={"section": key.value},
                as_of=NOW,
                observed_at=NOW,
                available_at=NOW,
                source_refs=[SOURCE],
                freshness_status=FreshnessStatus.FRESH,
                quality_flags=[],
            )
            for key in MarketHomeSectionKey
        ],
    )


def _snapshots() -> list[MarketHomeSnapshot]:
    return [
        MarketHomeSnapshot(
            snapshot_id=f"snap-{key.value}",
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


class StubMarketHomeService:
    def __init__(self) -> None:
        self.raise_get: Exception | None = None
        self.raise_create: Exception | None = None
        self.last_event_id: str | None = None

    def get_live(self) -> MarketHomeEnvelope:
        return _envelope()

    def get_live_section(self, section_key: MarketHomeSectionKey) -> MarketHomeSection:
        return next(item for item in _envelope().sections if item.section_key == section_key)

    def get_snapshot(self, trading_day: date) -> list[MarketHomeSnapshot]:
        if self.raise_get:
            raise self.raise_get
        return _snapshots()

    def create_close_snapshot(self, trading_day: date) -> list[MarketHomeSnapshot]:
        if self.raise_create:
            raise self.raise_create
        return _snapshots()

    def list_invalidation_events(
        self, last_event_id: str | None
    ) -> list[MarketHomeInvalidationEvent]:
        self.last_event_id = last_event_id
        return [
            MarketHomeInvalidationEvent(
                event_id="event-2",
                section_key=MarketHomeSectionKey.A_SHARE_STATUS,
                as_of=NOW,
            )
        ]


def test_market_home_routes_expose_live_and_close_snapshots() -> None:
    service = StubMarketHomeService()
    app.dependency_overrides[get_market_home_service] = lambda: service
    try:
        client = TestClient(app)

        live = client.get("/api/market-home/live")
        drill_down = client.get("/api/market-home/drill-down/market_mainlines")
        historical = client.get("/api/market-home/snapshots/2026-09-01")
        created = client.post("/api/market-home/snapshots/2026-09-01")

        assert live.status_code == 200
        assert len(live.json()["sections"]) == 5
        assert drill_down.status_code == 200
        assert drill_down.json()["section_key"] == "market_mainlines"
        assert historical.status_code == 200
        assert created.status_code == 200
        assert len(created.json()) == 5
    finally:
        app.dependency_overrides.pop(get_market_home_service, None)


def test_market_home_routes_map_not_found_and_conflict_without_leaking_errors() -> None:
    service = StubMarketHomeService()
    app.dependency_overrides[get_market_home_service] = lambda: service
    try:
        client = TestClient(app)
        service.raise_get = SnapshotNotFoundError("secret database detail")
        missing = client.get("/api/market-home/snapshots/2026-09-01")
        service.raise_create = SnapshotConflictError("secret database detail")
        conflict = client.post("/api/market-home/snapshots/2026-09-01")

        assert missing.status_code == 404
        assert missing.json() == {"detail": "市场首页历史快照不存在。"}
        assert conflict.status_code == 409
        assert conflict.json() == {"detail": "市场首页收盘快照冲突。"}
    finally:
        app.dependency_overrides.pop(get_market_home_service, None)


def test_sse_payload_is_only_an_invalidation_reference_and_supports_resume() -> None:
    event = MarketHomeInvalidationEvent(
        event_id="event-2",
        section_key=MarketHomeSectionKey.IMPORTANT_EVENTS,
        as_of=NOW,
    )

    wire = _format_market_home_sse_event(event)

    assert wire.startswith("id: event-2\nevent: market_home.section_invalidated\ndata: ")
    data = json.loads(wire.split("data: ", 1)[1])
    assert data == {
        "event_id": "event-2",
        "section_key": "important_events",
        "as_of": "2026-09-01T08:00:00Z",
    }
    assert "payload" not in data
