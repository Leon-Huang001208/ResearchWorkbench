"""将安全的整机容量摘要保留为分钟级健康指标历史。"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from core.contracts.monitoring import HealthMetrics, Subsystem
from core.observability import get_logger

logger = get_logger(__name__)

_HOST_FIELDS = (
    "cpu_percent",
    "cpu_idle_percent",
    "logical_cpu_count",
    "memory_total_bytes",
    "memory_used_bytes",
    "memory_available_bytes",
    "memory_available_percent",
)
_ALPHA_FIELDS = (
    "cpu_percent",
    "memory_bytes",
    "cpu_host_percent",
    "memory_host_percent",
)
_MAX_HISTORY_POINTS = 1500
_RETENTION = timedelta(hours=24)


class ResourceHostHistoryService:
    """使用既有健康指标表持久化整机容量分钟汇总。"""

    def __init__(
        self,
        repository: Any,
        now: Optional[Callable[[], datetime] | datetime] = None,
    ) -> None:
        self._repository = repository
        if callable(now):
            self._now = now
        elif isinstance(now, datetime):
            self._now = lambda: now
        else:
            self._now = lambda: datetime.now(timezone.utc)

    def record_if_due(self, snapshot: object) -> bool:
        """在当前 UTC 分钟尚未保存时持久化一条安全的容量摘要。"""
        try:
            extra = self._safe_extra(snapshot)
            if extra is None:
                return False
            current_time = self._as_utc(self._now())
            minute = current_time.replace(second=0, microsecond=0)
            if self._has_recorded_minute(minute):
                return False

            self._repository.save_health_metrics(
                HealthMetrics(
                    metric_id=f"resource-host-{minute.strftime('%Y%m%dT%H%M')}-{uuid4().hex}",
                    subsystem=Subsystem.RESOURCE_MONITORING,
                    timestamp=minute,
                    extra=extra,
                )
            )
            self.purge_expired(current_time)
            return True
        except Exception as exc:
            logger.warning("resource host history record failed", error_type=type(exc).__name__)
            return False

    def list_history(self) -> list[dict[str, object]]:
        """返回最多 1500 条按时间升序排列的安全公开容量点位。"""
        try:
            metrics = self._repository.list_metrics(
                subsystem=Subsystem.RESOURCE_MONITORING,
                limit=_MAX_HISTORY_POINTS,
                metric_type="host_capacity",
            )
            points: list[dict[str, object]] = []
            for metric in metrics:
                extra = metric.extra if isinstance(metric.extra, Mapping) else {}
                if extra.get("metric_type") != "host_capacity":
                    continue
                points.append(
                    {
                        "timestamp": metric.timestamp,
                        "host": self._safe_fields(extra.get("host"), _HOST_FIELDS),
                        "alpha": self._safe_fields(extra.get("alpha"), _ALPHA_FIELDS),
                    }
                )
            return sorted(points, key=lambda point: self._as_utc(point["timestamp"]))
        except Exception as exc:
            logger.warning("resource host history query failed", error_type=type(exc).__name__)
            return []

    def purge_expired(self, now: Optional[datetime] = None) -> int:
        """精确删除超过 24 小时的容量历史，不影响其他资源监控指标。"""
        try:
            current_time = self._as_utc(now or self._now())
            cutoff = current_time - _RETENTION
            metrics = self._repository.list_metrics(
                subsystem=Subsystem.RESOURCE_MONITORING,
                until=cutoff,
                limit=_MAX_HISTORY_POINTS,
                metric_type="host_capacity",
            )
            expired_ids = [
                metric.metric_id
                for metric in metrics
                if self._is_host_capacity(metric)
                and self._as_utc(metric.timestamp) < cutoff
                and isinstance(metric.metric_id, str)
                and metric.metric_id
            ]
            if not expired_ids:
                return 0
            return self._repository.delete_health_metrics(expired_ids)
        except Exception as exc:
            logger.warning("resource host history purge failed", error_type=type(exc).__name__)
            return 0

    def _has_recorded_minute(self, minute: datetime) -> bool:
        metrics = self._repository.list_metrics(
            subsystem=Subsystem.RESOURCE_MONITORING,
            since=minute,
            until=minute + timedelta(minutes=1) - timedelta(microseconds=1),
            limit=_MAX_HISTORY_POINTS,
            metric_type="host_capacity",
        )
        return any(
            self._is_host_capacity(metric)
            and minute <= self._as_utc(metric.timestamp) < minute + timedelta(minutes=1)
            for metric in metrics
        )

    @staticmethod
    def _is_host_capacity(metric: HealthMetrics) -> bool:
        return (
            metric.subsystem == Subsystem.RESOURCE_MONITORING
            and isinstance(metric.extra, Mapping)
            and metric.extra.get("metric_type") == "host_capacity"
        )

    def _safe_extra(self, snapshot: object) -> Optional[dict[str, object]]:
        if not isinstance(snapshot, Mapping):
            logger.warning("resource host history snapshot rejected", error_type="invalid_snapshot")
            return None
        host = snapshot.get("host")
        if not isinstance(host, Mapping):
            logger.warning("resource host history snapshot rejected", error_type="invalid_host")
            return None
        summary = snapshot.get("summary")
        return {
            "metric_type": "host_capacity",
            "host": self._safe_fields(host, _HOST_FIELDS),
            "alpha": self._safe_fields(summary, _ALPHA_FIELDS),
        }

    @staticmethod
    def _safe_fields(source: object, fields: tuple[str, ...]) -> dict[str, Optional[int | float]]:
        values = source if isinstance(source, Mapping) else {}
        return {
            field: ResourceHostHistoryService._number_or_none(values.get(field)) for field in fields
        }

    @staticmethod
    def _number_or_none(value: object) -> Optional[int | float]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return value if math.isfinite(value) else None

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
