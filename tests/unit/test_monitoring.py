"""Production Monitoring, Drift Detection & Alerting 测试。

测试覆盖：
- 健康指标提交与查询
- 漂移检测（Jensen-Shannon 散度计算、阈值判断）
- 告警阈值 CRUD
- 告警触发（指标阈值触发、漂移触发）
- 告警冷却时间
- 事件记录与解决
- 系统健康仪表盘
- 子系统健康状态判定
"""
import math
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

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
from core.services.monitoring_service import MonitoringService


# ─── 辅助函数 ────────────────────────────────────────────

def _make_mock_repo():
    """创建 mock 仓储"""
    repo = MagicMock()
    repo.save_health_metrics.side_effect = lambda m: m
    repo.save_drift_report.side_effect = lambda r: r
    repo.save_alert_threshold.side_effect = lambda t: t
    repo.save_alert.side_effect = lambda a: a
    repo.save_incident.side_effect = lambda i: i
    repo.get_latest_metrics.return_value = None
    repo.list_metrics.return_value = []
    repo.get_alert_threshold.return_value = None
    repo.list_alert_thresholds.return_value = []
    repo.get_alert.return_value = None
    repo.list_alerts.return_value = []
    repo.get_incident.return_value = None
    repo.list_incidents.return_value = []
    repo.recent_incidents.return_value = []
    repo.count_open_alerts.return_value = 0
    repo.count_open_critical.return_value = 0
    repo.get_last_alert_for_threshold.return_value = None
    repo.delete_alert_threshold.return_value = True
    return repo


def _make_health_metrics(
    subsystem: Subsystem = Subsystem.INGESTION,
    error_rate: float = 0.01,
    avg_latency_ms: float = 100.0,
    **kwargs,
) -> HealthMetrics:
    """创建测试用健康指标"""
    return HealthMetrics(
        metric_id=kwargs.get("metric_id", f"hm-{subsystem.value}-test001"),
        subsystem=subsystem,
        timestamp=kwargs.get("timestamp", datetime.now(timezone.utc)),
        throughput=kwargs.get("throughput", 10.0),
        error_rate=error_rate,
        avg_latency_ms=avg_latency_ms,
        p99_latency_ms=kwargs.get("p99_latency_ms", 200.0),
        queue_depth=kwargs.get("queue_depth", 0),
        items_processed=kwargs.get("items_processed", 100),
        items_failed=kwargs.get("items_failed", 1),
        extra=kwargs.get("extra", {}),
    )


def _make_threshold(
    threshold_id: str = "at-test001",
    name: str = "High Error Rate",
    subsystem: Subsystem = Subsystem.INGESTION,
    metric_field: str = "error_rate",
    operator: str = "gte",
    value: float = 0.1,
    severity: AlertSeverity = AlertSeverity.WARNING,
    enabled: bool = True,
    **kwargs,
) -> AlertThreshold:
    """创建测试用告警阈值"""
    return AlertThreshold(
        threshold_id=threshold_id,
        name=name,
        subsystem=subsystem,
        dimension=kwargs.get("dimension"),
        metric_field=metric_field,
        operator=operator,
        value=value,
        severity=severity,
        cooldown_minutes=kwargs.get("cooldown_minutes", 30),
        enabled=enabled,
    )


# ─── 健康指标测试 ────────────────────────────────────────

