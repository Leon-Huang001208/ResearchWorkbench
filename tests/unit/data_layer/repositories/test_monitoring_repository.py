"""Monitoring 仓储的条件告警详情更新测试。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.contracts.monitoring import AlertPayload, AlertSeverity, AlertStatus, Subsystem
from data_layer.repositories.base import Base
from data_layer.repositories.models import AlertPayloadDB
from data_layer.repositories.monitoring_repository import MonitoringRepositoryImpl
from services.resource_monitor_alert_service import ResourceMonitorAlertService


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


def _host_snapshot(cpu_percent: float) -> dict[str, object]:
    return {
        "status": "ok",
        "warnings": [],
        "task_failures": [],
        "processes": [],
        "host": {"cpu_percent": cpu_percent, "memory_available_percent": 50.0},
    }


def _task_failure_snapshot() -> dict[str, object]:
    return {
        "status": "ok",
        "warnings": [],
        "processes": [],
        "host": {},
        "task_failures": [{"task_id": "concurrent-task", "task_kind": "crawl"}],
    }


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


def test_concurrent_host_services_create_one_open_event_per_cycle(tmp_path) -> None:
    database_path = tmp_path / "monitoring-alerts.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}", connect_args={"check_same_thread": False, "timeout": 5}
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    barrier = Barrier(2)

    def evaluate_third_sample() -> None:
        session = session_factory()
        try:
            service = ResourceMonitorAlertService(MonitoringRepositoryImpl(session))
            service.evaluate(_host_snapshot(85.0))
            service.evaluate(_host_snapshot(85.0))
            barrier.wait()
            service.evaluate(_host_snapshot(85.0))
            session.commit()
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _: evaluate_third_sample(), range(2)))

    verification_session = session_factory()
    try:
        events = (
            verification_session.query(AlertPayloadDB)
            .filter(
                AlertPayloadDB.status != AlertStatus.RESOLVED.value,
                AlertPayloadDB.alert_metadata["dedupe_key"].as_string() == "host_cpu_pressure",
            )
            .all()
        )
        assert len(events) == 1
        assert events[0].status == AlertStatus.OPEN.value
    finally:
        verification_session.close()
        Base.metadata.drop_all(bind=engine)


def test_concurrent_task_failure_services_create_one_open_event(tmp_path) -> None:
    database_path = tmp_path / "monitoring-task-alerts.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}", connect_args={"check_same_thread": False, "timeout": 5}
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    barrier = Barrier(2)

    def evaluate_failure() -> None:
        session = session_factory()
        try:
            service = ResourceMonitorAlertService(MonitoringRepositoryImpl(session))
            barrier.wait()
            service.evaluate(_task_failure_snapshot())
            session.commit()
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _: evaluate_failure(), range(2)))

    verification_session = session_factory()
    try:
        events = (
            verification_session.query(AlertPayloadDB)
            .filter(
                AlertPayloadDB.status != AlertStatus.RESOLVED.value,
                AlertPayloadDB.alert_metadata["dedupe_key"].as_string()
                == "task_failed:concurrent-task",
            )
            .all()
        )
        assert len(events) == 1
        assert events[0].status == AlertStatus.OPEN.value
    finally:
        verification_session.close()
        Base.metadata.drop_all(bind=engine)


def test_host_pressure_after_resolution_creates_a_new_alert_cycle(db_session) -> None:
    repo = MonitoringRepositoryImpl(db_session)
    first_service = ResourceMonitorAlertService(repo)
    for _ in range(3):
        first_service.evaluate(_host_snapshot(85.0))
    first = repo.list_alerts(subsystem=Subsystem.RESOURCE_MONITORING)[0]
    assert first_service.resolve(first.alert_id) is not None

    next_service = ResourceMonitorAlertService(repo)
    for _ in range(3):
        next_service.evaluate(_host_snapshot(85.0))

    alerts = repo.list_alerts(subsystem=Subsystem.RESOURCE_MONITORING)
    assert len(alerts) == 2
    assert {alert.status for alert in alerts} == {AlertStatus.OPEN, AlertStatus.RESOLVED}
    assert len({alert.alert_id for alert in alerts}) == 2
