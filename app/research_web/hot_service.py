"""Bounded lazy Host bridge; Hot faults never own base research startup."""

from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Lock

from core.observability import get_logger
from research_workbench_entrypoint.hot import HotError, _read, normalize, save_settings, status
from research_workbench_entrypoint.hot_manager import HotManager

from .credential_backend import default_credential_backend

log = get_logger(__name__)


class HotWebError(RuntimeError):
    """Stable, content-free HTTP error."""

    def __init__(self, code: str, message: str, status_code: int = 503):
        super().__init__(message)
        self.code, self.status = code, status_code


class HotWebService:
    def __init__(self, project: Path, home: Path, *, manager_factory=None, capacity: int = 4, deadline: float = 20):
        self.project, self.home = project, home
        self._manager_factory = manager_factory
        self._manager_instance = None
        self._manager_lock = Lock()
        self._capacity = asyncio.Semaphore(capacity)
        self._deadline = deadline
        self._inflight: set[asyncio.Task] = set()
        self._closed = False

    def _manager(self):
        with self._manager_lock:
            if self._manager_instance is None:
                self._manager_instance = self._manager_factory() if self._manager_factory else HotManager(self.project, self.home, default_credential_backend())
        return self._manager_instance

    def _perform(self, operation: str, args: tuple):
        if operation == "status":
            basic = status(self.project, self.home)
            if not (self.home / "hot" / "process.json").exists():
                return {**basic, "state": "stopped" if basic["enabled"] else "disabled", "service": "stopped"}
            return {**self._manager().status(), "enabled": basic["enabled"]}
        if operation == "configuration":
            path = self.home / "hot" / "settings.json"
            if not path.exists():
                return {"configured": False, "config": _read(self.project / "services/hot/config.example.json")}
            value = _read(path, private=True)
            if value.get("projectRoot") != str(self.project):
                raise HotError("hot_foreign_config")
            return {"configured": True, "config": normalize(self.project, value["config"])}
        if operation == "configure":
            return save_settings(self.project, self.home, args[0])
        allowed = {"channels", "events", "event_detail", "sources", "configure_channel", "correct_event", "configure_source", "start", "stop", "restart"}
        if operation not in allowed:
            raise HotError("hot_web_operation_invalid")
        return getattr(self._manager(), operation)(*args)

    async def call(self, operation: str, *args, request_id: str | None = None):
        if self._closed:
            raise HotWebError("hot_host_closed", "热点服务桥接已关闭。")
        try:
            await asyncio.wait_for(self._capacity.acquire(), timeout=0.1)
        except TimeoutError:
            raise HotWebError("hot_host_busy", "热点请求较多，请稍后重试。") from None
        if self._closed:
            self._capacity.release()
            raise HotWebError("hot_host_closed", "热点服务桥接已关闭。")
        task = asyncio.create_task(asyncio.to_thread(self._perform, operation, args))
        self._inflight.add(task)
        def finished(completed):
            self._inflight.discard(completed)
            self._capacity.release()
            # Consume late exceptions without logging inputs or backend diagnostics.
            if not completed.cancelled() and completed.exception() is not None:
                log.warning("hot_host_operation_failed")
        task.add_done_callback(finished)
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=self._deadline)
        except TimeoutError:
            log.warning("hot_host_deadline")
            if request_id:
                return {"state": "outcome_unknown", "code": "hot_host_outcome_unknown", "requestId": request_id}
            raise HotWebError("hot_host_timeout", "热点服务响应超时，基础研究仍可使用。") from None
        except HotError as error:
            code = str(error)
            if "conflict" in code:
                raise HotWebError(code, "版本或请求参数冲突，请先刷新并核对。", 409) from None
            if any(term in code for term in ("invalid", "limit", "required")):
                raise HotWebError(code, "请求格式或范围不正确。", 400) from None
            if "denied" in code:
                raise HotWebError(code, "当前操作未获授权。", 403) from None
            raise HotWebError(code, "Hot 尚未就绪，请检查配置、服务与数据库状态。") from None
        except (OSError, ValueError, TypeError, KeyError):
            raise HotWebError("hot_host_unavailable", "热点服务暂时不可用。") from None
        except Exception:
            log.warning("hot_host_backend_failed")
            raise HotWebError("hot_host_unavailable", "热点服务暂时不可用。") from None

    async def close(self):
        self._closed = True
        # Stop admitting requests, not the independently managed Hot daemon.
        if self._inflight:
            await asyncio.wait(set(self._inflight), timeout=2)