class TestHealthMetrics:
    """健康指标测试"""

    def test_submit_health_metrics(self):
        """提交健康指标"""
        repo = _make_mock_repo()
        service = MonitoringService(monitoring_repository=repo)

        request = HealthMetricsSubmitRequest(
            subsystem=Subsystem.INGESTION,
            throughput=15.0,
            error_rate=0.02,
            avg_latency_ms=120.0,
            p99_latency_ms=250.0,
            queue_depth=5,
            items_processed=200,
            items_failed=4,
        )

        metrics = service.submit_health_metrics(request)
        assert metrics.subsystem == Subsystem.INGESTION
        assert metrics.throughput == 15.0
        assert metrics.error_rate == 0.02
        assert metrics.metric_id.startswith("hm-ingestion-")
        repo.save_health_metrics.assert_called_once()

    def test_submit_health_metrics_no_repo(self):
        """无仓储时提交指标"""
        service = MonitoringService(monitoring_repository=None)
        request = HealthMetricsSubmitRequest(subsystem=Subsystem.EXTRACTION)
        metrics = service.submit_health_metrics(request)
        assert metrics.subsystem == Subsystem.EXTRACTION

    def test_get_latest_health(self):
        """获取最新健康指标"""
        repo = _make_mock_repo()
        latest = _make_health_metrics()
        repo.get_latest_metrics.return_value = latest
        service = MonitoringService(monitoring_repository=repo)

        result = service.get_latest_health(Subsystem.INGESTION)
        assert result is not None
        assert result.subsystem == Subsystem.INGESTION
        repo.get_latest_metrics.assert_called_once_with(Subsystem.INGESTION)

    def test_list_health_metrics(self):
        """查询健康指标历史"""
        repo = _make_mock_repo()
        metrics_list = [_make_health_metrics()]
        repo.list_metrics.return_value = metrics_list
        service = MonitoringService(monitoring_repository=repo)

        results = service.list_health_metrics(subsystem=Subsystem.INGESTION, limit=10)
        assert len(results) == 1
        repo.list_metrics.assert_called_once()


# ─── 漂移检测测试 ────────────────────────────────────────

class TestDriftDetection:
    """漂移检测测试"""

    def test_check_drift_no_drift(self):
        """检测无漂移"""
        repo = _make_mock_repo()
        repo.list_metrics.return_value = []
        service = MonitoringService(monitoring_repository=repo)

        request = DriftCheckRequest(
            dimension=DriftDimension.SOURCE_MIX,
            threshold=0.3,
        )
        report = service.check_drift(request)
        assert report.dimension == DriftDimension.SOURCE_MIX
        assert report.drift_score == 0.0
        assert not report.is_drift
        assert report.threshold == 0.3

    def test_check_drift_with_drift(self):
        """检测到漂移 — 两个窗口分布差异大"""
        repo = _make_mock_repo()
        # 基准窗口: 全部 ingestion
        baseline_metrics = [
            _make_health_metrics(subsystem=Subsystem.INGESTION, timestamp=datetime.now(timezone.utc) - timedelta(hours=100)),
            _make_health_metrics(subsystem=Subsystem.INGESTION, timestamp=datetime.now(timezone.utc) - timedelta(hours=99)),
        ]
        # 当前窗口: 全部 extraction
        current_metrics = [
            _make_health_metrics(subsystem=Subsystem.EXTRACTION, timestamp=datetime.now(timezone.utc) - timedelta(hours=12)),
            _make_health_metrics(subsystem=Subsystem.EXTRACTION, timestamp=datetime.now(timezone.utc) - timedelta(hours=11)),
        ]

        call_count = [0]

        def list_metrics_side_effect(subsystem=None, since=None, until=None, limit=100):
            # _compute_distributions calls list_metrics twice: baseline then current
            call_count[0] += 1
            if call_count[0] == 1:
                return baseline_metrics
            elif call_count[0] == 2:
                return current_metrics
            return []

        repo.list_metrics.side_effect = list_metrics_side_effect
        service = MonitoringService(monitoring_repository=repo)

        request = DriftCheckRequest(
            dimension=DriftDimension.SOURCE_MIX,
            baseline_window_hours=168,
            current_window_hours=24,
            threshold=0.1,
        )
        report = service.check_drift(request)
        # 两个窗口分布完全不同，应该有漂移
        assert report.is_drift
        assert report.drift_score > 0.1

    def test_js_divergence_identical(self):
        """JS 散度：相同分布"""
        service = MonitoringService(monitoring_repository=None)
        p = {"a": 0.5, "b": 0.5}
        q = {"a": 0.5, "b": 0.5}
        score = service._js_divergence(p, q)
        assert abs(score) < 0.001

    def test_js_divergence_completely_different(self):
        """JS 散度：完全不同分布"""
        service = MonitoringService(monitoring_repository=None)
        p = {"a": 1.0}
        q = {"b": 1.0}
        score = service._js_divergence(p, q)
        assert score > 0.9

    def test_js_divergence_empty(self):
        """JS 散度：空分布"""
        service = MonitoringService(monitoring_repository=None)
        assert service._js_divergence({}, {}) == 0.0
        assert service._js_divergence({}, {"a": 1.0}) == 1.0
        assert service._js_divergence({"a": 1.0}, {}) == 1.0

    def test_list_drift_reports(self):
        """查询漂移报告"""
        repo = _make_mock_repo()
        report = DriftReport(
            report_id="dr-test",
            dimension=DriftDimension.SOURCE_MIX,
            timestamp=datetime.now(timezone.utc),
            baseline_window_start=datetime.now(timezone.utc) - timedelta(hours=168),
            baseline_window_end=datetime.now(timezone.utc) - timedelta(hours=24),
            current_window_start=datetime.now(timezone.utc) - timedelta(hours=24),
            current_window_end=datetime.now(timezone.utc),
            drift_score=0.5,
            is_drift=True,
            threshold=0.3,
        )
        repo.list_drift_reports.return_value = [report]
        service = MonitoringService(monitoring_repository=repo)

        results = service.list_drift_reports(dimension=DriftDimension.SOURCE_MIX)
        assert len(results) == 1


