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

    def save_incident(self, incident):
        for index, existing in enumerate(self.incidents):
            if existing.incident_id == incident.incident_id:
                self.incidents[index] = incident
                return incident
        self.incidents.append(incident)
        return incident

    def list_incidents(self, **_: object):
        return list(self.incidents)


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


def test_pressure_opens_once_then_resolves_after_three_recovered_samples() -> None:
    """连续压力只创建一个事件，连续恢复后自动解决。"""
    repo = FakeRepository()
    service = ResourceMonitorAlertService(repo)

    for _ in range(3):
        service.evaluate(_snapshot_with_process(cpu=95.0))

    assert len(repo.alerts) == 1
    alert = repo.alerts[0]
    assert alert.metadata["event_kind"] == "resource_pressure"
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
    assert len(repo.incidents) == 1


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
