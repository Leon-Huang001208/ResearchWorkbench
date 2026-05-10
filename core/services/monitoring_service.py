"""Monitoring 服务 — 健康指标采集、漂移检测、告警触发、事件记录。"""
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.contracts.monitoring import (
    AlertPayload,
    AlertSeverity,
    AlertStatus,
    AlertThreshold,
    AlertThresholdCreateRequest,
    AlertThresholdUpdateRequest,
    DriftCheckRequest,
    DriftDimension,
    DriftReport,
    HealthMetrics,
    HealthMetricsSubmitRequest,
    IncidentRecord,
    IncidentResolveRequest,
    Subsystem,
    SubsystemHealthSummary,
    SystemHealthDashboard,
)
from core.observability import get_logger

logger = get_logger(__name__)

# 漂移检测默认阈值
DEFAULT_DRIFT_THRESHOLDS: Dict[DriftDimension, float] = {
    DriftDimension.SOURCE_MIX: 0.3,
    DriftDimension.EVENT_TYPE_MIX: 0.3,
    DriftDimension.MAPPING_HIT_RATE: 0.2,
    DriftDimension.SIGNAL_VOLUME: 0.4,
    DriftDimension.READINESS_DISTRIBUTION: 0.3,
    DriftDimension.OUTCOME_DISTRIBUTION: 0.3,
}

# 子系统健康判定阈值
_HEALTHY_ERROR_RATE = 0.05
_DEGRADED_ERROR_RATE = 0.2
_HEALTHY_LATENCY_MS = 500.0
_DEGRADED_LATENCY_MS = 2000.0


