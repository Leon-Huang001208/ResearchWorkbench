"""Actual Host/ASGI boundaries, without vendor, keychain or model calls."""

import pytest
from fastapi.testclient import TestClient

from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store
from tests.research_web.test_api import NativeFixture


@pytest.fixture
def event_api(tmp_path, monkeypatch):
    import keyring

    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    monkeypatch.setenv("RESEARCH_FRAMEWORK_COLLECTORS_ENABLED", "0")
    secrets = {}
    monkeypatch.setattr(
        keyring, "get_password", lambda service, account: secrets.get((service, account))
    )
    monkeypatch.setattr(
        keyring,
        "set_password",
        lambda service, account, value: secrets.__setitem__((service, account), value),
    )
    monkeypatch.setattr(
        keyring, "delete_password", lambda service, account: secrets.pop((service, account), None)
    )
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path / "owner"))
    with TestClient(create_app(service)) as client:
        yield client, service, native


def draft(key="event-api-create-01"):
    return {
        "title": "合成测试事件",
        "category": "policy",
        "occurrence_start": "2026-12-01",
        "date_precision": "day",
        "markets": ["CN"],
        "lifecycle": "announced",
        "idempotency_key": key,
    }


def test_cold_read_does_not_initialize_events_or_call_model(event_api):
    client, service, native = event_api
    assert client.get("/api/research/events").status_code == 200
    assert client.get("/api/research/event-studies").status_code == 200
    assert client.get("/api/research/market-scores?index_id=SP500").json()["total_score"] is None
    assert not service.event_timeline.records.marker.exists()
    assert not any(call[0] == "session.prompt" for call in native.calls)


def test_explicit_action_size_and_origin_guards_precede_storage(event_api):
    client, service, _ = event_api
    assert client.post("/api/research/events", json=draft()).status_code == 403
    assert (
        client.post(
            "/api/research/events",
            json=draft(),
            headers={"X-Research-User-Action": "?1", "Origin": "https://example.test"},
        ).status_code
        == 403
    )
    oversized = client.post(
        "/api/research/events",
        content=b"x" * 65537,
        headers={"X-Research-User-Action": "?1", "Content-Type": "application/json"},
    )
    assert oversized.status_code == 413
    assert not service.event_timeline.records.marker.exists()


def test_confirm_freeze_and_idempotency_are_real_host_operations(event_api):
    client, _, native = event_api
    headers = {"X-Research-User-Action": "?1"}
    created = client.post("/api/research/events", json=draft(), headers=headers)
    assert created.status_code == 200, created.text
    record = created.json()
    assert client.post("/api/research/events", json=draft(), headers=headers).json() == record
    stale = client.post(
        "/api/research/events/decisions",
        headers=headers,
        json={
            "events": [{"id": record["id"], "revision": 9}],
            "decision": "confirmed",
            "reason": "测试",
            "idempotency_key": "stale-event-api-01",
        },
    )
    assert stale.status_code == 409
    decision = client.post(
        "/api/research/events/decisions",
        headers=headers,
        json={
            "events": [{"id": record["id"], "revision": 1}],
            "decision": "confirmed",
            "reason": "明确确认合成事件",
            "idempotency_key": "confirm-event-api-01",
        },
    )
    assert decision.status_code == 200, decision.text
    confirmed = decision.json()["items"][0]
    frozen = client.post(
        "/api/research/events/freeze",
        headers=headers,
        json={
            "events": [{"id": confirmed["id"], "revision": confirmed["revision"]}],
            "label": "合成冻结",
            "idempotency_key": "freeze-event-api-01",
        },
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["payload"]["formal_backtest_eligible"] is False
    assert not any(call[0] == "session.prompt" for call in native.calls)


def test_client_cannot_post_trust_flags_or_enable_production_score(event_api):
    client, _, _ = event_api
    body = {**draft(), "formal_backtest_eligible": True}
    assert (
        client.post(
            "/api/research/events", json=body, headers={"X-Research-User-Action": "?1"}
        ).status_code
        == 422
    )
    for index in ("SSE", "CSI300", "CHINEXT", "SP500", "NASDAQ", "DJI", "HSI", "HSCEI", "HSTECH"):
        response = client.get("/api/research/market-scores", params={"index_id": index})
        assert response.status_code == 200, response.text
        assert response.json()["production_enabled"] is False
        assert response.json()["total_score"] is None


def test_collection_plan_arms_existing_scheduler_and_disable_removes_only_its_job(event_api):
    client, service, native = event_api
    headers = {"X-Research-User-Action": "?1"}
    enabled = client.post(
        "/api/research/events/sources/fed_fomc/schedule",
        headers=headers,
        json={
            "expected_revision": 1,
            "enabled": True,
            "interval_hours": 24,
            "idempotency_key": "enable-collection-api",
        },
    )
    assert enabled.status_code == 200, enabled.text
    job = service.automations.scheduler.get_job("event-source-collection-heartbeat")
    assert job is not None and job.trigger.interval.total_seconds() == 60
    assert service.event_timeline.records.list("source_job")["items"] == []
    disabled = client.post(
        "/api/research/events/sources/fed_fomc/schedule",
        headers=headers,
        json={
            "expected_revision": enabled.json()["revision"],
            "enabled": False,
            "interval_hours": 24,
            "idempotency_key": "disable-collection-api",
        },
    )
    assert disabled.status_code == 200, disabled.text
    assert service.automations.scheduler.get_job("event-source-collection-heartbeat") is None
    assert not any(call[0] == "session.prompt" for call in native.calls)


def test_disabled_host_collection_is_not_enabled_by_source_consent(event_api, monkeypatch):
    client, service, _ = event_api
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", "0")
    response = client.post(
        "/api/research/events/sources/fed_fomc/schedule",
        headers={"X-Research-User-Action": "?1"},
        json={
            "expected_revision": 1,
            "enabled": True,
            "interval_hours": 24,
            "idempotency_key": "host-disabled-api",
        },
    )
    assert response.status_code == 403
    assert service.event_timeline.records.list("source_schedule")["items"] == []
