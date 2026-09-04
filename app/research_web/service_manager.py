"""Persistent, project-owned process manager for the Research Workbench Web stack."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.observability import get_logger

log = get_logger(__name__)

WEB_PORT = 8088
RUNTIME_PORT = 3081
WEB_URL = f"http://127.0.0.1:{WEB_PORT}/#/fingpt"
ACTIVE_STATES = {"running", "awaiting_approval", "disconnected", "interrupted"}


class ServiceManagerError(RuntimeError):
    """Safe CLI-facing service lifecycle failure."""


@dataclass(frozen=True)
class ManagedProcess:
    role: str
    port: int
    command: tuple[str, ...]
    signature: tuple[str, ...]


class WebServiceManager:
    """Start and stop only processes whose private state and command both match."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        data_root: Path | None = None,
        runtime_source: Path | None = None,
        python: str | None = None,
        node: str | None = None,
    ) -> None:
        self.project_root = (project_root or Path(__file__).parents[2]).resolve()
        configured_data = os.environ.get("RESEARCH_DATA_HOME")
        self.data_root = (
            data_root
            or (Path(configured_data).expanduser() if configured_data else None)
            or Path.home() / ".research-workbench" / "research-web"
        ).resolve()
        configured_source = os.environ.get("RESEARCH_DSH_SOURCE")
        self.runtime_source = (
            runtime_source
            or (Path(configured_source).expanduser() if configured_source else None)
            or self.data_root.parent / "dsh-source"
        ).resolve()
        self.python = python or sys.executable
        self.node = node or shutil.which("node") or "/usr/local/bin/node"
        self.run_root = self.data_root.parent / "run"
        self.log_root = self.data_root.parent / "logs"

    def _processes(self) -> tuple[ManagedProcess, ManagedProcess]:
        runtime_command = (
            self.python,
            "-m",
            "app.research_web.launch_runtime",
            "--source",
            str(self.runtime_source),
            "--data",
            str(self.data_root),
            "--node",
            self.node,
            "--port",
            str(RUNTIME_PORT),
            "--datahub-url",
            f"http://127.0.0.1:{WEB_PORT}",
            "--research-tools",
        )
        web_command = (
            self.python,
            "-m",
            "uvicorn",
            "app.research_web.main:app",
            "--app-dir",
            str(self.project_root),
            "--host",
            "127.0.0.1",
            "--port",
            str(WEB_PORT),
        )
        return (
            ManagedProcess(
                "runtime",
                RUNTIME_PORT,
                runtime_command,
                (
                    str(self.runtime_source / "apps/cli/lib/bin.js"),
                    str(self.data_root / "runtime/overlay.yml"),
                    str(RUNTIME_PORT),
                ),
            ),
            ManagedProcess(
                "web",
                WEB_PORT,
                web_command,
                ("app.research_web.main:app", str(self.project_root), str(WEB_PORT)),
            ),
        )

    def _prepare_private_directories(self) -> None:
        for path in (self.data_root, self.run_root, self.log_root):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            if path.is_symlink() or path.stat().st_mode & 0o077:
                raise ServiceManagerError(f"私有运行目录不安全：{path}")

    def _state_path(self, role: str) -> Path:
        return self.run_root / f"{role}.json"

    @staticmethod
    def _fingerprint(command: tuple[str, ...] | list[str]) -> str:
        payload = json.dumps(list(command), ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def _write_state(self, process: ManagedProcess, pid: int) -> None:
        payload = {
            "version": 1,
            "role": process.role,
            "pid": pid,
            "port": process.port,
            "started_at": time.time(),
            "project_root": str(self.project_root),
            "data_root": str(self.data_root),
            "command": list(process.command),
            "fingerprint": self._fingerprint(process.command),
            "signature": list(process.signature),
        }
        fd, name = tempfile.mkstemp(prefix=f"{process.role}-", dir=self.run_root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, 0o600)
            os.replace(name, self._state_path(process.role))
        except OSError as exc:
            Path(name).unlink(missing_ok=True)
            raise ServiceManagerError("无法写入服务状态") from exc

    def _read_state(self, process: ManagedProcess) -> dict[str, Any] | None:
        path = self._state_path(process.role)
        if not path.exists():
            return None
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            if (
                state.get("version") != 1
                or state.get("role") != process.role
                or state.get("port") != process.port
                or state.get("project_root") != str(self.project_root)
                or state.get("data_root") != str(self.data_root)
                or not isinstance(state.get("command"), list)
                or state.get("fingerprint") != self._fingerprint(state["command"])
                or state.get("signature") != list(process.signature)
                or not isinstance(state.get("pid"), int)
                or state["pid"] <= 1
            ):
                raise ValueError("state mismatch")
            return state
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            log.warning("research_service_state_invalid", role=process.role)
            raise ServiceManagerError(f"{process.role} 服务状态无法安全确认") from exc

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    @staticmethod
    def _command_line(pid: int) -> str:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def _owned_state(self, process: ManagedProcess) -> dict[str, Any] | None:
        state = self._read_state(process)
        if state is None:
            return None
        pid = state["pid"]
        if not self._pid_exists(pid):
            self._state_path(process.role).unlink(missing_ok=True)
            return None
        command_line = self._command_line(pid)
        if not command_line or any(part not in command_line for part in process.signature):
            raise ServiceManagerError(f"{process.role} PID 已被其他进程占用，拒绝操作")
        return state

    @staticmethod
    def _port_open(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            return sock.connect_ex(("127.0.0.1", port)) == 0

    @staticmethod
    def _json_request(
        port: int, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(2 * 1024 * 1024)
            if response.status < 200 or response.status >= 300:
                raise ServiceManagerError(f"HTTP {response.status}")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ServiceManagerError("响应不是 JSON 对象")
            return value
        except (OSError, ValueError, json.JSONDecodeError, http.client.HTTPException) as exc:
            raise ServiceManagerError("本地服务尚未就绪") from exc
        finally:
            connection.close()

    def _runtime_healthy(self) -> bool:
        rpc_id = str(uuid4())
        try:
            value = self._json_request(
                RUNTIME_PORT,
                "POST",
                "/api/host.describe",
                {
                    "type": "client-request",
                    "rpcId": rpc_id,
                    "method": "host.describe",
                    "payload": {},
                },
            )
            return (
                value.get("type") == "server-response"
                and value.get("rpcId") == rpc_id
                and value.get("result", {}).get("ok") is True
            )
        except ServiceManagerError:
            return False

    def _web_healthy(self) -> bool:
        try:
            value = self._json_request(WEB_PORT, "GET", "/api/research/runtime")
            return value.get("connected") is True
        except ServiceManagerError:
            return False

    @staticmethod
    def _wait(check, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if check():
                return True
            time.sleep(0.25)
        return False

    def _spawn(self, process: ManagedProcess) -> int:
        log_path = self.log_root / f"{process.role}.log"
        environment = os.environ.copy()
        environment.update(
            {
                "RESEARCH_DATA_HOME": str(self.data_root),
                "RESEARCH_RUNTIME_URL": f"http://127.0.0.1:{RUNTIME_PORT}",
                "RESEARCH_DSH_SOURCE": str(self.runtime_source),
                "PYTHONUNBUFFERED": "1",
            }
        )
        try:
            stream = log_path.open("ab", buffering=0)
            try:
                child = subprocess.Popen(
                    process.command,
                    cwd=self.project_root,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    close_fds=True,
                )
            finally:
                stream.close()
            self._write_state(process, child.pid)
            log.info("research_service_started", role=process.role, pid=child.pid)
            return child.pid
        except OSError as exc:
            log.error("research_service_start_failed", role=process.role)
            raise ServiceManagerError(f"无法启动 {process.role} 服务") from exc

    def _ensure_startable(self, process: ManagedProcess) -> bool:
        state = self._owned_state(process)
        if state is not None:
            return False
        if self._port_open(process.port):
            raise ServiceManagerError(f"端口 {process.port} 已被非本项目进程占用，未执行启动")
        return True

    def start(self, *, open_browser: bool = True) -> dict[str, Any]:
        self._prepare_private_directories()
        if not self.runtime_source.is_dir():
            raise ServiceManagerError("DSH 源码目录不存在；请设置 RESEARCH_DSH_SOURCE")
        if not Path(self.python).exists() or not Path(self.node).exists():
            raise ServiceManagerError("Python 或 Node.js 可执行文件不存在")
        runtime, web = self._processes()
        created: list[ManagedProcess] = []
        try:
            if self._ensure_startable(runtime):
                self._spawn(runtime)
                created.append(runtime)
            if not self._wait(self._runtime_healthy, 35):
                raise ServiceManagerError("DSH 3081 启动超时，请查看 runtime.log")
            if self._ensure_startable(web):
                self._spawn(web)
                created.append(web)
            if not self._wait(self._web_healthy, 35):
                raise ServiceManagerError("Web 8088 启动超时，请查看 web.log")
        except Exception:
            for process in reversed(created):
                try:
                    self._stop_one(process)
                except ServiceManagerError:
                    log.error("research_service_rollback_failed", role=process.role)
            raise
        if open_browser:
            webbrowser.open(WEB_URL)
        return self.status()

    def _active_research(self) -> list[str]:
        try:
            result = self._json_request(WEB_PORT, "GET", "/api/research/sessions")
        except ServiceManagerError:
            raise ServiceManagerError("无法核对活动研究；未执行重启，可显式使用 --force")
        return [
            str(item.get("id"))
            for item in result.get("items", [])
            if item.get("status") in ACTIVE_STATES
        ]

    def _stop_one(self, process: ManagedProcess) -> bool:
        state = self._owned_state(process)
        if state is None:
            return False
        pid = state["pid"]
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            self._state_path(process.role).unlink(missing_ok=True)
            return False
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and self._pid_exists(pid):
            time.sleep(0.1)
        if self._pid_exists(pid):
            if self._owned_state(process) is None:
                raise ServiceManagerError(f"无法确认 {process.role} 进程归属")
            os.killpg(pid, signal.SIGKILL)
        self._state_path(process.role).unlink(missing_ok=True)
        log.info("research_service_stopped", role=process.role, pid=pid)
        return True

    def stop(self) -> dict[str, Any]:
        self._prepare_private_directories()
        runtime, web = self._processes()
        self._stop_one(web)
        self._stop_one(runtime)
        return self.status()

    def restart(self, *, force: bool = False, open_browser: bool = True) -> dict[str, Any]:
        self._prepare_private_directories()
        runtime, web = self._processes()
        running = self._owned_state(runtime) is not None or self._owned_state(web) is not None
        if running and not force:
            active = self._active_research()
            if active:
                raise ServiceManagerError(
                    f"存在 {len(active)} 个活动研究，拒绝重启；确需中断时使用 --force"
                )
        self.stop()
        return self.start(open_browser=open_browser)

    def status(self) -> dict[str, Any]:
        self._prepare_private_directories()
        result: dict[str, Any] = {"url": WEB_URL, "services": {}}
        for process in self._processes():
            state = self._owned_state(process)
            healthy = self._runtime_healthy() if process.role == "runtime" else self._web_healthy()
            result["services"][process.role] = {
                "running": state is not None,
                "healthy": healthy,
                "pid": state["pid"] if state else None,
                "port": process.port,
                "log": str(self.log_root / f"{process.role}.log"),
            }
        return result


def format_status(status: dict[str, Any]) -> str:
    lines = []
    for role in ("runtime", "web"):
        item = status["services"][role]
        state = "healthy" if item["healthy"] else "running" if item["running"] else "stopped"
        lines.append(f"{role}: {state} (port {item['port']}, pid {item['pid'] or '-'})")
    lines.append(f"url: {status['url']}")
    return "\n".join(lines)
