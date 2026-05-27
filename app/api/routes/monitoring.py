"""Monitoring API — 健康指标、漂移检测、告警管理、事件记录路由"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.models import (
    IngestOverviewResponse,
    IngestSourceStatus,
    PDFArtifactResponse,
    PDFStats,
    ProcessedItemResponse,
    ProcessedStatsResponse,
)
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
    SystemHealthDashboard,
)
from core.observability import get_logger
from data_layer.repositories import (
    crawl_state_repository,
    pdf_artifact_repository,
    processed_item_repository,
)
from data_layer.repositories.base import get_db
from data_layer.repositories.monitoring_repository import MonitoringRepositoryImpl
from services.monitoring_service import MonitoringService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# 模块级单例
_monitoring_service: MonitoringService | None = None


# ── 请求/响应模型 ──────────────────────────────────────


class HealthMetricsSubmitBody(BaseModel):
    """提交健康指标请求体"""

    subsystem: Subsystem
    throughput: float = 0.0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    queue_depth: int = 0
    items_processed: int = 0
    items_failed: int = 0
    extra: Dict[str, Any] = Field(default_factory=dict)


class HealthMetricsResponse(BaseModel):
    """健康指标响应"""

    metric_id: str
    subsystem: str
    timestamp: str
    throughput: float
    error_rate: float
    avg_latency_ms: float
    p99_latency_ms: float
    queue_depth: int
    items_processed: int
    items_failed: int
    extra: Dict[str, Any]


class DriftCheckBody(BaseModel):
    """漂移检测请求体"""

    dimension: DriftDimension
    baseline_window_hours: int = 168
    current_window_hours: int = 24
    threshold: Optional[float] = None


class DriftReportResponse(BaseModel):
    """漂移报告响应"""

    report_id: str
    dimension: str
    timestamp: str
    baseline_window_start: str
    baseline_window_end: str
    current_window_start: str
    current_window_end: str
    drift_score: float
    is_drift: bool
    threshold: float
    baseline_distribution: Dict[str, float]
    current_distribution: Dict[str, float]
    details: Dict[str, Any]


class AlertThresholdCreateBody(BaseModel):
    """创建告警阈值请求体"""

    name: str
    subsystem: Optional[Subsystem] = None
    dimension: Optional[DriftDimension] = None
    metric_field: Optional[str] = None
    operator: str = "gte"
    value: float = 0.0
    severity: AlertSeverity = AlertSeverity.WARNING
    cooldown_minutes: int = 30
    enabled: bool = True


class AlertThresholdUpdateBody(BaseModel):
    """更新告警阈值请求体"""

    name: Optional[str] = None
    value: Optional[float] = None
    operator: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    cooldown_minutes: Optional[int] = None
    enabled: Optional[bool] = None


class AlertThresholdResponse(BaseModel):
    """告警阈值响应"""

    threshold_id: str
    name: str
    subsystem: Optional[str] = None
    dimension: Optional[str] = None
    metric_field: Optional[str] = None
    operator: str
    value: float
    severity: str
    cooldown_minutes: int
    enabled: bool


class AlertResponse(BaseModel):
    """告警响应"""

    alert_id: str
    threshold_id: str
    severity: str
    status: str
    subsystem: Optional[str] = None
    dimension: Optional[str] = None
    title: str
    description: str
    observed_value: float
    threshold_value: float
    triggered_at: str
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    metadata: Dict[str, Any]


class IncidentResponse(BaseModel):
    """事件响应"""

    incident_id: str
    alert_id: str
    subsystem: str
    severity: str
    title: str
    description: str
    detected_at: str
    resolved_at: Optional[str] = None
    resolution_notes: str = ""
    metadata: Dict[str, Any]


class IncidentResolveBody(BaseModel):
    """事件解决请求体"""

    resolution_notes: str = ""


class SubsystemHealthSummaryResponse(BaseModel):
    """子系统健康摘要响应"""

    subsystem: str
    status: str
    open_alerts: int = 0
    latest_metrics: Optional[HealthMetricsResponse] = None


class SystemHealthDashboardResponse(BaseModel):
    """系统健康仪表盘响应"""

    generated_at: str
    subsystems: List[SubsystemHealthSummaryResponse]
    total_open_alerts: int = 0
    total_open_critical: int = 0
    recent_incidents: List[IncidentResponse] = Field(default_factory=list)


# ── 依赖注入 ───────────────────────────────────────────


def get_monitoring_service(db: Session = Depends(get_db)) -> MonitoringService:
    """获取监控服务实例（单例 + 请求级 DB session）"""
    global _monitoring_service
    if _monitoring_service is None:
        repo = MonitoringRepositoryImpl(db)
        _monitoring_service = MonitoringService(monitoring_repository=repo)
    else:
        if _monitoring_service._repo:
            _monitoring_service._repo.db = db
    return _monitoring_service


def _reset_monitoring_service():
    """重置模块级单例（仅用于测试）"""
    global _monitoring_service
    _monitoring_service = None


# ── 辅助转换 ───────────────────────────────────────────


def _metrics_to_response(m: HealthMetrics) -> HealthMetricsResponse:
    return HealthMetricsResponse(
        metric_id=m.metric_id,
        subsystem=m.subsystem.value,
        timestamp=m.timestamp.isoformat() if m.timestamp else "",
        throughput=m.throughput,
        error_rate=m.error_rate,
        avg_latency_ms=m.avg_latency_ms,
        p99_latency_ms=m.p99_latency_ms,
        queue_depth=m.queue_depth,
        items_processed=m.items_processed,
        items_failed=m.items_failed,
        extra=m.extra,
    )


def _drift_to_response(r: DriftReport) -> DriftReportResponse:
    return DriftReportResponse(
        report_id=r.report_id,
        dimension=r.dimension.value,
        timestamp=r.timestamp.isoformat() if r.timestamp else "",
        baseline_window_start=r.baseline_window_start.isoformat()
        if r.baseline_window_start
        else "",
        baseline_window_end=r.baseline_window_end.isoformat() if r.baseline_window_end else "",
        current_window_start=r.current_window_start.isoformat() if r.current_window_start else "",
        current_window_end=r.current_window_end.isoformat() if r.current_window_end else "",
        drift_score=r.drift_score,
        is_drift=r.is_drift,
        threshold=r.threshold,
        baseline_distribution=r.baseline_distribution,
        current_distribution=r.current_distribution,
        details=r.details,
    )


def _threshold_to_response(t: AlertThreshold) -> AlertThresholdResponse:
    return AlertThresholdResponse(
        threshold_id=t.threshold_id,
        name=t.name,
        subsystem=t.subsystem.value if t.subsystem else None,
        dimension=t.dimension.value if t.dimension else None,
        metric_field=t.metric_field,
        operator=t.operator,
        value=t.value,
        severity=t.severity.value,
        cooldown_minutes=t.cooldown_minutes,
        enabled=t.enabled,
    )


def _alert_to_response(a: AlertPayload) -> AlertResponse:
    return AlertResponse(
        alert_id=a.alert_id,
        threshold_id=a.threshold_id,
        severity=a.severity.value,
        status=a.status.value,
        subsystem=a.subsystem.value if a.subsystem else None,
        dimension=a.dimension.value if a.dimension else None,
        title=a.title,
        description=a.description,
        observed_value=a.observed_value,
        threshold_value=a.threshold_value,
        triggered_at=a.triggered_at.isoformat() if a.triggered_at else "",
        acknowledged_at=a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
        metadata=a.metadata,
    )


def _incident_to_response(i: IncidentRecord) -> IncidentResponse:
    return IncidentResponse(
        incident_id=i.incident_id,
        alert_id=i.alert_id,
        subsystem=i.subsystem.value,
        severity=i.severity.value,
        title=i.title,
        description=i.description,
        detected_at=i.detected_at.isoformat() if i.detected_at else "",
        resolved_at=i.resolved_at.isoformat() if i.resolved_at else None,
        resolution_notes=i.resolution_notes,
        metadata=i.metadata,
    )


def _dashboard_to_response(d: SystemHealthDashboard) -> SystemHealthDashboardResponse:
    subsystems = []
    for s in d.subsystems:
        latest = _metrics_to_response(s.latest_metrics) if s.latest_metrics else None
        subsystems.append(
            SubsystemHealthSummaryResponse(
                subsystem=s.subsystem.value,
                status=s.status,
                open_alerts=s.open_alerts,
                latest_metrics=latest,
            )
        )
    return SystemHealthDashboardResponse(
        generated_at=d.generated_at.isoformat(),
        subsystems=subsystems,
        total_open_alerts=d.total_open_alerts,
        total_open_critical=d.total_open_critical,
        recent_incidents=[_incident_to_response(i) for i in d.recent_incidents],
    )


# ── 健康指标路由 ────────────────────────────────────────


@router.post(
    "/health",
    response_model=HealthMetricsResponse,
)
async def submit_health_metrics(
    body: HealthMetricsSubmitBody,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """提交子系统健康指标"""
    try:
        request = HealthMetricsSubmitRequest(
            subsystem=body.subsystem,
            throughput=body.throughput,
            error_rate=body.error_rate,
            avg_latency_ms=body.avg_latency_ms,
            p99_latency_ms=body.p99_latency_ms,
            queue_depth=body.queue_depth,
            items_processed=body.items_processed,
            items_failed=body.items_failed,
            extra=body.extra,
        )
        metrics = service.submit_health_metrics(request)
        return _metrics_to_response(metrics)
    except Exception as e:
        logger.error(f"Submit health metrics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/health/{subsystem}",
    response_model=HealthMetricsResponse,
)
async def get_latest_health(
    subsystem: Subsystem,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """获取子系统最新健康指标"""
    try:
        metrics = service.get_latest_health(subsystem)
        if metrics is None:
            raise HTTPException(status_code=404, detail=f"No metrics found for {subsystem.value}")
        return _metrics_to_response(metrics)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get latest health failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/health",
    response_model=List[HealthMetricsResponse],
)
async def list_health_metrics(
    subsystem: Optional[Subsystem] = Query(None),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    service: MonitoringService = Depends(get_monitoring_service),
):
    """查询健康指标历史"""
    try:
        since_dt = None
        until_dt = None
        if since:
            since_dt = __import__("datetime").datetime.fromisoformat(since)
        if until:
            until_dt = __import__("datetime").datetime.fromisoformat(until)
        metrics = service.list_health_metrics(
            subsystem=subsystem,
            since=since_dt,
            until=until_dt,
            limit=limit,
        )
        return [_metrics_to_response(m) for m in metrics]
    except Exception as e:
        logger.error(f"List health metrics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 漂移检测路由 ────────────────────────────────────────


@router.post(
    "/drift/check",
    response_model=DriftReportResponse,
)
async def check_drift(
    body: DriftCheckBody,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """执行漂移检测"""
    try:
        request = DriftCheckRequest(
            dimension=body.dimension,
            baseline_window_hours=body.baseline_window_hours,
            current_window_hours=body.current_window_hours,
            threshold=body.threshold,
        )
        report = service.check_drift(request)
        return _drift_to_response(report)
    except Exception as e:
        logger.error(f"Drift check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/drift",
    response_model=List[DriftReportResponse],
)
async def list_drift_reports(
    dimension: Optional[DriftDimension] = Query(None),
    since: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    service: MonitoringService = Depends(get_monitoring_service),
):
    """查询漂移报告"""
    try:
        since_dt = None
        if since:
            since_dt = __import__("datetime").datetime.fromisoformat(since)
        reports = service.list_drift_reports(dimension=dimension, since=since_dt, limit=limit)
        return [_drift_to_response(r) for r in reports]
    except Exception as e:
        logger.error(f"List drift reports failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 告警阈值路由 ────────────────────────────────────────


@router.post(
    "/thresholds",
    response_model=AlertThresholdResponse,
)
async def create_alert_threshold(
    body: AlertThresholdCreateBody,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """创建告警阈值"""
    try:
        request = AlertThresholdCreateRequest(
            name=body.name,
            subsystem=body.subsystem,
            dimension=body.dimension,
            metric_field=body.metric_field,
            operator=body.operator,
            value=body.value,
            severity=body.severity,
            cooldown_minutes=body.cooldown_minutes,
            enabled=body.enabled,
        )
        threshold = service.create_alert_threshold(request)
        return _threshold_to_response(threshold)
    except Exception as e:
        logger.error(f"Create alert threshold failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/thresholds",
    response_model=List[AlertThresholdResponse],
)
async def list_alert_thresholds(
    subsystem: Optional[Subsystem] = Query(None),
    enabled_only: bool = Query(False),
    service: MonitoringService = Depends(get_monitoring_service),
):
    """列出告警阈值"""
    try:
        thresholds = service.list_alert_thresholds(subsystem=subsystem, enabled_only=enabled_only)
        return [_threshold_to_response(t) for t in thresholds]
    except Exception as e:
        logger.error(f"List alert thresholds failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/thresholds/{threshold_id}",
    response_model=AlertThresholdResponse,
)
async def get_alert_threshold(
    threshold_id: str,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """获取告警阈值"""
    try:
        threshold = service.get_alert_threshold(threshold_id)
        if threshold is None:
            raise HTTPException(status_code=404, detail=f"Threshold {threshold_id} not found")
        return _threshold_to_response(threshold)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get alert threshold failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/thresholds/{threshold_id}",
    response_model=AlertThresholdResponse,
)
async def update_alert_threshold(
    threshold_id: str,
    body: AlertThresholdUpdateBody,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """更新告警阈值"""
    try:
        request = AlertThresholdUpdateRequest(
            name=body.name,
            value=body.value,
            operator=body.operator,
            severity=body.severity,
            cooldown_minutes=body.cooldown_minutes,
            enabled=body.enabled,
        )
        threshold = service.update_alert_threshold(threshold_id, request)
        if threshold is None:
            raise HTTPException(status_code=404, detail=f"Threshold {threshold_id} not found")
        return _threshold_to_response(threshold)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update alert threshold failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/thresholds/{threshold_id}",
)
async def delete_alert_threshold(
    threshold_id: str,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """删除告警阈值"""
    try:
        deleted = service.delete_alert_threshold(threshold_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Threshold {threshold_id} not found")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete alert threshold failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 告警路由 ───────────────────────────────────────────


@router.get(
    "/alerts",
    response_model=List[AlertResponse],
)
async def list_alerts(
    status: Optional[AlertStatus] = Query(None),
    severity: Optional[AlertSeverity] = Query(None),
    subsystem: Optional[Subsystem] = Query(None),
    since: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    service: MonitoringService = Depends(get_monitoring_service),
):
    """查询告警"""
    try:
        since_dt = None
        if since:
            since_dt = __import__("datetime").datetime.fromisoformat(since)
        alerts = service.list_alerts(
            status=status,
            severity=severity,
            subsystem=subsystem,
            since=since_dt,
            limit=limit,
        )
        return [_alert_to_response(a) for a in alerts]
    except Exception as e:
        logger.error(f"List alerts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertResponse,
)
async def acknowledge_alert(
    alert_id: str,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """确认告警"""
    try:
        alert = service.acknowledge_alert(alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        return _alert_to_response(alert)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Acknowledge alert failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/alerts/{alert_id}/resolve",
    response_model=AlertResponse,
)
async def resolve_alert(
    alert_id: str,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """解决告警"""
    try:
        alert = service.resolve_alert(alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        return _alert_to_response(alert)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resolve alert failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 事件路由 ───────────────────────────────────────────


@router.get(
    "/incidents",
    response_model=List[IncidentResponse],
)
async def list_incidents(
    subsystem: Optional[Subsystem] = Query(None),
    severity: Optional[AlertSeverity] = Query(None),
    resolved: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    service: MonitoringService = Depends(get_monitoring_service),
):
    """查询事件"""
    try:
        incidents = service.list_incidents(
            subsystem=subsystem,
            severity=severity,
            resolved=resolved,
            limit=limit,
        )
        return [_incident_to_response(i) for i in incidents]
    except Exception as e:
        logger.error(f"List incidents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=IncidentResponse,
)
async def resolve_incident(
    incident_id: str,
    body: IncidentResolveBody,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """解决事件"""
    try:
        request = IncidentResolveRequest(resolution_notes=body.resolution_notes)
        incident = service.resolve_incident(incident_id, request)
        if incident is None:
            raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
        return _incident_to_response(incident)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resolve incident failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 仪表盘路由 ────────────────────────────────────────


@router.get(
    "/dashboard",
    response_model=SystemHealthDashboardResponse,
)
async def get_system_health_dashboard(
    service: MonitoringService = Depends(get_monitoring_service),
):
    """获取系统健康仪表盘"""
    try:
        dashboard = service.get_system_health_dashboard()
        return _dashboard_to_response(dashboard)
    except Exception as e:
        logger.error(f"Get dashboard failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 摄入监控路由 ────────────────────────────────────────


def _crawl_state_to_status(state: Any) -> IngestSourceStatus:
    """转换爬虫状态为响应模型"""
    total = state.total_fetched + state.total_skipped + state.total_failed
    dedupe_rate = float(state.total_skipped) / total if total > 0 else 0.0

    # 确定状态
    status = "paused" if state.is_paused else "running"

    return IngestSourceStatus(
        source_type=state.source_type,
        source_name=state.source_name,
        status=status,
        last_fetch=state.last_run_end.isoformat() if state.last_run_end else None,
        total_fetched=state.total_fetched,
        total_skipped=state.total_skipped,
        total_failed=state.total_failed,
        dedupe_rate=dedupe_rate,
        is_paused=state.is_paused,
        pause_reason=state.pause_reason,
        watermark_id=state.watermark_id,
        watermark_timestamp=state.watermark_timestamp.isoformat()
        if state.watermark_timestamp
        else None,
    )


def _processed_item_to_response(item: Any) -> ProcessedItemResponse:
    """转换已处理项目为响应模型"""
    return ProcessedItemResponse(
        item_id=item.item_id,
        source_type=item.source_type,
        source_name=item.source_name,
        item_type=item.item_type,
        title=item.title,
        content_preview=item.content_preview,
        content_hash=item.content_hash,
        first_seen_at=item.first_seen_at.isoformat() if item.first_seen_at else None,
        first_processed_at=item.first_processed_at.isoformat() if item.first_processed_at else None,
        process_count=item.process_count,
    )


def _pdf_artifact_to_response(artifact: Any) -> PDFArtifactResponse:
    """转换 PDF 制品为响应模型"""
    return PDFArtifactResponse(
        pdf_id=artifact.pdf_id,
        doc_id=artifact.doc_id,
        source_obj_id=artifact.source_obj_id,
        file_path=artifact.file_path,
        file_name=artifact.file_name,
        file_size_bytes=artifact.file_size_bytes,
        file_hash_sha256=artifact.file_hash_sha256,
        source_type=artifact.source_type,
        source_name=artifact.source_name,
        source_url=artifact.source_url,
        source_broker=artifact.source_broker,
        fetch_timestamp=artifact.fetch_timestamp.isoformat() if artifact.fetch_timestamp else None,
        parse_status=artifact.parse_status,
        parse_error=artifact.parse_error,
    )


@router.get(
    "/ingest/status",
    response_model=IngestOverviewResponse,
)
async def get_ingest_status(
    db: Session = Depends(get_db),
):
    """获取摄入状态概览"""
    try:
        # 获取所有爬虫状态
        states = crawl_state_repository.get_all_crawl_states(db)
        sources = {}
        for state in states:
            sources[state.source_type] = _crawl_state_to_status(state)

        # 为标准来源创建默认状态（如果不存在）
        for source_type in ["cls", "cnstock", "zq"]:
            if source_type not in sources:
                sources[source_type] = IngestSourceStatus(
                    source_type=source_type,
                    status="unknown",
                    is_paused=False,
                )

        # 获取 PDF 统计
        pdf_stats_data = pdf_artifact_repository.get_conversion_stats(db)
        pdf_stats = PDFStats(**pdf_stats_data)

        # 确定整体健康状态
        overall_health = "healthy"
        for source in sources.values():
            if source.total_failed > 10:
                overall_health = "degraded"
            if source.status == "error":
                overall_health = "error"

        return IngestOverviewResponse(
            sources=sources,
            pdf_stats=pdf_stats,
            overall_health=overall_health,
            generated_at=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Get ingest status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/ingest/sources/{source_type}",
    response_model=IngestSourceStatus,
)
async def get_source_status(
    source_type: str,
    db: Session = Depends(get_db),
):
    """获取特定来源的详细状态"""
    try:
        state = crawl_state_repository.get_crawl_state(db, source_type)
        if state is None:
            # 返回默认状态
            return IngestSourceStatus(
                source_type=source_type,
                status="unknown",
                is_paused=False,
            )
        return _crawl_state_to_status(state)
    except Exception as e:
        logger.error(f"Get source status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/ingest/processed",
    response_model=ProcessedStatsResponse,
)
async def get_processed_stats(
    source_type: Optional[str] = Query(None),
    days: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """获取已处理项目统计"""
    try:
        stats = processed_item_repository.get_processed_stats(db, source_type=source_type)

        daily_stats = []
        if source_type and days:
            daily_stats = processed_item_repository.get_processed_stats_by_day(
                db, source_type, days
            )

        return ProcessedStatsResponse(
            total_items=stats.get("total_items", 0),
            by_source_type=stats.get("by_source_type", {}),
            daily_stats=daily_stats,
        )
    except Exception as e:
        logger.error(f"Get processed stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/ingest/processed/{source_type}/recent",
    response_model=List[ProcessedItemResponse],
)
async def get_recent_processed(
    source_type: str,
    source_name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """获取最近处理的项目"""
    try:
        items = processed_item_repository.get_recent_processed(db, source_type, source_name, limit)
        return [_processed_item_to_response(item) for item in items]
    except Exception as e:
        logger.error(f"Get recent processed failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/ingest/pdfs",
    response_model=List[PDFArtifactResponse],
)
async def get_pdfs(
    source_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """获取 PDF 制品列表"""
    try:
        if source_type:
            artifacts = pdf_artifact_repository.get_pdfs_by_source(db, source_type, limit=limit)
        else:
            # 临时处理：简单返回所有来源的最新（逐个获取）
            artifacts = []
            for st in ["cls", "cnstock", "zq"]:
                artifacts.extend(pdf_artifact_repository.get_pdfs_by_source(db, st, limit=limit))
            artifacts.sort(key=lambda a: a.fetch_timestamp, reverse=True)
            artifacts = artifacts[:limit]

        return [_pdf_artifact_to_response(a) for a in artifacts]
    except Exception as e:
        logger.error(f"Get PDFs failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
