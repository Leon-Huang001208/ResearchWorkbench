"""HTTP contract tests for the asset-observation vertical slice."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.contracts.asset_observation import (
    AlertEvent,
    AlertEventStatus,
    AlertOperator,
    AlertRule,
    AlertRuleStatus,
    Notification,
    PeerSet,
    Watchlist,
    WatchlistItem,
)
from core.contracts.platform_shared import AssetRef, FreshnessStatus, SourceRef

NOW = datetime(2026, 9, 1, 9, 30, tzinfo=UTC)
SOURCE = SourceRef(
    source_id="official",
    name="Official",
    tier="official",
    content_hash="sha256:api-test",
)


class FakeService:
    def __init__(self) -> None:
        self.status_updates: list[tuple[str, str]] = []
        self.notification_status = "pending"

    def get_asset_snapshot(self, asset_id: str):
        from core.contracts.asset_observation import AssetSnapshotEnvelope
        from services.asset_observation_service import AssetNotFoundError

        if asset_id == "missing":
            raise AssetNotFoundError(asset_id)
        asset_type = asset_id.split("-", 1)[0]
        return AssetSnapshotEnvelope(
            asset=AssetRef(asset_id=asset_id, asset_type=asset_type, display_name=asset_id),
            identifiers=[f"{asset_id}.CN"],
            market_data={"last": 1.0},
            history=[],
            events=[],
            themes=[],
            type_payload={},
            as_of=NOW,
            observed_at=NOW,
            available_at=NOW,
            source_refs=[SOURCE],
            freshness_status=FreshnessStatus.FRESH,
            quality_flags=[],
        )

    def get_peer_set(self, asset_id: str) -> PeerSet:
        return PeerSet(
            peer_set_id=f"peers:{asset_id}",
            asset_id=asset_id,
            rule="stock:sw_industry_level3",
            sample_size=1,
            asset_refs=[AssetRef(asset_id=asset_id, asset_type="stock")],
            as_of=NOW,
        )

    def create_watchlist(self, profile_id: str, name: str) -> Watchlist:
        from services.asset_observation_service import AssetObservationConflictError

        if name == "duplicate":
            raise AssetObservationConflictError("database constraint details")
        if name == "invalid":
            raise ValueError("invalid watchlist")
        return Watchlist(
            watchlist_id="watchlist-1",
            profile_id=profile_id,
            name=name,
            created_at=NOW,
            updated_at=NOW,
        )

    def list_watchlists(self, profile_id: str) -> list[Watchlist]:
        return [self.create_watchlist(profile_id, "核心观察")]

    def add_watchlist_item(
        self,
        watchlist_id: str,
        asset_id: str,
        position: int = 0,
        note: str | None = None,
    ) -> WatchlistItem:
        return WatchlistItem(
            item_id="item-1",
            watchlist_id=watchlist_id,
            asset_id=asset_id,
            position=position,
            note=note,
            created_at=NOW,
        )

    def create_alert_rule(self, **payload: Any) -> AlertRule:
        return AlertRule(rule_id="rule-1", **payload)

    def list_alert_rules(self, asset_id: str | None = None) -> list[AlertRule]:
        return []

    def evaluate_due_alerts(self, profile_id: str, evaluated_at: datetime | None = None) -> Any:
        from core.contracts.asset_observation import AlertBatchEvaluationSummary

        self.evaluation_request = (profile_id, evaluated_at)
        return AlertBatchEvaluationSummary(
            evaluated=4,
            triggered=1,
            deduplicated=1,
            skipped=1,
            failed=1,
        )

    def update_alert_rule_status(self, rule_id: str, status: AlertRuleStatus) -> AlertRule:
        self.status_updates.append((rule_id, status.value))
        return AlertRule(
            rule_id=rule_id,
            asset_id="stock-1",
            metric_type="price",
            metric_key="last",
            operator=AlertOperator.GT,
            threshold=100.0,
            unit="CNY/share",
            status=status,
        )

    def list_alert_events(self, rule_id: str | None = None) -> list[AlertEvent]:
        return [
            AlertEvent(
                event_id="event-1",
                rule_id=rule_id or "rule-1",
                observation_id="obs-1",
                dedupe_key="dedupe-1",
                status=AlertEventStatus.OPEN,
                triggered_at=NOW,
            )
        ]

    def acknowledge_alert_event(self, event_id: str) -> AlertEvent:
        return self._event(event_id, AlertEventStatus.ACKNOWLEDGED)

    def resolve_alert_event(self, event_id: str) -> AlertEvent:
        return self._event(event_id, AlertEventStatus.RESOLVED)

    def _event(self, event_id: str, status: AlertEventStatus) -> AlertEvent:
        return AlertEvent(
            event_id=event_id,
            rule_id="rule-1",
            observation_id="obs-1",
            dedupe_key="dedupe-1",
            status=status,
            triggered_at=NOW,
            acknowledged_at=NOW if status is AlertEventStatus.ACKNOWLEDGED else None,
            resolved_at=NOW if status is AlertEventStatus.RESOLVED else None,
        )

    def list_notifications(
        self,
        profile_id: str,
        unread_only: bool = False,
        status: str | None = None,
    ) -> list[Notification]:
        self.notification_filter = status
        return [
            Notification(
                notification_id="notification-1",
                alert_event_id="event-1",
                profile_id=profile_id,
                title="价格提醒",
                body="stock-1 已满足提醒条件",
                status=self.notification_status,
                created_at=NOW,
            )
        ]

    def mark_notification_delivery(
        self,
        notification_id: str,
        status: str,
        *,
        expected_status: str,
    ) -> Notification:
        from services.asset_observation_service import AssetObservationConflictError

        if self.notification_status != expected_status:
            raise AssetObservationConflictError("notification transition conflict")
        self.notification_status = status
        return Notification(
            notification_id=notification_id,
            alert_event_id="event-1",
            profile_id="local",
            title="价格提醒",
            body="stock-1 已满足提醒条件",
            status=status,
            created_at=NOW,
            delivered_at=NOW,
        )


@pytest.fixture()
def client_and_service():
    from app.api.routes.asset_observation import get_asset_observation_service, router

    app = FastAPI()
    service = FakeService()
    app.include_router(router)
    app.dependency_overrides[get_asset_observation_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False), service


@pytest.mark.parametrize("asset_type", ["stock", "index", "etf", "active_fund"])
def test_get_asset_supports_four_asset_types(client_and_service, asset_type: str):
    client, _ = client_and_service
    response = client.get(f"/api/asset-observation/assets/{asset_type}-1")

    assert response.status_code == 200
    assert response.json()["asset"]["asset_type"] == asset_type
    assert response.json()["source_refs"][0]["source_id"] == "official"


def test_asset_response_includes_transparent_peer_metadata(client_and_service):
    client, _ = client_and_service
    response = client.get("/api/asset-observation/assets/stock-1/peers")

    assert response.status_code == 200
    assert response.json()["rule"] == "stock:sw_industry_level3"
    assert response.json()["sample_size"] == 1


def test_missing_asset_maps_to_safe_404(client_and_service):
    client, _ = client_and_service
    response = client.get("/api/asset-observation/assets/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Asset not found"}


def test_watchlist_create_maps_invalid_and_conflict_without_leaking_internal_details(
    client_and_service,
):
    client, _ = client_and_service
    invalid = client.post(
        "/api/asset-observation/watchlists",
        json={"profile_id": "local", "name": "invalid"},
    )
    conflict = client.post(
        "/api/asset-observation/watchlists",
        json={"profile_id": "local", "name": "duplicate"},
    )

    assert invalid.status_code == 400
    assert invalid.json() == {"detail": "Invalid asset observation request"}
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "Asset observation conflict"}
    assert "constraint" not in conflict.text


def test_watchlists_and_items_use_canonical_asset_id(client_and_service):
    client, _ = client_and_service
    listed = client.get("/api/asset-observation/watchlists?profile_id=local")
    added = client.post(
        "/api/asset-observation/watchlists/watchlist-1/items",
        json={"asset_id": "stock-1", "position": 2, "note": "长期跟踪"},
    )

    assert listed.status_code == 200
    assert listed.json()[0]["profile_id"] == "local"
    assert added.status_code == 201
    assert added.json()["asset_id"] == "stock-1"


def test_alert_rule_status_and_event_lifecycle_routes(client_and_service):
    client, service = client_and_service
    created = client.post(
        "/api/asset-observation/alert-rules",
        json={
            "asset_id": "stock-1",
            "metric_type": "price",
            "metric_key": "last",
            "operator": "gt",
            "threshold": 100.0,
            "unit": "CNY/share",
            "cooldown_seconds": 60,
            "status": "active",
        },
    )
    paused = client.patch(
        "/api/asset-observation/alert-rules/rule-1/status",
        json={"status": "paused"},
    )
    acknowledged = client.post("/api/asset-observation/alert-events/event-1/acknowledge")
    resolved = client.post("/api/asset-observation/alert-events/event-1/resolve")

    assert created.status_code == 201
    assert paused.status_code == 200
    assert service.status_updates == [("rule-1", "paused")]
    assert acknowledged.json()["status"] == "acknowledged"
    assert resolved.json()["status"] == "resolved"


def test_notifications_expose_only_persisted_safe_payload_and_delivery_state(client_and_service):
    client, service = client_and_service
    listed = client.get("/api/asset-observation/notifications?profile_id=local&status=pending")
    delivered = client.patch(
        "/api/asset-observation/notifications/notification-1/delivery",
        json={
            "status": "desktop_permission_denied",
            "expected_status": "pending",
        },
    )
    conflict = client.patch(
        "/api/asset-observation/notifications/notification-1/delivery",
        json={"status": "desktop_failed", "expected_status": "pending"},
    )

    assert listed.status_code == 200
    assert listed.json()[0]["body"] == "stock-1 已满足提醒条件"
    assert service.notification_filter == "pending"
    assert delivered.status_code == 200
    assert delivered.json()["status"] == "desktop_permission_denied"
    assert conflict.status_code == 409


def test_evaluate_due_route_accepts_no_external_fact_payload(client_and_service):
    client, service = client_and_service
    response = client.post(
        "/api/asset-observation/alert-rules/evaluate-due",
        json={"profile_id": "local", "evaluated_at": NOW.isoformat()},
    )
    rejected = client.post(
        "/api/asset-observation/alert-rules/evaluate-due",
        json={"profile_id": "local", "observation": {"value": 999999}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "evaluated": 4,
        "triggered": 1,
        "deduplicated": 1,
        "skipped": 1,
        "failed": 1,
    }
    assert service.evaluation_request == ("local", NOW)
    assert rejected.status_code == 422


def test_main_app_registers_asset_observation_routes():
    from app.api.main import app as main_app
    from app.api.routes.asset_observation import get_asset_observation_service

    main_app.dependency_overrides[get_asset_observation_service] = FakeService
    try:
        response = TestClient(main_app).get("/api/asset-observation/assets/stock-1")
        assert response.status_code == 200
    finally:
        main_app.dependency_overrides.pop(get_asset_observation_service, None)
