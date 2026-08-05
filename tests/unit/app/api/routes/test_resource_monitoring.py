"""系统资源监控 API 的事件历史与处置测试。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
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


def test_managed_process_warning_exposes_only_stable_public_fields() -> None:
    """受控 Worker 不可用时 API 只公开稳定警告码与 PID。"""
    warning = system._sanitize_resource_warning(
        {
            "code": "managed_process_unavailable",
            "pid": 123,
            "error_type": "AccessDenied",
            "internal_detail": "must not escape",
        }
    )

    assert warning == {"code": "managed_process_unavailable", "pid": 123}


def test_resource_usage_exposes_only_safe_host_capacity_and_skips_event_evaluation(
    monkeypatch,
) -> None:
    """当前快照公开主机容量白名单，告警评估由常驻运行时负责。"""
    snapshot = {
        "sampled_at": "2026-08-05T00:00:00+00:00",
        "summary": {"cpu_percent": 6.0, "cpu_host_percent": 12.5},
        "task_failures": [],
        "host": {
            "cpu_percent": 12.5,
            "cpu_idle_percent": 87.5,
            "logical_cpu_count": 8,
            "memory_total_bytes": 16_000,
            "memory_used_bytes": 4_000,
            "memory_available_bytes": 12_000,
            "memory_available_percent": 75.0,
            "processes": [{"name": "other-app"}],
            "internal_detail": "must not escape",
        },
    }

    class SnapshotService:
        def collect_snapshot(self):
            return snapshot

    app = FastAPI()
    app.include_router(system.router)
    app.dependency_overrides[system.get_resource_monitoring_service] = SnapshotService
    monkeypatch.setattr(
        system,
        "_resource_event_service_call",
        lambda _callback: pytest.fail("resource-usage must not evaluate events"),
    )

    response = TestClient(app).get("/api/system/resource-usage")

    assert response.status_code == 200
    assert response.json()["host"] == {
        "cpu_percent": 12.5,
        "cpu_idle_percent": 87.5,
        "logical_cpu_count": 8,
        "memory_total_bytes": 16_000,
        "memory_used_bytes": 4_000,
        "memory_available_bytes": 12_000,
        "memory_available_percent": 75.0,
    }
    assert "processes" not in response.json()["host"]


def test_host_capacity_sanitizer_returns_empty_safe_protocol_for_invalid_host() -> None:
    """异常主机载荷也维持稳定的七字段公开协议。"""
    assert system._sanitize_host_capacity(["not", "a", "mapping"]) == {
        "cpu_percent": None,
        "cpu_idle_percent": None,
        "logical_cpu_count": None,
        "memory_total_bytes": None,
        "memory_used_bytes": None,
        "memory_available_bytes": None,
        "memory_available_percent": None,
    }


def test_resource_host_history_returns_sorted_safe_points(monkeypatch) -> None:
    """主机历史只含整机与 Alpha 汇总字段，并按采样时间升序输出。"""
    points = [
        {
            "timestamp": datetime(2026, 8, 5, 0, 2, tzinfo=timezone.utc),
            "host": {"cpu_percent": 20.0, "processes": [{"pid": 7}]},
            "alpha": {"cpu_percent": 4.0, "memory_bytes": 1024, "dedupe_key": "internal"},
        },
        {
            "timestamp": datetime(2026, 8, 5, 0, 1, tzinfo=timezone.utc),
            "host": {"cpu_percent": 10.0, "logical_cpu_count": True},
            "alpha": {"cpu_host_percent": 10.0, "memory_host_percent": 20.0},
        },
    ]

    class HostHistoryService:
        def list_history(self):
            return points

    monkeypatch.setattr(
        system,
        "_resource_host_history_call",
        lambda callback: callback(HostHistoryService()),
    )

    response = _client().get("/api/system/resource-usage/host-history?hours=24")

    assert response.status_code == 200
    payload = response.json()
    assert payload["hours"] == 24
    assert [point["sampled_at"] for point in payload["points"]] == [
        "2026-08-05T00:01:00+00:00",
        "2026-08-05T00:02:00+00:00",
    ]
    assert set(payload["points"][0]) == {"sampled_at", "host", "alpha"}
    assert set(payload["points"][0]["host"]) == {
        "cpu_percent",
        "cpu_idle_percent",
        "logical_cpu_count",
        "memory_total_bytes",
        "memory_used_bytes",
        "memory_available_bytes",
        "memory_available_percent",
    }
    assert payload["points"][0]["host"]["logical_cpu_count"] is None
    assert set(payload["points"][0]["alpha"]) == {
        "cpu_percent",
        "memory_bytes",
        "cpu_host_percent",
        "memory_host_percent",
    }


def test_resource_host_history_rejects_invalid_hours_without_storage_call(monkeypatch) -> None:
    """长期历史查询限制为最多 24 小时。"""
    monkeypatch.setattr(
        system,
        "_resource_host_history_call",
        lambda _callback: pytest.fail("invalid hours must not query storage"),
    )

    response = _client().get("/api/system/resource-usage/host-history?hours=25")

    assert response.status_code == 422


def test_resource_host_history_returns_stable_503_when_storage_is_unavailable(monkeypatch) -> None:
    """持久层异常不得泄露细节，并映射为稳定的服务不可用响应。"""
    monkeypatch.setattr(
        system,
        "_resource_host_history_call",
        lambda _callback: (_ for _ in ()).throw(RuntimeError("database password leaked")),
    )

    response = _client().get("/api/system/resource-usage/host-history?hours=24")

    assert response.status_code == 503
    assert response.json() == {"detail": "Host resource history unavailable"}


def test_resource_event_metadata_exposes_safe_host_threshold_fields_only() -> None:
    """主机事件可表达安全来源与阈值，但不公开内部去重或调试字段。"""
    event = _event(alert_id="host-1")
    event.metadata = {
        "source_scope": "host",
        "host_cpu_percent": 91.5,
        "host_memory_available_percent": 8.5,
        "threshold_percent": 90,
        "dedupe_key": "internal-resource-key",
        "internal_detail": "must not escape",
    }

    assert system._serialize_resource_event(event)["metadata"] == {
        "source_scope": "host",
        "host_cpu_percent": 91.5,
        "host_memory_available_percent": 8.5,
        "threshold_percent": 90,
    }


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
