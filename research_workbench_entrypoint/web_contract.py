"""Standard-library-only facts shared by Research Web bootstrap paths."""

from __future__ import annotations

import hashlib
import http.client
import json
import logging
import os
import re
import socket
import stat
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ENVIRONMENT_MARKER = ".rwb-web-environment.json"
PROCESS_TIMEOUT_SECONDS = 2
PORT_TIMEOUT_SECONDS = 0.25
HTTP_TIMEOUT_SECONDS = 2
MAX_HTTP_BODY_BYTES = 2 * 1024 * 1024

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


@dataclass(frozen=True)
class HttpFact:
    """Bounded direct-loopback HTTP result."""

    status: int | None
    content_type: str | None
    body: bytes
    issue: str | None


def node_version_issue(value: str | None) -> str | None:
    """Return the stable issue for a Node version under the Web install contract."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (value or "").strip())
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
    return ProcessFact("alive", command.stdout.strip() or None, None)


def _posix_process(pid: int) -> ProcessFact:
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
    return ProcessFact("alive", command.stdout.strip() or None, None)


def probe_process(pid: int, *, platform_name: str | None = None) -> ProcessFact:
    """Inspect one PID with bounded, non-shell operating-system probes."""
    if pid <= 1:
        return ProcessFact("missing", None, None)
    return _windows_process(pid) if (platform_name or os.name) == "nt" else _posix_process(pid)


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
