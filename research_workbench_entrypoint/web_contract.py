"""Standard-library-only facts shared by Research Web bootstrap paths."""

from __future__ import annotations

import ctypes
import hashlib
import http.client
import json
import logging
import os
import re
import shlex
import socket
import stat
import struct
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

ENVIRONMENT_MARKER = ".rwb-web-environment.json"
PROCESS_TIMEOUT_SECONDS = 2
# State is persisted immediately after Popen; ps/CIM timestamps may be second-granularity.
PROCESS_START_TOLERANCE_SECONDS = 5.0
PORT_TIMEOUT_SECONDS = 0.25
HTTP_TIMEOUT_SECONDS = 2
MAX_HTTP_BODY_BYTES = 2 * 1024 * 1024
CONTROL_JSON_MAX_BYTES = 64 * 1024
PROCESS_ARGV_MAX_BYTES = 256 * 1024

log = logging.getLogger("research_workbench.web_contract")


@dataclass(frozen=True)
class PythonEnvironmentFact:
    """Safe facts about the installer-owned project Python environment."""

    issue: str | None
    interpreter: Path
    marker_valid: bool


@dataclass(frozen=True)
class ProcessFact:
    """Bounded process-probe result without operating-system error text."""

    state: Literal["missing", "alive", "inaccessible"]
    command_line: str | None
    issue: str | None
    argv: tuple[str, ...] | None = None
    started_at: float | None = None


@dataclass(frozen=True)
class ListenerFact:
    """Exact listener-owner facts, or unknown when the platform probe failed."""

    state: Literal["closed", "listening", "unknown"]
    pids: tuple[int, ...]
    issue: str | None


@dataclass(frozen=True)
class PrivateJsonFact:
    """A bounded private control-file read without path or parser disclosure."""

    state: Literal["missing", "valid", "invalid"]
    value: object | None
    issue: str | None


@dataclass(frozen=True)
class HttpFact:
    """Bounded direct-loopback HTTP result."""

    status: int | None
    content_type: str | None
    body: bytes
    issue: str | None


def _file_identity(identity: os.stat_result | object) -> tuple[int, int, int]:
    return int(identity.st_dev), int(identity.st_ino), int(identity.st_size)  # type: ignore[attr-defined]


def _directory_identity(identity: os.stat_result | object) -> tuple[int, int]:
    return int(identity.st_dev), int(identity.st_ino)  # type: ignore[attr-defined]


def _unsafe_control_identity(
    identity: os.stat_result | object,
    *,
    directory: bool,
    platform_name: str,
) -> bool:
    mode = int(identity.st_mode)  # type: ignore[attr-defined]
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return (
        (not stat.S_ISDIR(mode) if directory else not stat.S_ISREG(mode))
        or stat.S_ISLNK(mode)
        or bool(getattr(identity, "st_file_attributes", 0) & reparse_flag)
        or (not directory and getattr(identity, "st_nlink", 1) != 1)
        or (platform_name != "nt" and not directory and bool(mode & 0o077))
    )


