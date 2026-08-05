"""Monitoring 持久化仓储实现"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError

from core.contracts.monitoring import (
    AlertPayload,
    AlertSeverity,
    AlertStatus,
    AlertThreshold,
    DriftDimension,
    DriftReport,
    HealthMetrics,
    IncidentRecord,
    Subsystem,
)
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import (
    AlertPayloadDB,
    AlertThresholdDB,
    DriftReportDB,
    HealthMetricsDB,
    IncidentRecordDB,
)

logger = get_logger(__name__)


class MonitoringRepositoryImpl(BaseRepository):
    """Monitoring 仓储实现"""

    # ── HealthMetrics ────────────────────────────────────

    def save_health_metrics(self, metrics: HealthMetrics) -> HealthMetrics:
        """保存健康指标"""
        data = self._metrics_to_dict(metrics)
        db_obj = HealthMetricsDB(**data)
        self.db.add(db_obj)
        self.db.flush()
        logger.info(
            "health metrics saved", metric_id=metrics.metric_id, subsystem=metrics.subsystem.value
        )
        return self._dict_to_metrics(self._db_metrics_to_dict(db_obj))

    def save_health_metrics_if_absent(self, metrics: HealthMetrics) -> Optional[HealthMetrics]:
        """通过 savepoint 保存指标；主键冲突时不污染外层事务。"""
        data = self._metrics_to_dict(metrics)
        try:
            with self.db.begin_nested():
                db_obj = HealthMetricsDB(**data)
                self.db.add(db_obj)
                self.db.flush()
                saved = self._dict_to_metrics(self._db_metrics_to_dict(db_obj))
        except IntegrityError:
            logger.info(
                "health metrics already exists",
                metric_id=metrics.metric_id,
                subsystem=metrics.subsystem.value,
            )
            return None
        except Exception as exc:
            logger.warning("health metrics conditional save failed", error_type=type(exc).__name__)
            raise
        logger.info(
            "health metrics saved",
            metric_id=metrics.metric_id,
            subsystem=metrics.subsystem.value,
        )
        return saved

    def get_latest_metrics(self, subsystem: Subsystem) -> Optional[HealthMetrics]:
        """获取子系统最新指标"""
        db_obj = (
            self.db.query(HealthMetricsDB)
            .filter(HealthMetricsDB.subsystem == subsystem.value)
            .order_by(HealthMetricsDB.timestamp.desc())
            .first()
        )
        if not db_obj:
            return None
        return self._dict_to_metrics(self._db_metrics_to_dict(db_obj))

    def list_metrics(
        self,
        subsystem: Optional[Subsystem] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        metric_type: Optional[str] = None,
    ) -> List[HealthMetrics]:
        """查询健康指标"""
        query = self.db.query(HealthMetricsDB)
        if subsystem:
            query = query.filter(HealthMetricsDB.subsystem == subsystem.value)
        if since:
            query = query.filter(HealthMetricsDB.timestamp >= since)
        if until:
            query = query.filter(HealthMetricsDB.timestamp <= until)
        if metric_type is not None:
            query = query.filter(HealthMetricsDB.extra["metric_type"].as_string() == metric_type)
        db_objs = query.order_by(HealthMetricsDB.timestamp.desc()).limit(limit).all()
        return [self._dict_to_metrics(self._db_metrics_to_dict(o)) for o in db_objs]

    def delete_health_metrics(self, metric_ids: List[str]) -> int:
        """按精确 ID 批量删除健康指标。"""
        valid_ids = [
            metric_id for metric_id in metric_ids if isinstance(metric_id, str) and metric_id
        ]
        if not valid_ids:
            return 0
        try:
            with self.db.begin_nested():
                deleted = (
                    self.db.query(HealthMetricsDB)
                    .filter(HealthMetricsDB.metric_id.in_(valid_ids))
                    .delete(synchronize_session=False)
                )
                self.db.flush()
            logger.info(
                "health metrics deleted",
                metric_count=len(valid_ids),
                deleted_count=deleted,
            )
            return deleted
        except Exception as exc:
            logger.warning("health metrics deletion failed", error_type=type(exc).__name__)
            raise

    # ── DriftReport ──────────────────────────────────────

    def save_drift_report(self, report: DriftReport) -> DriftReport:
        """保存漂移报告"""
        data = self._drift_to_dict(report)
        db_obj = DriftReportDB(**data)
        self.db.add(db_obj)
        self.db.flush()
        logger.info(
            "drift report saved", report_id=report.report_id, dimension=report.dimension.value
        )
        return self._dict_to_drift(self._db_drift_to_dict(db_obj))

    def list_drift_reports(
        self,
        dimension: Optional[DriftDimension] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[DriftReport]:
        """查询漂移报告"""
        query = self.db.query(DriftReportDB)
        if dimension:
            query = query.filter(DriftReportDB.dimension == dimension.value)
        if since:
            query = query.filter(DriftReportDB.timestamp >= since)
        db_objs = query.order_by(DriftReportDB.timestamp.desc()).limit(limit).all()
        return [self._dict_to_drift(self._db_drift_to_dict(o)) for o in db_objs]

    # ── AlertThreshold ───────────────────────────────────

    def save_alert_threshold(self, threshold: AlertThreshold) -> AlertThreshold:
        """保存告警阈值"""
        existing = (
            self.db.query(AlertThresholdDB).filter_by(threshold_id=threshold.threshold_id).first()
        )
        data = self._threshold_to_dict(threshold)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            db_obj = existing
        else:
            db_obj = AlertThresholdDB(**data)
            self.db.add(db_obj)
        self.db.flush()
        logger.info("alert threshold saved", threshold_id=threshold.threshold_id)
        return self._dict_to_threshold(self._db_threshold_to_dict(db_obj))

    def get_alert_threshold(self, threshold_id: str) -> Optional[AlertThreshold]:
        """获取告警阈值"""
        db_obj = (
            self.db.query(AlertThresholdDB)
            .filter(AlertThresholdDB.threshold_id == threshold_id)
            .first()
        )
        if not db_obj:
            return None
        return self._dict_to_threshold(self._db_threshold_to_dict(db_obj))

    def list_alert_thresholds(
        self,
        subsystem: Optional[Subsystem] = None,
        enabled_only: bool = False,
    ) -> List[AlertThreshold]:
        """列出告警阈值"""
        query = self.db.query(AlertThresholdDB)
        if subsystem:
            query = query.filter(AlertThresholdDB.subsystem == subsystem.value)
        if enabled_only:
            query = query.filter(AlertThresholdDB.enabled == True)  # noqa: E712
        db_objs = query.all()
        return [self._dict_to_threshold(self._db_threshold_to_dict(o)) for o in db_objs]

    def delete_alert_threshold(self, threshold_id: str) -> bool:
        """删除告警阈值"""
        db_obj = (
            self.db.query(AlertThresholdDB)
            .filter(AlertThresholdDB.threshold_id == threshold_id)
            .first()
        )
        if db_obj:
            self.db.delete(db_obj)
            self.db.flush()
            return True
        return False

    # ── AlertPayload ─────────────────────────────────────

    def save_alert(self, alert: AlertPayload) -> AlertPayload:
        """保存告警"""
        existing = self.db.query(AlertPayloadDB).filter_by(alert_id=alert.alert_id).first()
        data = self._alert_to_dict(alert)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            db_obj = existing
        else:
            db_obj = AlertPayloadDB(**data)
            self.db.add(db_obj)
        self.db.flush()
        logger.info("alert saved", alert_id=alert.alert_id, severity=alert.severity.value)
        return self._dict_to_alert(self._db_alert_to_dict(db_obj))

    def get_alert(self, alert_id: str) -> Optional[AlertPayload]:
        """获取告警"""
        db_obj = self.db.query(AlertPayloadDB).filter(AlertPayloadDB.alert_id == alert_id).first()
        if not db_obj:
            return None
        return self._dict_to_alert(self._db_alert_to_dict(db_obj))

    def update_alert_details_if_unresolved(
        self,
        alert_id: str,
        severity: AlertSeverity,
        title: str,
        description: str,
        threshold_value: float,
        metadata: Dict[str, Any],
    ) -> Optional[AlertPayload]:
        """原子更新未解决告警的详情，绝不覆盖确认或解决状态。"""
        query = self.db.query(AlertPayloadDB).filter(AlertPayloadDB.alert_id == alert_id)
        updated_count = query.filter(AlertPayloadDB.status != AlertStatus.RESOLVED.value).update(
            {
                AlertPayloadDB.severity: severity.value,
                AlertPayloadDB.title: title,
                AlertPayloadDB.description: description,
                AlertPayloadDB.threshold_value: threshold_value,
                AlertPayloadDB.alert_metadata: metadata,
            },
            synchronize_session=False,
        )
        self.db.flush()
        self.db.expire_all()
        db_obj = query.first()
        if db_obj is None:
            return None
        saved = self._dict_to_alert(self._db_alert_to_dict(db_obj))
        if updated_count:
            logger.info("unresolved alert details updated", alert_id=alert_id)
        return saved

    def list_alerts(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        subsystem: Optional[Subsystem] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AlertPayload]:
        """查询告警"""
        query = self.db.query(AlertPayloadDB)
        if status:
            query = query.filter(AlertPayloadDB.status == status.value)
        if severity:
            query = query.filter(AlertPayloadDB.severity == severity.value)
        if subsystem:
            query = query.filter(AlertPayloadDB.subsystem == subsystem.value)
        if since:
            query = query.filter(AlertPayloadDB.triggered_at >= since)
        db_objs = query.order_by(AlertPayloadDB.triggered_at.desc()).limit(limit).all()
        return [self._dict_to_alert(self._db_alert_to_dict(o)) for o in db_objs]

    def count_open_alerts(self, subsystem: Optional[Subsystem] = None) -> int:
        """统计未关闭告警数量"""
        from sqlalchemy import func

        query = self.db.query(func.count(AlertPayloadDB.alert_id)).filter(
            AlertPayloadDB.status != AlertStatus.RESOLVED.value
        )
        if subsystem:
            query = query.filter(AlertPayloadDB.subsystem == subsystem.value)
        return query.scalar() or 0

    def count_open_critical(self) -> int:
        """统计未关闭的 critical 告警"""
        from sqlalchemy import func

        return (
            self.db.query(func.count(AlertPayloadDB.alert_id))
            .filter(
                AlertPayloadDB.status != AlertStatus.RESOLVED.value,
                AlertPayloadDB.severity == AlertSeverity.CRITICAL.value,
            )
            .scalar()
            or 0
        )

    def get_last_alert_for_threshold(self, threshold_id: str) -> Optional[AlertPayload]:
        """获取指定阈值的最近告警（用于冷却时间判断）"""
        db_obj = (
            self.db.query(AlertPayloadDB)
            .filter(AlertPayloadDB.threshold_id == threshold_id)
            .order_by(AlertPayloadDB.triggered_at.desc())
            .first()
        )
        if not db_obj:
            return None
        return self._dict_to_alert(self._db_alert_to_dict(db_obj))

    # ── IncidentRecord ───────────────────────────────────

    def save_incident(self, incident: IncidentRecord) -> IncidentRecord:
        """保存事件"""
        existing = (
            self.db.query(IncidentRecordDB).filter_by(incident_id=incident.incident_id).first()
        )
        data = self._incident_to_dict(incident)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            db_obj = existing
        else:
            db_obj = IncidentRecordDB(**data)
            self.db.add(db_obj)
        self.db.flush()
        logger.info("incident saved", incident_id=incident.incident_id)
        return self._dict_to_incident(self._db_incident_to_dict(db_obj))

    def get_incident(self, incident_id: str) -> Optional[IncidentRecord]:
        """获取事件"""
        db_obj = (
            self.db.query(IncidentRecordDB)
            .filter(IncidentRecordDB.incident_id == incident_id)
            .first()
        )
        if not db_obj:
            return None
        return self._dict_to_incident(self._db_incident_to_dict(db_obj))

    def list_incidents(
        self,
        subsystem: Optional[Subsystem] = None,
        severity: Optional[AlertSeverity] = None,
        resolved: Optional[bool] = None,
        limit: int = 50,
    ) -> List[IncidentRecord]:
        """查询事件"""
        query = self.db.query(IncidentRecordDB)
        if subsystem:
            query = query.filter(IncidentRecordDB.subsystem == subsystem.value)
        if severity:
            query = query.filter(IncidentRecordDB.severity == severity.value)
        if resolved is True:
            query = query.filter(IncidentRecordDB.resolved_at.isnot(None))
        elif resolved is False:
            query = query.filter(IncidentRecordDB.resolved_at.is_(None))
        db_objs = query.order_by(IncidentRecordDB.detected_at.desc()).limit(limit).all()
        return [self._dict_to_incident(self._db_incident_to_dict(o)) for o in db_objs]

    def recent_incidents(self, limit: int = 10) -> List[IncidentRecord]:
        """获取最近事件"""
        db_objs = (
            self.db.query(IncidentRecordDB)
            .order_by(IncidentRecordDB.detected_at.desc())
            .limit(limit)
            .all()
        )
        return [self._dict_to_incident(self._db_incident_to_dict(o)) for o in db_objs]

    # ── 序列化辅助 ──────────────────────────────────────

    @staticmethod
    def _metrics_to_dict(m: HealthMetrics) -> Dict[str, Any]:
        return {
            "metric_id": m.metric_id,
            "subsystem": m.subsystem.value,
            "timestamp": m.timestamp,
            "throughput": m.throughput,
            "error_rate": m.error_rate,
            "avg_latency_ms": m.avg_latency_ms,
            "p99_latency_ms": m.p99_latency_ms,
            "queue_depth": m.queue_depth,
            "items_processed": m.items_processed,
            "items_failed": m.items_failed,
            "extra": m.extra,
        }

    @staticmethod
    def _db_metrics_to_dict(o: HealthMetricsDB) -> Dict[str, Any]:
        return {
            "metric_id": o.metric_id,
            "subsystem": o.subsystem,
            "timestamp": o.timestamp,
            "throughput": float(o.throughput or 0),
            "error_rate": float(o.error_rate or 0),
            "avg_latency_ms": float(o.avg_latency_ms or 0),
            "p99_latency_ms": float(o.p99_latency_ms or 0),
            "queue_depth": o.queue_depth or 0,
            "items_processed": o.items_processed or 0,
            "items_failed": o.items_failed or 0,
            "extra": o.extra or {},
        }

    @staticmethod
    def _dict_to_metrics(d: Dict[str, Any]) -> HealthMetrics:
        return HealthMetrics(
            metric_id=d["metric_id"],
            subsystem=Subsystem(d["subsystem"]),
            timestamp=d["timestamp"],
            throughput=d.get("throughput", 0.0),
            error_rate=d.get("error_rate", 0.0),
            avg_latency_ms=d.get("avg_latency_ms", 0.0),
            p99_latency_ms=d.get("p99_latency_ms", 0.0),
            queue_depth=d.get("queue_depth", 0),
            items_processed=d.get("items_processed", 0),
            items_failed=d.get("items_failed", 0),
            extra=d.get("extra", {}),
        )

    @staticmethod
    def _drift_to_dict(r: DriftReport) -> Dict[str, Any]:
        return {
            "report_id": r.report_id,
            "dimension": r.dimension.value,
            "timestamp": r.timestamp,
            "baseline_window_start": r.baseline_window_start,
            "baseline_window_end": r.baseline_window_end,
            "current_window_start": r.current_window_start,
            "current_window_end": r.current_window_end,
            "drift_score": r.drift_score,
            "is_drift": r.is_drift,
            "threshold": r.threshold,
            "baseline_distribution": r.baseline_distribution,
            "current_distribution": r.current_distribution,
            "details": r.details,
        }

    @staticmethod
    def _db_drift_to_dict(o: DriftReportDB) -> Dict[str, Any]:
        return {
            "report_id": o.report_id,
            "dimension": o.dimension,
            "timestamp": o.timestamp,
            "baseline_window_start": o.baseline_window_start,
            "baseline_window_end": o.baseline_window_end,
            "current_window_start": o.current_window_start,
            "current_window_end": o.current_window_end,
            "drift_score": float(o.drift_score or 0),
            "is_drift": bool(o.is_drift),
            "threshold": float(o.threshold or 0),
            "baseline_distribution": o.baseline_distribution or {},
            "current_distribution": o.current_distribution or {},
            "details": o.details or {},
        }

    @staticmethod
    def _dict_to_drift(d: Dict[str, Any]) -> DriftReport:
        return DriftReport(
            report_id=d["report_id"],
            dimension=DriftDimension(d["dimension"]),
            timestamp=d["timestamp"],
            baseline_window_start=d["baseline_window_start"],
            baseline_window_end=d["baseline_window_end"],
            current_window_start=d["current_window_start"],
            current_window_end=d["current_window_end"],
            drift_score=d.get("drift_score", 0.0),
            is_drift=d.get("is_drift", False),
            threshold=d.get("threshold", 0.0),
            baseline_distribution=d.get("baseline_distribution", {}),
            current_distribution=d.get("current_distribution", {}),
            details=d.get("details", {}),
        )

    @staticmethod
    def _threshold_to_dict(t: AlertThreshold) -> Dict[str, Any]:
        return {
            "threshold_id": t.threshold_id,
            "name": t.name,
            "subsystem": t.subsystem.value if t.subsystem else None,
            "dimension": t.dimension.value if t.dimension else None,
            "metric_field": t.metric_field,
            "operator": t.operator,
            "value": t.value,
            "severity": t.severity.value,
            "cooldown_minutes": t.cooldown_minutes,
            "enabled": t.enabled,
        }

    @staticmethod
    def _db_threshold_to_dict(o: AlertThresholdDB) -> Dict[str, Any]:
        return {
            "threshold_id": o.threshold_id,
            "name": o.name,
            "subsystem": o.subsystem,
            "dimension": o.dimension,
            "metric_field": o.metric_field,
            "operator": o.operator or "gte",
            "value": float(o.value or 0),
            "severity": o.severity or "warning",
            "cooldown_minutes": o.cooldown_minutes or 30,
            "enabled": bool(o.enabled),
        }

    @staticmethod
    def _dict_to_threshold(d: Dict[str, Any]) -> AlertThreshold:
        return AlertThreshold(
            threshold_id=d["threshold_id"],
            name=d["name"],
            subsystem=Subsystem(d["subsystem"]) if d.get("subsystem") else None,
            dimension=DriftDimension(d["dimension"]) if d.get("dimension") else None,
            metric_field=d.get("metric_field"),
            operator=d.get("operator", "gte"),
            value=d.get("value", 0.0),
            severity=AlertSeverity(d.get("severity", "warning")),
            cooldown_minutes=d.get("cooldown_minutes", 30),
            enabled=d.get("enabled", True),
        )

    @staticmethod
    def _alert_to_dict(a: AlertPayload) -> Dict[str, Any]:
        return {
            "alert_id": a.alert_id,
            "threshold_id": a.threshold_id,
            "severity": a.severity.value,
            "status": a.status.value,
            "subsystem": a.subsystem.value if a.subsystem else None,
            "dimension": a.dimension.value if a.dimension else None,
            "title": a.title,
            "description": a.description,
            "observed_value": a.observed_value,
            "threshold_value": a.threshold_value,
            "triggered_at": a.triggered_at,
            "acknowledged_at": a.acknowledged_at,
            "resolved_at": a.resolved_at,
            "alert_metadata": a.metadata,
        }

    @staticmethod
    def _db_alert_to_dict(o: AlertPayloadDB) -> Dict[str, Any]:
        return {
            "alert_id": o.alert_id,
            "threshold_id": o.threshold_id,
            "severity": o.severity or "warning",
            "status": o.status or "open",
            "subsystem": o.subsystem,
            "dimension": o.dimension,
            "title": o.title,
            "description": o.description or "",
            "observed_value": float(o.observed_value or 0),
            "threshold_value": float(o.threshold_value or 0),
            "triggered_at": o.triggered_at,
            "acknowledged_at": o.acknowledged_at,
            "resolved_at": o.resolved_at,
            "metadata": o.alert_metadata or {},
        }

    @staticmethod
    def _dict_to_alert(d: Dict[str, Any]) -> AlertPayload:
        return AlertPayload(
            alert_id=d["alert_id"],
            threshold_id=d["threshold_id"],
            severity=AlertSeverity(d.get("severity", "warning")),
            status=AlertStatus(d.get("status", "open")),
            subsystem=Subsystem(d["subsystem"]) if d.get("subsystem") else None,
            dimension=DriftDimension(d["dimension"]) if d.get("dimension") else None,
            title=d["title"],
            description=d.get("description", ""),
            observed_value=d.get("observed_value", 0.0),
            threshold_value=d.get("threshold_value", 0.0),
            triggered_at=d["triggered_at"],
            acknowledged_at=d.get("acknowledged_at"),
            resolved_at=d.get("resolved_at"),
            metadata=d.get("metadata", {}),
        )

    @staticmethod
    def _incident_to_dict(i: IncidentRecord) -> Dict[str, Any]:
        return {
            "incident_id": i.incident_id,
            "alert_id": i.alert_id,
            "subsystem": i.subsystem.value,
            "severity": i.severity.value,
            "title": i.title,
            "description": i.description,
            "detected_at": i.detected_at,
            "resolved_at": i.resolved_at,
            "resolution_notes": i.resolution_notes,
            "incident_metadata": i.metadata,
        }

    @staticmethod
    def _db_incident_to_dict(o: IncidentRecordDB) -> Dict[str, Any]:
        return {
            "incident_id": o.incident_id,
            "alert_id": o.alert_id,
            "subsystem": o.subsystem,
            "severity": o.severity or "warning",
            "title": o.title,
            "description": o.description or "",
            "detected_at": o.detected_at,
            "resolved_at": o.resolved_at,
            "resolution_notes": o.resolution_notes or "",
            "metadata": o.incident_metadata or {},
        }

    @staticmethod
    def _dict_to_incident(d: Dict[str, Any]) -> IncidentRecord:
        return IncidentRecord(
            incident_id=d["incident_id"],
            alert_id=d["alert_id"],
            subsystem=Subsystem(d["subsystem"]),
            severity=AlertSeverity(d.get("severity", "warning")),
            title=d["title"],
            description=d.get("description", ""),
            detected_at=d["detected_at"],
            resolved_at=d.get("resolved_at"),
            resolution_notes=d.get("resolution_notes", ""),
            metadata=d.get("metadata", {}),
        )
