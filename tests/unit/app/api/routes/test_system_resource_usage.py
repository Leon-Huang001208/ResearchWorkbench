"""System resource usage API route tests."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import system


class StubResourceMonitoringService:
    """Keep route tests independent of psutil and process state."""

    def __init__(self) -> None:
        self.snapshot = {
            "sampled_at": "2026-08-05T00:00:00+00:00",
            "root_pid": 123,
            "status": "ok",
            "warnings": [],
            "summary": {
                "cpu_percent": 12.5,
                "memory_bytes": 4096,
                "process_count": 1,
                "disk_read_bytes_per_second": 10.0,
                "disk_write_bytes_per_second": 5.0,
                "network_connection_count": 2,
            },
            "processes": [
                {
                    "pid": 123,
                    "parent_pid": 1,
                    "name": "api",
                    "command": "python [redacted]",
                    "create_time": 123.0,
                    "status": "running",
                    "role": "API",
                    "cpu_percent": 12.5,
                    "memory_bytes": 4096,
                    "thread_count": 4,
                    "disk_read_bytes_per_second": 10.0,
                    "disk_write_bytes_per_second": 5.0,
                    "network_connection_count": 2,
                    "unavailable_reason": None,
                }
            ],
        }
        self.history_calls: list[int] = []

    def collect_snapshot(self) -> dict:
        return self.snapshot

    def history(self, window_seconds: int) -> list[dict]:
        self.history_calls.append(window_seconds)
        return [self.snapshot]


@pytest.fixture
def resource_usage_client(monkeypatch: pytest.MonkeyPatch):
    """Provide a clean route app and remove any lazy-service singleton state."""
    monkeypatch.delattr(system.get_resource_monitoring_service, "_instance", raising=False)
    app = FastAPI()
    app.include_router(system.router)
    service = StubResourceMonitoringService()
    app.dependency_overrides[system.get_resource_monitoring_service] = lambda: service

    try:
        yield TestClient(app, raise_server_exceptions=True), service
    finally:
        app.dependency_overrides.pop(system.get_resource_monitoring_service, None)
        monkeypatch.delattr(system.get_resource_monitoring_service, "_instance", raising=False)


def test_resource_usage_returns_snapshot_schema_via_service_stub(resource_usage_client) -> None:
    client, service = resource_usage_client

    response = client.get("/api/system/resource-usage")

    assert response.status_code == 200
    assert response.json() == service.snapshot


def test_resource_usage_history_returns_requested_window_and_points(resource_usage_client) -> None:
    client, service = resource_usage_client

    response = client.get("/api/system/resource-usage/history?window_seconds=60")

    assert response.status_code == 200
    assert response.json() == {"window_seconds": 60, "points": [service.snapshot]}
    assert service.history_calls == [60]


@pytest.mark.parametrize("window_seconds", [1, 301])
def test_resource_usage_history_rejects_out_of_range_window(
    resource_usage_client, window_seconds
) -> None:
    client, service = resource_usage_client

    response = client.get(f"/api/system/resource-usage/history?window_seconds={window_seconds}")

    assert response.status_code == 422
    assert service.history_calls == []


def test_system_minimal_health_route_remains_available() -> None:
    result = asyncio.run(system.get_health_minimal())

    assert result["status"] == "ok"
