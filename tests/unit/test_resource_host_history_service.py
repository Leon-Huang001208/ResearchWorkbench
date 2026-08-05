"""整机容量分钟历史持久化测试。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from core.contracts.monitoring import HealthMetrics, Subsystem
from data_layer.repositories.monitoring_repository import MonitoringRepositoryImpl
from services.resource_host_history_service import ResourceHostHistoryService


class InMemoryMonitoringRepository:
    """模拟 MonitoringRepository 的最小可观察行为。"""

    def __init__(self, metrics: list[HealthMetrics] | None = None) -> None:
        self.metrics = list(metrics or [])
        self.deleted_metric_ids: list[str] = []

    def save_health_metrics(self, metrics: HealthMetrics) -> HealthMetrics:
        self.metrics.append(metrics)
        return metrics

    def list_metrics(
        self,
        subsystem: Subsystem | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[HealthMetrics]:
        results = self.metrics
        if subsystem is not None:
            results = [metric for metric in results if metric.subsystem == subsystem]
        if since is not None:
            results = [metric for metric in results if metric.timestamp >= since]
        if until is not None:
            results = [metric for metric in results if metric.timestamp <= until]
        return list(reversed(results))[:limit]

    def delete_health_metrics(self, metric_ids: list[str]) -> int:
        self.deleted_metric_ids.extend(metric_ids)
        before = len(self.metrics)
        self.metrics = [metric for metric in self.metrics if metric.metric_id not in metric_ids]
        return before - len(self.metrics)


def _snapshot() -> dict[str, object]:
    return {
        "host": {
            "cpu_percent": 40.0,
            "cpu_idle_percent": 60.0,
            "logical_cpu_count": 8,
            "memory_total_bytes": 16_000,
            "memory_used_bytes": 6_000,
            "memory_available_bytes": 10_000,
            "memory_available_percent": 62.5,
            "internal_host_key": "must-not-persist",
        },
        "summary": {
            "cpu_percent": 12.5,
            "memory_bytes": 2_000,
            "cpu_host_percent": 1.5625,
            "memory_host_percent": 12.5,
            "root_pid": 9999,
        },
        "processes": [{"pid": 9999, "cmdline": ["secret"]}],
    }


def _host_capacity_metric(metric_id: str, timestamp: datetime, **extra: object) -> HealthMetrics:
    return HealthMetrics(
        metric_id=metric_id,
        subsystem=Subsystem.RESOURCE_MONITORING,
        timestamp=timestamp,
        extra={
            "metric_type": "host_capacity",
            "host": _snapshot()["host"],
            "alpha": _snapshot()["summary"],
            **extra,
        },
    )


def test_record_if_due_saves_only_once_per_utc_minute() -> None:
    now = datetime(2026, 8, 5, 8, 30, 5, tzinfo=timezone.utc)
    repo = InMemoryMonitoringRepository()
    service = ResourceHostHistoryService(repo, now=lambda: now)

    assert service.record_if_due(_snapshot()) is True
    assert service.record_if_due(_snapshot()) is False

    saved = repo.metrics[0]
    assert saved.metric_id.startswith("resource-host-20260805T0830-")
    assert saved.timestamp == datetime(2026, 8, 5, 8, 30, tzinfo=timezone.utc)
    assert saved.subsystem == Subsystem.RESOURCE_MONITORING


def test_record_if_due_deletes_expired_host_capacity_only() -> None:
    now = datetime(2026, 8, 5, 8, 30, tzinfo=timezone.utc)
    expired = now - timedelta(hours=24, minutes=1)
    old_host_capacity = _host_capacity_metric("old-host", expired)
    other_metric_type = HealthMetrics(
        metric_id="old-other",
        subsystem=Subsystem.RESOURCE_MONITORING,
        timestamp=expired,
        extra={"metric_type": "resource_event", "private": "retain"},
    )
    repo = InMemoryMonitoringRepository([old_host_capacity, other_metric_type])
    service = ResourceHostHistoryService(repo, now=lambda: now)

    assert service.record_if_due(_snapshot()) is True

    assert repo.deleted_metric_ids == ["old-host"]
    assert [metric.metric_id for metric in repo.metrics] == [
        "old-other",
        repo.metrics[-1].metric_id,
    ]


def test_list_history_returns_only_safe_host_capacity_points_in_time_order() -> None:
    first = datetime(2026, 8, 5, 8, 28, tzinfo=timezone.utc)
    second = first + timedelta(minutes=1)
    repo = InMemoryMonitoringRepository(
        [
            _host_capacity_metric("second", second, internal_marker="discard"),
            HealthMetrics(
                metric_id="event",
                subsystem=Subsystem.RESOURCE_MONITORING,
                timestamp=first,
                extra={"metric_type": "resource_event", "processes": ["discard"]},
            ),
            _host_capacity_metric("first", first),
        ]
    )
    service = ResourceHostHistoryService(repo, now=lambda: second)

    points = service.list_history()

    assert [point["timestamp"] for point in points] == [first, second]
    assert all(set(point) == {"timestamp", "host", "alpha"} for point in points)
    assert points[0]["host"] == {
        "cpu_percent": 40.0,
        "cpu_idle_percent": 60.0,
        "logical_cpu_count": 8,
        "memory_total_bytes": 16_000,
        "memory_used_bytes": 6_000,
        "memory_available_bytes": 10_000,
        "memory_available_percent": 62.5,
    }
    assert points[0]["alpha"] == {
        "cpu_percent": 12.5,
        "memory_bytes": 2_000,
        "cpu_host_percent": 1.5625,
        "memory_host_percent": 12.5,
    }


def test_record_if_due_discards_internal_snapshot_keys() -> None:
    repo = InMemoryMonitoringRepository()
    service = ResourceHostHistoryService(
        repo,
        now=lambda: datetime(2026, 8, 5, 8, 30, tzinfo=timezone.utc),
    )

    assert service.record_if_due(_snapshot()) is True

    assert repo.metrics[0].extra == {
        "metric_type": "host_capacity",
        "host": {
            "cpu_percent": 40.0,
            "cpu_idle_percent": 60.0,
            "logical_cpu_count": 8,
            "memory_total_bytes": 16_000,
            "memory_used_bytes": 6_000,
            "memory_available_bytes": 10_000,
            "memory_available_percent": 62.5,
        },
        "alpha": {
            "cpu_percent": 12.5,
            "memory_bytes": 2_000,
            "cpu_host_percent": 1.5625,
            "memory_host_percent": 12.5,
        },
    }


def test_record_if_due_handles_missing_or_invalid_host_snapshot() -> None:
    repo = InMemoryMonitoringRepository()
    service = ResourceHostHistoryService(
        repo,
        now=lambda: datetime(2026, 8, 5, 8, 30, tzinfo=timezone.utc),
    )

    assert service.record_if_due({}) is False
    assert service.record_if_due({"host": "not-a-mapping"}) is False
    assert repo.metrics == []


def test_delete_health_metrics_ignores_empty_ids_and_flushes() -> None:
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value.delete.return_value = 2
    repository = MonitoringRepositoryImpl(db)

    assert repository.delete_health_metrics(["metric-1", "", "metric-2"]) == 2

    query.filter.return_value.delete.assert_called_once_with(synchronize_session=False)
    db.flush.assert_called_once()
    db.reset_mock()
    assert repository.delete_health_metrics([]) == 0
    db.query.assert_not_called()
    db.flush.assert_not_called()
