"""在 API 进程内持续采样并持久化资源监控数据。"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, MutableMapping
from contextlib import AbstractContextManager
from typing import Any, Optional

from core.observability import get_logger

logger = get_logger(__name__)


class ResourceMonitorRuntime:
    """以单一可停止线程协调资源快照、历史和告警评估。"""

    def __init__(
        self,
        *,
        monitor: Optional[Any] = None,
        history_factory: Optional[Callable[[Any], Any]] = None,
        alert_factory: Optional[Callable[..., Any]] = None,
        session_factory: Optional[Callable[[], AbstractContextManager[Any]]] = None,
        repository_factory: Optional[Callable[[Any], Any]] = None,
        interval_seconds: float = 60.0,
        state: Optional[MutableMapping[str, Any]] = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._monitor = monitor or self._create_monitor()
        self._history_factory = history_factory or self._create_history_service
        self._alert_factory = alert_factory or self._create_alert_service
        self._session_factory = session_factory or self._create_session
        self._repository_factory = repository_factory or self._create_repository
        self._interval_seconds = interval_seconds
        self._state: MutableMapping[str, Any] = state if state is not None else {}
        self._monotonic = monotonic
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_error_type: Optional[str] = None

    @property
    def state(self) -> MutableMapping[str, Any]:
        """返回跨采样周期共享的告警状态容器。"""
        return self._state

    @property
    def last_error_type(self) -> Optional[str]:
        """返回最近一次采样失败的异常类型，成功后清空。"""
        return self._last_error_type

    def start(self) -> bool:
        """启动后台线程；已有活动线程时不重复启动。"""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            if self._stop_event.is_set():
                self._stop_event = threading.Event()
            thread = threading.Thread(
                target=self._run,
                name="resource-monitor-runtime",
                daemon=True,
            )
            self._thread = thread
            try:
                thread.start()
            except Exception as exc:
                self._thread = None
                logger.warning(
                    "resource monitor runtime thread startup failed",
                    error_type=type(exc).__name__,
                )
                raise
        logger.info("resource monitor runtime started", interval_seconds=self._interval_seconds)
        return True

    def stop(self) -> bool:
        """请求线程停止，并等待正在运行的采样完成。"""
        with self._lock:
            thread = self._thread
            if thread is None or not thread.is_alive():
                return False
            self._stop_event.set()
        if thread is not threading.current_thread():
            thread.join()
        logger.info("resource monitor runtime stopped")
        return True

    def run_once(self) -> bool:
        """执行一次快照采集、分钟历史写入和告警评估。"""
        self._last_error_type = None
        try:
            snapshot = self._monitor.collect_snapshot()
            with self._session_factory() as session:
                repository = self._repository_factory(session)
                success = self._record_history(repository, snapshot)
                return self._evaluate_alerts(repository, snapshot) and success
        except Exception as exc:
            self._record_failure(exc, "resource monitor runtime cycle failed")
            return False

    def _run(self) -> None:
        next_run_at = self._monotonic()
        while not self._stop_event.is_set():
            if self._monotonic() >= next_run_at:
                self.run_once()
                next_run_at = self._monotonic() + self._interval_seconds
            wait_seconds = max(0.0, next_run_at - self._monotonic())
            self._stop_event.wait(wait_seconds)

    def _record_history(self, repository: Any, snapshot: Any) -> bool:
        try:
            self._history_factory(repository).record_if_due(snapshot)
            return True
        except Exception as exc:
            self._record_failure(exc, "resource monitor history record failed")
            return False

    def _evaluate_alerts(self, repository: Any, snapshot: Any) -> bool:
        try:
            self._alert_factory(repository, state=self._state).evaluate(snapshot)
            return True
        except Exception as exc:
            self._record_failure(exc, "resource monitor alert evaluation failed")
            return False

    def _record_failure(self, exc: Exception, event: str) -> None:
        self._last_error_type = type(exc).__name__
        logger.warning(event, error_type=self._last_error_type)

    @staticmethod
    def _create_monitor() -> Any:
        from services.resource_monitor_service import ResourceMonitoringService

        return ResourceMonitoringService()

    @staticmethod
    def _create_history_service(repository: Any) -> Any:
        from services.resource_host_history_service import ResourceHostHistoryService

        return ResourceHostHistoryService(repository)

    @staticmethod
    def _create_alert_service(repository: Any, *, state: MutableMapping[str, Any]) -> Any:
        from services.resource_monitor_alert_service import ResourceMonitorAlertService

        try:
            return ResourceMonitorAlertService(repository, state=state)
        except TypeError:
            return ResourceMonitorAlertService(repository)

    @staticmethod
    def _create_session() -> AbstractContextManager[Any]:
        from data_layer.repositories.base import db_session

        return db_session()

    @staticmethod
    def _create_repository(session: Any) -> Any:
        from data_layer.repositories.monitoring_repository import MonitoringRepositoryImpl

        return MonitoringRepositoryImpl(session)
