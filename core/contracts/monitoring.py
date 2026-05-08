"""Production Monitoring, Drift Detection & Alerting 契约。

健康指标采集、数据漂移检测、告警触发、事件记录。
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── 子系统枚举 ────────────────────────────────────────

class Subsystem(str, Enum):
    """被监控的子系统"""
    INGESTION = "ingestion"
    EXTRACTION = "extraction"
    MAPPING = "mapping"
    SIGNAL_GENERATION = "signal_generation"
    TIMING = "timing"
    REPLAY = "replay"
    PORTFOLIO_SIMULATION = "portfolio_simulation"


class AlertSeverity(str, Enum):
    """告警严重级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """告警状态"""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


# ─── 健康指标 ──────────────────────────────────────────

class HealthMetrics(BaseModel):
    """子系统健康指标快照。

    每个子系统定期上报，包含吞吐量、错误率、延迟、队列深度等维度。
    """
    metric_id: str
    subsystem: Subsystem
    timestamp: datetime
    throughput: float = 0.0  # 每秒处理量
    error_rate: float = 0.0  # 错误率 (0.0 ~ 1.0)
    avg_latency_ms: float = 0.0  # 平均延迟（毫秒）
    p99_latency_ms: float = 0.0  # P99 延迟
    queue_depth: int = 0  # 队列积压深度
    items_processed: int = 0  # 已处理条目数
    items_failed: int = 0  # 失败条目数
    extra: Dict[str, Any] = Field(default_factory=dict)  # 子系统特有指标


# ─── 漂移报告 ──────────────────────────────────────────

class DriftDimension(str, Enum):
    """漂移检测维度"""
    SOURCE_MIX = "source_mix"  # 数据源占比分布
    EVENT_TYPE_MIX = "event_type_mix"  # 事件类型分布
    MAPPING_HIT_RATE = "mapping_hit_rate"  # 映射命中率
    SIGNAL_VOLUME = "signal_volume"  # 信号生成量
    READINESS_DISTRIBUTION = "readiness_distribution"  # Timing readiness 分布
    OUTCOME_DISTRIBUTION = "outcome_distribution"  # 结果分布


class DriftReport(BaseModel):
    """漂移检测报告。

    对比当前窗口与基准窗口的分布差异，量化各维度的漂移程度。
    """
    report_id: str
    dimension: DriftDimension
    timestamp: datetime
    baseline_window_start: datetime
    baseline_window_end: datetime
    current_window_start: datetime
    current_window_end: datetime
    drift_score: float  # 0.0 ~ 1.0，越大漂移越严重
    is_drift: bool  # 是否超过阈值
    threshold: float  # 使用的阈值
    baseline_distribution: Dict[str, float] = Field(default_factory=dict)
    current_distribution: Dict[str, float] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)


# ─── 告警 ─────────────────────────────────────────────

class AlertThreshold(BaseModel):
    """告警阈值配置。

    定义某个指标/维度的告警触发条件。
    """
    threshold_id: str
    name: str
    subsystem: Optional[Subsystem] = None
    dimension: Optional[DriftDimension] = None
    metric_field: Optional[str] = None  # HealthMetrics 字段名，如 error_rate
    operator: str = "gte"  # gte | lte | eq | gt | lt
    value: float = 0.0  # 阈值
    severity: AlertSeverity = AlertSeverity.WARNING
    cooldown_minutes: int = 30  # 冷却时间，避免告警风暴
    enabled: bool = True


class AlertPayload(BaseModel):
    """告警载荷。

    告警触发后产生的完整告警记录。
    """
    alert_id: str
    threshold_id: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.OPEN
    subsystem: Optional[Subsystem] = None
    dimension: Optional[DriftDimension] = None
    title: str
    description: str = ""
    observed_value: float = 0.0
    threshold_value: float = 0.0
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── 事件记录 ──────────────────────────────────────────

class IncidentRecord(BaseModel):
    """事件记录。

    持久化存储的事件，用于后续调查和审计。
    """
    incident_id: str
    alert_id: str
    subsystem: Subsystem
    severity: AlertSeverity
    title: str
    description: str = ""
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_notes: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── 仪表盘摘要 ───────────────────────────────────────

class SubsystemHealthSummary(BaseModel):
    """子系统健康摘要"""
    subsystem: Subsystem
    latest_metrics: Optional[HealthMetrics] = None
    status: str = "unknown"  # healthy / degraded / unhealthy / unknown
    open_alerts: int = 0


class SystemHealthDashboard(BaseModel):
    """系统健康仪表盘"""
    generated_at: datetime
    subsystems: List[SubsystemHealthSummary] = Field(default_factory=list)
    total_open_alerts: int = 0
    total_open_critical: int = 0
    recent_incidents: List[IncidentRecord] = Field(default_factory=list)


# ─── 请求模型 ──────────────────────────────────────────

class AlertThresholdCreateRequest(BaseModel):
    """创建告警阈值请求"""
    name: str
    subsystem: Optional[Subsystem] = None
    dimension: Optional[DriftDimension] = None
    metric_field: Optional[str] = None
    operator: str = "gte"
    value: float = 0.0
    severity: AlertSeverity = AlertSeverity.WARNING
    cooldown_minutes: int = 30
    enabled: bool = True


class AlertThresholdUpdateRequest(BaseModel):
    """更新告警阈值请求"""
    name: Optional[str] = None
    value: Optional[float] = None
    operator: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    cooldown_minutes: Optional[int] = None
    enabled: Optional[bool] = None


class HealthMetricsSubmitRequest(BaseModel):
    """提交健康指标请求"""
    subsystem: Subsystem
    throughput: float = 0.0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    queue_depth: int = 0
    items_processed: int = 0
    items_failed: int = 0
    extra: Dict[str, Any] = Field(default_factory=dict)


class DriftCheckRequest(BaseModel):
    """漂移检测请求"""
    dimension: DriftDimension
    baseline_window_hours: int = 168  # 默认 7 天
    current_window_hours: int = 24  # 默认 1 天
    threshold: Optional[float] = None  # 不传则使用默认值


class IncidentResolveRequest(BaseModel):
    """事件解决请求"""
    resolution_notes: str = ""