# ─── 告警阈值测试 ────────────────────────────────────────

class TestAlertThresholds:
    """告警阈值测试"""

    def test_create_alert_threshold(self):
        """创建告警阈值"""
        repo = _make_mock_repo()
        service = MonitoringService(monitoring_repository=repo)

        request = AlertThresholdCreateRequest(
            name="High Error Rate",
            subsystem=Subsystem.INGESTION,
            metric_field="error_rate",
            operator="gte",
            value=0.1,
            severity=AlertSeverity.WARNING,
        )
        threshold = service.create_alert_threshold(request)
        assert threshold.name == "High Error Rate"
        assert threshold.subsystem == Subsystem.INGESTION
        assert threshold.value == 0.1
        assert threshold.threshold_id.startswith("at-")
        repo.save_alert_threshold.assert_called_once()

    def test_list_alert_thresholds(self):
        """列出告警阈值"""
        repo = _make_mock_repo()
        repo.list_alert_thresholds.return_value = [_make_threshold()]
        service = MonitoringService(monitoring_repository=repo)

        results = service.list_alert_thresholds(subsystem=Subsystem.INGESTION)
        assert len(results) == 1

    def test_update_alert_threshold(self):
        """更新告警阈值"""
        repo = _make_mock_repo()
        existing = _make_threshold(value=0.1)
        repo.get_alert_threshold.return_value = existing
        service = MonitoringService(monitoring_repository=repo)

        request = AlertThresholdUpdateRequest(value=0.2)
        threshold = service.update_alert_threshold("at-test001", request)
        assert threshold is not None
        assert threshold.value == 0.2

    def test_update_nonexistent_threshold(self):
        """更新不存在的阈值"""
        repo = _make_mock_repo()
        service = MonitoringService(monitoring_repository=repo)
        result = service.update_alert_threshold("nonexistent", AlertThresholdUpdateRequest(value=0.5))
        assert result is None

    def test_delete_alert_threshold(self):
        """删除告警阈值"""
        repo = _make_mock_repo()
        service = MonitoringService(monitoring_repository=repo)
        assert service.delete_alert_threshold("at-test001") is True


# ─── 告警触发测试 ────────────────────────────────────────