def _read_bounded_descriptor(fd: int, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    remaining = max_bytes + 1
    while remaining:
        chunk = os.read(fd, min(8192, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_private_json_posix(path: Path, trusted_root: Path, max_bytes: int) -> bytes:
    root = trusted_root.absolute()
    target = path.absolute()
    if not target.is_relative_to(root):
        raise ValueError("control path outside trusted root")
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    current = os.open(root.anchor, directory_flags)
    try:
        parent_parts = (*root.parts[1:], *target.relative_to(root).parts[:-1])
        for part in parent_parts:
            before = os.stat(part, dir_fd=current, follow_symlinks=False)
            following = os.open(part, directory_flags, dir_fd=current)
            opened = os.fstat(following)
            after = os.stat(part, dir_fd=current, follow_symlinks=False)
            if (
                _unsafe_control_identity(before, directory=True, platform_name="posix")
                or _unsafe_control_identity(opened, directory=True, platform_name="posix")
                or _unsafe_control_identity(after, directory=True, platform_name="posix")
                or _directory_identity(before) != _directory_identity(opened)
                or _directory_identity(opened) != _directory_identity(after)
            ):
                os.close(following)
                raise ValueError("unsafe control directory")
            os.close(current)
            current = following
        leaf = target.name
        before = os.stat(leaf, dir_fd=current, follow_symlinks=False)
        if (
            _unsafe_control_identity(before, directory=False, platform_name="posix")
            or before.st_size > max_bytes
        ):
            raise ValueError("unsafe control file")
        handle = os.open(leaf, file_flags, dir_fd=current)
        try:
            opened = os.fstat(handle)
            raw = _read_bounded_descriptor(handle, max_bytes)
        finally:
            os.close(handle)
        after = os.stat(leaf, dir_fd=current, follow_symlinks=False)
        if (
            _unsafe_control_identity(opened, directory=False, platform_name="posix")
            or _unsafe_control_identity(after, directory=False, platform_name="posix")
            or opened.st_size > max_bytes
            or after.st_size > max_bytes
            or len(raw) > max_bytes
            or _file_identity(before) != _file_identity(opened)
            or _file_identity(opened) != _file_identity(after)
        ):
            raise ValueError("control file identity changed")
        return raw
    finally:
        os.close(current)


def _read_private_json_windows(path: Path, trusted_root: Path, max_bytes: int) -> bytes:
    root = trusted_root.absolute()
    target = path.absolute()
    if not target.is_relative_to(root):
        raise ValueError("control path outside trusted root")
    parents = [root]
    current = root
    for part in target.relative_to(root).parts[:-1]:
        current = current / part
        parents.append(current)
    parent_identities = []
    for parent in parents:
        identity = parent.lstat()
        if _unsafe_control_identity(identity, directory=True, platform_name="nt"):
            raise ValueError("unsafe control directory")
        parent_identities.append((parent, identity))
    before = target.lstat()
    if (
        _unsafe_control_identity(before, directory=False, platform_name="nt")
        or before.st_size > max_bytes
    ):
        raise ValueError("unsafe control file")
    with target.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(max_bytes + 1)
    after = target.lstat()
    if (
        _unsafe_control_identity(opened, directory=False, platform_name="nt")
        or _unsafe_control_identity(after, directory=False, platform_name="nt")
        or len(raw) > max_bytes
        or _file_identity(before) != _file_identity(opened)
        or _file_identity(opened) != _file_identity(after)
    ):
        raise ValueError("control file identity changed")
    for parent, before_parent in parent_identities:
        after_parent = parent.lstat()
        if _unsafe_control_identity(
            after_parent, directory=True, platform_name="nt"
        ) or _directory_identity(before_parent) != _directory_identity(after_parent):
            raise ValueError("control directory identity changed")
    return raw


def read_private_json(
    path: Path,
    *,
    trusted_root: Path,
    max_bytes: int = CONTROL_JSON_MAX_BYTES,
    platform_name: str | None = None,
) -> PrivateJsonFact:
    """Read bounded JSON below a trusted root without following aliases or leaking errors."""
    if max_bytes < 1:
        return PrivateJsonFact("invalid", None, "private_json_invalid")
    current_platform = platform_name or os.name
    try:
        raw = (
            _read_private_json_windows(path, trusted_root, max_bytes)
            if current_platform == "nt"
            else _read_private_json_posix(path, trusted_root, max_bytes)
        )
        value = json.loads(raw.decode("utf-8"))
        return PrivateJsonFact("valid", value, None)
    except FileNotFoundError:
        return PrivateJsonFact("missing", None, "private_json_missing")
    except (
        OSError,
        TypeError,
        ValueError,
        UnicodeError,
        OverflowError,
        RecursionError,
        json.JSONDecodeError,
    ):
        return PrivateJsonFact("invalid", None, "private_json_invalid")


def node_version_issue(value: str | None) -> str | None:
    """Return the stable issue for a Node version under the Web install contract."""
    match = re.fullmatch(r"v?([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})", (value or "").strip())
    if match is None:
        return "node_version_invalid"
    major, minor, _patch = (int(part) for part in match.groups())
    return None if (major == 22 and minor >= 19) or major == 24 else "node_version_unsupported"


def environment_marker_valid(
    environment: Path,
    project_root: Path,
    *,
    platform_name: str | None = None,
) -> bool:
    """Validate the exact installer marker without following aliases."""
    marker = environment / ENVIRONMENT_MARKER
    current_platform = platform_name or os.name
    try:
        environment_identity = environment.lstat()
        marker_identity = marker.lstat()
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (
            not stat.S_ISDIR(environment_identity.st_mode)
            or stat.S_ISLNK(environment_identity.st_mode)
            or not stat.S_ISREG(marker_identity.st_mode)
            or stat.S_ISLNK(marker_identity.st_mode)
            or (
                current_platform == "nt"
                and (
                    bool(getattr(environment_identity, "st_file_attributes", 0) & reparse_flag)
                    or bool(getattr(marker_identity, "st_file_attributes", 0) & reparse_flag)
                )
            )
        ):
            return False
        value = json.loads(marker.read_text(encoding="utf-8"))
        project_root_digest = hashlib.sha256(str(project_root.resolve()).encode()).hexdigest()
    except (OSError, ValueError, UnicodeError):
        return False
    return (
        type(value) is dict
        and set(value)
        == {
            "schema_version",
            "owner",
            "project_root_sha256",
            "python",
            "created_at",
        }
        and type(value.get("schema_version")) is int
        and value["schema_version"] == 1
        and type(value.get("owner")) is str
        and value["owner"] == "research-workbench-web-installer"
        and type(value.get("project_root_sha256")) is str
        and value["project_root_sha256"] == project_root_digest
        and type(value.get("python")) is str
        and type(value.get("created_at")) is str
    )


def classify_python_environment(
    project_root: Path, *, platform_name: str | None = None
) -> PythonEnvironmentFact:
    """Classify the project-local Python without importing project dependencies."""
    current_platform = platform_name or os.name
    environment = project_root / ".venv"
    relative = "Scripts/python.exe" if current_platform == "nt" else "bin/python"
    interpreter = environment / relative
    marker_valid = environment_marker_valid(
        environment, project_root, platform_name=current_platform
    )
    if not environment.exists():
        issue = "python_environment_missing"
    elif not interpreter.is_file() or not marker_valid:
        issue = "python_environment_incomplete"
    elif not os.access(interpreter, os.X_OK):
        issue = "python_environment_unusable"
    else:
        issue = None
    return PythonEnvironmentFact(issue, interpreter, marker_valid)


def proxy_warnings(environment: Mapping[str, str]) -> list[str]:
    """Return allowlisted proxy warnings without retaining proxy values."""
    configured = any(
        environment.get(key) for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
    )
    bypass = ",".join(filter(None, (environment.get("NO_PROXY"), environment.get("no_proxy"))))
    entries = {item.strip().lower() for item in bypass.split(",") if item.strip()}
    covered = "*" in entries or {"127.0.0.1", "localhost"}.issubset(entries)
    return ["loopback_proxy_bypass_missing"] if configured and not covered else []


def _run_process_probe(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROCESS_TIMEOUT_SECONDS,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        log.warning(
            "research_web_process_probe_failed",
            extra={"error_type": type(exc).__name__},
        )
        return None


def _command_argv(command_line: str, *, platform_name: str) -> tuple[str, ...] | None:
    try:
        values = shlex.split(command_line, posix=platform_name != "nt")
    except ValueError:
        return None
    if platform_name == "nt":
        values = [
            (
                value[1:-1]
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}
                else value
            )
            for value in values
        ]
    return tuple(values) if values else None


def signature_matches_argv(signature: tuple[str, ...], argv: tuple[str, ...] | None) -> bool:
    """Require signature items as an exact ordered argv subsequence."""
    if not argv or not signature:
        return False
    position = 0
    for token in argv:
        if token == signature[position]:
            position += 1
            if position == len(signature):
                return True
    return False


def _read_linux_argv(
    pid: int,
    *,
    proc_root: Path = Path("/proc"),
) -> tuple[str, ...] | None:
    """Read exact Linux argv boundaries from the bounded procfs cmdline record."""
    try:
        with (proc_root / str(pid) / "cmdline").open("rb") as stream:
            raw = stream.read(PROCESS_ARGV_MAX_BYTES + 1)
    except OSError:
        return None
    if not raw or len(raw) > PROCESS_ARGV_MAX_BYTES or not raw.endswith(b"\0"):
        return None
    values = raw[:-1].split(b"\0")
    if not values or not values[0]:
        return None
    return tuple(os.fsdecode(value) for value in values)


def _parse_macos_procargs2(raw: bytes) -> tuple[str, ...] | None:
    """Parse one bounded KERN_PROCARGS2 payload without guessing token boundaries."""
    if len(raw) < 4 or len(raw) > PROCESS_ARGV_MAX_BYTES:
        return None
    argc = struct.unpack_from("=i", raw)[0]
    if argc < 1 or argc > 4096:
        return None
    position = 4
    executable_end = raw.find(b"\0", position)
    if executable_end < position:
        return None
    position = executable_end + 1
    while position < len(raw) and raw[position] == 0:
        position += 1
    argv: list[str] = []
    for _index in range(argc):
        end = raw.find(b"\0", position)
        if end < position:
            return None
        argv.append(os.fsdecode(raw[position:end]))
        position = end + 1
    return tuple(argv) if argv and argv[0] else None


def _read_macos_argv(pid: int) -> tuple[str, ...] | None:
    """Read exact macOS argv through bounded KERN_PROCARGS2 sysctl."""
    try:
        library = ctypes.CDLL(None, use_errno=True)
        sysctl = library.sysctl
        mib = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2, pid
        size = ctypes.c_size_t(PROCESS_ARGV_MAX_BYTES)
        buffer = ctypes.create_string_buffer(PROCESS_ARGV_MAX_BYTES)
        result = sysctl(
            mib,
            ctypes.c_uint(3),
            buffer,
            ctypes.byref(size),
            None,
            ctypes.c_size_t(0),
        )
        if result != 0 or size.value > PROCESS_ARGV_MAX_BYTES:
            return None
        return _parse_macos_procargs2(buffer.raw[: size.value])
    except (AttributeError, OSError, OverflowError, TypeError, ValueError):
        return None


def _exact_posix_argv(pid: int, *, platform_name: str) -> tuple[str, ...] | None:
    if platform_name.startswith("linux"):
        return _read_linux_argv(pid)
    if platform_name == "darwin":
        return _read_macos_argv(pid)
    return None


def _parse_process_start(value: str, *, platform_name: str) -> float | None:
    try:
        if platform_name == "nt":
            return datetime.fromisoformat(value.strip()).timestamp()
        return datetime.strptime(value.strip(), "%a %b %d %H:%M:%S %Y").astimezone().timestamp()
    except (OverflowError, ValueError):
        return None


def _windows_process(pid: int) -> ProcessFact:
    presence = _run_process_probe(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) "
                "{ exit 0 } else { exit 1 }"
            ),
        ]
    )
    if presence is None:
        return ProcessFact("inaccessible", None, "process_probe_failed")
    if presence.returncode == 1:
        return ProcessFact("missing", None, None)
    if presence.returncode != 0:
        return ProcessFact("inaccessible", None, "process_probe_failed")
    command = _run_process_probe(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                f"$process = Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; "
                "if ($null -ne $process) { $process.CommandLine }"
            ),
        ]
    )
    if command is None or command.returncode != 0:
        return ProcessFact("inaccessible", None, "process_probe_failed")
    command_line = command.stdout.strip() or None
    started = _run_process_probe(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                f"$process = Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; "
                "if ($null -ne $process) { "
                "$process.CreationDate.ToUniversalTime().ToString('o') }"
            ),
        ]
    )
    started_at = (
        _parse_process_start(started.stdout, platform_name="nt")
        if started is not None and started.returncode == 0
        else None
    )
    issue = None if started_at is not None else "process_start_probe_failed"
    return ProcessFact(
        "alive",
        command_line,
        issue,
        _command_argv(command_line, platform_name="nt") if command_line else None,
        started_at,
    )


