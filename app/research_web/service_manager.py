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
import stat
import subprocess
import sys
import tempfile
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from core.observability import get_logger

from .launch_runtime import PINNED_COMMIT, calculate_build_closure
from .runtime_auth import read_runtime_auth_record

log = get_logger(__name__)

WEB_PORT = 8088
RUNTIME_PORT = 3081
WEB_URL = f"http://127.0.0.1:{WEB_PORT}/#/fingpt"
ACTIVE_STATES = {"running", "awaiting_approval", "disconnected", "interrupted"}
RUNTIME_TOKEN_PATTERN = re.compile(
    r"dsh web: http://127\.0\.0\.1:(\d+)/\?token=([A-Za-z0-9_-]{43})"
)
CJPY_VERSION = "0.5.2"
CJPY_SHA256 = "d8c6820a718ae5f79061b54815473dd3ecd3be73cd808634fbac5bc1c385bd94"
ENVIRONMENT_MARKER = ".rwb-web-environment.json"


class ServiceManagerError(RuntimeError):
    """Safe CLI-facing service lifecycle failure."""


def _is_unsafe_private_directory(
    path: Path,
    identity: os.stat_result,
    *,
    platform_name: str,
) -> bool:
    """Validate directory structure without treating Windows mode bits as ACLs."""
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    is_reparse_point = bool(getattr(identity, "st_file_attributes", 0) & reparse_flag)
    return (
        not stat.S_ISDIR(identity.st_mode)
        or path.is_symlink()
        or is_reparse_point
        or (platform_name != "nt" and bool(identity.st_mode & 0o077))
    )


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
            or self.data_root.parent / "runtime" / "dsh" / PINNED_COMMIT
        ).resolve()
        self.python = python or sys.executable
        self.node = (
            node
            or os.environ.get("RESEARCH_NODE_BINARY")
            or shutil.which("node")
            or "/usr/local/bin/node"
        )
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
            ManagedProcess(  # type: ignore[call-arg]
                "runtime",
                self.runtime_port,
                runtime_command,
                (
                    str(self.runtime_source / "apps/cli/lib/bin.js"),
                    str(self.data_root / "runtime/overlay.yml"),
                    str(self.runtime_port),
                ),
            ),
            ManagedProcess(  # type: ignore[call-arg]
                "web",
                self.web_port,
                web_command,
                ("app.research_web.main:app", str(self.project_root), str(self.web_port)),
            ),
        )

    def _prepare_private_directories(self) -> None:
        for path in (self.data_root, self.run_root, self.log_root):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            identity = path.lstat()
            if _is_unsafe_private_directory(path, identity, platform_name=os.name):
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
    def _pid_exists(pid: int, *, platform_name: str | None = None) -> bool:
        platform_name = platform_name or os.name
        if platform_name == "nt":
            try:
                result = subprocess.run(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        (
                            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) "
                            "{ exit 0 } else { exit 1 }"
                        ),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=False,
                )
            except (OSError, subprocess.SubprocessError):
                return True
            return result.returncode == 0
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        try:
            status = subprocess.run(
                ["ps", "-p", str(pid), "-o", "stat="],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
                shell=False,
            )
            if status.returncode == 0 and status.stdout.strip().startswith("Z"):
                return False
        except (OSError, subprocess.SubprocessError):
            pass
        return True

    @staticmethod
    def _command_line(pid: int, *, platform_name: str | None = None) -> str:
        platform_name = platform_name or os.name
        command = (
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                (
                    f"$process = Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; "
                    f"if ($null -ne $process) {{ $process.CommandLine }}"
                ),
            ]
            if platform_name == "nt"
            else ["ps", "-p", str(pid), "-o", "command="]
        )
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    def _terminate_pid(
        self,
        pid: int,
        *,
        force: bool,
        platform_name: str | None = None,
    ) -> None:
        platform_name = platform_name or os.name
        if platform_name != "nt":
            try:
                os.killpg(pid, signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                return
            return
        command = ["taskkill.exe", "/PID", str(pid), "/T"]
        if force:
            command.append("/F")
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ServiceManagerError("无法停止 Windows 服务进程树") from exc
        if result.returncode != 0 and self._pid_exists(pid):
            raise ServiceManagerError("无法停止 Windows 服务进程树")

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
        try:
            value = read_runtime_auth_record(path)
            expected = {
                "authority": f"127.0.0.1:{self.runtime_port}",
                "cwd": str((self.data_root / "runtime/work").resolve()),
                "source_commit": PINNED_COMMIT,
            }
            if (
                not isinstance(value, dict)
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
        except FileNotFoundError:
            return None
        except (OSError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
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
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            value = environment.get(key)
            if value and urlsplit(value).scheme.lower() not in {"http", "https"}:
                environment.pop(key, None)
        environment.update(
            {
                "RESEARCH_DATA_HOME": str(self.data_root),
                "RESEARCH_RUNTIME_URL": f"http://127.0.0.1:{self.runtime_port}",
                "RESEARCH_RUNTIME_AUTH": str(self._runtime_auth_path()),
                "RESEARCH_DSH_SOURCE": str(self.runtime_source),
                "RESEARCH_WEB_INTERNAL_URL": f"http://127.0.0.1:{self.web_port}",
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
        self._terminate_pid(pid, force=False)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and self._pid_exists(pid):
            time.sleep(0.1)
        if self._pid_exists(pid):
            if self._owned_state(process) is None:
                raise ServiceManagerError(f"无法确认 {process.role} 进程归属")
            self._terminate_pid(pid, force=True)
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

    def restart_runtime(self, *, force: bool = False) -> dict[str, Any]:
        """Restart only the owned DSH process while keeping Research Web online."""

        self._prepare_private_directories()
        runtime, _web = self._processes()
        running = self._owned_state(runtime) is not None
        if running and not force:
            active = self._active_research()
            if active:
                raise ServiceManagerError(
                    f"存在 {len(active)} 个活动研究，拒绝重启 Runtime；确需中断时使用 --force"
                )
        if running:
            self._stop_one(runtime)
        try:
            if self._ensure_startable(runtime):
                pid = self._spawn(runtime)
            else:
                state = self._owned_state(runtime)
                pid = int(state["pid"]) if state else None
            if not self._wait(self._runtime_healthy, 35):
                raise ServiceManagerError(f"DSH {self.runtime_port} 启动超时，请查看 runtime.log")
        except Exception:
            try:
                self._stop_one(runtime)
            except ServiceManagerError:
                log.error("research_runtime_restart_cleanup_failed")
            raise
        log.info("research_runtime_restarted", pid=pid)
        return {
            "running": True,
            "healthy": True,
            "pid": pid,
            "port": runtime.port,
        }

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

    @staticmethod
    def _executable_version(path: str) -> str | None:
        try:
            result = subprocess.run(
                [path, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return None
            return (result.stdout or result.stderr).strip()[:80] or None
        except (OSError, subprocess.SubprocessError):
            return None

    def _installed_package_versions(self) -> dict[str, str | None]:
        script = (
            "import importlib.metadata as m, json\n"
            "out = {}\n"
            "for name in ('cjpy', 'requests', 'urllib3'):\n"
            "    try:\n"
            "        out[name] = m.version(name)\n"
            "    except m.PackageNotFoundError:\n"
            "        out[name] = None\n"
            "print(json.dumps(out))\n"
        )
        try:
            result = subprocess.run(
                [self.python, "-c", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            value = json.loads(result.stdout) if result.returncode == 0 else {}
            return {
                name: str(value[name]) if isinstance(value.get(name), str) else None
                for name in ("cjpy", "requests", "urllib3")
            }
        except (OSError, TypeError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
            return {name: None for name in ("cjpy", "requests", "urllib3")}

    def _read_install_manifest(self) -> dict[str, Any]:
        path = self.data_root.parent / "install" / "manifest.json"
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024:
                return {}
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) and value.get("schema_version") == 1 else {}
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _dsh_build_status(self) -> dict[str, Any]:
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=self.runtime_source,
                text=True,
                timeout=10,
            ).strip()
            closure_sha256, closure_files = calculate_build_closure(self.runtime_source)
            manifest = self._read_install_manifest()
            ready = (
                commit == PINNED_COMMIT
                and manifest.get("dsh_commit") == commit
                and manifest.get("dsh_closure_sha256") == closure_sha256
                and manifest.get("dsh_closure_files") == closure_files
                and (self.runtime_source / "apps/cli/lib/bin.js").is_file()
            )
            return {
                "commit": commit,
                "closure_sha256": closure_sha256,
                "closure_files": closure_files,
                "ready": ready,
            }
        except (OSError, subprocess.SubprocessError):
            return {
                "commit": None,
                "closure_sha256": None,
                "closure_files": None,
                "ready": False,
            }

    def doctor(self) -> dict[str, Any]:
        """Return a path-free, credential-free Web installation diagnosis."""
        manifest = self._read_install_manifest()
        lock = self.project_root / "requirements" / "web.lock"
        try:
            lock_sha256 = hashlib.sha256(lock.read_bytes()).hexdigest()
        except OSError:
            lock_sha256 = None
        package_versions = self._installed_package_versions()
        dsh = self._dsh_build_status()
        try:
            raw_status = self.status()
            services = {
                role: {
                    "port": int(raw_status["services"][role]["port"]),
                    "running": bool(raw_status["services"][role]["running"]),
                    "healthy": bool(raw_status["services"][role]["healthy"]),
                }
                for role in ("runtime", "web")
            }
        except (KeyError, TypeError, ValueError, ServiceManagerError):
            services = {
                "runtime": {"port": self.runtime_port, "running": False, "healthy": False},
                "web": {"port": self.web_port, "running": False, "healthy": False},
            }
        environment_owned = (self.project_root / ".venv" / ENVIRONMENT_MARKER).is_file()
        lock_matches = bool(lock_sha256 and manifest.get("web_lock_sha256") == lock_sha256)
        cjpy_ready = (
            package_versions.get("cjpy") == CJPY_VERSION
            and bool(package_versions.get("requests"))
            and bool(package_versions.get("urllib3"))
            and manifest.get("cjpy_version") == CJPY_VERSION
            and manifest.get("cjpy_sha256") == CJPY_SHA256
        )
        dsh_ready = bool(
            dsh.get("ready")
            and manifest.get("dsh_commit") == PINNED_COMMIT
            and manifest.get("dsh_closure_sha256") == dsh.get("closure_sha256")
        )
        issues = []
        for ready, code in (
            (manifest.get("status") == "installed", "install_manifest_invalid"),
            (environment_owned, "environment_not_owned"),
            (lock_matches, "web_lock_mismatch"),
            (cjpy_ready, "cjpy_not_ready"),
            (self._executable_version(self.node) is not None, "node_unavailable"),
            (dsh_ready, "dsh_not_ready"),
        ):
            if not ready:
                issues.append(code)
        return {
            "schema_version": 1,
            "ok": not issues,
            "issues": issues,
            "python": {
                "version": self._executable_version(self.python),
                "environment_owned": environment_owned,
                "lock_sha256": lock_sha256,
                "lock_matches_manifest": lock_matches,
            },
            "node": {"version": self._executable_version(self.node)},
            "cjpy": {
                "version": package_versions.get("cjpy"),
                "wheel_sha256": CJPY_SHA256 if cjpy_ready else None,
                "requests": package_versions.get("requests"),
                "urllib3": package_versions.get("urllib3"),
                "ready": cjpy_ready,
            },
            "dsh": {
                "commit": dsh.get("commit"),
                "closure_sha256": dsh.get("closure_sha256"),
                "closure_files": dsh.get("closure_files"),
                "ready": dsh_ready,
            },
            "data": {"ready": self.data_root.is_dir()},
            "services": services,
        }

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


def format_doctor_status(status: dict[str, Any]) -> str:
    """Render the safe doctor projection for a terminal."""
    return "\n".join(
        [
            f"overall: {'ready' if status.get('ok') else 'needs attention'}",
            f"Python: {status.get('python', {}).get('version') or 'missing'}",
            "Web lock: "
            + ("verified" if status.get("python", {}).get("lock_matches_manifest") else "invalid"),
            f"CJPY: {status.get('cjpy', {}).get('version') or 'missing'}",
            f"Node: {status.get('node', {}).get('version') or 'missing'}",
            f"DSH: {'ready' if status.get('dsh', {}).get('ready') else 'invalid'}",
            f"Runtime 3081: {'healthy' if status.get('services', {}).get('runtime', {}).get('healthy') else 'stopped'}",
            f"Web 8088: {'healthy' if status.get('services', {}).get('web', {}).get('healthy') else 'stopped'}",
            "issues: " + (", ".join(status.get("issues", [])) or "none"),
        ]
    )
