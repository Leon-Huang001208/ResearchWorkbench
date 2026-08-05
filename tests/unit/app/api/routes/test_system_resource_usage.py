"""System resource usage API route tests."""

import asyncio
import inspect
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

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
            "task_failures": [],
            "summary": {
                "cpu_percent": 12.5,
                "memory_bytes": 4096,
                "process_count": 1,
                "disk_read_bytes_per_second": 10.0,
                "disk_write_bytes_per_second": 5.0,
                "network_connection_count": 2,
            },
            "host": {
                "cpu_percent": 20.0,
                "cpu_idle_percent": 80.0,
                "logical_cpu_count": 8,
                "memory_total_bytes": 16_000,
                "memory_used_bytes": 4_000,
                "memory_available_bytes": 12_000,
                "memory_available_percent": 75.0,
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
def reset_resource_monitoring_singleton(monkeypatch: pytest.MonkeyPatch):
    """Clear the route-local singleton before and after direct factory tests."""
    monkeypatch.delattr(system.get_resource_monitoring_service, "_instance", raising=False)
    try:
        yield
    finally:
        monkeypatch.delattr(system.get_resource_monitoring_service, "_instance", raising=False)


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


def test_system_route_import_does_not_eagerly_import_resource_monitoring_service() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "import app.api.routes.system\n"
            "assert 'services.resource_monitor_service' not in sys.modules\n",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_resource_monitoring_factory_creates_one_lazy_singleton(
    monkeypatch: pytest.MonkeyPatch,
    reset_resource_monitoring_singleton,
) -> None:
    from services import resource_monitor_service

    created_instances = []

    class StubFactoryService:
        def __init__(self) -> None:
            created_instances.append(self)

    monkeypatch.setattr(resource_monitor_service, "ResourceMonitoringService", StubFactoryService)

    first = system.get_resource_monitoring_service()
    second = system.get_resource_monitoring_service()

    assert first is second
    assert created_instances == [first]


def test_resource_monitoring_factory_is_thread_safe(
    monkeypatch: pytest.MonkeyPatch,
    reset_resource_monitoring_singleton,
) -> None:
    from services import resource_monitor_service

    created_instances = []

    class StubFactoryService:
        def __init__(self) -> None:
            created_instances.append(self)

    monkeypatch.setattr(resource_monitor_service, "ResourceMonitoringService", StubFactoryService)

    with ThreadPoolExecutor(max_workers=8) as executor:
        instances = list(
            executor.map(lambda _: system.get_resource_monitoring_service(), range(32))
        )

    assert len({id(instance) for instance in instances}) == 1
    assert len(created_instances) == 1


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


def test_resource_usage_history_uses_300_second_default(resource_usage_client) -> None:
    client, service = resource_usage_client

    response = client.get("/api/system/resource-usage/history")

    assert response.status_code == 200
    assert response.json() == {"window_seconds": 300, "points": [service.snapshot]}
    assert service.history_calls == [300]


@pytest.mark.parametrize("window_seconds", [1, 301])
def test_resource_usage_history_rejects_out_of_range_window(
    resource_usage_client, window_seconds
) -> None:
    client, service = resource_usage_client

    response = client.get(f"/api/system/resource-usage/history?window_seconds={window_seconds}")

    assert response.status_code == 422
    assert service.history_calls == []


def test_resource_usage_sanitizes_internal_collection_errors(resource_usage_client) -> None:
    client, service = resource_usage_client
    service.snapshot["warnings"] = [
        {
            "code": "process_field_unavailable",
            "pid": 123,
            "field": "name",
            "error_type": "AccessDenied",
            "details": "permission denied for secret process data",
        },
        {
            "code": "root_process_unavailable",
            "error_type": "NoSuchProcess",
        },
        {
            "code": "child_process_unavailable",
            "pid": 456,
            "error_type": "NotImplementedError",
        },
    ]
    service.snapshot["processes"][0][
        "unavailable_reason"
    ] = "name:AccessDenied; io_counters:NotImplementedError"

    response = client.get("/api/system/resource-usage")

    assert response.status_code == 200
    assert response.json()["warnings"] == [
        {"code": "field_unavailable", "pid": 123, "field": "name"},
        {"code": "root_process_unavailable"},
        {"code": "partial_data"},
    ]
    assert response.json()["processes"][0]["unavailable_reason"] == "field_unavailable"
    assert "AccessDenied" not in response.text
    assert "NotImplementedError" not in response.text


def test_resource_usage_routes_are_synchronous_for_threadpool_execution() -> None:
    assert not inspect.iscoroutinefunction(system.get_resource_usage)
    assert not inspect.iscoroutinefunction(system.get_resource_usage_history)


def test_system_minimal_health_route_remains_available() -> None:
    result = asyncio.run(system.get_health_minimal())

    assert result["status"] == "ok"