def _posix_process(pid: int, *, platform_name: str) -> ProcessFact:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return ProcessFact("missing", None, None)
    except PermissionError:
        return ProcessFact("inaccessible", None, "process_access_denied")
    except OSError as exc:
        log.warning(
            "research_web_process_probe_failed",
            extra={"error_type": type(exc).__name__},
        )
        return ProcessFact("inaccessible", None, "process_probe_failed")

    status = _run_process_probe(["ps", "-p", str(pid), "-o", "stat="])
    if status is None or status.returncode != 0:
        return ProcessFact("inaccessible", None, "process_probe_failed")
    if status.stdout.strip().startswith("Z"):
        return ProcessFact("missing", None, None)
    command = _run_process_probe(["ps", "-p", str(pid), "-o", "command="])
    if command is None or command.returncode != 0:
        return ProcessFact("inaccessible", None, "process_probe_failed")
    command_line = command.stdout.strip() or None
    started = _run_process_probe(["ps", "-p", str(pid), "-o", "lstart="])
    started_at = (
        _parse_process_start(started.stdout, platform_name="posix")
        if started is not None and started.returncode == 0
        else None
    )
    issue = None if started_at is not None else "process_start_probe_failed"
    argv = _exact_posix_argv(pid, platform_name=platform_name)
    if issue is None and argv is None:
        issue = "process_argv_unavailable"
    return ProcessFact(
        "alive",
        command_line,
        issue,
        argv,
        started_at,
    )


