"""整机容量分钟历史持久化测试。"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock
from unittest.mock import MagicMock

from core.contracts.monitoring import HealthMetrics, Subsystem
from data_layer.repositories.models import HealthMetricsDB
from data_layer.repositories.monitoring_repository import MonitoringRepositoryImpl
from services.resource_host_history_service import ResourceHostHistoryService


class InMemoryMonitoringRepository:
    """模拟 MonitoringRepository 的最小可观察行为。"""

    def __init__(self, metrics: list[HealthMetrics] | None = None) -> None:
        self.metrics = list(metrics or [])
        self.deleted_metric_ids: list[str] = []
        self._lock = Lock()

    def save_health_metrics(self, metrics: HealthMetrics) -> HealthMetrics:
        self.metrics.append(metrics)
        return metrics

    def save_health_metrics_if_absent(self, metrics: HealthMetrics) -> HealthMetrics | None:
        with self._lock:
            if any(existing.metric_id == metrics.metric_id for existing in self.metrics):
                return None
            self.metrics.append(metrics)
            return metrics

    def list_metrics(
        self,
        subsystem: Subsystem | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        metric_type: str | None = None,
        limit: int = 100,
    ) -> list[HealthMetrics]:
        results = self.metrics
        if subsystem is not None:
            results = [metric for metric in results if metric.subsystem == subsystem]
        if since is not None:
            results = [metric for metric in results if metric.timestamp >= since]
        if until is not None:
            results = [metric for metric in results if metric.timestamp <= until]
        if metric_type is not None:
            results = [
                metric for metric in results if metric.extra.get("metric_type") == metric_type
            ]
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


def _resource_event_metric(metric_id: str, timestamp: datetime) -> HealthMetrics:
    return HealthMetrics(
        metric_id=metric_id,
        subsystem=Subsystem.RESOURCE_MONITORING,
        timestamp=timestamp,
        extra={"metric_type": "resource_event"},
    )


def _host_metric_id(minute: datetime) -> str:
    return (
        f"resource-host-{minute.strftime('%Y%m%d%H%M')}-"
        f"{uuid.uuid5(uuid.NAMESPACE_URL, f'resource-host:{minute.isoformat()}').hex}"
    )


def test_record_if_due_saves_only_once_per_utc_minute() -> None:
    now = datetime(2026, 8, 5, 8, 30, 5, tzinfo=timezone.utc)
    repo = InMemoryMonitoringRepository()
    service = ResourceHostHistoryService(repo, now=lambda: now)

    assert service.record_if_due(_snapshot()) is True
    assert service.record_if_due(_snapshot()) is False

    saved = repo.metrics[0]
    assert saved.metric_id == _host_metric_id(saved.timestamp)
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


def test_two_instances_record_only_one_capacity_point_per_utc_minute() -> None:
    now = datetime(2026, 8, 5, 8, 30, 5, tzinfo=timezone.utc)
    repo = InMemoryMonitoringRepository()
    barrier = Barrier(2)
    services = [
        ResourceHostHistoryService(repo, now=lambda: now),
        ResourceHostHistoryService(repo, now=lambda: now),
    ]

    def record(service: ResourceHostHistoryService) -> bool:
        barrier.wait()
        return service.record_if_due(_snapshot())

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(record, services))

    assert sorted(results) == [False, True]
    assert [metric.metric_id for metric in repo.metrics] == [
        _host_metric_id(now.replace(second=0, microsecond=0))
    ]


def test_save_if_absent_recovers_after_sqlite_unique_flush_failure(db_session) -> None:
    repo = MonitoringRepositoryImpl(db_session)
    clock = [datetime(2026, 8, 5, 8, 30, tzinfo=timezone.utc)]
    service = ResourceHostHistoryService(repo, now=lambda: clock[0])
    concurrent_service = ResourceHostHistoryService(repo, now=lambda: clock[0])

    assert service.record_if_due(_snapshot()) is True
    assert concurrent_service.record_if_due(_snapshot()) is False
    clock[0] += timedelta(minutes=1)
    assert service.record_if_due(_snapshot()) is True
    db_session.commit()

    assert db_session.query(HealthMetricsDB).count() == 2


def test_record_flush_failure_returns_false_and_leaves_sqlite_session_usable(
    monkeypatch, db_session
) -> None:
    repo = MonitoringRepositoryImpl(db_session)
    now = datetime(2026, 8, 5, 8, 30, tzinfo=timezone.utc)
    service = ResourceHostHistoryService(repo, now=lambda: now)
    original_flush = db_session.flush

    def failing_flush() -> None:
        raise RuntimeError("flush failed")

    monkeypatch.setattr(db_session, "flush", failing_flush)
    assert service.record_if_due(_snapshot()) is False
    monkeypatch.setattr(db_session, "flush", original_flush)

    assert (
        repo.save_health_metrics_if_absent(
            _host_capacity_metric(
                _host_metric_id(now + timedelta(minutes=1)), now + timedelta(minutes=1)
            )
        )
        is not None
    )
    db_session.commit()
    assert db_session.query(HealthMetricsDB).count() == 1


def test_record_returns_false_when_followup_cleanup_delete_fails() -> None:
    class FailingDeleteRepository(InMemoryMonitoringRepository):
        def delete_health_metrics(self, metric_ids: list[str]) -> int:
            raise RuntimeError("delete failed")

    now = datetime(2026, 8, 6, 8, 31, tzinfo=timezone.utc)
    repo = FailingDeleteRepository(
        [
            _host_capacity_metric(
                _host_metric_id(now - timedelta(hours=24, minutes=1)),
                now - timedelta(hours=24, minutes=1),
            )
        ]
    )
    service = ResourceHostHistoryService(repo, now=lambda: now)

    assert service.record_if_due(_snapshot()) is False


def test_delete_flush_failure_leaves_sqlite_session_usable(monkeypatch, db_session) -> None:
    repo = MonitoringRepositoryImpl(db_session)
    now = datetime(2026, 8, 6, 8, 31, tzinfo=timezone.utc)
    existing = _host_capacity_metric(
        _host_metric_id(now - timedelta(hours=24, minutes=1)),
        now - timedelta(hours=24, minutes=1),
    )
    next_minute = _host_capacity_metric(
        _host_metric_id(datetime(2026, 8, 5, 8, 31, tzinfo=timezone.utc)),
        datetime(2026, 8, 5, 8, 31, tzinfo=timezone.utc),
    )
    assert repo.save_health_metrics_if_absent(existing) is not None
    service = ResourceHostHistoryService(repo, now=lambda: now)
    original_flush = db_session.flush

    def failing_flush() -> None:
        raise RuntimeError("flush failed")

    monkeypatch.setattr(db_session, "flush", failing_flush)
    assert service.purge_expired() == 0
    monkeypatch.setattr(db_session, "flush", original_flush)

    assert repo.save_health_metrics_if_absent(next_minute) is not None
    db_session.commit()
    assert db_session.query(HealthMetricsDB).count() == 2


def test_purge_expired_does_not_hide_capacity_behind_newer_resource_events() -> None:
    now = datetime(2026, 8, 5, 8, 30, tzinfo=timezone.utc)
    expired = now - timedelta(hours=24, minutes=1)
    repo = InMemoryMonitoringRepository(
        [
            _host_capacity_metric("old-host", expired),
            *[
                _resource_event_metric(f"event-{index}", expired + timedelta(seconds=1))
                for index in range(1500)
            ],
        ]
    )
    service = ResourceHostHistoryService(repo, now=lambda: now)

    assert service.purge_expired() == 1

    assert repo.deleted_metric_ids == ["old-host"]
    assert len(repo.metrics) == 1500
    assert all(metric.extra["metric_type"] == "resource_event" for metric in repo.metrics)


def test_purge_expired_removes_all_capacity_points_across_multiple_batches() -> None:
    now = datetime(2026, 8, 5, 8, 30, tzinfo=timezone.utc)
    expired = now - timedelta(hours=24, minutes=1)
    repo = InMemoryMonitoringRepository(
        [_host_capacity_metric(f"old-host-{index}", expired) for index in range(1501)]
    )
    service = ResourceHostHistoryService(repo, now=lambda: now)

    assert service.purge_expired() == 1501

    assert repo.metrics == []
    assert len(repo.deleted_metric_ids) == 1501


def test_record_if_due_finds_current_capacity_behind_newer_resource_events() -> None:
    now = datetime(2026, 8, 5, 8, 30, 5, tzinfo=timezone.utc)
    minute = now.replace(second=0, microsecond=0)
    repo = InMemoryMonitoringRepository(
        [
            _host_capacity_metric(_host_metric_id(minute), minute),
            *[_resource_event_metric(f"event-{index}", minute) for index in range(1500)],
        ]
    )
    service = ResourceHostHistoryService(repo, now=lambda: now)

    assert service.record_if_due(_snapshot()) is False

    assert [
        metric.metric_id
        for metric in repo.metrics
        if metric.extra["metric_type"] == "host_capacity"
    ] == [_host_metric_id(minute)]


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
