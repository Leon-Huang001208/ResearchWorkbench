"""将受控资源异常转换为可持久化、可处置的监控告警。"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from core.contracts.monitoring import (
    AlertPayload,
    AlertSeverity,
    AlertStatus,
    IncidentRecord,
    Subsystem,
)
from core.observability import get_logger

logger = get_logger(__name__)

_PRESSURE_CPU_PERCENT = 90.0
_PRESSURE_MEMORY_BYTES = 1024 * 1024 * 1024
_HOST_CPU_WARNING_PERCENT = 85.0
_HOST_CPU_CRITICAL_PERCENT = 95.0
_HOST_MEMORY_WARNING_PERCENT = 15.0
_HOST_MEMORY_CRITICAL_PERCENT = 8.0
_CONSECUTIVE_SAMPLES = 3
_AUTO_RESOLVABLE_KINDS = frozenset(
    {
        "managed_process_unavailable",
        "monitor_sampling_failed",
        "resource_pressure",
        "host_cpu_pressure",
        "host_memory_pressure",
    }
)
_SAFE_METADATA_KEYS = frozenset(
    {
        "event_kind",
        "task_id",
        "task_kind",
        "source_key",
        "label",
        "pid",
        "role",
        "attribution_kind",
        "confidence",
        "error_type",
        "cpu_percent",
        "memory_bytes",
    }
)


@dataclass
class ResourceAlertState:
    """跨资源采样周期保留的告警计数状态。"""

    pressure_counts: Dict[str, int] = field(default_factory=dict)
    recovery_counts: Dict[str, int] = field(default_factory=dict)


class ResourceMonitorAlertService:
    """资源快照的异常去重、持久化、确认、恢复和历史查询。"""

    def __init__(self, repo: Any, *, state: Optional[ResourceAlertState] = None) -> None:
        self._repo = repo
        self._state = state if state is not None else ResourceAlertState()

    def evaluate(self, snapshot: Dict[str, Any]) -> list[AlertPayload]:
        """从一次受控快照创建或恢复资源异常，单项失败不得阻断采样。"""
        events: list[AlertPayload] = []
        try:
            events.extend(self._evaluate_task_failures(snapshot.get("task_failures", [])))
            events.extend(self._evaluate_sampling_status(snapshot))
            events.extend(self._evaluate_managed_process_warnings(snapshot.get("warnings", [])))
            events.extend(self._evaluate_pressure(snapshot.get("processes", [])))
            events.extend(self._evaluate_host_capacity(snapshot.get("host")))
        except Exception as exc:
            logger.warning(
                "resource monitor alert evaluation failed", error_type=type(exc).__name__
            )
        return events

    def list_events(
        self,
        *,
        days: int = 90,
        status: str = "all",
        severity: Optional[str] = None,
        task_kind: Optional[str] = None,
        source_key: Optional[str] = None,
    ) -> list[AlertPayload]:
        """查询资源事件；任何未恢复事件不受历史时间窗口限制。"""
        if days < 1:
            raise ValueError("days must be at least 1")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        normalized_status = status.lower()
        if normalized_status not in {"all", *[item.value for item in AlertStatus]}:
            raise ValueError("status is invalid")
        alerts = self._resource_alerts()
        selected: list[AlertPayload] = []
        for alert in alerts:
            if severity and alert.severity.value != severity:
                continue
            metadata = alert.metadata if isinstance(alert.metadata, dict) else {}
            if task_kind and metadata.get("task_kind") != task_kind:
                continue
            if source_key and metadata.get("source_key") != source_key:
                continue
            is_open = alert.status != AlertStatus.RESOLVED
            status_matches = normalized_status == "all" or alert.status.value == normalized_status
            if not status_matches and not is_open:
                continue
            if is_open or alert.triggered_at >= cutoff:
                selected.append(alert)
        return sorted(selected, key=lambda alert: alert.triggered_at, reverse=True)

    def acknowledge(self, alert_id: str) -> Optional[AlertPayload]:
        """将资源异常标记为已阅，已解决事件不回退状态。"""
        alert = self._find_resource_alert(alert_id)
        if alert is None or alert.status == AlertStatus.RESOLVED:
            return None
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now(timezone.utc)
        saved = self._repo.save_alert(alert)
        logger.info("resource monitor alert acknowledged", alert_id=alert_id)
        return saved

    def resolve(self, alert_id: str, *, notes: str = "") -> Optional[AlertPayload]:
        """人工解决资源异常，并同步关联事件记录。"""
        alert = self._find_resource_alert(alert_id)
        if alert is None:
            return None
        return self._resolve_alert(alert, notes=notes or "已人工解决。")

    def _evaluate_task_failures(self, failures: Any) -> list[AlertPayload]:
        events: list[AlertPayload] = []
        if not isinstance(failures, list):
            return events
        for failure in failures:
            if not isinstance(failure, dict) or not isinstance(failure.get("task_id"), str):
                continue
            events.append(
                self._open_event(
                    event_kind="task_failed",
                    dedupe_key=f"task_failed:{failure['task_id']}",
                    severity=AlertSeverity.CRITICAL,
                    metadata=failure,
                )
            )
        return events

    def _evaluate_sampling_status(self, snapshot: Dict[str, Any]) -> list[AlertPayload]:
        if snapshot.get("status") == "unavailable":
            return [
                self._open_event(
                    event_kind="monitor_sampling_failed",
                    dedupe_key="monitor_sampling_failed:api",
                    severity=AlertSeverity.WARNING,
                    metadata={"role": "API", "attribution_kind": "api"},
                )
            ]
        return self._resolve_auto_event("monitor_sampling_failed:api")

    def _evaluate_managed_process_warnings(self, warnings: Any) -> list[AlertPayload]:
        events: list[AlertPayload] = []
        unavailable_pids: set[int] = set()
        if isinstance(warnings, list):
            for warning in warnings:
                if (
                    not isinstance(warning, dict)
                    or warning.get("code") != "managed_process_unavailable"
                ):
                    continue
                pid = warning.get("pid")
                if not isinstance(pid, int):
                    continue
                unavailable_pids.add(pid)
                events.append(
                    self._open_event(
                        event_kind="managed_process_unavailable",
                        dedupe_key=f"managed_process_unavailable:{pid}",
                        severity=AlertSeverity.WARNING,
                        metadata={"pid": pid, "attribution_kind": "worker"},
                    )
                )
        for alert in self._resource_alerts():
            if alert.metadata.get("event_kind") != "managed_process_unavailable":
                continue
            pid = alert.metadata.get("pid")
            if isinstance(pid, int) and pid not in unavailable_pids:
                events.extend(self._resolve_auto_event(f"managed_process_unavailable:{pid}"))
        return events

    def _evaluate_pressure(self, processes: Any) -> list[AlertPayload]:
        events: list[AlertPayload] = []
        if not isinstance(processes, list):
            return events
        seen_keys: set[str] = set()
        for process in processes:
            if not isinstance(process, dict) or not isinstance(process.get("pid"), int):
                continue
            pid = process["pid"]
            key = f"resource_pressure:{pid}"
            seen_keys.add(key)
            cpu = process.get("cpu_percent")
            memory = process.get("memory_bytes")
            is_pressure = (
                isinstance(cpu, (int, float))
                and cpu >= _PRESSURE_CPU_PERCENT
                or isinstance(memory, (int, float))
                and memory >= _PRESSURE_MEMORY_BYTES
            )
            if is_pressure:
                self._state.pressure_counts[key] = self._state.pressure_counts.get(key, 0) + 1
                self._state.recovery_counts[key] = 0
                if self._state.pressure_counts[key] >= _CONSECUTIVE_SAMPLES:
                    events.append(
                        self._open_event(
                            event_kind="resource_pressure",
                            dedupe_key=key,
                            severity=AlertSeverity.WARNING,
                            metadata=process,
                        )
                    )
                continue
            self._state.pressure_counts[key] = 0
            self._state.recovery_counts[key] = self._state.recovery_counts.get(key, 0) + 1
            if self._state.recovery_counts[key] >= _CONSECUTIVE_SAMPLES:
                events.extend(self._resolve_auto_event(key))

        for key in list(self._state.pressure_counts):
            if key.startswith("resource_pressure:") and key not in seen_keys:
                self._state.pressure_counts.pop(key, None)
                self._state.recovery_counts.pop(key, None)
        return events

    def _evaluate_host_capacity(self, host: Any) -> list[AlertPayload]:
        """评估整机 CPU 与可用内存容量，不可用读数不能被当作恢复。"""
        if not isinstance(host, dict):
            self._reset_host_metric_streak("host_cpu_pressure")
            self._reset_host_metric_streak("host_memory_pressure")
            return []
        return [
            *self._evaluate_host_metric(
                dedupe_key="host_cpu_pressure",
                event_kind="host_cpu_pressure",
                value=host.get("cpu_percent"),
                warning_threshold=_HOST_CPU_WARNING_PERCENT,
                critical_threshold=_HOST_CPU_CRITICAL_PERCENT,
                pressure_when="above",
                host=host,
            ),
            *self._evaluate_host_metric(
                dedupe_key="host_memory_pressure",
                event_kind="host_memory_pressure",
                value=host.get("memory_available_percent"),
                warning_threshold=_HOST_MEMORY_WARNING_PERCENT,
                critical_threshold=_HOST_MEMORY_CRITICAL_PERCENT,
                pressure_when="below",
                host=host,
            ),
        ]

    def _evaluate_host_metric(
        self,
        *,
        dedupe_key: str,
        event_kind: str,
        value: Any,
        warning_threshold: float,
        critical_threshold: float,
        pressure_when: str,
        host: Dict[str, Any],
    ) -> list[AlertPayload]:
        """按 warning/critical 分别累计连续主机容量压力样本。"""
        warning_key = f"{dedupe_key}:warning"
        critical_key = f"{dedupe_key}:critical"
        if not self._is_valid_percent(value):
            self._reset_host_metric_streak(dedupe_key)
            return []

        numeric_value = float(value)
        if pressure_when == "above":
            is_warning = numeric_value >= warning_threshold
            is_critical = numeric_value >= critical_threshold
        else:
            is_warning = numeric_value <= warning_threshold
            is_critical = numeric_value <= critical_threshold

        if not is_warning:
            self._state.pressure_counts[warning_key] = 0
            self._state.pressure_counts[critical_key] = 0
            self._state.recovery_counts[dedupe_key] = (
                self._state.recovery_counts.get(dedupe_key, 0) + 1
            )
            if self._state.recovery_counts[dedupe_key] >= _CONSECUTIVE_SAMPLES:
                return self._resolve_auto_event(dedupe_key)
            return []

        self._state.recovery_counts[dedupe_key] = 0
        self._state.pressure_counts[warning_key] = (
            self._state.pressure_counts.get(warning_key, 0) + 1
        )
        if is_critical:
            self._state.pressure_counts[critical_key] = (
                self._state.pressure_counts.get(critical_key, 0) + 1
            )
        else:
            self._state.pressure_counts[critical_key] = 0

        severity: Optional[AlertSeverity] = None
        threshold: Optional[float] = None
        if self._state.pressure_counts[critical_key] >= _CONSECUTIVE_SAMPLES:
            severity = AlertSeverity.CRITICAL
            threshold = critical_threshold
        elif self._state.pressure_counts[warning_key] >= _CONSECUTIVE_SAMPLES:
            severity = AlertSeverity.WARNING
            threshold = warning_threshold
        if severity is None or threshold is None:
            return []

        return [
            self._open_or_upgrade_host_event(
                event_kind=event_kind,
                dedupe_key=dedupe_key,
                severity=severity,
                threshold_percent=threshold,
                host=host,
            )
        ]

    def _reset_host_metric_streak(self, dedupe_key: str) -> None:
        """无效主机读数中断该指标的压力与恢复连续计数。"""
        self._state.pressure_counts[f"{dedupe_key}:warning"] = 0
        self._state.pressure_counts[f"{dedupe_key}:critical"] = 0
        self._state.recovery_counts[dedupe_key] = 0

    def _open_or_upgrade_host_event(
        self,
        *,
        event_kind: str,
        dedupe_key: str,
        severity: AlertSeverity,
        threshold_percent: float,
        host: Dict[str, Any],
    ) -> AlertPayload:
        """创建主机容量事件，或仅向上更新同一未解决事件。"""
        metadata = self._safe_host_metadata(
            host,
            event_kind=event_kind,
            dedupe_key=dedupe_key,
            threshold_percent=threshold_percent,
        )
        existing = self._find_open_by_dedupe_key(dedupe_key)
        if existing is None:
            return self._create_event(
                event_kind=event_kind,
                dedupe_key=dedupe_key,
                severity=severity,
                metadata=metadata,
                threshold_value=threshold_percent,
                open_dedupe_key=dedupe_key,
            )
        if severity == AlertSeverity.CRITICAL and existing.severity != AlertSeverity.CRITICAL:
            update_details = getattr(self._repo, "update_alert_details_if_unresolved", None)
            if not callable(update_details):
                logger.warning(
                    "resource monitor host event upgrade unavailable",
                    alert_id=existing.alert_id,
                    error_type="NotImplementedError",
                )
                return existing
            saved = update_details(
                alert_id=existing.alert_id,
                severity=severity,
                title=self._title_for(event_kind, metadata),
                description=self._description_for(event_kind, metadata),
                threshold_value=threshold_percent,
                metadata=metadata,
            )
            if saved is None:
                return existing
            if saved.status != AlertStatus.RESOLVED and saved.severity == AlertSeverity.CRITICAL:
                logger.warning(
                    "resource monitor host event upgraded",
                    alert_id=saved.alert_id,
                    event_kind=event_kind,
                    dedupe_key=dedupe_key,
                )
            return saved
        return existing

    def _open_event(
        self,
        *,
        event_kind: str,
        dedupe_key: str,
        severity: AlertSeverity,
        metadata: Dict[str, Any],
    ) -> AlertPayload:
        existing = self._find_open_by_dedupe_key(dedupe_key)
        if existing is not None:
            return existing
        safe_metadata = self._safe_metadata(metadata)
        safe_metadata.update(
            {
                "event_kind": event_kind,
                "dedupe_key": dedupe_key,
                "source_scope": "alphafoundry",
            }
        )
        return self._create_event(
            event_kind=event_kind,
            dedupe_key=dedupe_key,
            severity=severity,
            metadata=safe_metadata,
            open_dedupe_key=dedupe_key,
        )

    def _create_event(
        self,
        *,
        event_kind: str,
        dedupe_key: str,
        severity: AlertSeverity,
        metadata: Dict[str, Any],
        threshold_value: float = 0.0,
        open_dedupe_key: Optional[str] = None,
    ) -> AlertPayload:
        alert = AlertPayload(
            alert_id=f"resource-{uuid.uuid4().hex[:12]}",
            threshold_id=f"resource-{event_kind}",
            subsystem=Subsystem.RESOURCE_MONITORING,
            severity=severity,
            title=self._title_for(event_kind, metadata),
            description=self._description_for(event_kind, metadata),
            threshold_value=threshold_value,
            triggered_at=datetime.now(timezone.utc),
            metadata=metadata,
        )
        created = True
        get_or_create = getattr(self._repo, "get_or_create_open_resource_alert", None)
        if open_dedupe_key is not None and callable(get_or_create):
            saved, created = get_or_create(alert, open_dedupe_key)
        else:
            saved = self._repo.save_alert(alert)
        if created:
            incident = IncidentRecord(
                incident_id=f"resource-incident-{uuid.uuid4().hex[:12]}",
                alert_id=saved.alert_id,
                subsystem=Subsystem.RESOURCE_MONITORING,
                severity=saved.severity,
                title=saved.title,
                description=saved.description,
                detected_at=saved.triggered_at,
                metadata=saved.metadata,
            )
            self._repo.save_incident(incident)
            logger.warning(
                "resource monitor event opened",
                alert_id=saved.alert_id,
                event_kind=event_kind,
                dedupe_key=dedupe_key,
            )
        return saved

    def _resolve_auto_event(self, dedupe_key: str) -> list[AlertPayload]:
        alert = self._find_open_by_dedupe_key(dedupe_key)
        if alert is None or alert.metadata.get("event_kind") not in _AUTO_RESOLVABLE_KINDS:
            return []
        return [self._resolve_alert(alert, notes="监控连续采样恢复正常。")]

    def _resolve_alert(self, alert: AlertPayload, *, notes: str) -> AlertPayload:
        if alert.status != AlertStatus.RESOLVED:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now(timezone.utc)
            alert = self._repo.save_alert(alert)
            self._resolve_incidents(alert.alert_id, notes=notes)
            logger.info("resource monitor alert resolved", alert_id=alert.alert_id)
        return alert

    def _resolve_incidents(self, alert_id: str, *, notes: str) -> None:
        try:
            incidents: Iterable[IncidentRecord] = self._repo.list_incidents(
                subsystem=Subsystem.RESOURCE_MONITORING,
                resolved=False,
                limit=5000,
            )
        except Exception as exc:
            logger.warning("resource monitor incident lookup failed", error_type=type(exc).__name__)
            return
        for incident in incidents:
            if incident.alert_id != alert_id or incident.resolved_at is not None:
                continue
            incident.resolved_at = datetime.now(timezone.utc)
            incident.resolution_notes = notes[:500]
            self._repo.save_incident(incident)

    def _resource_alerts(self) -> list[AlertPayload]:
        try:
            alerts = self._repo.list_alerts(subsystem=Subsystem.RESOURCE_MONITORING, limit=5000)
        except Exception as exc:
            logger.warning("resource monitor alert lookup failed", error_type=type(exc).__name__)
            return []
        return [
            alert
            for alert in alerts
            if isinstance(alert, AlertPayload) and alert.subsystem == Subsystem.RESOURCE_MONITORING
        ]

    def _find_open_by_dedupe_key(self, dedupe_key: str) -> Optional[AlertPayload]:
        for alert in self._resource_alerts():
            if (
                alert.status != AlertStatus.RESOLVED
                and alert.metadata.get("dedupe_key") == dedupe_key
            ):
                return alert
        return None

    def _find_resource_alert(self, alert_id: str) -> Optional[AlertPayload]:
        return next(
            (alert for alert in self._resource_alerts() if alert.alert_id == alert_id), None
        )

    @staticmethod
    def _safe_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: value
            for key, value in metadata.items()
            if key in _SAFE_METADATA_KEYS and isinstance(value, (str, int, float, type(None)))
        }

    @staticmethod
    def _safe_host_metadata(
        host: Dict[str, Any],
        *,
        event_kind: str,
        dedupe_key: str,
        threshold_percent: float,
    ) -> Dict[str, Any]:
        """仅保留公开整机容量指标，避免持久化原始采集错误。"""
        metadata: Dict[str, Any] = {
            "event_kind": event_kind,
            "source_scope": "host_capacity",
            "threshold_percent": threshold_percent,
            "dedupe_key": dedupe_key,
        }
        cpu_percent = host.get("cpu_percent")
        if ResourceMonitorAlertService._is_valid_percent(cpu_percent):
            metadata["host_cpu_percent"] = float(cpu_percent)
        memory_available_percent = host.get("memory_available_percent")
        if ResourceMonitorAlertService._is_valid_percent(memory_available_percent):
            metadata["host_memory_available_percent"] = float(memory_available_percent)
        return metadata

    @staticmethod
    def _is_valid_percent(value: Any) -> bool:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        numeric_value = float(value)
        return math.isfinite(numeric_value) and 0.0 <= numeric_value <= 100.0

    @staticmethod
    def _title_for(event_kind: str, metadata: Dict[str, Any]) -> str:
        if event_kind == "task_failed":
            return f"任务失败：{metadata.get('label') or metadata.get('task_kind') or 'AlphaFoundry 任务'}"
        if event_kind == "resource_pressure":
            role = metadata.get("role")
            process_label = (
                role if isinstance(role, str) and role else f"PID {metadata.get('pid', '未知')}"
            )
            return f"资源压力：{process_label}"
        if event_kind == "managed_process_unavailable":
            return f"受控 Worker 不可用：PID {metadata.get('pid', '未知')}"
        if event_kind == "host_cpu_pressure":
            return "整机 CPU 容量压力"
        if event_kind == "host_memory_pressure":
            return "整机可用内存容量压力"
        return "资源监控采样不可用"

    @staticmethod
    def _description_for(event_kind: str, metadata: Dict[str, Any]) -> str:
        if event_kind == "task_failed":
            return "任务执行失败；请查看 AlphaFoundry 日志获取受控诊断信息。"
        if event_kind == "resource_pressure":
            return "受控进程连续三个采样周期超出资源压力阈值。"
        if event_kind == "managed_process_unavailable":
            return "已登记的 AlphaFoundry Worker 在采样时不可用。"
        if event_kind == "host_cpu_pressure":
            return "整机 CPU 连续三个采样周期达到 " f"{metadata.get('threshold_percent')}% 容量压力阈值。"
        if event_kind == "host_memory_pressure":
            return "整机可用内存连续三个采样周期低于 " f"{metadata.get('threshold_percent')}% 容量压力阈值。"
        return "AlphaFoundry API 进程资源采样暂不可用。"
