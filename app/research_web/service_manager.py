"""Persistent, project-owned process manager for the Research Workbench Web stack."""

from __future__ import annotations

import hashlib
import http.client
import json
import math
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
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import uuid4

from core.observability import get_logger
from research_workbench_entrypoint.runtime_endpoints import (
    EndpointError,
    EndpointStore,
    select_port,
)
from research_workbench_entrypoint.web_contract import (
    CONTROL_JSON_MAX_BYTES,
    MAX_HTTP_BODY_BYTES,
    PROCESS_START_TOLERANCE_SECONDS,
    ListenerFact,
    listener_argv_is_foreign,
    listener_pids,
    node_version_issue,
    probe_process,
    proxy_warnings,
    read_private_json,
    signature_matches_argv,
)

from . import PINNED_DSH_COMMIT, RUNTIME_CONTRACT
from .control_origin import ControlOriginError, ControlOriginTransaction
from .lifecycle_lock import LifecycleLock, LifecycleLockError, _fsync_directory
from .process_spec import ProcessSpec, build_process_specs
from .runtime_auth import read_runtime_auth_record
from .runtime_state import RuntimeStateError, runtime_state_directory
from .service_diagnostics import ServiceProbe

log = get_logger(__name__)
PINNED_COMMIT = PINNED_DSH_COMMIT

WEB_PORT = 8088
RUNTIME_PORT = 3081
WEB_URL = f"http://127.0.0.1:{WEB_PORT}/#/fingpt"
RUNTIME_TOKEN_PATTERN = re.compile(
    r"dsh web: http://127\.0\.0\.1:(\d+)/\?token=([A-Za-z0-9_-]{43})"
)
CJPY_VERSION = RUNTIME_CONTRACT.cjpy_version
CJPY_SHA256 = RUNTIME_CONTRACT.cjpy_sha256
ENVIRONMENT_MARKER = ".rwb-web-environment.json"
STATE_LIMIT_BYTES = CONTROL_JSON_MAX_BYTES
WEB_TEXT_MAX_BYTES = min(MAX_HTTP_BODY_BYTES, 256 * 1024)
WEB_ROOT_MARKER = "Research Workbench · Research"
WEB_STATIC_MARKER = "const defaultCatalogNames ="
MAX_STATE_STRING_LENGTH = 4096
STATE_KEYS = {
    "version",
    "role",
    "pid",
    "port",
    "started_at",
    "project_root",
    "data_root",
    "command",
    "fingerprint",
    "signature",
}


def calculate_build_closure(source: Path) -> tuple[str, int]:
    """Load the expensive DSH build scanner only for installation diagnosis."""
    from .launch_runtime import calculate_build_closure as calculate

    return calculate(source)


