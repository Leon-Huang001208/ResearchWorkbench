"""Monitoring 仓储的条件告警详情更新测试。"""

from datetime import datetime, timezone

from core.contracts.monitoring import AlertPayload, AlertSeverity, AlertStatus, Subsystem
from data_layer.repositories.monitoring_repository import MonitoringRepositoryImpl


def _alert(*, status: AlertStatus, alert_id: str) -> AlertPayload:
    return AlertPayload(
        alert_id=alert_id,
        threshold_id="resource-host_cpu_pressure",
        subsystem=Subsystem.RESOURCE_MONITORING,
        severity=AlertSeverity.WARNING,
        status=status,
        title="旧标题",
        description="旧描述",
        threshold_value=85.0,
        triggered_at=datetime.now(timezone.utc),
        acknowledged_at=(
            datetime.now(timezone.utc) if status == AlertStatus.ACKNOWLEDGED else None
        ),
        resolved_at=(datetime.now(timezone.utc) if status == AlertStatus.RESOLVED else None),
        metadata={"event_kind": "host_cpu_pressure", "threshold_percent": 85.0},
    )


def test_update_alert_details_if_unresolved_preserves_acknowledgement(db_session) -> None:
    repo = MonitoringRepositoryImpl(db_session)
    original = repo.save_alert(_alert(status=AlertStatus.ACKNOWLEDGED, alert_id="alert-ack"))

    updated = repo.update_alert_details_if_unresolved(
        alert_id=original.alert_id,
        severity=AlertSeverity.CRITICAL,
        title="新标题",
        description="新描述",
        threshold_value=95.0,
        metadata={"event_kind": "host_cpu_pressure", "threshold_percent": 95.0},
    )

    assert updated is not None
    assert updated.status == AlertStatus.ACKNOWLEDGED
    assert updated.acknowledged_at is not None
    assert updated.acknowledged_at.replace(tzinfo=None) == original.acknowledged_at.replace(
        tzinfo=None
    )
    assert updated.resolved_at is None
    assert updated.severity == AlertSeverity.CRITICAL
    assert updated.title == "新标题"
    assert updated.threshold_value == 95.0


def test_update_alert_details_if_unresolved_does_not_modify_resolved_alert(db_session) -> None:
    repo = MonitoringRepositoryImpl(db_session)
    original = repo.save_alert(_alert(status=AlertStatus.RESOLVED, alert_id="alert-resolved"))

    updated = repo.update_alert_details_if_unresolved(
        alert_id=original.alert_id,
        severity=AlertSeverity.CRITICAL,
        title="不应写入",
        description="不应写入",
        threshold_value=95.0,
        metadata={"event_kind": "host_cpu_pressure", "threshold_percent": 95.0},
    )

    assert updated is not None
    assert updated.status == AlertStatus.RESOLVED
    assert updated.resolved_at is not None
    assert updated.resolved_at.replace(tzinfo=None) == original.resolved_at.replace(tzinfo=None)
    assert updated.severity == AlertSeverity.WARNING
    assert updated.title == "旧标题"
    assert updated.threshold_value == 85.0
