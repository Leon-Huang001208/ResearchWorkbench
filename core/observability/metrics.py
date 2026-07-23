import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    name: str
    value: float | int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """指标收集器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> "MetricsCollector":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._metrics: list[Metric] = []
        self._initialized = True

    def increment(self, name: str, value: int = 1, tags: dict[str, str] | None = None) -> None:
        """增加计数器"""
        with self._lock:
            self._counters[name] += value
            self._metrics.append(Metric(name=name, value=value, tags=tags or {}))
        logger.debug("metric increment", metric_name=name, value=value, tags=tags)

    def record(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """记录直方图值"""
        with self._lock:
            self._histograms[name].append(value)
            self._metrics.append(Metric(name=name, value=value, tags=tags or {}))
        logger.debug("metric record", metric_name=name, value=value, tags=tags)

    def get_counter(self, name: str) -> int:
        """获取计数器值"""
        return self._counters.get(name, 0)

    def get_histogram_stats(self, name: str) -> dict[str, float] | None:
        """获取直方图统计"""
        values = self._histograms.get(name, [])
        if not values:
            return None
        import statistics

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
        }

    def get_recent_metrics(self, limit: int = 100) -> list[Metric]:
        """获取最近的指标"""
        with self._lock:
            return self._metrics[-limit:]