class TestAlertTriggering:
    """告警触发测试"""

    def test_metric_threshold_triggers_alert(self):
        """指标超出阈值触发告警"""
        repo = _make_mock_repo()
        threshold = _make_threshold(
            metric_field="error_rate",
            operator="gte",
            value=0.1,
        )
        repo.list_alert_thresholds.return_value = [threshold]
        repo.get_last_alert_for_threshold.return_value = None  # 无冷却限制

        service = MonitoringService(monitoring_repository=repo)

        # 提交高错误率指标
        request = HealthMetricsSubmitRequest(
            subsystem=Subsystem.INGESTION,
            error_rate=0.25,  # 超过阈值 0.1
        )
        metrics = service.submit_health_metrics(request)

        # 应该触发了告警
        repo.save_alert.assert_called()
        repo.save_incident.assert_called()

    def test_metric_below_threshold_no_alert(self):
        """指标低于阈值不触发告警"""
        repo = _make_mock_repo()
        threshold = _make_threshold(
            metric_field="error_rate",
            operator="gte",
            value=0.5,
        )
        repo.list_alert_thresholds.return_value = [threshold]
        service = MonitoringService(monitoring_repository=repo)

        request = HealthMetricsSubmitRequest(
            subsystem=Subsystem.INGESTION,
            error_rate=0.02,  # 低于阈值
        )
        metrics = service.submit_health_metrics(request)
        repo.save_alert.assert_not_called()

    def test_alert_cooldown_prevents_duplicate(self):
        """冷却时间内不重复触发告警"""
        repo = _make_mock_repo()
        threshold = _make_threshold(cooldown_minutes=30)
        # 最近 5 分钟前刚触发过
        recent_alert = AlertPayload(
            alert_id="al-recent",
            threshold_id="at-test001",
            severity=AlertSeverity.WARNING,
            title="test",
            triggered_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        repo.get_last_alert_for_threshold.return_value = recent_alert
        repo.list_alert_thresholds.return_value = [threshold]

        service = MonitoringService(monitoring_repository=repo)

        request = HealthMetricsSubmitRequest(
            subsystem=Subsystem.INGESTION,
            error_rate=0.25,
        )
        metrics = service.submit_health_metrics(request)
        # 冷却期内不应触发
        repo.save_alert.assert_not_called()

    def test_alert_after_cooldown(self):
        """冷却期后可再次触发"""
        repo = _make_mock_repo()
        threshold = _make_threshold(cooldown_minutes=30)
        # 60 分钟前的告警，冷却已过
        old_alert = AlertPayload(
            alert_id="al-old",
            threshold_id="at-test001",
            severity=AlertSeverity.WARNING,
            title="test",
            triggered_at=datetime.now(timezone.utc) - timedelta(minutes=60),
        )
        repo.get_last_alert_for_threshold.return_value = old_alert
        repo.list_alert_thresholds.return_value = [threshold]

        service = MonitoringService(monitoring_repository=repo)

        request = HealthMetricsSubmitRequest(
            subsystem=Subsystem.INGESTION,
            error_rate=0.25,
        )
        metrics = service.submit_health_metrics(request)
        repo.save_alert.assert_called()

    def test_drift_triggers_alert(self):
        """漂移检测触发告警"""
        repo = _make_mock_repo()
        # 构造分布差异大的数据
        baseline = [
            _make_health_metrics(subsystem=Subsystem.INGESTION, timestamp=datetime.now(timezone.utc) - timedelta(hours=100)),
        ]
        current = [
            _make_health_metrics(subsystem=Subsystem.EXTRACTION, timestamp=datetime.now(timezone.utc) - timedelta(hours=12)),
        ]

        call_count = [0]

        def list_metrics_side_effect(subsystem=None, since=None, until=None, limit=100):
            call_count[0] += 1
            if call_count[0] == 1:
                return baseline
            elif call_count[0] == 2:
                return current
            return []

        repo.list_metrics.side_effect = list_metrics_side_effect
        service = MonitoringService(monitoring_repository=repo)

        request = DriftCheckRequest(
            dimension=DriftDimension.SOURCE_MIX,
            threshold=0.1,
        )
        report = service.check_drift(request)
        assert report.is_drift
        repo.save_alert.assert_called()

    def test_evaluate_threshold_operators(self):
        """测试各种阈值比较运算符"""
        service = MonitoringService(monitoring_repository=None)

        assert service._evaluate_threshold(0.5, "gte", 0.3) is True
        assert service._evaluate_threshold(0.2, "gte", 0.3) is False
        assert service._evaluate_threshold(0.1, "lte", 0.3) is True
        assert service._evaluate_threshold(0.5, "lte", 0.3) is False
        assert service._evaluate_threshold(0.5, "gt", 0.3) is True
        assert service._evaluate_threshold(0.3, "gt", 0.3) is False
        assert service._evaluate_threshold(0.1, "lt", 0.3) is True
        assert service._evaluate_threshold(0.5, "lt", 0.3) is False
        assert service._evaluate_threshold(0.3, "eq", 0.3) is True
        assert service._evaluate_threshold(0.5, "eq", 0.3) is False


# ─── 告警管理测试 ────────────────────────────────────────

class TestAlertManagement:
    """告警管理测试"""

    def test_list_alerts(self):
        """查询告警列表"""
        repo = _make_mock_repo()
        service = MonitoringService(monitoring_repository=repo)
        results = service.list_alerts(status=AlertStatus.OPEN)
        repo.list_alerts.assert_called_once()

    def test_acknowledge_alert(self):
        """确认告警"""
        repo = _make_mock_repo()
        alert = AlertPayload(
            alert_id="al-test",
            threshold_id="at-001",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.OPEN,
            title="test",
            triggered_at=datetime.now(timezone.utc),
        )
        repo.get_alert.return_value = alert
        service = MonitoringService(monitoring_repository=repo)

        result = service.acknowledge_alert("al-test")
        assert result is not None
        assert result.status == AlertStatus.ACKNOWLEDGED
        assert result.acknowledged_at is not None

    def test_resolve_alert(self):
        """解决告警"""
        repo = _make_mock_repo()
        alert = AlertPayload(
            alert_id="al-test",
            threshold_id="at-001",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.OPEN,
            title="test",
            triggered_at=datetime.now(timezone.utc),
        )
        repo.get_alert.return_value = alert
        service = MonitoringService(monitoring_repository=repo)

        result = service.resolve_alert("al-test")
        assert result is not None
        assert result.status == AlertStatus.RESOLVED
        assert result.resolved_at is not None

    def test_acknowledge_nonexistent_alert(self):
        """确认不存在的告警"""
        repo = _make_mock_repo()
        service = MonitoringService(monitoring_repository=repo)
        result = service.acknowledge_alert("nonexistent")
        assert result is None


# ─── 事件记录测试 ────────────────────────────────────────

class TestIncidentRecords:
    """事件记录测试"""

    def test_list_incidents(self):
        """查询事件列表"""
        repo = _make_mock_repo()
        service = MonitoringService(monitoring_repository=repo)
        results = service.list_incidents(subsystem=Subsystem.INGESTION)
        repo.list_incidents.assert_called_once()

    def test_resolve_incident(self):
        """解决事件"""
        repo = _make_mock_repo()
        incident = IncidentRecord(
            incident_id="inc-test",
            alert_id="al-001",
            subsystem=Subsystem.INGESTION,
            severity=AlertSeverity.WARNING,
            title="test incident",
            detected_at=datetime.now(timezone.utc),
        )
        repo.get_incident.return_value = incident
        service = MonitoringService(monitoring_repository=repo)

        request = IncidentResolveRequest(resolution_notes="Fixed by restarting service")
        result = service.resolve_incident("inc-test", request)
        assert result is not None
        assert result.resolved_at is not None
        assert result.resolution_notes == "Fixed by restarting service"

    def test_resolve_nonexistent_incident(self):
        """解决不存在的事件"""
        repo = _make_mock_repo()
        service = MonitoringService(monitoring_repository=repo)
        result = service.resolve_incident("nonexistent", IncidentResolveRequest())
        assert result is None


# ─── 系统健康仪表盘测试 ────────────────────────────────

class TestSystemHealthDashboard:
    """系统健康仪表盘测试"""

    def test_get_dashboard(self):
        """获取仪表盘"""
        repo = _make_mock_repo()
        service = MonitoringService(monitoring_repository=repo)

        dashboard = service.get_system_health_dashboard()
        assert isinstance(dashboard, SystemHealthDashboard)
        assert len(dashboard.subsystems) == len(Subsystem)
        assert dashboard.total_open_alerts == 0
        assert dashboard.total_open_critical == 0

    def test_get_dashboard_with_metrics(self):
        """获取有指标的仪表盘"""
        repo = _make_mock_repo()
        latest = _make_health_metrics(error_rate=0.01, avg_latency_ms=100.0)
        repo.get_latest_metrics.return_value = latest
        service = MonitoringService(monitoring_repository=repo)

        dashboard = service.get_system_health_dashboard()
        # 健康指标
        for s in dashboard.subsystems:
            if s.subsystem == Subsystem.INGESTION:
                assert s.status == "healthy"

    def test_subsystem_status_healthy(self):
        """健康状态判定"""
        assert MonitoringService._determine_subsystem_status(
            _make_health_metrics(error_rate=0.01, avg_latency_ms=100.0)
        ) == "healthy"

    def test_subsystem_status_degraded(self):
        """降级状态判定"""
        assert MonitoringService._determine_subsystem_status(
            _make_health_metrics(error_rate=0.08, avg_latency_ms=100.0)
        ) == "degraded"

    def test_subsystem_status_unhealthy(self):
        """不健康状态判定"""
        assert MonitoringService._determine_subsystem_status(
            _make_health_metrics(error_rate=0.25, avg_latency_ms=100.0)
        ) == "unhealthy"

    def test_subsystem_status_unhealthy_latency(self):
        """延迟导致不健康"""
        assert MonitoringService._determine_subsystem_status(
            _make_health_metrics(error_rate=0.01, avg_latency_ms=3000.0)
        ) == "unhealthy"

    def test_subsystem_status_unknown(self):
        """无指标时状态未知"""
        assert MonitoringService._determine_subsystem_status(None) == "unknown"

    def test_get_dashboard_no_repo(self):
        """无仓储时获取仪表盘"""
        service = MonitoringService(monitoring_repository=None)
        dashboard = service.get_system_health_dashboard()
        assert len(dashboard.subsystems) == len(Subsystem)
        for s in dashboard.subsystems:
            assert s.status == "unknown"


# ─── 归一化和分布计算测试 ───────────────────────────────

class TestDistributionUtils:
    """分布工具函数测试"""

    def test_normalize(self):
        """归一化分布"""
        service = MonitoringService(monitoring_repository=None)
        dist = {"a": 3, "b": 7}
        result = service._normalize(dist)
        assert abs(result["a"] - 0.3) < 0.001
        assert abs(result["b"] - 0.7) < 0.001

    def test_normalize_empty(self):
        """归一化空分布"""
        service = MonitoringService(monitoring_repository=None)
        assert service._normalize({}) == {}

    def test_normalize_zero_total(self):
        """归一化零总和"""
        service = MonitoringService(monitoring_repository=None)
        assert service._normalize({"a": 0}) == {"a": 0}

    def test_js_divergence_symmetric(self):
        """JS 散度对称性"""
        service = MonitoringService(monitoring_repository=None)
        p = {"a": 0.6, "b": 0.4}
        q = {"a": 0.3, "b": 0.7}
        assert abs(service._js_divergence(p, q) - service._js_divergence(q, p)) < 0.001

    def test_js_divergence_bounded(self):
        """JS 散度在 [0, 1] 范围内"""
        service = MonitoringService(monitoring_repository=None)
        p = {"a": 1.0}
        q = {"b": 1.0}
        score = service._js_divergence(p, q)
        assert 0.0 <= score <= 1.0
