"""系统资源监控 API 的事件历史与处置测试。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import system
from core.contracts.monitoring import AlertPayload, AlertSeverity, AlertStatus, Subsystem


def _event(*, alert_id: str, status: AlertStatus = AlertStatus.OPEN) -> AlertPayload:
    return AlertPayload(
        alert_id=alert_id,
        threshold_id="resource-task_failed",
        subsystem=Subsystem.RESOURCE_MONITORING,
        severity=AlertSeverity.CRITICAL,
        status=status,
        title="任务失败：测试",
        triggered_at=datetime.now(timezone.utc),
        metadata={"event_kind": "task_failed", "task_kind": "crawl", "source_key": "cls"},
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(system.router)
    return TestClient(app, raise_server_exceptions=True)


def test_list_resource_events_returns_sanitized_persisted_events(monkeypatch) -> None:
    """查询 API 返回持久化资源事件，且不建立数据库依赖于路由外。"""
    monkeypatch.setattr(
        system,
        "_resource_event_service_call",
        lambda callback: callback(FakeEventService([_event(alert_id="open-1")])),
    )

    response = _client().get("/api/system/resource-events?days=90&status=all")

    assert response.status_code == 200
    assert response.json()["items"][0]["alert_id"] == "open-1"
    assert response.json()["items"][0]["metadata"]["task_kind"] == "crawl"


def test_acknowledge_and_resolve_resource_event(monkeypatch) -> None:
    """处置 API 应调用资源事件服务并返回状态机结果。"""
    service = FakeEventService([_event(alert_id="open-1")])
    monkeypatch.setattr(system, "_resource_event_service_call", lambda callback: callback(service))
    client = _client()

    acknowledge = client.post("/api/system/resource-events/open-1/acknowledge")
    resolve = client.post("/api/system/resource-events/open-1/resolve", json={"notes": "已处理"})

    assert acknowledge.status_code == 200
    assert acknowledge.json()["status"] == "acknowledged"
    assert resolve.status_code == 200
    assert resolve.json()["status"] == "resolved"


class FakeEventService:
    """路由契约所需的轻量服务替身。"""

    def __init__(self, events: list[AlertPayload]) -> None:
        self.events = events

    def list_events(self, **_: object) -> list[AlertPayload]:
        return self.events

    def acknowledge(self, alert_id: str):
        event = next((item for item in self.events if item.alert_id == alert_id), None)
        if event:
            event.status = AlertStatus.ACKNOWLEDGED
        return event

    def resolve(self, alert_id: str, *, notes: str = ""):
        event = next((item for item in self.events if item.alert_id == alert_id), None)
        if event:
            event.status = AlertStatus.RESOLVED
        return event
