"""资源异常事件协调器测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from core.contracts.monitoring import AlertSeverity, AlertStatus, Subsystem
from services import resource_monitor_alert_service
from services.resource_monitor_alert_service import ResourceAlertState, ResourceMonitorAlertService


class FakeRepository:
    """覆盖资源告警所需仓储方法的内存替身。"""

    def __init__(self) -> None:
        self.alerts = []
        self.incidents = []

    def list_alerts(self, **_: object):
        return list(self.alerts)

    def save_alert(self, alert):
        for index, existing in enumerate(self.alerts):
            if existing.alert_id == alert.alert_id:
                self.alerts[index] = alert
                return alert
        self.alerts.append(alert)
        return alert

    def update_alert_details_if_unresolved(
        self,
        alert_id,
        severity,
        title,
        description,
        threshold_value,
        metadata,
    ):
        for alert in self.alerts:
            if alert.alert_id != alert_id:
                continue
            if alert.status == AlertStatus.RESOLVED:
                return alert
            alert.severity = severity
            alert.title = title
            alert.description = description
            alert.threshold_value = threshold_value
            alert.metadata = metadata
            return alert
        return None

    def get_or_create_open_resource_alert(self, alert, dedupe_key):
        for existing in self.alerts:
            if (
                existing.status != AlertStatus.RESOLVED
                and existing.metadata.get("dedupe_key") == dedupe_key
            ):
                return existing, False
        return self.save_alert(alert), True

    def save_incident(self, incident):
        for index, existing in enumerate(self.incidents):
            if existing.incident_id == incident.incident_id:
                self.incidents[index] = incident
                return incident
        self.incidents.append(incident)
        return incident

    def list_incidents(self, **_: object):
        return list(self.incidents)


class InterleavingFakeRepository(FakeRepository):
    """在原子详情更新前模拟另一个数据库会话改变告警状态。"""

    def __init__(self, transition: AlertStatus) -> None:
        super().__init__()
        self._transition = transition
        self._transitioned = False

    def update_alert_details_if_unresolved(
        self,
        alert_id,
        severity,
        title,
        description,
        threshold_value,
        metadata,
    ):
        for alert in self.alerts:
            if alert.alert_id != alert_id:
                continue
            if not self._transitioned:
                alert.status = self._transition
                if self._transition == AlertStatus.ACKNOWLEDGED:
                    alert.acknowledged_at = datetime.now(timezone.utc)
                else:
                    alert.resolved_at = datetime.now(timezone.utc)
                self._transitioned = True
            break
        return super().update_alert_details_if_unresolved(
            alert_id,
            severity,
            title,
            description,
            threshold_value,
            metadata,
        )


def _snapshot_with_process(*, cpu: float, memory_bytes: int = 1, pid: int = 101) -> dict:
    return {
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "warnings": [],
        "task_failures": [],
        "processes": [
            {
                "pid": pid,
                "role": "API",
                "attribution_kind": "api",
                "confidence": "exact_process",
                "cpu_percent": cpu,
                "memory_bytes": memory_bytes,
            }
        ],
    }


def _snapshot_with_host(*, cpu: object = 10.0, memory_available: object = 50.0) -> dict:
    """构造只包含整机容量读数的资源快照。"""
    return {
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "warnings": [],
        "task_failures": [],
        "processes": [],
        "host": {
            "cpu_percent": cpu,
            "memory_available_percent": memory_available,
        },
    }


def test_pressure_opens_once_then_resolves_after_three_recovered_samples() -> None:
    """连续压力只创建一个事件，连续恢复后自动解决。"""
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_process(cpu=95.0))

    assert len(repo.alerts) == 1
    alert = repo.alerts[0]
    assert alert.metadata["event_kind"] == "resource_pressure"
    assert alert.metadata["source_scope"] == "alphafoundry"
    assert alert.status == AlertStatus.OPEN

    service.evaluate(_snapshot_with_process(cpu=95.0))
    assert len(repo.alerts) == 1

    for _ in range(3):
        service.evaluate(_snapshot_with_process(cpu=5.0))

    assert alert.status == AlertStatus.RESOLVED
    assert alert.resolved_at is not None


def test_shared_state_keeps_pressure_counts_across_service_instances() -> None:
    repo = FakeRepository()
    state = ResourceAlertState()

    ResourceMonitorAlertService(repo, state=state).evaluate(_snapshot_with_process(cpu=95.0))
    ResourceMonitorAlertService(repo, state=state).evaluate(_snapshot_with_process(cpu=95.0))
    ResourceMonitorAlertService(repo, state=state).evaluate(_snapshot_with_process(cpu=95.0))

    assert len(repo.alerts) == 1
    assert state.pressure_counts["resource_pressure:101"] == 3


def test_evaluate_logs_warning_when_an_alert_stage_fails(monkeypatch) -> None:
    log = MagicMock()
    monkeypatch.setattr(resource_monitor_alert_service, "logger", log)
    service = ResourceMonitorAlertService(FakeRepository())
    monkeypatch.setattr(
        service,
        "_evaluate_task_failures",
        lambda _: (_ for _ in ()).throw(RuntimeError("repository unavailable")),
    )

    assert service.evaluate(_snapshot_with_process(cpu=1.0)) == []
    log.warning.assert_called_once_with(
        "resource monitor alert evaluation failed", error_type="RuntimeError"
    )
    log.error.assert_not_called()


def test_failed_task_creates_deduplicated_critical_event() -> None:
    """相同失败任务跨多次采样只能保留一个未恢复 critical 事件。"""
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)
    snapshot = _snapshot_with_process(cpu=1.0)
    snapshot["task_failures"] = [
        {
            "task_id": "resource-task-1",
            "task_kind": "crawl",
            "source_key": "cls",
            "label": "财联社抓取",
            "pid": 101,
            "error_type": "ValueError",
        }
    ]

    service.evaluate(snapshot)
    service.evaluate(snapshot)

    assert len(repo.alerts) == 1
    alert = repo.alerts[0]
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.subsystem == Subsystem.RESOURCE_MONITORING
    assert alert.metadata["task_kind"] == "crawl"
    assert alert.metadata["source_key"] == "cls"
    assert alert.metadata["source_scope"] == "alphafoundry"
    assert len(repo.incidents) == 1


def test_host_cpu_pressure_opens_warning_after_three_samples_and_deduplicates() -> None:
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=85.0))

    assert len(repo.alerts) == 1
    alert = repo.alerts[0]
    assert alert.severity == AlertSeverity.WARNING
    assert alert.metadata["event_kind"] == "host_cpu_pressure"
    assert alert.metadata["source_scope"] == "host_capacity"
    assert alert.metadata["threshold_percent"] == 85.0
    assert set(alert.metadata) <= {
        "event_kind",
        "source_scope",
        "host_cpu_percent",
        "host_memory_available_percent",
        "threshold_percent",
        "dedupe_key",
    }

    service.evaluate(_snapshot_with_host(cpu=90.0))

    assert len(repo.alerts) == 1


def test_host_cpu_pressure_upgrades_existing_warning_after_three_critical_samples() -> None:
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=85.0))
    warning = repo.alerts[0]
    assert service.acknowledge(warning.alert_id) is not None

    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=95.0))

    assert len(repo.alerts) == 1
    assert repo.alerts[0].alert_id == warning.alert_id
    assert warning.severity == AlertSeverity.CRITICAL
    assert warning.status == AlertStatus.ACKNOWLEDGED
    assert warning.metadata["threshold_percent"] == 95.0
    assert repo.incidents[0].severity == AlertSeverity.WARNING


def test_host_upgrade_preserves_acknowledgement_changed_by_another_session() -> None:
    repo = InterleavingFakeRepository(AlertStatus.ACKNOWLEDGED)
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=85.0))
    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=95.0))

    alert = repo.alerts[0]
    assert alert.status == AlertStatus.ACKNOWLEDGED
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.resolved_at is None


def test_host_upgrade_does_not_reopen_alert_resolved_by_another_session() -> None:
    repo = InterleavingFakeRepository(AlertStatus.RESOLVED)
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=85.0))
    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=95.0))

    alert = repo.alerts[0]
    assert alert.status == AlertStatus.RESOLVED
    assert alert.severity == AlertSeverity.WARNING
    assert alert.resolved_at is not None


def test_host_cpu_pressure_resolves_after_three_healthy_samples() -> None:
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=85.0))
    alert = repo.alerts[0]

    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=20.0))

    assert alert.status == AlertStatus.RESOLVED
    assert alert.resolved_at is not None


def test_host_memory_pressure_opens_at_warning_and_upgrades_at_critical_threshold() -> None:
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_host(memory_available=15.0))
    alert = repo.alerts[0]

    assert alert.severity == AlertSeverity.WARNING
    assert alert.metadata["event_kind"] == "host_memory_pressure"
    assert alert.metadata["host_memory_available_percent"] == 15.0
    assert alert.metadata["threshold_percent"] == 15.0

    for _ in range(3):
        service.evaluate(_snapshot_with_host(memory_available=8.0))

    assert len(repo.alerts) == 1
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.metadata["threshold_percent"] == 8.0


def test_invalid_or_missing_host_capacity_does_not_open_or_resolve_host_event() -> None:
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=85.0))
    alert = repo.alerts[0]

    for snapshot in (
        {"status": "ok", "warnings": [], "task_failures": [], "processes": []},
        _snapshot_with_host(cpu=None),
        _snapshot_with_host(cpu="not-a-number"),
    ):
        for _ in range(3):
            service.evaluate(snapshot)

    assert len(repo.alerts) == 1
    assert alert.status == AlertStatus.OPEN


def test_nonfinite_or_out_of_range_host_capacity_does_not_open_or_resolve_event() -> None:
    invalid_values = (float("nan"), float("inf"), float("-inf"), -1.0, 101.0, True, False)
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=85.0))
    alert = repo.alerts[0]

    for value in invalid_values:
        for _ in range(3):
            service.evaluate(_snapshot_with_host(cpu=value))

    assert len(repo.alerts) == 1
    assert alert.status == AlertStatus.OPEN

    no_event_repo = FakeRepository()
    no_event_service = ResourceMonitorAlertService(no_event_repo)
    for value in invalid_values:
        for _ in range(3):
            no_event_service.evaluate(_snapshot_with_host(cpu=value))

    assert no_event_repo.alerts == []


def test_invalid_host_sample_resets_pressure_streak() -> None:
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)

    for _ in range(2):
        service.evaluate(_snapshot_with_host(cpu=85.0))
    service.evaluate(_snapshot_with_host(cpu=None))
    service.evaluate(_snapshot_with_host(cpu=85.0))

    assert repo.alerts == []


def test_invalid_host_sample_resets_recovery_streak() -> None:
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_host(cpu=85.0))
    alert = repo.alerts[0]
    for _ in range(2):
        service.evaluate(_snapshot_with_host(cpu=20.0))
    service.evaluate(_snapshot_with_host(cpu=None))
    service.evaluate(_snapshot_with_host(cpu=20.0))

    assert alert.status == AlertStatus.OPEN


def test_host_event_metadata_drops_raw_collection_errors() -> None:
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)
    snapshot = _snapshot_with_host(cpu=85.0)
    snapshot["host"]["error"] = "permission denied: /sensitive/path"

    for _ in range(3):
        service.evaluate(snapshot)

    assert "error" not in repo.alerts[0].metadata
    assert "permission denied" not in str(repo.alerts[0].metadata)


def test_all_alphafoundry_event_categories_have_an_explicit_source_scope() -> None:
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)
    snapshot = _snapshot_with_process(cpu=95.0)
    snapshot["status"] = "unavailable"
    snapshot["warnings"] = [{"code": "managed_process_unavailable", "pid": 101}]
    snapshot["task_failures"] = [{"task_id": "task-1", "task_kind": "crawl"}]

    for _ in range(3):
        service.evaluate(snapshot)

    assert {alert.metadata["event_kind"] for alert in repo.alerts} == {
        "task_failed",
        "monitor_sampling_failed",
        "managed_process_unavailable",
        "resource_pressure",
    }
    assert {alert.metadata["source_scope"] for alert in repo.alerts} == {"alphafoundry"}


def test_list_events_keeps_open_event_even_when_before_history_window() -> None:
    """历史窗口不会隐藏仍未解决的异常。"""
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)
    old = service._open_event(
        event_kind="task_failed",
        dedupe_key="task:old",
        severity=AlertSeverity.CRITICAL,
        metadata={"task_id": "old", "task_kind": "crawl"},
    )
    old.triggered_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    repo.save_alert(old)

    items = service.list_events(days=1, status="resolved")

    assert [item.alert_id for item in items] == [old.alert_id]
