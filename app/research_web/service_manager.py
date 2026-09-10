"""Persistent, project-owned process manager for the Research Workbench Web stack."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
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

from .launch_runtime import PINNED_COMMIT

log = get_logger(__name__)

WEB_PORT = 8088
RUNTIME_PORT = 3081
WEB_URL = f"http://127.0.0.1:{WEB_PORT}/#/fingpt"
ACTIVE_STATES = {"running", "awaiting_approval", "disconnected", "interrupted"}
RUNTIME_TOKEN_PATTERN = re.compile(
    r"dsh web: http://127\.0\.0\.1:(\d+)/\?token=([A-Za-z0-9_-]{43})"
)


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
        web_port: int = WEB_PORT,
        runtime_port: int = RUNTIME_PORT,
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
        self.web_port = web_port
        self.runtime_port = runtime_port
        self.web_url = f"http://127.0.0.1:{self.web_port}/#/fingpt"
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
            str(self.runtime_port),
            "--datahub-url",
            f"http://127.0.0.1:{self.web_port}",
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
            str(self.web_port),
        )
        return (
            ManagedProcess(
                "runtime",
                self.runtime_port,
                runtime_command,
                (
                    str(self.runtime_source / "apps/cli/lib/bin.js"),
                    str(self.data_root / "runtime/overlay.yml"),
                    str(self.runtime_port),
                ),
            ),
            ManagedProcess(
                "web",
                self.web_port,
                web_command,
                ("app.research_web.main:app", str(self.project_root), str(self.web_port)),
            ),
        )

    def _prepare_private_directories(self) -> None:
        for path in (self.data_root, self.run_root, self.log_root):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            if path.is_symlink() or path.stat().st_mode & 0o077:
                raise ServiceManagerError(f"私有运行目录不安全：{path}")

    def _state_path(self, role: str) -> Path:
        return self.run_root / f"{role}.json"

    def _runtime_auth_path(self) -> Path:
        return self.data_root / "runtime" / "auth.json"

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
        except (OSError, TypeError, json.JSONDecodeError) as exc:
            log.warning("research_service_state_invalid", role=process.role)
            raise ServiceManagerError(f"{process.role} 服务状态无法安全确认") from exc
        valid = (
            state.get("version") == 1
            and state.get("role") == process.role
            and state.get("port") == process.port
            and state.get("project_root") == str(self.project_root)
            and state.get("data_root") == str(self.data_root)
            and isinstance(state.get("command"), list)
            and state.get("fingerprint") == self._fingerprint(state["command"])
            and state.get("signature") == list(process.signature)
            and isinstance(state.get("pid"), int)
            and state["pid"] > 1
        )
        if valid:
            return state
        pid = state.get("pid")
        if isinstance(pid, int) and pid > 1 and not self._pid_exists(pid):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                raise ServiceManagerError(f"{process.role} 过期服务状态无法清理") from exc
            log.info("research_service_stale_state_removed", role=process.role, pid=pid)
            return None
        log.warning("research_service_state_invalid", role=process.role)
        raise ServiceManagerError(f"{process.role} 服务状态无法安全确认")

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
        port: int,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        headers.update(extra_headers or {})
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

    def _read_runtime_auth(self) -> dict[str, str] | None:
        path = self._runtime_auth_path()
        if not path.exists():
            return None
        try:
            identity = path.lstat()
            value = json.loads(path.read_text(encoding="utf-8"))
            expected = {
                "authority": f"127.0.0.1:{self.runtime_port}",
                "cwd": str((self.data_root / "runtime/work").resolve()),
                "source_commit": PINNED_COMMIT,
            }
            if (
                path.is_symlink()
                or not path.is_file()
                or identity.st_mode & 0o077
                or not isinstance(value, dict)
                or any(value.get(key) != item for key, item in expected.items())
                or not isinstance(value.get("cookie"), str)
                or not value["cookie"].startswith("dsh-auth-")
                or "\r" in value["cookie"]
                or "\n" in value["cookie"]
                or len(value["cookie"]) > 4096
                or not isinstance(value.get("version"), str)
            ):
                raise ValueError("invalid runtime auth record")
            return {key: str(item) for key, item in value.items()}
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            log.warning("research_runtime_auth_invalid")
            return None

    def _runtime_launch_token(self) -> str | None:
        log_path = self.log_root / "runtime.log"
        try:
            with log_path.open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                stream.seek(max(0, size - 2 * 1024 * 1024))
                text = stream.read().decode("utf-8", errors="replace")
        except OSError:
            return None
        matches = [
            token
            for port, token in RUNTIME_TOKEN_PATTERN.findall(text)
            if int(port) == self.runtime_port
        ]
        return matches[-1] if matches else None

    def _exchange_runtime_cookie(self, token: str) -> str | None:
        connection = http.client.HTTPConnection("127.0.0.1", self.runtime_port, timeout=2)
        try:
            connection.request("GET", f"/?token={token}")
            response = connection.getresponse()
            response.read(4096)
            raw = response.getheader("Set-Cookie")
            if response.status != 303 or raw is None:
                return None
            cookie = raw.split(";", 1)[0]
            if (
                not cookie.startswith("dsh-auth-")
                or "\r" in cookie
                or "\n" in cookie
                or len(cookie) > 4096
            ):
                return None
            return cookie
        except (OSError, http.client.HTTPException):
            return None
        finally:
            connection.close()

    def _write_runtime_auth(self, cookie: str) -> dict[str, str]:
        runtime = self.data_root / "runtime"
        runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        package = json.loads((self.runtime_source / "package.json").read_text(encoding="utf-8"))
        value = {
            "authority": f"127.0.0.1:{self.runtime_port}",
            "cookie": cookie,
            "cwd": str((runtime / "work").resolve()),
            "source_commit": PINNED_COMMIT,
            "version": str(package["version"]),
        }
        fd, name = tempfile.mkstemp(prefix="auth-", dir=runtime)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, 0o600)
            os.replace(name, self._runtime_auth_path())
        except (OSError, KeyError, TypeError, ValueError) as exc:
            Path(name).unlink(missing_ok=True)
            raise ServiceManagerError("无法写入 DSH 认证控制文件") from exc
        return value

    def _runtime_healthy(self) -> bool:
        rpc_id = str(uuid4())
        auth = self._read_runtime_auth()
        if auth is None:
            token = self._runtime_launch_token()
            cookie = self._exchange_runtime_cookie(token) if token else None
            if cookie is None:
                return False
            try:
                auth = self._write_runtime_auth(cookie)
            except (OSError, ValueError, json.JSONDecodeError, ServiceManagerError):
                return False
        try:
            value = self._json_request(
                self.runtime_port,
                "POST",
                "/api/session/list",
                {
                    "type": "client-request",
                    "rpcId": rpc_id,
                    "method": "session/list",
                    "payload": {"args": {"_request": {}}},
                },
                {"Cookie": auth["cookie"]},
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
            value = self._json_request(self.web_port, "GET", "/api/research/runtime")
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
                "RESEARCH_RUNTIME_URL": f"http://127.0.0.1:{self.runtime_port}",
                "RESEARCH_RUNTIME_AUTH": str(self._runtime_auth_path()),
                "RESEARCH_DSH_SOURCE": str(self.runtime_source),
                "PYTHONUNBUFFERED": "1",
            }
        )
        try:
            if process.role == "runtime":
                self._runtime_auth_path().unlink(missing_ok=True)
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
                raise ServiceManagerError(f"DSH {self.runtime_port} 启动超时，请查看 runtime.log")
            if self._ensure_startable(web):
                self._spawn(web)
                created.append(web)
            if not self._wait(self._web_healthy, 35):
                raise ServiceManagerError(f"Web {self.web_port} 启动超时，请查看 web.log")
        except Exception:
            for process in reversed(created):
                try:
                    self._stop_one(process)
                except ServiceManagerError:
                    log.error("research_service_rollback_failed", role=process.role)
            raise
        if open_browser:
            webbrowser.open(self.web_url)
        return self.status()

    def _active_research(self) -> list[str]:
        try:
            result = self._json_request(self.web_port, "GET", "/api/research/sessions")
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
        if process.role == "runtime":
            self._runtime_auth_path().unlink(missing_ok=True)
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
        result: dict[str, Any] = {"url": self.web_url, "services": {}}
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

    def tabbit_status(self) -> dict[str, Any]:
        """Return the safe, read-only Tabbit diagnostic exposed by the BFF."""
        if not self._web_healthy():
            raise ServiceManagerError("Research Web 尚未就绪；请先运行 rwb web start")
        value = self._json_request(self.web_port, "GET", "/api/research/runtime/tabbit")
        allowed = {
            "status",
            "browser_enabled",
            "web_fetch_enabled",
            "plugin_version",
            "browser_version",
            "launcher_present",
            "cli_available",
            "online_instances",
            "selected_instance",
            "restart_required",
        }
        return {key: value.get(key) for key in allowed}


def format_status(status: dict[str, Any]) -> str:
    lines = []
    for role in ("runtime", "web"):
        item = status["services"][role]
        state = "healthy" if item["healthy"] else "running" if item["running"] else "stopped"
        lines.append(f"{role}: {state} (port {item['port']}, pid {item['pid'] or '-'})")
    lines.append(f"url: {status['url']}")
    return "\n".join(lines)


def format_tabbit_status(status: dict[str, Any]) -> str:
    """Render diagnostics without paths, page metadata, cookies, or content."""
    return "\n".join(
        [
            f"status: {status.get('status') or 'error'}",
            f"browser automation: {'enabled' if status.get('browser_enabled') else 'disabled'}",
            f"web_fetch takeover: {'enabled' if status.get('web_fetch_enabled') else 'disabled'}",
            f"plugin: {status.get('plugin_version') or 'unknown'}",
            f"browser: {status.get('browser_version') or 'unknown'}",
            f"launcher: {'available' if status.get('launcher_present') else 'missing'}",
            f"online instances: {status.get('online_instances') or 0}",
            f"selected instance: {status.get('selected_instance') or '-'}",
            f"restart required: {'yes' if status.get('restart_required') else 'no'}",
        ]
    )