class MonitoringService:
    """生产监控核心服务"""

    def __init__(self, monitoring_repository: Optional[Any] = None):
        self._repo = monitoring_repository

    # ── 健康指标 ────────────────────────────────────────

    def submit_health_metrics(
        self,
        request: HealthMetricsSubmitRequest,
    ) -> HealthMetrics:
        """提交子系统健康指标"""
        metric_id = f"hm-{request.subsystem.value}-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        metrics = HealthMetrics(
            metric_id=metric_id,
            subsystem=request.subsystem,
            timestamp=now,
            throughput=request.throughput,
            error_rate=request.error_rate,
            avg_latency_ms=request.avg_latency_ms,
            p99_latency_ms=request.p99_latency_ms,
            queue_depth=request.queue_depth,
            items_processed=request.items_processed,
            items_failed=request.items_failed,
            extra=request.extra,
        )

        if self._repo:
            metrics = self._repo.save_health_metrics(metrics)
            logger.info(
                "health metrics submitted",
                subsystem=request.subsystem.value,
                metric_id=metric_id,
            )

            # 自动检查是否触发告警
            self._check_metric_thresholds(metrics)

        return metrics

    def get_latest_health(self, subsystem: Subsystem) -> Optional[HealthMetrics]:
        """获取子系统最新健康指标"""
        if self._repo:
            return self._repo.get_latest_metrics(subsystem)
        return None

    def list_health_metrics(
        self,
        subsystem: Optional[Subsystem] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[HealthMetrics]:
        """查询健康指标历史"""
        if self._repo:
            return self._repo.list_metrics(
                subsystem=subsystem,
                since=since,
                until=until,
                limit=limit,
            )
        return []

    # ── 漂移检测 ────────────────────────────────────────

    def check_drift(self, request: DriftCheckRequest) -> DriftReport:
        """执行漂移检测。

        对比基准窗口和当前窗口的数据分布，计算 Jensen-Shannon 散度作为漂移分数。
        """
        now = datetime.now(timezone.utc)
        current_end = now
        current_start = now - timedelta(hours=request.current_window_hours)
        baseline_end = current_start
        baseline_start = current_start - timedelta(hours=request.baseline_window_hours)

        threshold = request.threshold or DEFAULT_DRIFT_THRESHOLDS.get(request.dimension, 0.3)

        # 从仓储获取两个窗口的指标数据来计算分布
        baseline_dist: Dict[str, float] = {}
        current_dist: Dict[str, float] = {}

        if self._repo:
            baseline_dist, current_dist = self._compute_distributions(
                request.dimension,
                baseline_start,
                baseline_end,
                current_start,
                current_end,
            )

        drift_score = self._js_divergence(baseline_dist, current_dist)
        is_drift = drift_score >= threshold

        report_id = f"dr-{request.dimension.value}-{uuid.uuid4().hex[:8]}"
        report = DriftReport(
            report_id=report_id,
            dimension=request.dimension,
            timestamp=now,
            baseline_window_start=baseline_start,
            baseline_window_end=baseline_end,
            current_window_start=current_start,
            current_window_end=current_end,
            drift_score=drift_score,
            is_drift=is_drift,
            threshold=threshold,
            baseline_distribution=baseline_dist,
            current_distribution=current_dist,
            details={
                "js_divergence": drift_score,
                "baseline_samples": sum(baseline_dist.values()) if baseline_dist else 0,
                "current_samples": sum(current_dist.values()) if current_dist else 0,
            },
        )

        if self._repo:
            report = self._repo.save_drift_report(report)
            logger.info(
                "drift check completed",
                dimension=request.dimension.value,
                drift_score=drift_score,
                is_drift=is_drift,
            )

            # 如果漂移超出阈值，触发告警
            if is_drift:
                self._trigger_drift_alert(report)

        return report

    def list_drift_reports(
        self,
        dimension: Optional[DriftDimension] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[DriftReport]:
        """查询漂移报告"""
        if self._repo:
            return self._repo.list_drift_reports(dimension=dimension, since=since, limit=limit)
        return []

    # ── 告警阈值管理 ────────────────────────────────────

    def create_alert_threshold(
        self,
        request: AlertThresholdCreateRequest,
    ) -> AlertThreshold:
        """创建告警阈值"""
        threshold_id = f"at-{uuid.uuid4().hex[:8]}"
        threshold = AlertThreshold(
            threshold_id=threshold_id,
            name=request.name,
            subsystem=request.subsystem,
            dimension=request.dimension,
            metric_field=request.metric_field,
            operator=request.operator,
            value=request.value,
            severity=request.severity,
            cooldown_minutes=request.cooldown_minutes,
            enabled=request.enabled,
        )
        if self._repo:
            threshold = self._repo.save_alert_threshold(threshold)
            logger.info("alert threshold created", threshold_id=threshold_id, name=request.name)
        return threshold

    def get_alert_threshold(self, threshold_id: str) -> Optional[AlertThreshold]:
        """获取告警阈值"""
        if self._repo:
            return self._repo.get_alert_threshold(threshold_id)
        return None

    def list_alert_thresholds(
        self,
        subsystem: Optional[Subsystem] = None,
        enabled_only: bool = False,
    ) -> List[AlertThreshold]:
        """列出告警阈值"""
        if self._repo:
            return self._repo.list_alert_thresholds(subsystem=subsystem, enabled_only=enabled_only)
        return []

    def update_alert_threshold(
        self,
        threshold_id: str,
        request: AlertThresholdUpdateRequest,
    ) -> Optional[AlertThreshold]:
        """更新告警阈值"""
        if not self._repo:
            return None
        threshold = self._repo.get_alert_threshold(threshold_id)
        if not threshold:
            return None

        if request.name is not None:
            threshold.name = request.name
        if request.value is not None:
            threshold.value = request.value
        if request.operator is not None:
            threshold.operator = request.operator
        if request.severity is not None:
            threshold.severity = request.severity
        if request.cooldown_minutes is not None:
            threshold.cooldown_minutes = request.cooldown_minutes
        if request.enabled is not None:
            threshold.enabled = request.enabled

        return self._repo.save_alert_threshold(threshold)

    def delete_alert_threshold(self, threshold_id: str) -> bool:
        """删除告警阈值"""
        if self._repo:
            return self._repo.delete_alert_threshold(threshold_id)
        return False

    # ── 告警管理 ────────────────────────────────────────

    def list_alerts(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        subsystem: Optional[Subsystem] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AlertPayload]:
        """查询告警"""
        if self._repo:
            return self._repo.list_alerts(
                status=status,
                severity=severity,
                subsystem=subsystem,
                since=since,
                limit=limit,
            )
        return []

    def acknowledge_alert(self, alert_id: str) -> Optional[AlertPayload]:
        """确认告警"""
        if not self._repo:
            return None
        alert = self._repo.get_alert(alert_id)
        if not alert:
            return None
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now(timezone.utc)
        return self._repo.save_alert(alert)

    def resolve_alert(self, alert_id: str) -> Optional[AlertPayload]:
        """解决告警"""
        if not self._repo:
            return None
        alert = self._repo.get_alert(alert_id)
        if not alert:
            return None
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)
        return self._repo.save_alert(alert)

    # ── 事件管理 ────────────────────────────────────────

    def list_incidents(
        self,
        subsystem: Optional[Subsystem] = None,
        severity: Optional[AlertSeverity] = None,
        resolved: Optional[bool] = None,
        limit: int = 50,
    ) -> List[IncidentRecord]:
        """查询事件"""
        if self._repo:
            return self._repo.list_incidents(
                subsystem=subsystem,
                severity=severity,
                resolved=resolved,
                limit=limit,
            )
        return []

    def resolve_incident(
        self,
        incident_id: str,
        request: IncidentResolveRequest,
    ) -> Optional[IncidentRecord]:
        """解决事件"""
        if not self._repo:
            return None
        incident = self._repo.get_incident(incident_id)
        if not incident:
            return None
        incident.resolved_at = datetime.now(timezone.utc)
        incident.resolution_notes = request.resolution_notes
        return self._repo.save_incident(incident)

    # ── 仪表盘 ─────────────────────────────────────────

    def get_system_health_dashboard(self) -> SystemHealthDashboard:
        """获取系统健康仪表盘"""
        now = datetime.now(timezone.utc)
        summaries: List[SubsystemHealthSummary] = []

        total_open = 0
        total_critical = 0

        if self._repo:
            total_open = self._repo.count_open_alerts()
            total_critical = self._repo.count_open_critical()

            for subsystem in Subsystem:
                latest = self._repo.get_latest_metrics(subsystem)
                open_count = self._repo.count_open_alerts(subsystem=subsystem)
                status = self._determine_subsystem_status(latest)
                summaries.append(
                    SubsystemHealthSummary(
                        subsystem=subsystem,
                        latest_metrics=latest,
                        status=status,
                        open_alerts=open_count,
                    )
                )

            recent_incidents = self._repo.recent_incidents(limit=10)
        else:
            for subsystem in Subsystem:
                summaries.append(
                    SubsystemHealthSummary(
                        subsystem=subsystem,
                        status="unknown",
                    )
                )
            recent_incidents = []

        return SystemHealthDashboard(
            generated_at=now,
            subsystems=summaries,
            total_open_alerts=total_open,
            total_open_critical=total_critical,
            recent_incidents=recent_incidents,
        )

    # ── 内部方法 ────────────────────────────────────────

    def _check_metric_thresholds(self, metrics: HealthMetrics) -> None:
        """检查健康指标是否触发告警"""
        if not self._repo:
            return

        thresholds = self._repo.list_alert_thresholds(
            subsystem=metrics.subsystem,
            enabled_only=True,
        )

        now = datetime.now(timezone.utc)
        for threshold in thresholds:
            if not threshold.metric_field:
                continue

            observed = getattr(metrics, threshold.metric_field, None)
            if observed is None:
                continue

            if not self._evaluate_threshold(observed, threshold.operator, threshold.value):
                continue

            # 冷却时间检查
            if not self._check_cooldown(threshold, now):
                continue

            self._create_metric_alert(metrics, threshold, observed)

    def _evaluate_threshold(
        self,
        observed: float,
        operator: str,
        threshold_value: float,
    ) -> bool:
        """评估阈值条件"""
        if operator == "gte":
            return observed >= threshold_value
        elif operator == "lte":
            return observed <= threshold_value
        elif operator == "gt":
            return observed > threshold_value
        elif operator == "lt":
            return observed < threshold_value
        elif operator == "eq":
            return abs(observed - threshold_value) < 1e-10
        return False

    def _check_cooldown(self, threshold: AlertThreshold, now: datetime) -> bool:
        """检查是否在冷却期外"""
        if not self._repo:
            return True
        last_alert = self._repo.get_last_alert_for_threshold(threshold.threshold_id)
        if not last_alert:
            return True
        cooldown_end = last_alert.triggered_at + timedelta(minutes=threshold.cooldown_minutes)
        return now >= cooldown_end

    def _create_metric_alert(
        self,
        metrics: HealthMetrics,
        threshold: AlertThreshold,
        observed: float,
    ) -> AlertPayload:
        """创建指标告警"""
        alert_id = f"al-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        title = f"{metrics.subsystem.value}: {threshold.metric_field} {threshold.operator} {threshold.value}"
        description = (
            f"Subsystem {metrics.subsystem.value} metric '{threshold.metric_field}' "
            f"= {observed}, threshold = {threshold.value} ({threshold.operator}). "
            f"Severity: {threshold.severity.value}."
        )

        alert = AlertPayload(
            alert_id=alert_id,
            threshold_id=threshold.threshold_id,
            severity=threshold.severity,
            status=AlertStatus.OPEN,
            subsystem=metrics.subsystem,
            dimension=threshold.dimension,
            title=title,
            description=description,
            observed_value=observed,
            threshold_value=threshold.value,
            triggered_at=now,
            metadata={"metric_id": metrics.metric_id},
        )

        if self._repo:
            alert = self._repo.save_alert(alert)

            # 自动创建事件
            self._create_incident_from_alert(alert)

            logger.warning(
                "alert triggered",
                alert_id=alert_id,
                subsystem=metrics.subsystem.value,
                metric_field=threshold.metric_field,
                observed=observed,
                threshold=threshold.value,
            )

        return alert

    def _trigger_drift_alert(self, report: DriftReport) -> AlertPayload:
        """漂移告警"""
        alert_id = f"al-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        title = f"Drift detected: {report.dimension.value} (score={report.drift_score:.3f})"
        description = (
            f"Dimension '{report.dimension.value}' drift score = {report.drift_score:.3f} "
            f"exceeds threshold {report.threshold:.3f}. "
            f"Baseline window: {report.baseline_window_start.isoformat()} - "
            f"{report.baseline_window_end.isoformat()}, "
            f"Current window: {report.current_window_start.isoformat()} - "
            f"{report.current_window_end.isoformat()}."
        )

        # 根据 drift_score 决定严重级别
        severity = AlertSeverity.WARNING
        if report.drift_score >= 0.6:
            severity = AlertSeverity.CRITICAL

        alert = AlertPayload(
            alert_id=alert_id,
            threshold_id=f"drift-{report.dimension.value}",
            severity=severity,
            status=AlertStatus.OPEN,
            dimension=report.dimension,
            title=title,
            description=description,
            observed_value=report.drift_score,
            threshold_value=report.threshold,
            triggered_at=now,
            metadata={"report_id": report.report_id},
        )

        if self._repo:
            alert = self._repo.save_alert(alert)

            # 为漂移创建事件 — 需要指定子系统，使用 ingestion 作为默认
            incident = IncidentRecord(
                incident_id=f"inc-{uuid.uuid4().hex[:8]}",
                alert_id=alert.alert_id,
                subsystem=Subsystem.INGESTION,
                severity=severity,
                title=f"Data drift: {report.dimension.value}",
                description=description,
                detected_at=now,
                metadata={"report_id": report.report_id, "dimension": report.dimension.value},
            )
            self._repo.save_incident(incident)

            logger.warning(
                "drift alert triggered",
                alert_id=alert_id,
                dimension=report.dimension.value,
                drift_score=report.drift_score,
            )

        return alert

    def _create_incident_from_alert(self, alert: AlertPayload) -> IncidentRecord:
        """从告警创建事件"""
        incident_id = f"inc-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        subsystem = alert.subsystem or Subsystem.INGESTION

        incident = IncidentRecord(
            incident_id=incident_id,
            alert_id=alert.alert_id,
            subsystem=subsystem,
            severity=alert.severity,
            title=alert.title,
            description=alert.description,
            detected_at=now,
            metadata=alert.metadata,
        )

        if self._repo:
            incident = self._repo.save_incident(incident)

        return incident

    @staticmethod
    def _determine_subsystem_status(latest: Optional[HealthMetrics]) -> str:
        """根据最新指标判定子系统健康状态"""
        if latest is None:
            return "unknown"

        if (
            latest.error_rate >= _DEGRADED_ERROR_RATE
            or latest.avg_latency_ms >= _DEGRADED_LATENCY_MS
        ):
            return "unhealthy"

        if latest.error_rate >= _HEALTHY_ERROR_RATE or latest.avg_latency_ms >= _HEALTHY_LATENCY_MS:
            return "degraded"

        return "healthy"

    def _compute_distributions(
        self,
        dimension: DriftDimension,
        baseline_start: datetime,
        baseline_end: datetime,
        current_start: datetime,
        current_end: datetime,
    ) -> tuple:
        """从仓储数据计算基准窗口和当前窗口的分布。

        根据维度类型查询不同的数据源并归一化为分布。
        """
        baseline_dist: Dict[str, float] = {}
        current_dist: Dict[str, float] = {}

        if not self._repo:
            return baseline_dist, current_dist

        # 使用健康指标作为代理数据来计算分布
        baseline_metrics = self._repo.list_metrics(
            since=baseline_start,
            until=baseline_end,
            limit=10000,
        )
        current_metrics = self._repo.list_metrics(
            since=current_start,
            until=current_end,
            limit=10000,
        )

        if dimension == DriftDimension.SOURCE_MIX:
            # 按 subsystem 归一化条目数
            baseline_dist = self._count_by_field(baseline_metrics, "subsystem")
            current_dist = self._count_by_field(current_metrics, "subsystem")
        elif dimension == DriftDimension.EVENT_TYPE_MIX:
            # 同上，按 subsystem（事件类型无单独字段，用 subsystem 代理）
            baseline_dist = self._count_by_field(baseline_metrics, "subsystem")
            current_dist = self._count_by_field(current_metrics, "subsystem")
        elif dimension == DriftDimension.MAPPING_HIT_RATE:
            # 按 subsystem 的命中率
            baseline_dist = self._avg_by_field(baseline_metrics, "subsystem", "items_processed")
            current_dist = self._avg_by_field(current_metrics, "subsystem", "items_processed")
        elif dimension == DriftDimension.SIGNAL_VOLUME:
            # 按 subsystem 的吞吐量
            baseline_dist = self._avg_by_field(baseline_metrics, "subsystem", "throughput")
            current_dist = self._avg_by_field(current_metrics, "subsystem", "throughput")
        elif dimension == DriftDimension.READINESS_DISTRIBUTION:
            # 按 subsystem 的队列深度
            baseline_dist = self._avg_by_field(baseline_metrics, "subsystem", "queue_depth")
            current_dist = self._avg_by_field(current_metrics, "subsystem", "queue_depth")
        elif dimension == DriftDimension.OUTCOME_DISTRIBUTION:
            # 按 subsystem 的错误率
            baseline_dist = self._avg_by_field(baseline_metrics, "subsystem", "error_rate")
            current_dist = self._avg_by_field(current_metrics, "subsystem", "error_rate")

        return self._normalize(baseline_dist), self._normalize(current_dist)

    @staticmethod
    def _count_by_field(items: List[HealthMetrics], field: str) -> Dict[str, float]:
        """按字段值计数"""
        counts: Dict[str, float] = {}
        for item in items:
            key = getattr(item, field, None)
            if key is not None:
                key = key.value if hasattr(key, "value") else str(key)
                counts[key] = counts.get(key, 0) + 1
        return counts

    @staticmethod
    def _avg_by_field(
        items: List[HealthMetrics],
        group_field: str,
        value_field: str,
    ) -> Dict[str, float]:
        """按分组字段聚合平均值"""
        groups: Dict[str, list] = {}
        for item in items:
            key = getattr(item, group_field, None)
            if key is not None:
                key = key.value if hasattr(key, "value") else str(key)
                groups.setdefault(key, []).append(getattr(item, value_field, 0))

        result: Dict[str, float] = {}
        for k, vals in groups.items():
            result[k] = sum(vals) / len(vals) if vals else 0
        return result

    @staticmethod
    def _normalize(dist: Dict[str, float]) -> Dict[str, float]:
        """归一化分布使总和为 1"""
        total = sum(dist.values())
        if total <= 0:
            return dist
        return {k: v / total for k, v in dist.items()}

    @staticmethod
    def _js_divergence(
        p: Dict[str, float],
        q: Dict[str, float],
    ) -> float:
        """计算 Jensen-Shannon 散度。

        JS(P||Q) = 0.5 * KL(P||M) + 0.5 * KL(Q||M), M = 0.5*(P+Q)
        范围 [0, ln(2)] ≈ [0, 0.693]，归一化到 [0, 1]。
        """
        if not p and not q:
            return 0.0
        if not p or not q:
            return 1.0

        all_keys = set(p.keys()) | set(q.keys())
        m: Dict[str, float] = {}
        for k in all_keys:
            pv = p.get(k, 0.0)
            qv = q.get(k, 0.0)
            m[k] = 0.5 * (pv + qv)

        def kl(a: Dict[str, float], b: Dict[str, float]) -> float:
            result = 0.0
            for k in a:
                av = a[k]
                bv = b.get(k, 0.0)
                if av > 0 and bv > 0:
                    result += av * math.log(av / bv)
            return result

        js = 0.5 * kl(p, m) + 0.5 * kl(q, m)
        # 归一化到 [0, 1]
        return min(js / math.log(2), 1.0)
