"""
Core contracts for production monitoring, drift detection, and alerting.

This module defines Pydantic models for health metrics collection, data drift
detection, alert triggering, and incident recording in AlphaFoundry, ensuring
consistent monitoring and alerting across subsystems.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ─── 子系统枚举 ────────────────────────────────────────


class Subsystem(str, Enum):
    """被监控的子系统.

    Enumeration of subsystems that are monitored in AlphaFoundry.

    Attributes:
        INGESTION: Ingestion subsystem.
        EXTRACTION: Extraction subsystem.
        MAPPING: Mapping subsystem.
        SIGNAL_GENERATION: Signal generation subsystem.
        TIMING: Timing subsystem.
        REPLAY: Replay subsystem.
        PORTFOLIO_SIMULATION: Portfolio simulation subsystem.
    """

    INGESTION = "ingestion"
    EXTRACTION = "extraction"
    MAPPING = "mapping"
    SIGNAL_GENERATION = "signal_generation"
    TIMING = "timing"
    REPLAY = "replay"
    PORTFOLIO_SIMULATION = "portfolio_simulation"
    RESOURCE_MONITORING = "resource_monitoring"


class AlertSeverity(str, Enum):
    """告警严重级别.

    Enumeration of alert severity levels.

    Attributes:
        INFO: Informational alert (lowest severity).
        WARNING: Warning alert (medium severity).
        CRITICAL: Critical alert (highest severity).
    """

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """告警状态.

    Enumeration of alert statuses.

    Attributes:
        OPEN: Alert is open (not acknowledged or resolved).
        ACKNOWLEDGED: Alert has been acknowledged but not resolved.
        RESOLVED: Alert has been resolved.
    """

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


# ─── 健康指标 ──────────────────────────────────────────


class HealthMetrics(BaseModel):
    """子系统健康指标快照.

    Each subsystem reports periodically, including throughput, error rate,
    latency, queue depth, and other dimensions.

    Attributes:
        metric_id: Unique identifier for the metrics snapshot.
        subsystem: Subsystem that these metrics belong to.
        timestamp: Timestamp when these metrics were collected.
        throughput: Throughput in items per second (default 0.0).
        error_rate: Error rate (0.0 to 1.0) (default 0.0).
        avg_latency_ms: Average latency in milliseconds (default 0.0).
        p99_latency_ms: 99th percentile latency in milliseconds (default 0.0).
        queue_depth: Queue backlog depth (default 0).
        items_processed: Number of items processed (default 0).
        items_failed: Number of items failed (default 0).
        extra: Subsystem-specific extra metrics as a dictionary.
    """

    metric_id: str = Field(description="Unique identifier for the metrics snapshot")
    subsystem: Subsystem = Field(description="Subsystem that these metrics belong to")
    timestamp: datetime = Field(description="Timestamp when these metrics were collected")
    throughput: float = Field(default=0.0, description="Throughput in items per second")
    error_rate: float = Field(default=0.0, description="Error rate (0.0 to 1.0)")
    avg_latency_ms: float = Field(default=0.0, description="Average latency in milliseconds")
    p99_latency_ms: float = Field(
        default=0.0, description="99th percentile latency in milliseconds"
    )
    queue_depth: int = Field(default=0, description="Queue backlog depth")
    items_processed: int = Field(default=0, description="Number of items processed")
    items_failed: int = Field(default=0, description="Number of items failed")
    extra: Dict[str, Any] = Field(
        default_factory=dict, description="Subsystem-specific extra metrics"
    )


# ─── 漂移报告 ──────────────────────────────────────────


class DriftDimension(str, Enum):
    """漂移检测维度.

    Enumeration of dimensions for drift detection.

    Attributes:
        SOURCE_MIX: Data source mix/distribution.
        EVENT_TYPE_MIX: Event type distribution.
        MAPPING_HIT_RATE: Mapping hit rate.
        SIGNAL_VOLUME: Signal generation volume.
        READINESS_DISTRIBUTION: Timing readiness distribution.
        OUTCOME_DISTRIBUTION: Outcome distribution.
    """

    SOURCE_MIX = "source_mix"  # 数据源占比分布
    EVENT_TYPE_MIX = "event_type_mix"  # 事件类型分布
    MAPPING_HIT_RATE = "mapping_hit_rate"  # 映射命中率
    SIGNAL_VOLUME = "signal_volume"  # 信号生成量
    READINESS_DISTRIBUTION = "readiness_distribution"  # Timing readiness 分布
    OUTCOME_DISTRIBUTION = "outcome_distribution"  # 结果分布


class DriftReport(BaseModel):
    """漂移检测报告.

    Compares the distribution difference between the current window and a baseline
    window, quantifying the drift severity for each dimension.

    Attributes:
        report_id: Unique identifier for the drift report.
        dimension: Drift dimension that was checked.
        timestamp: Timestamp when the report was generated.
        baseline_window_start: Start of the baseline window.
        baseline_window_end: End of the baseline window.
        current_window_start: Start of the current window.
        current_window_end: End of the current window.
        drift_score: Drift score (0.0 to 1.0, higher means more severe drift).
        is_drift: Whether drift was detected (score exceeded threshold).
        threshold: Threshold used for drift detection.
        baseline_distribution: Distribution of the dimension in the baseline window.
        current_distribution: Distribution of the dimension in the current window.
        details: Additional details as a dictionary.
    """

    report_id: str = Field(description="Unique identifier for the drift report")
    dimension: DriftDimension = Field(description="Drift dimension that was checked")
    timestamp: datetime = Field(description="Timestamp when the report was generated")
    baseline_window_start: datetime = Field(description="Start of the baseline window")
    baseline_window_end: datetime = Field(description="End of the baseline window")
    current_window_start: datetime = Field(description="Start of the current window")
    current_window_end: datetime = Field(description="End of the current window")
    drift_score: float = Field(
        description="Drift score (0.0 to 1.0, higher means more severe drift)"
    )
    is_drift: bool = Field(description="Whether drift was detected (score exceeded threshold)")
    threshold: float = Field(description="Threshold used for drift detection")
    baseline_distribution: Dict[str, float] = Field(
        default_factory=dict, description="Distribution in the baseline window"
    )
    current_distribution: Dict[str, float] = Field(
        default_factory=dict, description="Distribution in the current window"
    )
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")


# ─── 告警 ─────────────────────────────────────────────


class AlertThreshold(BaseModel):
    """告警阈值配置.

    Defines the alert triggering conditions for a specific metric or dimension.

    Attributes:
        threshold_id: Unique identifier for the threshold.
        name: Name of the threshold.
        subsystem: Optional subsystem that this threshold applies to.
        dimension: Optional drift dimension that this threshold applies to.
        metric_field: Optional field name from HealthMetrics (e.g., "error_rate").
        operator: Comparison operator ("gte", "lte", "eq", "gt", "lt") (default "gte").
        value: Threshold value (default 0.0).
        severity: Severity level for alerts from this threshold (default WARNING).
        cooldown_minutes: Cooldown time in minutes to avoid alert storms (default 30).
        enabled: Whether this threshold is enabled (default True).
    """

    threshold_id: str = Field(description="Unique identifier for the threshold")
    name: str = Field(description="Name of the threshold")
    subsystem: Optional[Subsystem] = Field(
        default=None, description="Optional subsystem that this threshold applies to"
    )
    dimension: Optional[DriftDimension] = Field(
        default=None, description="Optional drift dimension that this threshold applies to"
    )
    metric_field: Optional[str] = Field(
        default=None, description="Optional HealthMetrics field name (e.g., error_rate)"
    )
    operator: str = Field(default="gte", description="Comparison operator (gte, lte, eq, gt, lt)")
    value: float = Field(default=0.0, description="Threshold value")
    severity: AlertSeverity = Field(
        default=AlertSeverity.WARNING, description="Severity level for alerts from this threshold"
    )
    cooldown_minutes: int = Field(
        default=30, description="Cooldown time in minutes to avoid alert storms"
    )
    enabled: bool = Field(default=True, description="Whether this threshold is enabled")


class AlertPayload(BaseModel):
    """告警载荷.

    Complete alert record generated after an alert is triggered.

    Attributes:
        alert_id: Unique identifier for the alert.
        threshold_id: Unique identifier of the threshold that triggered this alert.
        severity: Severity level of the alert.
        status: Status of the alert (default OPEN).
        subsystem: Optional subsystem associated with this alert.
        dimension: Optional drift dimension associated with this alert.
        title: Title of the alert.
        description: Description of the alert (default "").
        observed_value: Observed value that triggered the alert (default 0.0).
        threshold_value: Threshold value that was crossed (default 0.0).
        triggered_at: Timestamp when the alert was triggered.
        acknowledged_at: Timestamp when the alert was acknowledged (if applicable).
        resolved_at: Timestamp when the alert was resolved (if applicable).
        metadata: Additional metadata as a dictionary.
    """

    alert_id: str = Field(description="Unique identifier for the alert")
    threshold_id: str = Field(
        description="Unique identifier of the threshold that triggered this alert"
    )
    severity: AlertSeverity = Field(description="Severity level of the alert")
    status: AlertStatus = Field(default=AlertStatus.OPEN, description="Status of the alert")
    subsystem: Optional[Subsystem] = Field(
        default=None, description="Optional subsystem associated with this alert"
    )
    dimension: Optional[DriftDimension] = Field(
        default=None, description="Optional drift dimension associated with this alert"
    )
    title: str = Field(description="Title of the alert")
    description: str = Field(default="", description="Description of the alert")
    observed_value: float = Field(
        default=0.0, description="Observed value that triggered the alert"
    )
    threshold_value: float = Field(default=0.0, description="Threshold value that was crossed")
    triggered_at: datetime = Field(description="Timestamp when the alert was triggered")
    acknowledged_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the alert was acknowledged (if applicable)"
    )
    resolved_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the alert was resolved (if applicable)"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# ─── 事件记录 ──────────────────────────────────────────


class IncidentRecord(BaseModel):
    """事件记录.

    Persistently stored incident record for later investigation and auditing.

    Attributes:
        incident_id: Unique identifier for the incident.
        alert_id: Unique identifier of the associated alert.
        subsystem: Subsystem associated with the incident.
        severity: Severity level of the incident.
        title: Title of the incident.
        description: Description of the incident (default "").
        detected_at: Timestamp when the incident was detected.
        resolved_at: Timestamp when the incident was resolved (if applicable).
        resolution_notes: Notes about how the incident was resolved (default "").
        metadata: Additional metadata as a dictionary.
    """

    incident_id: str = Field(description="Unique identifier for the incident")
    alert_id: str = Field(description="Unique identifier of the associated alert")
    subsystem: Subsystem = Field(description="Subsystem associated with the incident")
    severity: AlertSeverity = Field(description="Severity level of the incident")
    title: str = Field(description="Title of the incident")
    description: str = Field(default="", description="Description of the incident")
    detected_at: datetime = Field(description="Timestamp when the incident was detected")
    resolved_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the incident was resolved (if applicable)"
    )
    resolution_notes: str = Field(
        default="", description="Notes about how the incident was resolved"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# ─── 仪表盘摘要 ───────────────────────────────────────


class SubsystemHealthSummary(BaseModel):
    """子系统健康摘要.

    Summary of a subsystem's health, including subsystem, latest metrics, status,
    and number of open alerts.

    Attributes:
        subsystem: Subsystem that this summary is for.
        latest_metrics: Latest health metrics for the subsystem (if available).
        status: Health status ("healthy", "degraded", "unhealthy", "unknown") (default "unknown").
        open_alerts: Number of open alerts for the subsystem (default 0).
    """

    subsystem: Subsystem = Field(description="Subsystem that this summary is for")
    latest_metrics: Optional[HealthMetrics] = Field(
        default=None, description="Latest health metrics for the subsystem (if available)"
    )
    status: str = Field(
        default="unknown", description="Health status (healthy, degraded, unhealthy, unknown)"
    )
    open_alerts: int = Field(default=0, description="Number of open alerts for the subsystem")


class SystemHealthDashboard(BaseModel):
    """系统健康仪表盘.

    Dashboard showing overall system health, including generation timestamp,
    subsystem summaries, total open alerts, total open critical alerts, and
    recent incidents.

    Attributes:
        generated_at: Timestamp when the dashboard was generated.
        subsystems: List of subsystem health summaries.
        total_open_alerts: Total number of open alerts across all subsystems (default 0).
        total_open_critical: Total number of open critical alerts (default 0).
        recent_incidents: List of recent incident records.
    """

    generated_at: datetime = Field(description="Timestamp when the dashboard was generated")
    subsystems: List[SubsystemHealthSummary] = Field(
        default_factory=list, description="List of subsystem health summaries"
    )
    total_open_alerts: int = Field(
        default=0, description="Total number of open alerts across all subsystems"
    )
    total_open_critical: int = Field(default=0, description="Total number of open critical alerts")
    recent_incidents: List[IncidentRecord] = Field(
        default_factory=list, description="List of recent incident records"
    )


# ─── 请求模型 ──────────────────────────────────────────


class AlertThresholdCreateRequest(BaseModel):
    """创建告警阈值请求.

    Request schema for creating a new alert threshold, including name, subsystem,
    dimension, metric field, operator, value, severity, cooldown, and enabled status.

    Attributes:
        name: Name of the threshold.
        subsystem: Optional subsystem that this threshold applies to.
        dimension: Optional drift dimension that this threshold applies to.
        metric_field: Optional field name from HealthMetrics (e.g., "error_rate").
        operator: Comparison operator ("gte", "lte", "eq", "gt", "lt") (default "gte").
        value: Threshold value (default 0.0).
        severity: Severity level for alerts from this threshold (default WARNING).
        cooldown_minutes: Cooldown time in minutes to avoid alert storms (default 30).
        enabled: Whether this threshold is enabled (default True).
    """

    name: str = Field(description="Name of the threshold")
    subsystem: Optional[Subsystem] = Field(
        default=None, description="Optional subsystem that this threshold applies to"
    )
    dimension: Optional[DriftDimension] = Field(
        default=None, description="Optional drift dimension that this threshold applies to"
    )
    metric_field: Optional[str] = Field(
        default=None, description="Optional HealthMetrics field name (e.g., error_rate)"
    )
    operator: str = Field(default="gte", description="Comparison operator (gte, lte, eq, gt, lt)")
    value: float = Field(default=0.0, description="Threshold value")
    severity: AlertSeverity = Field(
        default=AlertSeverity.WARNING, description="Severity level for alerts from this threshold"
    )
    cooldown_minutes: int = Field(
        default=30, description="Cooldown time in minutes to avoid alert storms"
    )
    enabled: bool = Field(default=True, description="Whether this threshold is enabled")


class AlertThresholdUpdateRequest(BaseModel):
    """更新告警阈值请求.

    Request schema for updating an existing alert threshold, with optional fields
    for name, value, operator, severity, cooldown, and enabled status.

    Attributes:
        name: Optional new name for the threshold.
        value: Optional new threshold value.
        operator: Optional new comparison operator.
        severity: Optional new severity level.
        cooldown_minutes: Optional new cooldown time in minutes.
        enabled: Optional new enabled status.
    """

    name: Optional[str] = Field(default=None, description="Optional new name for the threshold")
    value: Optional[float] = Field(default=None, description="Optional new threshold value")
    operator: Optional[str] = Field(default=None, description="Optional new comparison operator")
    severity: Optional[AlertSeverity] = Field(
        default=None, description="Optional new severity level"
    )
    cooldown_minutes: Optional[int] = Field(
        default=None, description="Optional new cooldown time in minutes"
    )
    enabled: Optional[bool] = Field(default=None, description="Optional new enabled status")


class HealthMetricsSubmitRequest(BaseModel):
    """提交健康指标请求.

    Request schema for submitting health metrics for a subsystem, including
    subsystem, throughput, error rate, latency, queue depth, items processed/failed,
    and extra metrics.

    Attributes:
        subsystem: Subsystem that these metrics belong to.
        throughput: Throughput in items per second (default 0.0).
        error_rate: Error rate (0.0 to 1.0) (default 0.0).
        avg_latency_ms: Average latency in milliseconds (default 0.0).
        p99_latency_ms: 99th percentile latency in milliseconds (default 0.0).
        queue_depth: Queue backlog depth (default 0).
        items_processed: Number of items processed (default 0).
        items_failed: Number of items failed (default 0).
        extra: Subsystem-specific extra metrics as a dictionary.
    """

    subsystem: Subsystem = Field(description="Subsystem that these metrics belong to")
    throughput: float = Field(default=0.0, description="Throughput in items per second")
    error_rate: float = Field(default=0.0, description="Error rate (0.0 to 1.0)")
    avg_latency_ms: float = Field(default=0.0, description="Average latency in milliseconds")
    p99_latency_ms: float = Field(
        default=0.0, description="99th percentile latency in milliseconds"
    )
    queue_depth: int = Field(default=0, description="Queue backlog depth")
    items_processed: int = Field(default=0, description="Number of items processed")
    items_failed: int = Field(default=0, description="Number of items failed")
    extra: Dict[str, Any] = Field(
        default_factory=dict, description="Subsystem-specific extra metrics"
    )


class DriftCheckRequest(BaseModel):
    """漂移检测请求.

    Request schema for checking drift in a specific dimension, including dimension,
    baseline window hours, current window hours, and optional threshold.

    Attributes:
        dimension: Drift dimension to check.
        baseline_window_hours: Length of the baseline window in hours (default 168, 7 days).
        current_window_hours: Length of the current window in hours (default 24, 1 day).
        threshold: Optional threshold to use (uses default if not provided).
    """

    dimension: DriftDimension = Field(description="Drift dimension to check")
    baseline_window_hours: int = Field(
        default=168, description="Length of the baseline window in hours (default 7 days)"
    )
    current_window_hours: int = Field(
        default=24, description="Length of the current window in hours (default 1 day)"
    )
    threshold: Optional[float] = Field(
        default=None, description="Optional threshold to use (uses default if not provided)"
    )


class IncidentResolveRequest(BaseModel):
    """事件解决请求.

    Request schema for resolving an incident, including optional resolution notes.

    Attributes:
        resolution_notes: Notes about how the incident was resolved (default "").
    """

    resolution_notes: str = Field(
        default="", description="Notes about how the incident was resolved"
    )