class ServiceManagerError(RuntimeError):
    """Safe CLI-facing service lifecycle failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "service_manager_error",
        role: str | None = None,
    ) -> None:
        self.code = code if re.fullmatch(r"[a-z][a-z0-9_]{0,95}", code) else "service_manager_error"
        self.role = role if role in {None, "runtime", "web"} else None
        self.safe_message = message
        super().__init__(self.safe_message)


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


# Preserve the import name used by Native lifecycle consumers.
ManagedProcess = ProcessSpec


@dataclass(frozen=True)
class _StateFact:
    """Validated state-file facts private to the service manager."""

    state: str
    pid: int | None
    signature: tuple[str, ...]
    issues: tuple[str, ...]
    started_at: float | None = None


@dataclass(frozen=True)
class _ProcessFact:
    """Process ownership facts without commands or operating-system errors."""

    process: str
    ownership: str
    pid: int | None
    issues: tuple[str, ...]


@dataclass(frozen=True)
class _WebReadiness:
    """Complete, allowlisted Research Web protocol readiness."""

    ready: bool
    issues: tuple[str, ...]

    def __bool__(self) -> bool:
        return self.ready


class WebServiceManager:
    """Start and stop only processes whose private state and command both match."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        data_root: Path | None = None,
        runtime_source: Path | None = None,
        runtime_state_root: Path | None = None,
        python: str | None = None,
        node: str | None = None,
        web_port: int | None = None,
        runtime_port: int | None = None,
    ) -> None:
        self.project_root = (project_root or Path(__file__).parents[2]).resolve()
        configured_data = os.environ.get("RESEARCH_DATA_HOME")
        configured_data_root = (
            data_root
            or (Path(configured_data).expanduser() if configured_data else None)
            or Path.home() / ".research-workbench" / "research-web"
        )
        self.data_root = Path(os.path.abspath(configured_data_root))
        self.runtime_state_root = Path(
            os.path.abspath(runtime_state_root or self.data_root / "runtime")
        )
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
        self.requested_web_port = web_port
        self.requested_runtime_port = runtime_port
        self.endpoint_store = EndpointStore(self.data_root.parent)
        self._endpoint_error = None
        try:
            self.endpoint_snapshot = self.endpoint_store.read("native")
        except EndpointError as exc:
            self._endpoint_error = exc.code
            self.endpoint_snapshot = None
        self.web_port = (
            self.endpoint_snapshot.web_port
            if self.endpoint_snapshot
            else WEB_PORT if web_port is None else web_port
        )
        self.runtime_port = (
            cast(int, self.endpoint_snapshot.runtime_port)
            if self.endpoint_snapshot
            else RUNTIME_PORT if runtime_port is None else runtime_port
        )
        self.web_url = f"http://127.0.0.1:{self.web_port}/#/fingpt"
        self.run_root = self.data_root.parent / "run"
        self.log_root = self.data_root.parent / "logs"
        self._spawn_log_windows: dict[tuple[str, int], tuple[int, int, int]] = {}
        self._lifecycle_lease = None
        self._foreign_scope = None
        self._foreign_scope_lease = None
        self._foreign_ledger = None
        self._foreign_attempted = False
        self._foreign_started: dict[tuple[str, int], dict[str, Any]] = {}
        self._fresh_root_identity = None
        self._fresh_recovery = None
        self._recovering_attempt = None
        self._active_spawn_attempt = None
        self._installation_root_identity = None
        if (
            self.endpoint_snapshot is None
            and self._endpoint_error is None
            and web_port is None
            and runtime_port is None
        ):
            from research_workbench_entrypoint.web_bootstrap import native_endpoint_ports

            try:
                self.web_port, self.runtime_port = native_endpoint_ports(
                    self.project_root, self.data_root
                )
                self.web_url = f"http://127.0.0.1:{self.web_port}/#/fingpt"
            except EndpointError as exc:
                self._endpoint_error = exc.code

    @contextmanager
    def _lifecycle_lock(self):
        """Map lock ownership failures to the stable lifecycle error contract."""
        try:
            with (
                LifecycleLock(
                    self.run_root / "lifecycle.lock",
                    self._pid_exists,
                    trusted_root=self.data_root.parent,
                ) as lease,
                ExitStack() as scope,
            ):
                self._lifecycle_lease = lease
                self._foreign_scope = scope
                self._foreign_scope_lease = lease
                try:
                    yield lease
                finally:
                    self._lifecycle_lease = None
                    self._foreign_scope = None
                    self._foreign_scope_lease = None
                    self._foreign_ledger = None
                    self._foreign_attempted = False
                    self._foreign_started.clear()
        except LifecycleLockError as exc:
            messages = {
                "lifecycle_lock_ownership_lost": "服务生命周期锁归属已丢失",
                "lifecycle_lock_release_failed": "服务生命周期锁释放失败",
            }
            message = messages.get(exc.code, "另一项服务生命周期操作正在进行")
            raise ServiceManagerError(f"{exc.code}: {message}", code=exc.code) from exc

    def _processes(self) -> tuple[ManagedProcess, ManagedProcess]:
        specs = build_process_specs(
            python=self.python,
            node=self.node,
            project_root=self.project_root,
            data_root=self.data_root,
            runtime_source=self.runtime_source,
            state_root=self.runtime_state_root,
            web_host="127.0.0.1",
            web_port=self.web_port,
            runtime_port=self.runtime_port,
        )
        return specs.runtime, specs.web

    def _prepare_private_directories(self, *, track_creation: bool = False) -> None:
        try:
            with runtime_state_directory(self.runtime_state_root, native_data_root=self.data_root):
                pass
        except FileNotFoundError:
            pass  # A first launch creates private runtime state at the write boundary.
        except RuntimeStateError as exc:
            raise ServiceManagerError("Runtime 状态目录不安全") from exc
        for path in (self.data_root.parent, self.data_root, self.run_root, self.log_root):
            created = False
            if path == self.data_root and track_creation:
                if self._lifecycle_lease is None:
                    raise ServiceManagerError(
                        "lifecycle_lock_ownership_lost", code="lifecycle_lock_ownership_lost"
                    )
                self._lifecycle_lease.assert_held()
                try:
                    path.mkdir(parents=True, mode=0o700)
                    created = True
                except FileExistsError:
                    pass
            else:
                path.mkdir(parents=True, exist_ok=True, mode=0o700)
            identity = path.lstat()
            if _is_unsafe_private_directory(path, identity, platform_name=os.name):
                raise ServiceManagerError(f"私有运行目录不安全：{path}")
            if created:
                self._fresh_root_identity = identity.st_dev, identity.st_ino

    def _state_path(self, role: str) -> Path:
        return self.run_root / f"{role}.json"

    def _runtime_auth_path(self) -> Path:
        return self.runtime_state_root / "auth.json"

    @staticmethod
    def _fingerprint(command: tuple[str, ...] | list[str]) -> str:
        payload = json.dumps(list(command), ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def _write_state(self, process: ManagedProcess, pid: int) -> None:
        self._assert_foreign_observation()
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
        witness = self._foreign_started.get((process.role, pid))
        try:
            retained = os.dup(fd) if witness is not None else None
            if retained is not None:
                self._foreign_scope.callback(os.close, retained)
        except OSError:
            os.close(fd)
            Path(name).unlink(missing_ok=True)
            raise
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, 0o600)
            os.replace(name, self._state_path(process.role))
            if witness is not None and retained is not None:
                from research_workbench_entrypoint.runtime_mode import _validate_posix_private_file

                opened = os.fstat(retained)
                _validate_posix_private_file(opened)
                identity = self._foreign_ledger._identity(opened, file=True)
                if (
                    self._foreign_ledger._identity(
                        self._state_path(process.role).lstat(), file=True
                    )
                    != identity
                ):
                    raise ServiceManagerError(
                        "runtime_ownership_unknown", code="runtime_ownership_unknown"
                    )
                witness["record"] = retained, identity
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

    def _probe_state(self, process: ManagedProcess) -> _StateFact:
        """Read one bounded state file without repairing or otherwise mutating it."""
        path = self._state_path(process.role)
        fact = read_private_json(
            path,
            trusted_root=self.data_root.parent,
            max_bytes=STATE_LIMIT_BYTES,
        )
        if fact.state == "missing":
            return _StateFact("missing", None, (), ())
        if fact.state != "valid":
            return _StateFact("invalid", None, (), (f"{process.role}_state_invalid",))
        value = fact.value

        safe_pid = (
            value.get("pid")
            if type(value) is dict
            and type(value.get("pid")) is int
            and 2 <= value["pid"] <= (2**31) - 1
            else None
        )
        if type(value) is not dict or set(value) != STATE_KEYS:
            return _StateFact("invalid", safe_pid, (), (f"{process.role}_state_invalid",))
        command = value.get("command")
        signature = value.get("signature")
        strings = (
            command,
            signature,
            [value.get("role"), value.get("project_root"), value.get("data_root")],
        )
        bounded = all(
            type(items) is list
            and items
            and all(
                type(item) is str and item and len(item) <= MAX_STATE_STRING_LENGTH
                for item in items
            )
            for items in strings
        )
        valid = (
            bounded
            and type(value.get("version")) is int
            and value["version"] == 1
            and value["role"] == process.role
            and safe_pid is not None
            and type(value.get("port")) is int
            and value["port"] == process.port
            and (
                (
                    type(value.get("started_at")) is int
                    and 0 <= value["started_at"] <= 253_402_300_799
                )
                or (
                    type(value.get("started_at")) is float
                    and math.isfinite(value["started_at"])
                    and 0 <= value["started_at"] <= 253_402_300_799
                )
            )
            and value["project_root"] == str(self.project_root)
            and value["data_root"] == str(self.data_root)
            and len(command) <= 64
            and len(signature) <= 8
            and value.get("fingerprint") == self._fingerprint(command)
            and signature == list(process.signature)
        )
        if not valid:
            return _StateFact("invalid", safe_pid, (), (f"{process.role}_state_invalid",))
        return _StateFact(
            "valid",
            safe_pid,
            tuple(signature),
            (),
            float(value["started_at"]),
        )

    def _probe_pid_and_ownership(
        self, process: ManagedProcess, state: _StateFact
    ) -> tuple[_StateFact, _ProcessFact]:
        """Classify PID presence and command ownership without lifecycle actions."""
        role = process.role
        if state.pid is None:
            process_state = "missing" if state.state == "missing" else "inaccessible"
            return state, _ProcessFact(process_state, "unknown", None, ())
        observed = probe_process(state.pid)
        if state.state != "valid":
            issue = (
                f"{role}_state_invalid_live_pid"
                if observed.state != "missing"
                else f"{role}_state_invalid"
            )
            return (
                _StateFact("invalid", state.pid, (), (issue,)),
                _ProcessFact(observed.state, "unknown", None, ()),
            )
        if observed.state == "missing":
            return (
                _StateFact("stale", state.pid, state.signature, (f"{role}_state_stale",)),
                _ProcessFact("missing", "unknown", None, ()),
            )
        if observed.state == "inaccessible" or not observed.command_line:
            return state, _ProcessFact(
                "inaccessible",
                "unknown",
                None,
                (f"{role}_process_inaccessible",),
            )
        if (
            observed.issue is not None
            or observed.argv is None
            or observed.started_at is None
            or state.started_at is None
        ):
            return state, _ProcessFact(
                "alive",
                "unknown",
                None,
                (f"{role}_process_identity_unavailable",),
            )
        if not signature_matches_argv(state.signature, observed.argv):
            return state, _ProcessFact("alive", "foreign", None, (f"{role}_pid_foreign",))
        if abs(observed.started_at - state.started_at) > PROCESS_START_TOLERANCE_SECONDS:
            return state, _ProcessFact("alive", "foreign", None, (f"{role}_pid_reused",))
        return state, _ProcessFact("alive", "owned", state.pid, ())

    def _runtime_protocol_healthy(self) -> bool:
        """Run session/list only with an existing authenticated runtime record."""
        auth = self._read_runtime_auth()
        if auth is None:
            return False
        try:
            self._runtime_sessions_authenticated(auth)
            return True
        except ServiceManagerError:
            return False

    def _protocol_health(self, process: ManagedProcess) -> bool | _WebReadiness:
        return self._runtime_protocol_healthy() if process.role == "runtime" else self._web_ready()

    def _probe_service(self, process: ManagedProcess) -> ServiceProbe:
        """Build the ordered state-to-protocol fact chain for one service."""
        try:
            state = self._probe_state(process)
        except (
            OSError,
            TypeError,
            ValueError,
            OverflowError,
            RecursionError,
            ServiceManagerError,
        ):
            state = _StateFact("invalid", None, (), (f"{process.role}_state_probe_failed",))
        try:
            state, observed = self._probe_pid_and_ownership(process, state)
        except (
            OSError,
            TypeError,
            ValueError,
            OverflowError,
            ServiceManagerError,
            subprocess.SubprocessError,
        ):
            observed = _ProcessFact(
                "inaccessible",
                "unknown",
                None,
                (f"{process.role}_process_probe_failed",),
            )
        try:
            listener = listener_pids(process.port)
        except (
            OSError,
            TypeError,
            ValueError,
            OverflowError,
            ServiceManagerError,
            subprocess.SubprocessError,
        ):
            listener = ListenerFact("unknown", (), "listener_probe_failed")
        issues = [*state.issues, *observed.issues]
        protocol = "not_run"
        ready = False
        if listener.state == "unknown":
            if observed.ownership == "owned":
                observed = _ProcessFact("alive", "unknown", None, observed.issues)
            issues.append(f"{process.role}_listener_probe_failed")
        elif (
            listener.state == "listening"
            and observed.ownership == "owned"
            and observed.pid not in listener.pids
        ):
            observed = _ProcessFact("alive", "foreign", None, observed.issues)
            issues.append(f"{process.role}_port_owner_mismatch")
        elif listener.state == "listening" and observed.ownership != "owned":
            invalid_port_issue = f"{process.role}_state_invalid_port_listening"
            if state.state == "invalid" and invalid_port_issue not in issues:
                issues.append(invalid_port_issue)
            issues.append(f"{process.role}_port_in_use_unknown")
        elif listener.state == "closed" and observed.ownership == "owned":
            issues.append(f"{process.role}_port_closed")
        if (
            observed.process == "alive"
            and observed.ownership == "owned"
            and listener.state == "listening"
            and observed.pid in listener.pids
        ):
            try:
                health = self._protocol_health(process)
                ready = bool(health)
                protocol = "passed" if ready else "failed"
                if not ready:
                    if isinstance(health, _WebReadiness):
                        issues.extend(health.issues)
                    else:
                        issues.append(
                            "runtime_health_failed"
                            if process.role == "runtime"
                            else "web_runtime_api_failed"
                        )
            except (OSError, TypeError, ValueError, ServiceManagerError):
                protocol = "failed"
                issues.append(f"{process.role}_protocol_probe_failed")
        return ServiceProbe(
            role=process.role,
            port=process.port,
            state=state.state,
            process=observed.process,
            ownership=observed.ownership,
            port_state=listener.state,
            protocol=protocol,
            ready=ready,
            pid=observed.pid,
            issues=tuple(dict.fromkeys(issues)),
        )

    def _service_probes(self) -> tuple[ServiceProbe, ...]:
        if self._endpoint_error:
            raise ServiceManagerError(self._endpoint_error, code=self._endpoint_error)
        return tuple(self._probe_service(process) for process in self._processes())

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
        if force and result.returncode != 0 and self._pid_exists(pid):
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
    def _text_request(
        port: int,
        path: str,
        *,
        max_bytes: int,
    ) -> tuple[int, str | None, str]:
        """Read one bounded direct-loopback response without proxy mediation."""
        if max_bytes <= 0 or max_bytes > MAX_HTTP_BODY_BYTES:
            raise ServiceManagerError("本地服务响应无效")
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request("GET", path, body=None, headers={})
            response = connection.getresponse()
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise ValueError("response too large")
            return response.status, response.getheader("Content-Type"), raw.decode("utf-8")
        except (
            OSError,
            ValueError,
            UnicodeError,
            http.client.HTTPException,
        ) as exc:
            raise ServiceManagerError("本地服务响应无效") from exc
        finally:
            try:
                connection.close()
            except (OSError, http.client.HTTPException):
                log.warning("research_loopback_connection_close_failed")

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
        request_succeeded = False
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            if response.status < 200 or response.status >= 300:
                raise ValueError("unexpected response status")
            content_type = WebServiceManager._media_type(response.getheader("Content-Type"))
            structured_json = (
                content_type.startswith("application/")
                and len(content_type) > len("application/+json")
                and content_type.endswith("+json")
            )
            if content_type != "application/json" and not structured_json:
                raise ValueError("unexpected response content type")
            raw = response.read(MAX_HTTP_BODY_BYTES + 1)
            if len(raw) > MAX_HTTP_BODY_BYTES:
                raise ValueError("response too large")
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise TypeError("response is not a JSON object")
            request_succeeded = True
            return value
        except (
            OSError,
            UnicodeError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            http.client.HTTPException,
        ) as exc:
            raise ServiceManagerError("本地服务尚未就绪") from exc
        finally:
            try:
                connection.close()
            except (OSError, http.client.HTTPException) as exc:
                if not request_succeeded:
                    log.warning(
                        "research_loopback_connection_close_failed",
                        error_type=type(exc).__name__,
                    )
                else:
                    raise ServiceManagerError("本地服务尚未就绪") from exc

    def _read_runtime_auth(self) -> dict[str, str] | None:
        path = self._runtime_auth_path()
        try:
            with runtime_state_directory(self.runtime_state_root, native_data_root=self.data_root):
                value = read_runtime_auth_record(path)
            expected = {
                "authority": f"127.0.0.1:{self.runtime_port}",
                "cwd": str((self.data_root / "runtime/work").resolve()),
                "source_commit": PINNED_COMMIT,
            }
            if isinstance(value, dict) and "bootstrap_token" in value and "cookie" not in value:
                return None
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
        try:
            value = read_runtime_auth_record(self._runtime_auth_path())
            expected = {
                "authority": f"127.0.0.1:{self.runtime_port}",
                "cwd": str((self.data_root / "runtime/work").resolve()),
                "source_commit": PINNED_COMMIT,
            }
            if not isinstance(value, dict) or any(
                value.get(key) != item for key, item in expected.items()
            ):
                return None
            token = value.get("bootstrap_token")
            return (
                token
                if isinstance(token, str) and re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
                else None
            )
        except (OSError, ValueError, TypeError, UnicodeDecodeError):
            return None

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
        self._assert_foreign_observation()
        try:
            with runtime_state_directory(
                self.runtime_state_root, create=True, native_data_root=self.data_root
            ):
                return self._write_runtime_auth_record(cookie)
        except (OSError, RuntimeStateError) as exc:
            raise ServiceManagerError("无法写入 DSH 认证控制文件") from exc

    def _write_runtime_auth_record(self, cookie: str) -> dict[str, str]:
        name: str | None = None
        try:
            runtime = self.runtime_state_root
            package = json.loads((self.runtime_source / "package.json").read_text(encoding="utf-8"))
            value = {
                "authority": f"127.0.0.1:{self.runtime_port}",
                "cookie": cookie,
                "cwd": str((self.data_root / "runtime/work").resolve()),
                "source_commit": PINNED_COMMIT,
                "version": str(package["version"]),
            }
            fd, name = tempfile.mkstemp(prefix="auth-", dir=runtime)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, 0o600)
            os.replace(name, self._runtime_auth_path())
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            ServiceManagerError,
        ) as exc:
            if name is not None:
                try:
                    Path(name).unlink(missing_ok=True)
                except OSError:
                    log.warning("research_runtime_auth_temp_cleanup_failed")
            raise ServiceManagerError("无法写入 DSH 认证控制文件") from exc
        return value

    def _runtime_sessions_authenticated(self, auth: dict[str, str]) -> list[dict[str, Any]]:
        """Read authoritative sessions using an already validated auth record."""
        rpc_id = str(uuid4())
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
        result = value.get("result")
        if (
            value.get("type") != "server-response"
            or value.get("rpcId") != rpc_id
            or not isinstance(result, dict)
            or result.get("ok") is not True
            or not isinstance(result.get("value"), dict)
            or not isinstance(result["value"].get("items"), list)
        ):
            raise ServiceManagerError("DSH 会话状态响应无效")
        items = result["value"]["items"]
        for item in items:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("sessionId"), str)
                or not item["sessionId"]
                or not isinstance(item.get("running"), bool)
            ):
                raise ServiceManagerError("DSH 会话状态响应无效")
        return items

    def _runtime_sessions(self) -> list[dict[str, Any]]:
        auth = self._read_runtime_auth()
        if auth is None:
            token = self._runtime_launch_token()
            cookie = self._exchange_runtime_cookie(token) if token else None
            if cookie is None:
                raise ServiceManagerError("DSH 认证不可用")
            auth = self._write_runtime_auth(cookie)
        return self._runtime_sessions_authenticated(auth)

    def _runtime_healthy(self) -> bool:
        try:
            self._runtime_sessions()
            return True
        except ServiceManagerError:
            return False

    @staticmethod
    def _media_type(value: str | None) -> str:
        return (value or "").split(";", 1)[0].strip().lower()

    def _web_ready(self) -> _WebReadiness:
        """Require Runtime projection, product shell, and primary module asset."""
        issues: list[str] = []
        try:
            status, content_type, body = self._text_request(
                self.web_port,
                "/api/research/runtime",
                max_bytes=CONTROL_JSON_MAX_BYTES,
            )
            value = json.loads(body)
            if (
                status < 200
                or status >= 300
                or self._media_type(content_type) != "application/json"
                or type(value) is not dict
                or value.get("connected") is not True
                or value.get("health_check_passed") is not True
            ):
                raise ValueError("runtime projection not ready")
        except (
            OSError,
            TypeError,
            ValueError,
            UnicodeError,
            ServiceManagerError,
        ):
            issues.append("web_runtime_api_failed")
        try:
            status, content_type, body = self._text_request(
                self.web_port,
                "/",
                max_bytes=WEB_TEXT_MAX_BYTES,
            )
            if (
                status != 200
                or self._media_type(content_type) != "text/html"
                or WEB_ROOT_MARKER not in body
            ):
                raise ValueError("root shell not ready")
        except (
            OSError,
            TypeError,
            ValueError,
            UnicodeError,
            ServiceManagerError,
        ):
            issues.append("web_root_failed")
        try:
            status, content_type, body = self._text_request(
                self.web_port,
                "/static/app.mjs",
                max_bytes=WEB_TEXT_MAX_BYTES,
            )
            if (
                status != 200
                or self._media_type(content_type)
                not in {"application/javascript", "text/javascript"}
                or WEB_STATIC_MARKER not in body
            ):
                raise ValueError("static module not ready")
        except (
            OSError,
            TypeError,
            ValueError,
            UnicodeError,
            ServiceManagerError,
        ):
            issues.append("web_static_asset_failed")
        stable_issues = tuple(dict.fromkeys(issues))
        return _WebReadiness(not stable_issues, stable_issues)

    def _web_healthy(self) -> bool:
        """Compatibility predicate backed by complete product readiness."""
        return self._web_ready().ready

    @staticmethod
    def _wait(check, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if check():
                return True
            time.sleep(0.25)
        return False

    @staticmethod
    def _terminate_failed_spawn(child: Any, *, platform_name: str | None = None) -> None:
        """Terminate and reap the exact just-created child after state write failure."""
        platform_name = platform_name or os.name
        try:
            if platform_name == "nt":
                child.terminate()
            else:
                os.killpg(child.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        try:
            child.wait(timeout=2)
            return
        except subprocess.TimeoutExpired:
            pass
        except (OSError, subprocess.SubprocessError):
            log.warning("research_service_failed_spawn_wait_failed")
        try:
            if platform_name == "nt":
                child.kill()
            else:
                os.killpg(child.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        try:
            child.wait(timeout=2)
        except (OSError, subprocess.SubprocessError):
            log.error("research_service_failed_spawn_reap_failed")

    def _spawn(self, process: ManagedProcess) -> int:
        self._assert_foreign_observation()
        try:
            with runtime_state_directory(
                self.runtime_state_root, create=True, native_data_root=self.data_root
            ):
                return self._spawn_owned_process(process)
        except (OSError, RuntimeStateError) as exc:
            raise ServiceManagerError(f"无法启动 {process.role} 服务") from exc

    def _spawn_owned_process(self, process: ManagedProcess) -> int:
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
            stream = log_path.open("ab", buffering=0)
            try:
                log_identity = os.fstat(stream.fileno())
                log_offset = stream.tell()
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
                try:
                    self._record_attempt_spawn(process, child.pid, child=child)
                except Exception:
                    self._terminate_failed_spawn(child)
                    log.error("research_service_spawn_registration_failed", role=process.role)
                    raise
                self._spawn_log_windows[(process.role, child.pid)] = (
                    log_identity.st_dev,
                    log_identity.st_ino,
                    log_offset,
                )
            finally:
                stream.close()
        except OSError as exc:
            log.error("research_service_start_failed", role=process.role)
            raise ServiceManagerError(
                f"{process.role}_process_exited: 无法启动 {process.role} 服务",
                code=f"{process.role}_process_exited",
                role=process.role,
            ) from exc
        try:
            self._write_state(process, child.pid)
        except LifecycleLockError:
            self._terminate_failed_spawn(child)
            raise
        except Exception as exc:
            self._terminate_failed_spawn(child)
            log.error("research_service_state_write_failed", role=process.role)
            raise ServiceManagerError(
                f"{process.role}_state_write_failed: 无法记录 {process.role} 服务状态",
                code=f"{process.role}_state_write_failed",
                role=process.role,
            ) from exc
        log.info("research_service_started", role=process.role, pid=child.pid)
        return child.pid

    def _ensure_startable(self, process: ManagedProcess) -> bool:
        state = self._owned_state(process)
        if state is not None:
            return False
        if self._port_open(process.port):
            raise ServiceManagerError(f"端口 {process.port} 已被非本项目进程占用，未执行启动")
        return True

    def _require_installation_ready(self) -> dict[str, Any]:
        """Run the read-only installation gate before any lifecycle mutation."""
        if not self.runtime_source.is_dir():
            raise ServiceManagerError(
                "DSH 源码目录不存在；请设置 RESEARCH_DSH_SOURCE",
                code="dsh_source_missing",
                role="runtime",
            )
        if not Path(self.python).exists() or not Path(self.node).exists():
            raise ServiceManagerError(
                "Python 或 Node.js 可执行文件不存在",
                code="runtime_executable_missing",
                role="runtime",
            )
        diagnosis = self._installation_diagnosis()
        if not diagnosis.get("ok"):
            issues = [issue for issue in diagnosis.get("issues", []) if isinstance(issue, str)] or [
                "unknown"
            ]
            log.error("research_web_installation_not_ready", issues=issues)
            raise ServiceManagerError(
                "Web 安装未就绪（"
                + ", ".join(issues)
                + "）；请先运行 ./setup-web.sh（Windows 使用 setup-web.cmd），"
                "再用 rwb web doctor --json 复核",
                code="installation_not_ready",
            )
        return diagnosis

    @staticmethod
    def _probe_refusal_code(probe: ServiceProbe) -> str:
        preferred = (
            f"{probe.role}_state_invalid_live_pid",
            f"{probe.role}_state_invalid_port_listening",
            f"{probe.role}_pid_foreign",
            f"{probe.role}_pid_reused",
            f"{probe.role}_port_owner_mismatch",
            f"{probe.role}_port_in_use_unknown",
            f"{probe.role}_process_identity_unavailable",
            f"{probe.role}_process_inaccessible",
            f"{probe.role}_listener_probe_failed",
        )
        for code in preferred:
            if code in probe.issues:
                return code
        return f"{probe.role}_ownership_unverified"

    @staticmethod
    def _is_owned_alive(probe: ServiceProbe) -> bool:
        return (
            probe.state == "valid"
            and probe.process == "alive"
            and probe.ownership == "owned"
            and type(probe.pid) is int
            and probe.pid > 1
        )

    @staticmethod
    def _is_safe_absent(probe: ServiceProbe) -> bool:
        if probe.port_state != "closed":
            return False
        if probe.state == "missing":
            return probe.process == "missing"
        if probe.state == "stale":
            return probe.process == "missing"
        if probe.state == "invalid":
            return f"{probe.role}_state_invalid_live_pid" not in probe.issues and probe.process in {
                "missing",
                "inaccessible",
            }
        return False

    def _probe_action(self, probe: ServiceProbe) -> str:
        if probe.ready and self._is_owned_alive(probe) and probe.port_state == "listening":
            return "ready"
        if self._is_owned_alive(probe):
            return "owned_unhealthy"
        if self._is_safe_absent(probe):
            return probe.state
        code = self._probe_refusal_code(probe)
        raise ServiceManagerError(
            f"{code}: {probe.role} 服务归属无法安全确认，拒绝生命周期操作",
            code=code,
            role=probe.role,
        )

    @staticmethod
    def _state_file_identity(path: Path) -> tuple[int, int, int]:
        identity = path.lstat()
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (
            path.is_symlink()
            or bool(getattr(identity, "st_file_attributes", 0) & reparse_flag)
            or not stat.S_ISREG(identity.st_mode)
            or identity.st_nlink != 1
            or identity.st_size > STATE_LIMIT_BYTES
        ):
            raise OSError("unsafe state identity")
        return identity.st_dev, identity.st_ino, identity.st_size

    def _remove_exact_state(self, process: ManagedProcess, *, expected_pid: int) -> None:
        self._assert_foreign_observation()
        path = self._state_path(process.role)
        try:
            before = self._state_file_identity(path)
            state = self._probe_state(process)
            after = self._state_file_identity(path)
            if state.state != "valid" or state.pid != expected_pid or before != after:
                raise OSError("state changed")
            path.unlink()
            witness = self._foreign_started.get((process.role, expected_pid))
            if witness is not None:
                witness["phase"] = "stopped"
        except (OSError, ServiceManagerError) as exc:
            raise ServiceManagerError(
                f"{process.role} 服务状态归属无法安全确认",
                code=f"{process.role}_ownership_unverified",
                role=process.role,
            ) from exc

    def _quarantine_invalid_state(
        self,
        process: ManagedProcess,
        *,
        platform_name: str | None = None,
    ) -> None:
        """Move one exact invalid state into one bounded private diagnostic copy."""
        source = self._state_path(process.role)
        quarantine = self.run_root / f"{process.role}.invalid.json"
        platform_name = platform_name or os.name
        try:
            before = self._state_file_identity(source)
            flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
            handle = os.open(source, flags)
            try:
                opened = os.fstat(handle)
                raw = os.read(handle, STATE_LIMIT_BYTES + 1)
            finally:
                os.close(handle)
            after = self._state_file_identity(source)
            if (
                (opened.st_dev, opened.st_ino, opened.st_size) != before
                or after != before
                or len(raw) > STATE_LIMIT_BYTES
            ):
                raise OSError("state changed")
            if platform_name != "nt":
                os.chmod(source, 0o600)
            if self._state_file_identity(source) != before:
                raise OSError("state changed")
            os.replace(source, quarantine)
            _fsync_directory(self.run_root, platform_name=platform_name)
            log.warning("research_service_state_quarantined", role=process.role)
        except OSError as exc:
            raise ServiceManagerError(
                f"{process.role} 服务状态无法安全隔离",
                code=f"{process.role}_ownership_unverified",
                role=process.role,
            ) from exc

    def _normalize_absent_probe(
        self,
        process: ManagedProcess,
        probe: ServiceProbe,
        *,
        clear_runtime_auth: bool = False,
    ) -> None:
        self._assert_foreign_observation()
        if probe.state == "missing":
            if process.role == "runtime" and clear_runtime_auth:
                self._clear_runtime_auth()
            return
        if probe.state == "invalid":
            self._quarantine_invalid_state(process)
            if process.role == "runtime" and clear_runtime_auth:
                self._clear_runtime_auth()
            return
        if probe.state == "stale":
            state = self._probe_state(process)
            if state.state != "valid" or state.pid is None:
                raise ServiceManagerError(
                    f"{process.role} 服务状态归属无法安全确认",
                    code=f"{process.role}_ownership_unverified",
                    role=process.role,
                )
            self._remove_exact_state(process, expected_pid=state.pid)
            if process.role == "runtime" and clear_runtime_auth:
                self._clear_runtime_auth()
            log.info("research_service_stale_state_removed", role=process.role, pid=state.pid)

    def _clear_runtime_auth(self) -> None:
        """Remove only the exact private Runtime auth file."""
        self._assert_foreign_observation()
        path = self._runtime_auth_path()
        try:
            before = path.lstat()
        except FileNotFoundError:
            return
        try:
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            if (
                path.is_symlink()
                or bool(getattr(before, "st_file_attributes", 0) & reparse_flag)
                or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
            ):
                raise OSError("unsafe runtime auth identity")
            after = path.lstat()
            if (before.st_dev, before.st_ino, before.st_size) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
            ):
                raise OSError("runtime auth changed")
            path.unlink()
        except OSError as exc:
            raise ServiceManagerError(
                "Runtime 认证状态无法安全清理",
                code="runtime_ownership_unverified",
                role="runtime",
            ) from exc

    def _spawned_process_pending(self, process: ManagedProcess, pid: int) -> bool:
        """Allow the exact new launcher to finish exec/bind before ownership is final."""
        try:
            state = self._probe_state(process)
            if state.state != "valid" or state.pid != pid or state.started_at is None:
                return False
            observed = probe_process(pid)
            if (
                observed.state != "alive"
                or observed.issue is not None
                or observed.argv is None
                or observed.started_at is None
                or abs(observed.started_at - state.started_at) > PROCESS_START_TOLERANCE_SECONDS
            ):
                return False
            launcher_args = process.command[1:]
            if not (
                signature_matches_argv(launcher_args, observed.argv)
                or signature_matches_argv(process.signature, observed.argv)
            ):
                return False
            listener = listener_pids(process.port)
            return listener.state != "listening" or pid in listener.pids
        except (OSError, TypeError, ValueError, OverflowError, ServiceManagerError):
            return False

    def _wait_for_ready(
        self,
        process: ManagedProcess,
        pid: int,
        *,
        timeout: float,
    ) -> ServiceProbe:
        deadline = time.monotonic() + timeout
        last_issue = f"{process.role}_not_ready"
        while True:
            self._assert_foreign_observation()
            probe = self._probe_service(process)
            if probe.ready and probe.pid == pid:
                self._assert_foreign_observation()
                return probe
            if (
                probe.process == "missing"
                or probe.state in {"missing", "stale"}
                or (
                    (probe.ownership != "owned" or probe.pid != pid)
                    and not self._spawned_process_pending(process, pid)
                )
            ):
                raise ServiceManagerError(
                    f"{process.role}_process_exited: "
                    f"{process.role} 服务进程在就绪前退出或归属丢失",
                    code=f"{process.role}_process_exited",
                    role=process.role,
                )
            if (
                process.role == "runtime"
                and probe.port_state == "listening"
                and probe.protocol == "failed"
            ):
                try:
                    self._runtime_sessions()
                except ServiceManagerError:
                    pass
            if probe.issues:
                last_issue = probe.issues[-1]
            if time.monotonic() >= deadline:
                raise ServiceManagerError(
                    f"{process.role}_health_timeout: "
                    f"{process.role} 服务健康检查超时（{last_issue}）",
                    code=f"{process.role}_health_timeout",
                    role=process.role,
                )
            time.sleep(0.25)

    def _stop_transition_pending(
        self, process: ManagedProcess, pid: int, probe: ServiceProbe
    ) -> bool:
        """Wait for an already signalled PID and its listener to disappear."""
        if probe.state == "stale" and probe.process == "missing":
            listener = listener_pids(process.port)
            return listener.state == "unknown" or (
                listener.state == "listening" and listener.pids == (pid,)
            )
        if (
            probe.state == "valid"
            and probe.process in {"alive", "inaccessible"}
            and probe.port_state in {"closed", "unknown"}
        ):
            if self._spawned_process_pending(process, pid):
                return True
            try:
                state = self._probe_state(process)
                listener = listener_pids(process.port)
                return (
                    state.state == "valid"
                    and state.pid == pid
                    and listener.state in {"closed", "unknown"}
                )
            except (OSError, TypeError, ValueError, ServiceManagerError):
                return False
        return False

    def _stop_owned_probe(self, process: ManagedProcess, probe: ServiceProbe) -> bool:
        self._assert_foreign_observation()
        if not self._is_owned_alive(probe) or probe.pid is None:
            raise ServiceManagerError(
                f"{process.role} 服务归属无法安全确认",
                code=f"{process.role}_ownership_unverified",
                role=process.role,
            )
        pid = probe.pid
        current = self._probe_service(process)
        if not self._is_owned_alive(current) or current.pid != pid:
            raise ServiceManagerError(
                f"{process.role} 服务归属无法安全确认",
                code=f"{process.role}_ownership_unverified",
                role=process.role,
            )
        self._assert_foreign_observation()
        witness = self._foreign_started.get((process.role, pid))
        if witness is not None:
            witness["phase"] = "stopping"
        self._terminate_pid(pid, force=False)

        def own_listener_gone(current):
            if current.state != "stale" or current.process != "missing":
                return False
            state = self._probe_state(process)
            listener = listener_pids(process.port)
            return (
                state.state == "valid"
                and state.pid == pid
                and probe_process(pid).state == "missing"
                and listener.state in {"closed", "listening"}
                and pid not in listener.pids
            )

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            current = self._probe_service(process)
            if self._is_safe_absent(current) or own_listener_gone(current):
                break
            if not (
                self._is_owned_alive(current) and current.pid == pid
            ) and not self._stop_transition_pending(process, pid, current):
                raise ServiceManagerError(
                    f"{process.role} 服务归属无法安全确认",
                    code=f"{process.role}_ownership_unverified",
                    role=process.role,
                )
            time.sleep(0.1)
        else:
            current = self._probe_service(process)
            if not self._is_owned_alive(current) or current.pid != pid:
                raise ServiceManagerError(
                    f"{process.role} 服务归属无法安全确认",
                    code=f"{process.role}_ownership_unverified",
                    role=process.role,
                )
            self._assert_foreign_observation()
            self._terminate_pid(pid, force=True)
            force_deadline = time.monotonic() + 2
            while time.monotonic() < force_deadline:
                current = self._probe_service(process)
                if self._is_safe_absent(current) or own_listener_gone(current):
                    break
                if not (
                    self._is_owned_alive(current) and current.pid == pid
                ) and not self._stop_transition_pending(process, pid, current):
                    raise ServiceManagerError(
                        f"{process.role} 服务归属无法安全确认",
                        code=f"{process.role}_ownership_unverified",
                        role=process.role,
                    )
                time.sleep(0.1)
            else:
                raise ServiceManagerError(
                    f"{process.role} 服务未能安全停止",
                    code=f"{process.role}_ownership_unverified",
                    role=process.role,
                )
        self._remove_exact_state(process, expected_pid=pid)
        if process.role == "runtime":
            self._clear_runtime_auth()
        log.info("research_service_stopped", role=process.role, pid=pid)
        return True

    def _rollback_spawned(self, process: ManagedProcess, pid: int) -> None:
        self._assert_foreign_observation()
        probe = self._probe_service(process)
        if self._is_owned_alive(probe) and probe.pid == pid:
            self._stop_owned_probe(process, probe)
        else:
            log.warning("research_service_rollback_ownership_lost", role=process.role)

    def _spawn_and_wait(self, process: ManagedProcess) -> int:
        """Spawn one service and roll back only that exact PID if readiness fails."""
        pid = self._spawn(process)
        try:
            self._record_attempt_spawn(process, pid)
        except Exception:
            witness = self._foreign_started.get((process.role, pid))
            if witness is not None:
                self._terminate_failed_spawn(witness["child"])
                witness["phase"] = "failed"
            raise
        try:
            self._wait_for_ready(process, pid, timeout=35)
        except Exception as exc:
            try:
                self._rollback_spawned(process, pid)
            except ServiceManagerError:
                log.error("research_service_rollback_failed", role=process.role)
            if self._confirmed_bind_failure(process, pid):
                code = f"{process.role}_bind_race"
                raise ServiceManagerError(code, code=code, role=process.role) from exc
            raise
        self._spawn_log_windows.pop((process.role, pid), None)
        return pid

    def _record_attempt_spawn(self, process, pid, *, child=None):
        if (
            self._active_spawn_attempt is not None
            and (process, pid) not in self._active_spawn_attempt
        ):
            self._active_spawn_attempt.append((process, pid))
        if not self._foreign_attempted:
            return
        if self._lifecycle_lease is None:
            raise LifecycleLockError("lost", code="lifecycle_lock_ownership_lost")
        self._lifecycle_lease.assert_held()
        key = process.role, pid
        previous = self._foreign_started.get(key)
        if previous is not None:
            if child is not None and previous["child"] is not child:
                previous["invalid"] = True
                raise ServiceManagerError(
                    "runtime_ownership_unknown", code="runtime_ownership_unknown"
                )
            self._assert_foreign_observation()
            return
        if child is None or child.pid != pid or self._foreign_scope is None:
            raise ServiceManagerError("runtime_ownership_unknown", code="runtime_ownership_unknown")
        self._foreign_started[key] = {
            "child": child,
            "process": process,
            "lease": self._lifecycle_lease,
            "scope": self._foreign_scope,
            "record": None,
            "started": None,
            "facts": None,
            "phase": "pending",
            "invalid": False,
        }

    def _confirmed_bind_failure(self, process, pid):
        """Read only this launch's retained log window; never expose child text."""
        window = self._spawn_log_windows.pop((process.role, pid), None)
        if window is None or probe_process(pid).state != "missing":
            return False
        listener = listener_pids(process.port)
        if listener.state != "listening" or not listener.pids:
            return False
        for owner in listener.pids:
            observed = probe_process(owner)
            if (
                observed.state != "alive"
                or observed.issue
                or not observed.argv
                or not listener_argv_is_foreign(
                    observed.argv, data_root=self.data_root, project_root=self.project_root
                )
            ):
                return False
        path = self.log_root / f"{process.role}.log"
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as stream:
                before = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or (before.st_dev, before.st_ino) != window[:2]
                    or before.st_size < window[2]
                    or before.st_size - window[2] > 65536
                ):
                    return False
                stream.seek(window[2])
                payload = stream.read(65537).lower()
                after = path.lstat()
                if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
                    before.st_dev,
                    before.st_ino,
                    before.st_size,
                    before.st_mtime_ns,
                ):
                    return False
            return b"eaddrinuse" in payload or (
                b"error while attempting to bind on address" in payload
                and b"address already in use" in payload
            )
        except OSError:
            log.warning("research_bind_failure_evidence_unavailable", role=process.role)
            return False

    def _start_locked(
        self,
        *,
        diagnosis: dict[str, Any],
        open_browser: bool,
        owned_attempt: list[tuple[ManagedProcess, int]] | None = None,
    ) -> dict[str, Any]:
        if not diagnosis.get("ok"):
            raise ServiceManagerError("Web 安装未就绪", code="installation_not_ready")
        runtime, web = self._processes()
        probes = {item.role: self._probe_service(item) for item in (runtime, web)}
        actions = {role: self._probe_action(probe) for role, probe in probes.items()}
        spawned: list[tuple[ManagedProcess, int]] = []
        try:
            if actions["runtime"] == "owned_unhealthy":
                active = self._active_research_read_only(probes["runtime"])
                if active:
                    raise ServiceManagerError(
                        f"存在 {len(active)} 个活动研究，拒绝自动重建 Runtime；"
                        "确需中断时使用 rwb web restart --force",
                        code="active_research",
                        role="runtime",
                    )
                if actions["web"] in {"ready", "owned_unhealthy"}:
                    self._stop_owned_probe(web, probes["web"])
                    actions["web"] = "missing"
                else:
                    self._normalize_absent_probe(web, probes["web"])
                    actions["web"] = "missing"
                self._stop_owned_probe(runtime, probes["runtime"])
                actions["runtime"] = "missing"
            elif actions["web"] == "owned_unhealthy":
                self._stop_owned_probe(web, probes["web"])
                actions["web"] = "missing"

            if actions["runtime"] != "ready":
                self._normalize_absent_probe(
                    runtime,
                    probes["runtime"],
                    clear_runtime_auth=True,
                )
                runtime_pid = self._spawn_and_wait(runtime)
                spawned.append((runtime, runtime_pid))
                if owned_attempt is not None and (runtime, runtime_pid) not in owned_attempt:
                    owned_attempt.append((runtime, runtime_pid))

            if actions["web"] != "ready":
                self._normalize_absent_probe(web, probes["web"])
                web_pid = self._spawn_and_wait(web)
                spawned.append((web, web_pid))
                if owned_attempt is not None and (web, web_pid) not in owned_attempt:
                    owned_attempt.append((web, web_pid))
        except Exception:
            for process, pid in reversed(spawned):
                try:
                    self._rollback_spawned(process, pid)
                except ServiceManagerError:
                    log.error("research_service_rollback_failed", role=process.role)
            raise
        status = self.status()
        for _attempt in range(10):
            if status.get("product_ready") is True:
                break
            time.sleep(0.5)
            status = self.status()
        if status.get("product_ready") is not True:
            services = status.get("services")
            role = None
            code = "product_not_ready"
            if isinstance(services, dict):
                for candidate in ("runtime", "web"):
                    service = services.get(candidate)
                    if isinstance(service, dict) and service.get("ready") is not True:
                        role = candidate
                        issues = service.get("issues")
                        if isinstance(issues, list) and issues and isinstance(issues[0], str):
                            code = issues[0]
                        else:
                            code = f"{candidate}_health_failed"
                        break
            log.error("research_web_final_readiness_failed", role=role, code=code)
            raise ServiceManagerError(
                f"{code}: Research Web 最终就绪检查失败；运行 rwb web doctor --json 查看服务状态",
                code=code,
                role=role,
            )
        if open_browser:
            browser_failed = False
            try:
                browser_failed = webbrowser.open(self.web_url) is not True
            except (webbrowser.Error, OSError, subprocess.SubprocessError):
                browser_failed = True
            if browser_failed:
                log.warning("research_web_browser_open_failed")
                status = dict(status)
                warnings = status.get("warnings", [])
                status["warnings"] = list(warnings) if isinstance(warnings, list) else []
                status["warnings"] = list(
                    dict.fromkeys([*status["warnings"], "browser_open_failed"])
                )
        return status

    def start(self, *, open_browser: bool = True) -> dict[str, Any]:
        diagnosis = self._require_installation_ready()
        with self._lifecycle_lock():
            try:
                self._prepare_private_directories(track_creation=True)
                return self._start_with_endpoints(diagnosis=diagnosis, open_browser=open_browser)
            finally:
                self._fresh_root_identity = None
                self._fresh_recovery = None
                self._recovering_attempt = None
                self._active_spawn_attempt = None

    @contextmanager
    def _installation_start_scope(self):
        """Retain only this manager's actual mkdir witness through auto-install."""
        with self._lifecycle_lock() as lease:
            try:
                self._prepare_private_directories(track_creation=True)
                identity = self.data_root.lstat()
                self._installation_root_identity = identity.st_dev, identity.st_ino
                self._assert_installation_scope(lease)
                yield lease
            finally:
                self._fresh_root_identity = None
                self._fresh_recovery = None
                self._recovering_attempt = None
                self._active_spawn_attempt = None
                self._installation_root_identity = None

    def _installation_root_matches(self):
        try:
            identity = self.data_root.lstat()
            return (
                self._installation_root_identity is not None
                and not _is_unsafe_private_directory(
                    self.data_root, identity, platform_name=os.name
                )
                and (identity.st_dev, identity.st_ino) == self._installation_root_identity
            )
        except OSError:
            return False

    def _assert_installation_scope(self, lease):
        """Recheck the actual borrowed lease/root before each runtime write."""
        if lease is not self._lifecycle_lease or lease is None:
            raise ServiceManagerError(
                "lifecycle_lock_ownership_lost", code="lifecycle_lock_ownership_lost"
            )
        lease.assert_held()
        if not self._installation_root_matches():
            raise ServiceManagerError("runtime_ownership_unknown", code="runtime_ownership_unknown")
        if not self._other_runtime_quiescent():
            raise ServiceManagerError("runtime_other_running", code="runtime_other_running")
        if self._fresh_root_identity is not None:
            if not self._fresh_root_proven() or not self._native_quiescent():
                raise ServiceManagerError(
                    "runtime_ownership_unknown", code="runtime_ownership_unknown"
                )
        else:
            probes = self._service_probes()
            if all(
                probe.process == "missing" and probe.state in {"missing", "stale"}
                for probe in probes
            ):
                if not self._native_quiescent():
                    raise ServiceManagerError(
                        "runtime_ownership_unknown", code="runtime_ownership_unknown"
                    )
            else:
                for probe in probes:
                    self._probe_action(probe)

    def _start_installed(self, lease, *, open_browser=True):
        """Installer-only startup using the very same active lifecycle lease."""
        self._assert_installation_scope(lease)
        diagnosis = self._require_installation_ready()
        self._assert_installation_scope(lease)
        return self._start_with_endpoints(diagnosis=diagnosis, open_browser=open_browser)

    def _fresh_root_proven(self) -> bool:
        if self._fresh_root_identity is None or self._lifecycle_lease is None:
            return False
        try:
            self._lifecycle_lease.assert_held()
            identity = self.data_root.lstat()
            return (
                not _is_unsafe_private_directory(self.data_root, identity, platform_name=os.name)
                and (identity.st_dev, identity.st_ino) == self._fresh_root_identity
            )
        except (OSError, LifecycleLockError):
            log.warning("research_fresh_root_identity_unverified")
            return False

    def _native_quiescent(self) -> bool:
        """Missing ledgers require fresh listener evidence before rebinding."""
        if self._installation_root_identity is not None and not self._installation_root_matches():
            return False
        try:
            self._assert_foreign_observation()
        except ServiceManagerError:
            return False
        for process in self._processes():
            state = self._probe_state(process)
            state, observed = self._probe_pid_and_ownership(process, state)
            if state.state not in {"missing", "stale"} or observed.process != "missing":
                return False
        if self._recovering_attempt is not None and self._fresh_recovery is not None:
            return self._fresh_recovery_proven()
        for process in self._processes():
            if not self._absent_listener_safe(process):
                return False
            if self.endpoint_snapshot is None:
                legacy_port = WEB_PORT if process.role == "web" else RUNTIME_PORT
                if legacy_port != process.port and not self._absent_listener_safe(
                    process, port=legacy_port
                ):
                    return False
        if self._fresh_root_proven():
            return self._capture_fresh_recovery()
        return True

    def _listener_recovery_fact(self, port):
        listener = listener_pids(port)
        if listener.state == "closed" and not listener.issue:
            return listener, ()
        if listener.state != "listening" or listener.issue or not listener.pids:
            return None
        identities = []
        for pid in listener.pids:
            observed = probe_process(pid)
            if (
                observed.state != "alive"
                or observed.issue
                or not observed.argv
                or observed.started_at is None
            ):
                return None
            checked = probe_process(pid)
            if (
                checked.state != "alive"
                or checked.issue
                or checked.argv != observed.argv
                or checked.started_at != observed.started_at
            ):
                return None
            identities.append((pid, observed.argv, observed.started_at))
        return (listener, tuple(identities)) if listener_pids(port) == listener else None

    def _capture_fresh_recovery(self):
        """RAM-only baseline; never refresh an existing observer identity."""
        if self._fresh_recovery is None:
            self._fresh_recovery = (self._lifecycle_lease, self._fresh_root_identity, {})
        lease, root_identity, before = self._fresh_recovery
        if lease is not self._lifecycle_lease or root_identity != self._fresh_root_identity:
            return False
        ports = {process.port for process in self._processes()}
        if self.endpoint_snapshot is None:
            ports.update((WEB_PORT, RUNTIME_PORT))
        ports.update(before)
        for port in ports:
            fact = self._listener_recovery_fact(port)
            if fact is None or (port in before and before[port] != fact):
                return False
            before[port] = fact
        return True

    def _fresh_recovery_proven(self):
        lease, root_identity, before = self._fresh_recovery
        if lease is not self._lifecycle_lease:
            return False
        try:
            lease.assert_held()
            identity = self.data_root.lstat()
            if (
                _is_unsafe_private_directory(self.data_root, identity, platform_name=os.name)
                or (identity.st_dev, identity.st_ino) != root_identity
            ):
                return False
            if any(
                probe_process(pid).state != "missing" for _process, pid in self._recovering_attempt
            ):
                return False
            return all(self._listener_recovery_fact(port) == fact for port, fact in before.items())
        except (OSError, LifecycleLockError):
            log.warning("research_fresh_recovery_unverified")
            return False

    def _absent_listener_safe(self, process, *, port=None) -> bool:
        from research_workbench_entrypoint.web_bootstrap import _foreign_native_listener_safe

        selected_port = process.port if port is None else port
        listener = listener_pids(selected_port)
        if self._foreign_attempted and (
            self._foreign_ledger is None or not self._foreign_ledger.current()
        ):
            return False
        if listener.state == "closed":
            return True
        if listener.state != "listening" or not listener.pids:
            return False
        for pid in listener.pids:
            observed = probe_process(pid)
            if (
                observed.state != "alive"
                or observed.issue
                or not observed.argv
                or not listener_argv_is_foreign(
                    observed.argv,
                    data_root=self.data_root,
                    project_root=self.project_root,
                    fresh_root=self._fresh_root_proven(),
                )
            ):
                return _foreign_native_listener_safe(
                    self.data_root,
                    selected_port,
                    listener,
                    owner=self if self._lifecycle_lease is not None else None,
                )
        return True

    def _assert_foreign_observation(self):
        from research_workbench_entrypoint.web_bootstrap import _ForeignNativeLedger

        if not self._foreign_attempted:
            return
        proof = self._foreign_ledger
        if type(proof) is _ForeignNativeLedger:
            port, listener = next(iter(proof.before[3].items()))
            if proof.permits(self, self._foreign_scope, self._lifecycle_lease, port, listener):
                for process in self._processes():
                    state, fact = self._probe_pid_and_ownership(process, self._probe_state(process))
                    if state.state == "missing" and fact.process == "missing":
                        if any(
                            witness["process"].role == process.role
                            and witness["record"] is not None
                            and witness["phase"] != "stopped"
                            for witness in self._foreign_started.values()
                        ):
                            break
                        continue
                    witness = self._foreign_started.get((process.role, state.pid))
                    if witness is None or not self._foreign_spawn_current(witness, state):
                        break
                else:
                    return
            proof._invalidate()
        log.warning("research_foreign_native_ledger_unverified")
        raise ServiceManagerError("runtime_ownership_unknown", code="runtime_ownership_unknown")

    def _foreign_spawn_current(self, witness, state):
        """Pin this actual Popen/write; establish owned-listen facts once only."""
        from research_workbench_entrypoint.runtime_mode import (
            RuntimeModeError,
            _validate_posix_private_file,
        )

        process = witness["process"]
        child = witness["child"]
        try:
            if (
                witness["invalid"]
                or witness["scope"] is not self._foreign_scope
                or witness["lease"] is not self._lifecycle_lease
                or witness["record"] is None
                or child.pid != state.pid
            ):
                raise ValueError("spawn unverified")
            descriptor, identity = witness["record"]
            _validate_posix_private_file(os.fstat(descriptor))
            _validate_posix_private_file(self._state_path(process.role).lstat())
            if (
                self._foreign_ledger._identity(os.fstat(descriptor), file=True) != identity
                or self._foreign_ledger._identity(self._state_path(process.role).lstat(), file=True)
                != identity
            ):
                raise ValueError("spawn unverified")
            observed = probe_process(child.pid)
            listener = listener_pids(process.port)
            exited = child.poll() is not None
            if observed.state == "missing" and exited:
                legitimate_exit = (
                    witness["phase"] in {"pending", "stopping", "failed"}
                    and listener.state in {"closed", "listening"}
                    and not listener.issue
                    and child.pid not in listener.pids
                )
                if not legitimate_exit:
                    raise ValueError("spawn unverified")
                return True
            if (
                exited
                or state.state != "valid"
                or observed.state != "alive"
                or observed.issue
                or not observed.argv
                or observed.started_at is None
                or state.started_at is None
                or abs(observed.started_at - state.started_at) > PROCESS_START_TOLERANCE_SECONDS
                or listener.issue
                or listener.state not in {"closed", "listening"}
            ):
                raise ValueError("spawn unverified")
            if witness["started"] is None:
                witness["started"] = observed.started_at
            if witness["started"] != observed.started_at:
                raise ValueError("spawn unverified")
            facts = witness["facts"]
            if facts is not None:
                if observed != facts[0] or (
                    listener != facts[1]
                    and not (witness["phase"] == "stopping" and listener.state == "closed")
                ):
                    raise ValueError("spawn unverified")
                return True
            owned = signature_matches_argv(process.signature, observed.argv)
            if not owned and not signature_matches_argv(process.command[1:], observed.argv):
                raise ValueError("spawn unverified")
            if listener.state == "listening":
                if listener.pids != (child.pid,):
                    raise ValueError("spawn unverified")
                if owned:
                    if (
                        probe_process(child.pid) != observed
                        or listener_pids(process.port) != listener
                    ):
                        raise ValueError("spawn unverified")
                    witness["facts"] = observed, listener
                    witness["phase"] = "bound"
            return True
        except (OSError, ValueError, TypeError, RuntimeModeError):
            witness["invalid"] = True
            log.warning("research_foreign_spawn_unverified", role=process.role)
            return False

    def _other_runtime_quiescent(self) -> bool:
        from research_workbench_entrypoint.bootstrap import _running
        from research_workbench_entrypoint.docker_runtime import DockerRuntime
        from research_workbench_entrypoint.runtime_mode import RuntimeModeStore

        record = RuntimeModeStore(self.data_root.parent).read()
        if record.mode == "docker":
            raise ServiceManagerError("runtime_other_selected", code="runtime_other_selected")
        if not record.installation_id:
            return True
        docker = DockerRuntime(self.project_root, self.data_root.parent)
        if (
            not docker.state_dir.exists()
            and not (self.data_root.parent / "install/docker-manifest.json").exists()
        ):
            return True
        report = docker.status()
        return report.get("ok") is True and not _running(report)

    def _start_with_endpoints(self, *, diagnosis, open_browser):
        for attempt in range(3):
            try:
                return self._start_endpoint_attempt(diagnosis=diagnosis, open_browser=open_browser)
            except ServiceManagerError as exc:
                if exc.code not in {"web_bind_race", "runtime_bind_race"} or getattr(
                    exc, "recovery_issues", ()
                ):
                    raise
                explicit = (
                    self.requested_web_port if exc.role == "web" else self.requested_runtime_port
                )
                if explicit is not None:
                    raise ServiceManagerError(
                        "endpoint_port_in_use", code="endpoint_port_in_use", role=exc.role
                    ) from exc
                if attempt == 2 or not self._native_quiescent():
                    raise
                log.warning("research_endpoint_bind_retry", role=exc.role)

    def _start_endpoint_attempt(self, *, diagnosis, open_browser):
        """Allocate only after ownership checks, and publish only after readiness."""
        if not self._other_runtime_quiescent():
            raise ServiceManagerError("runtime_other_running", code="runtime_other_running")
        for requested in (self.requested_web_port, self.requested_runtime_port):
            if requested is not None and (
                type(requested) is not int or not 1 <= requested <= 65535
            ):
                raise ServiceManagerError("endpoint_invalid_port", code="endpoint_invalid_port")
        if (
            self.requested_web_port is not None
            and self.requested_web_port == self.requested_runtime_port
        ):
            raise ServiceManagerError("endpoint_invalid_pair", code="endpoint_invalid_pair")
        try:
            if self.endpoint_store.read("native") != self.endpoint_snapshot:
                raise ServiceManagerError("endpoint_conflict", code="endpoint_conflict")
        except EndpointError as exc:
            raise ServiceManagerError(exc.code, code=exc.code) from exc
        probes = self._service_probes()
        if any(
            probe.process != "missing" or probe.state not in {"missing", "stale"}
            for probe in probes
        ):
            if (
                self.requested_web_port is not None and self.requested_web_port != self.web_port
            ) or (
                self.requested_runtime_port is not None
                and self.requested_runtime_port != self.runtime_port
            ):
                raise ServiceManagerError(
                    "endpoint_running_conflict", code="endpoint_running_conflict"
                )
            return self._start_locked(diagnosis=diagnosis, open_browser=open_browser)
        if not self._native_quiescent():
            raise ServiceManagerError("runtime_ownership_unknown", code="runtime_ownership_unknown")
        previous_ports = self.web_port, self.runtime_port
        previous_endpoint = self.endpoint_snapshot
        published_endpoint = None
        transaction = None
        prepared = False
        completed = False
        owned_attempt = []
        original_error = None
        try:
            web = select_port(
                self.requested_web_port or self.web_port,
                explicit=self.requested_web_port is not None,
            )
            runtime = select_port(
                self.requested_runtime_port or self.runtime_port,
                explicit=self.requested_runtime_port is not None,
                excluded=(web,),
            )
            # Remove only dead, exactly matching old records before changing specs.
            for process in self._processes():
                state = self._probe_state(process)
                if state.pid is not None:
                    self._remove_exact_state(process, expected_pid=state.pid)
            from .datahub.security import load_control
            from .mcp_runtime.control import ControlError as MCPControlError
            from .mcp_runtime.control import load_control as load_mcp_control
            from .store import StoreError

            try:
                from research_workbench_entrypoint.runtime_mode import RuntimeModeError, _read_bytes

                from .control_origin import _decode

                existing = []
                for name in ("datahub.json", "mcp-runtime.json"):
                    try:
                        raw, _identity = _read_bytes(self.data_root / ".control" / name)
                    except FileNotFoundError:
                        continue
                    value = json.loads(raw)
                    origin = value.get("url") if isinstance(value, dict) else None
                    _decode(name, raw, origin)
                    existing.append(origin)
                previous_origin = existing[0] if existing else "http://127.0.0.1:8088"
                if any(origin != previous_origin for origin in existing):
                    raise ControlOriginError("control_origin_unverified")
                if previous_origin not in {
                    "http://127.0.0.1:8088",
                    f"http://127.0.0.1:{previous_ports[0]}",
                }:
                    raise ServiceManagerError(
                        "control_origin_unverified", code="control_origin_unverified"
                    )
                load_control(self.data_root, previous_origin)
                load_mcp_control(self.data_root, previous_origin)
            except (
                StoreError,
                MCPControlError,
                ControlOriginError,
                RuntimeModeError,
                ValueError,
                OSError,
            ) as exc:
                log.warning("research_control_prepare_failed")
                raise ServiceManagerError(
                    "control_origin_prepare_failed", code="control_origin_prepare_failed"
                ) from exc
            self.web_port, self.runtime_port = web, runtime
            self.web_url = f"http://127.0.0.1:{web}/#/fingpt"
            transaction = ControlOriginTransaction(
                self.data_root,
                previous_origin,
                f"http://127.0.0.1:{web}",
                quiescent=self._native_quiescent,
            )
            transaction.prepare()
            prepared = True
            self._fresh_root_identity = None
            self._active_spawn_attempt = owned_attempt
            try:
                report = self._start_locked(
                    diagnosis=diagnosis, open_browser=False, owned_attempt=owned_attempt
                )
            finally:
                self._active_spawn_attempt = None
            if report.get("product_ready") is not True:
                raise ServiceManagerError("product_not_ready", code="product_not_ready")
            self.endpoint_snapshot = self.endpoint_store.publish(
                "native", web, runtime, expected=self.endpoint_snapshot
            )
            published_endpoint = self.endpoint_snapshot
            transaction.commit()
            completed = True
            if open_browser:
                try:
                    if not webbrowser.open(self.web_url):
                        log.warning("research_web_browser_open_failed")
                except (webbrowser.Error, OSError, subprocess.SubprocessError):
                    log.warning("research_web_browser_open_failed")
            return report
        except (EndpointError, ControlOriginError) as exc:
            original_error = ServiceManagerError(exc.code, code=exc.code)
            raise original_error from exc
        except Exception as exc:
            original_error = exc
            raise
        finally:
            if prepared and not completed:
                try:
                    cleanup_error = None
                    for process, pid in reversed(owned_attempt):
                        try:
                            if probe_process(pid).state != "missing":
                                self._rollback_spawned(process, pid)
                        except Exception as exc:  # noqa: BLE001
                            # Finish all owned cleanup before reporting failure.
                            code = getattr(exc, "code", "control_origin_recovery_unverified")
                            if not isinstance(code, str) or not re.fullmatch(
                                r"[a-z][a-z0-9_]{0,95}", code
                            ):
                                code = "control_origin_recovery_unverified"
                            log.error(
                                "research_endpoint_cleanup_failed", role=process.role, code=code
                            )
                            cleanup_error = exc
                    if cleanup_error is not None:
                        raise cleanup_error
                    self._recovering_attempt = owned_attempt
                    if published_endpoint is not None:
                        if not self._native_quiescent():
                            raise ServiceManagerError(
                                "control_origin_recovery_unverified",
                                code="control_origin_recovery_unverified",
                            )
                        self.endpoint_snapshot = self.endpoint_store.restore(
                            "native", previous_endpoint, expected=published_endpoint
                        )
                    transaction.rollback()
                except Exception as exc:
                    recovery_code = getattr(exc, "code", "control_origin_recovery_unverified")
                    if not isinstance(recovery_code, str) or not re.fullmatch(
                        r"[a-z][a-z0-9_]{0,95}", recovery_code
                    ):
                        recovery_code = "control_origin_recovery_unverified"
                    log.error("research_endpoint_recovery_failed", code=recovery_code)
                    if original_error is None:
                        raise ServiceManagerError(recovery_code, code=recovery_code) from exc
                    if isinstance(original_error, ServiceManagerError):
                        original_error.recovery_issues = (recovery_code,)
                    original_error.add_note(recovery_code)
                finally:
                    self._recovering_attempt = None
                    self._fresh_recovery = None
            else:
                self._fresh_recovery = None
            if not completed:
                self.web_port, self.runtime_port = previous_ports
                self.web_url = f"http://127.0.0.1:{self.web_port}/#/fingpt"

    def _active_research(self) -> list[str]:
        try:
            items = self._runtime_sessions()
            return [item["sessionId"] for item in items if item["running"]]
        except ServiceManagerError as exc:
            raise ServiceManagerError("无法核对活动研究；未执行重启，可显式使用 --force") from exc

    def _active_research_read_only(self, probe: ServiceProbe) -> list[str]:
        """Check activity with existing auth only; never bootstrap credentials."""
        unsafe_issues = {
            f"{probe.role}_state_invalid_live_pid",
            f"{probe.role}_state_invalid_port_listening",
            f"{probe.role}_pid_foreign",
            f"{probe.role}_pid_reused",
            f"{probe.role}_ownership_unverified",
            f"{probe.role}_port_in_use_unknown",
            f"{probe.role}_port_owner_mismatch",
            f"{probe.role}_process_identity_unavailable",
            f"{probe.role}_process_inaccessible",
            f"{probe.role}_listener_probe_failed",
        }
        if (
            not self._is_owned_alive(probe)
            or probe.port_state != "listening"
            or probe.pid is None
            or any(issue in unsafe_issues for issue in probe.issues)
        ):
            raise ServiceManagerError(
                "active_research_unverified: 无法只读核对活动研究；"
                "未执行重启，确需中断时使用 --force",
                code="active_research_unverified",
                role="runtime",
            )
        auth = self._read_runtime_auth()
        if auth is None:
            raise ServiceManagerError(
                "active_research_unverified: 无法只读核对活动研究；"
                "未执行重启，确需中断时使用 --force",
                code="active_research_unverified",
                role="runtime",
            )
        try:
            items = self._runtime_sessions_authenticated(auth)
        except (OSError, TypeError, ValueError, ServiceManagerError) as exc:
            raise ServiceManagerError(
                "active_research_unverified: 无法只读核对活动研究；"
                "未执行重启，确需中断时使用 --force",
                code="active_research_unverified",
                role="runtime",
            ) from exc
        return [item["sessionId"] for item in items if item["running"]]

    def _stop_one(self, process: ManagedProcess) -> bool:
        """Compatibility wrapper using the authoritative probe chain."""
        probe = self._probe_service(process)
        action = self._probe_action(probe)
        if action in {"ready", "owned_unhealthy"}:
            return self._stop_owned_probe(process, probe)
        self._normalize_absent_probe(process, probe)
        return False

    def _stop_locked(self) -> dict[str, Any]:
        runtime, web = self._processes()
        probes = {item.role: self._probe_service(item) for item in (runtime, web)}
        actions = {role: self._probe_stop_action(probe) for role, probe in probes.items()}
        for process in (web, runtime):
            action = actions[process.role]
            if action in {"ready", "owned_unhealthy"}:
                self._stop_owned_probe(process, probes[process.role])
            elif (
                probes[process.role].state == "missing"
                and probes[process.role].process == "missing"
            ):
                continue
            elif action == "stale" and probes[process.role].port_state == "listening":
                state = self._probe_state(process)
                self._remove_exact_state(process, expected_pid=cast(int, state.pid))
                if process.role == "runtime":
                    self._clear_runtime_auth()
            else:
                self._normalize_absent_probe(process, probes[process.role])
        return self.status()

    def _probe_stop_action(self, probe):
        if probe.state == "missing" and probe.process == "missing":
            return "missing"
        if probe.state == "stale" and probe.process == "missing":
            process = next(item for item in self._processes() if item.role == probe.role)
            state, observed = self._probe_pid_and_ownership(process, self._probe_state(process))
            if state.state == "stale" and observed.process == "missing":
                return "stale"
        return self._probe_action(probe)

    def stop(self) -> dict[str, Any]:
        with self._lifecycle_lock():
            self._prepare_private_directories()
            return self._stop_locked()

    def restart(self, *, force: bool = False, open_browser: bool = True) -> dict[str, Any]:
        diagnosis = self._require_installation_ready()
        with self._lifecycle_lock():
            self._prepare_private_directories()
            probes = self._service_probes()
            for probe in probes:
                self._probe_stop_action(probe)
            runtime_probe = next(probe for probe in probes if probe.role == "runtime")
            if self._is_owned_alive(runtime_probe) and not force:
                active = self._active_research_read_only(runtime_probe)
                if active:
                    raise ServiceManagerError(
                        f"存在 {len(active)} 个活动研究，拒绝重启；确需中断时使用 --force",
                        code="active_research",
                        role="runtime",
                    )
            self._stop_locked()
            if runtime_probe.state == "stale":
                self._clear_runtime_auth()
            return self._start_with_endpoints(diagnosis=diagnosis, open_browser=open_browser)

    def restart_runtime(self, *, force: bool = False) -> dict[str, Any]:
        """Restart only the owned DSH process while keeping Research Web online."""

        self._require_installation_ready()
        with self._lifecycle_lock():
            self._prepare_private_directories()
            runtime, _web = self._processes()
            probe = self._probe_service(runtime)
            action = self._probe_action(probe)
            if action in {"ready", "owned_unhealthy"} and not force:
                active = self._active_research_read_only(probe)
                if active:
                    raise ServiceManagerError(
                        f"存在 {len(active)} 个活动研究，拒绝重启 Runtime；确需中断时使用 --force",
                        code="active_research",
                        role="runtime",
                    )
            if action in {"ready", "owned_unhealthy"}:
                self._stop_owned_probe(runtime, probe)
            else:
                self._normalize_absent_probe(runtime, probe, clear_runtime_auth=True)
            pid: int | None = None
            try:
                pid = self._spawn_and_wait(runtime)
            except Exception:
                if pid is not None:
                    try:
                        self._rollback_spawned(runtime, pid)
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
        """Return independent, read-only facts for both product services."""
        probes = self._service_probes()
        return {
            "url": self.web_url,
            "product_ready": all(probe.ready for probe in probes),
            "warnings": [],
            "services": {
                probe.role: probe.public(log=str(self.log_root / f"{probe.role}.log"))
                for probe in probes
            },
        }

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

    def _node_diagnosis(self) -> tuple[str | None, str | None]:
        """Classify Node with the shared Web installation contract."""
        if not Path(self.node).is_file():
            return None, "node_unavailable"
        version = self._executable_version(self.node)
        return version, node_version_issue(version)

    def _read_install_manifest(self) -> dict[str, Any]:
        path = self.data_root.parent / "install" / "manifest.json"
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024:
                return {}
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) and value.get("schema_version") == 1 else {}
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _runtime_build_lock_matches(self, dsh: dict[str, Any]) -> bool:
        try:
            with runtime_state_directory(self.runtime_state_root, native_data_root=self.data_root):
                return self._read_runtime_build_lock_matches(dsh)
        except (OSError, RuntimeStateError):
            return False

    def _read_runtime_build_lock_matches(self, dsh: dict[str, Any]) -> bool:
        expected_sha256 = dsh.get("closure_sha256")
        expected_files = dsh.get("closure_files")
        if not isinstance(expected_sha256, str) or type(expected_files) is not int:
            return False
        path = self.runtime_state_root / "build-lock.json"
        try:
            if os.name == "nt":
                trusted_root = self.runtime_state_root.parent.resolve(strict=True)
                for directory in (
                    self.runtime_state_root.parent.parent,
                    self.runtime_state_root.parent,
                    self.runtime_state_root,
                ):
                    identity = directory.lstat()
                    if _is_unsafe_private_directory(
                        directory, identity, platform_name="nt"
                    ) or not directory.resolve(strict=True).is_relative_to(trusted_root.parent):
                        return False
                before = path.lstat()
                reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                if (
                    path.is_symlink()
                    or bool(getattr(before, "st_file_attributes", 0) & reparse_flag)
                    or not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or before.st_size > 64 * 1024
                ):
                    return False
                with path.open("rb") as stream:
                    opened = os.fstat(stream.fileno())
                    raw = stream.read(64 * 1024 + 1)
                after = path.lstat()
                identities = {
                    (item.st_dev, item.st_ino, item.st_size) for item in (before, opened, after)
                }
                if len(identities) != 1 or len(raw) > 64 * 1024:
                    return False
            else:
                parent = os.open(
                    self.runtime_state_root.parent.parent,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                )
                try:
                    root = os.open(
                        self.runtime_state_root.parent.name or ".",
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=parent,
                    )
                    try:
                        runtime = os.open(
                            self.runtime_state_root.name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=root,
                        )
                        try:
                            handle = os.open(
                                "build-lock.json",
                                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                dir_fd=runtime,
                            )
                            try:
                                identity = os.fstat(handle)
                                if (
                                    not stat.S_ISREG(identity.st_mode)
                                    or identity.st_nlink != 1
                                    or identity.st_size > 64 * 1024
                                    or bool(identity.st_mode & 0o077)
                                ):
                                    return False
                                raw = os.read(handle, 64 * 1024 + 1)
                            finally:
                                os.close(handle)
                        finally:
                            os.close(runtime)
                    finally:
                        os.close(root)
                finally:
                    os.close(parent)
            if len(raw) > 64 * 1024:
                return False
            value = json.loads(raw.decode("utf-8"))
            return (
                isinstance(value, dict)
                and set(value) == {"source_commit", "closure_sha256", "closure_files", "mode"}
                and type(value.get("closure_files")) is int
                and value
                == {
                    "source_commit": PINNED_COMMIT,
                    "closure_sha256": expected_sha256,
                    "closure_files": expected_files,
                    "mode": "build",
                }
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return False

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

    def _installation_diagnosis(self) -> dict[str, Any]:
        """Return installation facts without probing or mutating service health."""
        manifest = self._read_install_manifest()
        lock = self.project_root / "requirements" / "web.lock"
        try:
            lock_sha256 = hashlib.sha256(lock.read_bytes()).hexdigest()
        except OSError:
            lock_sha256 = None
        package_versions = self._installed_package_versions()
        dsh = self._dsh_build_status()
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
        runtime_lock_matches = bool(dsh_ready and self._runtime_build_lock_matches(dsh))
        node_version, node_issue = self._node_diagnosis()
        issues = []
        for ready, code in (
            (manifest.get("status") == "installed", "install_manifest_invalid"),
            (environment_owned, "environment_not_owned"),
            (lock_matches, "web_lock_mismatch"),
            (cjpy_ready, "cjpy_not_ready"),
            (dsh_ready, "dsh_not_ready"),
            (runtime_lock_matches, "dsh_runtime_lock_mismatch"),
        ):
            if not ready:
                issues.append(code)
        if node_issue is not None:
            issues.append(node_issue)
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
            "node": {"version": node_version},
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
                "runtime_lock_matches": runtime_lock_matches,
            },
            "data": {"ready": self.data_root.is_dir()},
        }

    def _model_diagnosis(self) -> tuple[bool, tuple[str, ...]]:
        """Read safe model configuration/catalog facts without generation calls."""
        warnings: list[str] = []
        try:
            runtime = self._json_request(self.web_port, "GET", "/api/research/runtime")
        except ServiceManagerError:
            return False, ("model_catalog_unavailable",)
        provider = runtime.get("provider")
        model = runtime.get("model")
        configured = (
            isinstance(provider, str)
            and bool(provider.strip())
            and isinstance(model, str)
            and bool(model.strip())
        )
        credential_configured = runtime.get("credential_configured") is True
        if not configured:
            warnings.append("model_configuration_missing")
        if not credential_configured:
            warnings.append("model_credential_missing")

        catalog_ready = False
        try:
            catalog = self._json_request(self.web_port, "GET", "/api/research/models")
            groups = catalog.get("groups")
            failures = catalog.get("failures")
            catalog_ready = isinstance(groups, list) and isinstance(failures, list) and not failures
            if not catalog_ready:
                warnings.append("model_catalog_unavailable")
        except ServiceManagerError:
            warnings.append("model_catalog_unavailable")
        stable_warnings = tuple(dict.fromkeys(warnings))
        return configured and credential_configured and catalog_ready, stable_warnings

    def doctor(self) -> dict[str, Any]:
        """Return a path-free, credential-free Web installation diagnosis."""
        diagnosis = self._installation_diagnosis()
        probes = self._service_probes()
        installation_issues = diagnosis.get("issues", [])
        if not isinstance(installation_issues, list):
            installation_issues = []
        service_issues = [issue for probe in probes for issue in probe.issues]
        installation_ok = bool(diagnosis.get("ok"))
        product_ready = all(probe.ready for probe in probes)
        model_ready, model_warnings = self._model_diagnosis() if product_ready else (False, ())
        warnings = list(dict.fromkeys([*model_warnings, *proxy_warnings(os.environ)]))
        return {
            **diagnosis,
            "runtime_mode": "native",
            "schema_version": 2,
            "ok": installation_ok,
            "installation_ok": installation_ok,
            "product_ready": product_ready,
            "model_ready": model_ready,
            "issues": list(dict.fromkeys([*installation_issues, *service_issues])),
            "warnings": warnings,
            "services": {probe.role: probe.public() for probe in probes},
        }

    def _validate_log_ownership(self) -> dict[str, tuple[bytes, tuple[int, ...]]]:
        """Read exact Native state without deleting stale state or probing Docker."""
        from research_workbench_entrypoint.runtime_mode import (
            RuntimeModeError,
            _identity,
            _read_bytes,
        )

        proofs = {}
        try:
            for process in self._processes():
                try:
                    raw, identity = _read_bytes(self._state_path(process.role))
                except FileNotFoundError:
                    if (self.log_root / f"{process.role}.log").exists():
                        raise ServiceManagerError("native_logs_ownership_unknown")
                    continue
                state = self._probe_state(process)
                if state.state != "valid":
                    raise ServiceManagerError("native_logs_ownership_unknown")
                _, observed = self._probe_pid_and_ownership(process, state)
                if observed.process != "missing" and observed.ownership != "owned":
                    raise ServiceManagerError("native_logs_ownership_unknown")
                # Bind the validated fact chain to the exact bytes and inode read.
                confirmed_raw, confirmed_identity = _read_bytes(self._state_path(process.role))
                if confirmed_raw != raw or _identity(confirmed_identity) != _identity(identity):
                    raise ServiceManagerError("native_logs_ownership_unknown")
                proofs[process.role] = (raw, _identity(identity))
            return proofs
        except (OSError, ValueError, RuntimeModeError):
            log.warning("native_logs_ownership_unknown")
            raise ServiceManagerError("native_logs_ownership_unknown") from None

    def logs(self, *, tail: int = 100, follow: bool = False) -> int:
        """Read only owned runtime.log/web.log, bounded to 64 KiB and 300 seconds."""
        if self._endpoint_error:
            raise ServiceManagerError(self._endpoint_error, code=self._endpoint_error)
        from research_workbench_entrypoint.docker_runtime import MAX_OUTPUT, safe_log_text
        from research_workbench_entrypoint.runtime_mode import (
            RuntimeModeError,
            _identity,
            _pin_posix_parents,
            _pin_windows_parents,
        )

        if type(tail) is not int or not 0 <= tail <= 10000:
            raise ServiceManagerError("native_logs_tail_invalid")
        offsets: dict[str, tuple[int, int, int]] = {}
        pending: dict[str, bytes] = {}
        consumed = 0
        emitted = 0
        deadline = time.monotonic() + 300
        try:
            while True:
                ownership = self._validate_log_ownership()
                output = []
                files = {}
                try:
                    pin = _pin_windows_parents if os.name == "nt" else _pin_posix_parents
                    with (
                        runtime_state_directory(self.log_root),
                        pin(self.log_root / "web.log", node_only=True) as parent,
                    ):
                        for role in ("runtime", "web"):
                            path = self.log_root / f"{role}.log"
                            name = str(path) if parent is None else path.name
                            try:
                                before = os.stat(name, dir_fd=parent, follow_symlinks=False)
                            except FileNotFoundError:
                                continue
                            if role not in ownership:
                                raise ServiceManagerError("native_logs_ownership_unknown")
                            if (
                                not stat.S_ISREG(before.st_mode)
                                or before.st_nlink != 1
                                or getattr(before, "st_file_attributes", 0) & 0x400
                                or (os.name == "posix" and before.st_uid != os.getuid())
                            ):
                                raise ServiceManagerError("native_logs_unsafe")
                            descriptor = os.open(
                                name,
                                os.O_RDONLY
                                | getattr(os, "O_NOFOLLOW", 0)
                                | getattr(os, "O_NONBLOCK", 0),
                                dir_fd=parent,
                            )
                            with os.fdopen(descriptor, "rb") as stream:
                                identity = os.fstat(stream.fileno())
                                key = (identity.st_dev, identity.st_ino)
                                if _identity(identity) != _identity(before):
                                    raise ServiceManagerError("native_logs_unsafe")
                                previous = offsets.get(role)
                                if previous and (
                                    previous[:2] != key or identity.st_size < previous[2]
                                ):
                                    raise ServiceManagerError("native_logs_changed")
                                start = (
                                    previous[2]
                                    if previous
                                    else max(0, identity.st_size - MAX_OUTPUT // 2)
                                )
                                if not previous and tail == 0:
                                    start = identity.st_size
                                stream.seek(start)
                                chunk = stream.read(min(MAX_OUTPUT // 2, MAX_OUTPUT - consumed))
                                consumed += len(chunk)
                                offsets[role] = (*key, stream.tell())
                                if _identity(os.fstat(stream.fileno())) != _identity(identity):
                                    raise ServiceManagerError("native_logs_changed")
                                files[role] = _identity(identity)
                            if not previous and start and chunk:
                                chunk = chunk.partition(b"\n")[2]
                            chunk = pending.get(role, b"") + chunk
                            if follow:
                                boundary = chunk.rfind(b"\n") + 1
                                pending[role], chunk = chunk[boundary:], chunk[:boundary]
                            lines = safe_log_text(chunk.decode("utf-8", "replace")).splitlines()
                            if not previous:
                                lines = lines[-tail:] if tail else []
                            output.append("\n".join(lines) + ("\n" if lines else ""))
                        if self._validate_log_ownership() != ownership:
                            raise ServiceManagerError("native_logs_ownership_unknown")
                        for role, identity in files.items():
                            path = self.log_root / f"{role}.log"
                            name = str(path) if parent is None else path.name
                            try:
                                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                            except FileNotFoundError:
                                raise ServiceManagerError("native_logs_changed") from None
                            if _identity(current) != identity:
                                raise ServiceManagerError("native_logs_changed")
                except FileNotFoundError:
                    if files or output:
                        raise ServiceManagerError("native_logs_changed") from None
                for text in output:
                    encoded = text.encode("utf-8")[: MAX_OUTPUT - emitted]
                    emitted += len(encoded)
                    sys.stdout.write(encoded.decode("utf-8", "ignore"))
                sys.stdout.flush()
                if not follow:
                    return 0
                if consumed >= MAX_OUTPUT or emitted >= MAX_OUTPUT or time.monotonic() >= deadline:
                    raise ServiceManagerError("native_logs_limit")
                time.sleep(0.1)
        except (OSError, RuntimeStateError, RuntimeModeError):
            log.warning("native_logs_unsafe")
            raise ServiceManagerError("native_logs_unsafe") from None

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
        if item.get("ready") or item.get("healthy"):
            summary = "healthy"
        elif (
            item.get("state", "missing") == "missing"
            and item.get("process", "missing") == "missing"
            and item.get("port_state", "closed") == "closed"
        ):
            summary = "stopped"
        else:
            summary = "not ready"
        lines.append(
            f"{role}: {summary} "
            f"(state={item.get('state', 'unknown')}, "
            f"process={item.get('process', 'unknown')}, "
            f"ownership={item.get('ownership', 'unknown')}, "
            f"port={item.get('port_state', 'unknown')}:{item.get('port', '-')}, "
            f"protocol={item.get('protocol', 'not_run')}, "
            f"ready={'yes' if item.get('ready', item.get('healthy')) else 'no'}, "
            f"pid={item.get('pid') or '-'})"
        )
        issues = item.get("issues", [])
        if issues:
            lines.append(f"  issues: {', '.join(issues)}")
    warnings = status.get("warnings", [])
    if warnings:
        lines.append(f"warnings: {', '.join(warnings)}")
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
    lines = [
        "Installation: "
        + ("ready" if status.get("installation_ok", status.get("ok")) else "needs attention"),
        f"Product: {'ready' if status.get('product_ready') else 'not ready'}",
        f"Model: {'ready' if status.get('model_ready') else 'not ready'}",
        f"Python: {status.get('python', {}).get('version') or 'missing'}",
        "Web lock: "
        + ("verified" if status.get("python", {}).get("lock_matches_manifest") else "invalid"),
        f"CJPY: {status.get('cjpy', {}).get('version') or 'missing'}",
        f"Node: {status.get('node', {}).get('version') or 'missing'}",
        f"DSH: {'ready' if status.get('dsh', {}).get('ready') else 'invalid'}",
    ]
    for role, label in (("runtime", "Runtime"), ("web", "Web")):
        item = status.get("services", {}).get(role, {})
        lines.append(
            f"{label} {item.get('port', 3081 if role == 'runtime' else 8088)}: "
            f"{'healthy' if item.get('ready', item.get('healthy')) else 'not ready'} "
            f"(state={item.get('state', 'unknown')}, "
            f"process={item.get('process', 'unknown')}, "
            f"ownership={item.get('ownership', 'unknown')}, "
            f"port={item.get('port_state', 'unknown')}, "
            f"protocol={item.get('protocol', 'not_run')})"
        )
    lines.extend(
        [
            "issues: " + (", ".join(status.get("issues", [])) or "none"),
            "warnings: " + (", ".join(status.get("warnings", [])) or "none"),
        ]
    )
    return "\n".join(lines)