def probe_process(pid: int, *, platform_name: str | None = None) -> ProcessFact:
    """Inspect one PID with bounded, non-shell operating-system probes."""
    if pid <= 1:
        return ProcessFact("missing", None, None)
    current_platform = platform_name or ("nt" if os.name == "nt" else sys.platform)
    return (
        _windows_process(pid)
        if current_platform == "nt"
        else _posix_process(pid, platform_name=current_platform)
    )


def pid_exists(pid: int, *, platform_name: str | None = None) -> bool:
    """Compatibility wrapper preserving conservative existing PID semantics."""
    return probe_process(pid, platform_name=platform_name).state != "missing"


def command_line(pid: int, *, platform_name: str | None = None) -> str:
    """Compatibility wrapper returning no error or exception text."""
    return probe_process(pid, platform_name=platform_name).command_line or ""


def port_listening(port: int) -> bool:
    """Return whether a direct IPv4 loopback TCP listener accepts connections."""
    if port < 1 or port > 65535:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=PORT_TIMEOUT_SECONDS):
            return True
    except OSError:
        return False


def listener_pids(port: int, *, platform_name: str | None = None) -> ListenerFact:
    """Return exact loopback TCP listener PIDs using bounded platform-native probes."""
    if port < 1 or port > 65535:
        return ListenerFact("unknown", (), "listener_probe_failed")
    current_platform = platform_name or os.name
    command = (
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "Get-NetTCPConnection -State Listen -LocalPort "
                f"{port} -ErrorAction SilentlyContinue | "
                "Select-Object -ExpandProperty OwningProcess -Unique"
            ),
        ]
        if current_platform == "nt"
        else ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"]
    )
    result = _run_process_probe(command)
    if result is None:
        return ListenerFact("unknown", (), "listener_probe_failed")
    if result.returncode != 0:
        if current_platform != "nt" and result.returncode == 1 and not result.stdout.strip():
            return ListenerFact("closed", (), None)
        return ListenerFact("unknown", (), "listener_probe_failed")
    try:
        values = tuple(
            sorted({int(item.strip()) for item in result.stdout.splitlines() if item.strip()})
        )
    except ValueError:
        return ListenerFact("unknown", (), "listener_probe_failed")
    if len(values) > 64 or any(pid <= 1 or pid > (2**31) - 1 for pid in values):
        return ListenerFact("unknown", (), "listener_probe_failed")
    return ListenerFact("listening", values, None) if values else ListenerFact("closed", (), None)


def http_get(port: int, path: str) -> HttpFact:
    """Perform a bounded GET directly against IPv4 loopback, without proxies."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=HTTP_TIMEOUT_SECONDS)
    status: int | None = None
    content_type: str | None = None
    try:
        connection.request("GET", path, headers={"Connection": "close"})
        response = connection.getresponse()
        status = response.status
        content_type = response.getheader("Content-Type")
        body = response.read(MAX_HTTP_BODY_BYTES + 1)
        if len(body) > MAX_HTTP_BODY_BYTES:
            return HttpFact(status, content_type, b"", "http_response_too_large")
        return HttpFact(status, content_type, body, None)
    except (OSError, TimeoutError):
        return HttpFact(status, content_type, b"", "http_connection_failed")
    except (ValueError, http.client.HTTPException):
        return HttpFact(status, content_type, b"", "http_protocol_failed")
    finally:
        connection.close()
