"""Read-only Research Web diagnostics when the product environment is broken."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import stat
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .web_contract import (
    HttpFact,
    ProcessFact,
    classify_python_environment,
    http_get,
    port_listening,
    probe_process,
    proxy_warnings,
)

STATE_LIMIT_BYTES = 64 * 1024
MAX_PID = (2**31) - 1
MAX_STARTED_AT = 253_402_300_799
MAX_STRING_BYTES = 4096
RUNTIME_PORT = 3081
WEB_PORT = 8088
PYTHON_ISSUES = {
    "python_environment_missing",
    "python_environment_incomplete",
    "python_environment_unusable",
}
ALLOWED_COMMANDS = {
    ("web", "status"),
    ("web", "doctor"),
    ("web", "doctor", "--json"),
}
ENVIRONMENT_EXIT_CODES = {
    None: 0,
    "python_environment_missing": 41,
    "python_environment_incomplete": 42,
    "python_environment_unusable": 43,
}

log = logging.getLogger("research_workbench.web_bootstrap")


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _data_home(environment: Mapping[str, str]) -> Path:
    configured = environment.get("RESEARCH_DATA_HOME")
    if configured:
        return _absolute(Path(configured))
    return _absolute(Path.home() / ".research-workbench" / "research-web")


def select_candidate_environment(
    project_root: Path,
    *,
    common_root: Path | None = None,
    platform_name: str | None = None,
) -> tuple[Path, Path]:
    """Select the local environment, or an explicit common-checkout fallback."""
    current_platform = platform_name or os.name
    relative = Path("Scripts/python.exe" if current_platform == "nt" else "bin/python")
    project = Path(project_root).resolve()
    local = project / ".venv" / relative
    if local.is_file() or common_root is None:
        return local, project
    common = Path(common_root).resolve()
    candidate = common / ".venv" / relative
    return (candidate, common) if candidate.is_file() else (local, project)


def candidate_environment_exit_code(owner_root: Path, *, platform_name: str | None = None) -> int:
    """Map the exact safe environment classification to a batch-friendly code."""
    issue = classify_python_environment(Path(owner_root), platform_name=platform_name).issue
    return ENVIRONMENT_EXIT_CODES.get(issue, ENVIRONMENT_EXIT_CODES["python_environment_unusable"])


def _fingerprint(command: list[str]) -> str:
    payload = json.dumps(command, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _argument(command: list[str], name: str) -> str | None:
    if command.count(name) != 1:
        return None
    index = command.index(name)
    return command[index + 1] if index + 1 < len(command) else None


def _safe_string_list(value: object, *, limit: int) -> list[str] | None:
    if type(value) is not list or not 1 <= len(value) <= limit:
        return None
    if any(type(item) is not str or not item or len(item) > MAX_STRING_BYTES for item in value):
        return None
    return value


def _bounded_string(value: object, *, limit: int = MAX_STRING_BYTES) -> str | None:
    if type(value) is not str or not value or len(value) > limit:
        return None
    return value


def _valid_started_at(value: object) -> bool:
    if type(value) is int:
        return 0 <= value <= MAX_STARTED_AT
    if type(value) is float:
        return math.isfinite(value) and 0 <= value <= MAX_STARTED_AT
    return False


def _expected_signature(
    role: str,
    command: list[str],
    project_root: Path,
    data_home: Path,
) -> list[str] | None:
    if role == "runtime":
        source = _argument(command, "--source")
        if (
            source is None
            or _argument(command, "--data") != str(data_home)
            or _argument(command, "--port") != str(RUNTIME_PORT)
            or _argument(command, "--datahub-url") != f"http://127.0.0.1:{WEB_PORT}"
            or "app.research_web.launch_runtime" not in command
        ):
            return None
        return [
            str(Path(source) / "apps/cli/lib/bin.js"),
            str(data_home / "runtime/overlay.yml"),
            str(RUNTIME_PORT),
        ]
    if (
        _argument(command, "--app-dir") != str(project_root)
        or _argument(command, "--host") != "127.0.0.1"
        or _argument(command, "--port") != str(WEB_PORT)
        or "uvicorn" not in command
        or "app.research_web.main:app" not in command
    ):
        return None
    return ["app.research_web.main:app", str(project_root), str(WEB_PORT)]


def _valid_state(
    value: object,
    *,
    role: str,
    port: int,
    project_root: Path,
    data_home: Path,
) -> dict[str, Any] | None:
    if type(value) is not dict or set(value) != {
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
    }:
        return None
    command = _safe_string_list(value.get("command"), limit=64)
    signature = _safe_string_list(value.get("signature"), limit=8)
    started_at = value.get("started_at")
    stored_role = _bounded_string(value.get("role"), limit=16)
    stored_project_root = _bounded_string(value.get("project_root"))
    stored_data_root = _bounded_string(value.get("data_root"))
    fingerprint = _bounded_string(value.get("fingerprint"), limit=64)
    expected_signature = (
        _expected_signature(role, command, project_root, data_home) if command else None
    )
    valid = (
        type(value.get("version")) is int
        and value["version"] == 1
        and stored_role == role
        and type(value.get("pid")) is int
        and 2 <= value["pid"] <= MAX_PID
        and type(value.get("port")) is int
        and 1 <= value["port"] <= 65535
        and value["port"] == port
        and _valid_started_at(started_at)
        and stored_project_root == str(project_root)
        and stored_data_root == str(data_home)
        and command is not None
        and fingerprint == _fingerprint(command)
        and signature is not None
        and expected_signature is not None
        and signature == expected_signature
    )
    return value if valid else None


def _identity(identity: os.stat_result | Any) -> tuple[int, int]:
    return int(identity.st_dev), int(identity.st_ino)


def _unsafe_identity(identity: os.stat_result | Any, *, directory: bool) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    expected = stat.S_ISDIR(identity.st_mode) if directory else stat.S_ISREG(identity.st_mode)
    return (
        not expected
        or stat.S_ISLNK(identity.st_mode)
        or bool(getattr(identity, "st_file_attributes", 0) & reparse_flag)
        or (not directory and getattr(identity, "st_nlink", 1) != 1)
    )


def _read_descriptor(fd: int) -> bytes:
    chunks: list[bytes] = []
    remaining = STATE_LIMIT_BYTES + 1
    while remaining:
        chunk = os.read(fd, min(8192, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _open_posix_directory(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    parts = path.absolute().parts
    current = os.open(parts[0], flags | no_follow)
    completed = False
    try:
        for part in parts[1:]:
            following = os.open(part, flags | no_follow, dir_fd=current)
            os.close(current)
            current = following
        completed = True
        return current
    finally:
        if not completed:
            os.close(current)


def _read_posix_state(path: Path) -> tuple[str, bytes | None]:
    directory_fd: int | None = None
    state_fd: int | None = None
    try:
        directory_fd = _open_posix_directory(path.parent)
        before = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        if _unsafe_identity(before, directory=False) or before.st_size > STATE_LIMIT_BYTES:
            return "invalid", None
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        state_fd = os.open(path.name, flags, dir_fd=directory_fd)
        opened = os.fstat(state_fd)
        after = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            _unsafe_identity(opened, directory=False)
            or _unsafe_identity(after, directory=False)
            or opened.st_size > STATE_LIMIT_BYTES
            or after.st_size > STATE_LIMIT_BYTES
            or _identity(before) != _identity(opened)
            or _identity(opened) != _identity(after)
        ):
            return "invalid", None
        raw = _read_descriptor(state_fd)
        return ("valid", raw) if len(raw) <= STATE_LIMIT_BYTES else ("invalid", None)
    except FileNotFoundError:
        return "missing", None
    except (OSError, TypeError, ValueError, OverflowError):
        return "invalid", None
    finally:
        if state_fd is not None:
            os.close(state_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _read_windows_state(path: Path) -> tuple[str, bytes | None]:
    try:
        parent_identities = []
        for ancestor in (path.parent.parent, path.parent):
            identity = ancestor.lstat()
            if _unsafe_identity(identity, directory=True):
                return "invalid", None
            parent_identities.append((ancestor, identity))
        before = path.lstat()
        if _unsafe_identity(before, directory=False) or before.st_size > STATE_LIMIT_BYTES:
            return "invalid", None
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(STATE_LIMIT_BYTES + 1)
        after = path.lstat()
        if (
            _unsafe_identity(opened, directory=False)
            or _unsafe_identity(after, directory=False)
            or len(raw) > STATE_LIMIT_BYTES
            or _identity(before) != _identity(opened)
            or _identity(opened) != _identity(after)
        ):
            return "invalid", None
        for ancestor, identity in parent_identities:
            current = ancestor.lstat()
            if _unsafe_identity(current, directory=True) or _identity(identity) != _identity(
                current
            ):
                return "invalid", None
        return "valid", raw
    except FileNotFoundError:
        return "missing", None
    except (OSError, TypeError, ValueError, OverflowError):
        return "invalid", None


def _read_state(
    path: Path,
    *,
    role: str,
    port: int,
    project_root: Path,
    data_home: Path,
    platform_name: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    state_status, raw = (
        _read_windows_state(path) if (platform_name or os.name) == "nt" else _read_posix_state(path)
    )
    if state_status != "valid" or raw is None:
        return state_status, None
    try:
        value = json.loads(raw.decode("utf-8"))
        state = _valid_state(
            value,
            role=role,
            port=port,
            project_root=project_root,
            data_home=data_home,
        )
    except (OSError, UnicodeError, TypeError, ValueError, OverflowError, RecursionError):
        return "invalid", None
    return ("valid", state) if state is not None else ("invalid", None)


def _http_protocol(port: int) -> tuple[str, bool]:
    root: HttpFact = http_get(port, "/")
    static: HttpFact = http_get(port, "/static/app.mjs")
    root_type = (root.content_type or "").split(";", 1)[0].strip().lower()
    static_type = (static.content_type or "").split(";", 1)[0].strip().lower()
    healthy = (
        root.issue is None
        and root.status == 200
        and root_type == "text/html"
        and static.issue is None
        and static.status == 200
        and static_type in {"application/javascript", "text/javascript"}
    )
    return ("passed", True) if healthy else ("failed", False)


def _service_fact(
    *,
    role: str,
    port: int,
    project_root: Path,
    data_home: Path,
) -> dict[str, Any]:
    state_status, state = _read_state(
        data_home.parent / "run" / f"{role}.json",
        role=role,
        port=port,
        project_root=project_root,
        data_home=data_home,
    )
    listening = port_listening(port)
    process_status = "missing" if state_status == "missing" else "inaccessible"
    ownership = "unknown"
    owned_pid: int | None = None
    issues: list[str] = []
    if state_status == "invalid":
        issues.append(f"{role}_state_invalid")
    elif state is not None:
        process: ProcessFact = probe_process(state["pid"])
        process_status = process.state
        if process.state == "missing":
            issues.append(f"{role}_process_missing")
        elif process.state == "inaccessible" or not process.command_line:
            issues.append(f"{role}_process_unavailable")
        elif all(part in process.command_line for part in state["signature"]):
            issues.append(f"{role}_ownership_unverified")
        else:
            ownership = "foreign"
            issues.append(f"{role}_process_foreign")
    if listening and ownership != "owned":
        ownership = "unknown" if ownership != "foreign" else ownership
        issues.append(f"{role}_port_in_use_unknown")
    if ownership == "owned" and not listening:
        issues.append(f"{role}_port_closed")

    protocol = "not_run"
    protocol_healthy = False
    if role == "web" and ownership == "owned" and listening:
        protocol, protocol_healthy = _http_protocol(port)
        if not protocol_healthy:
            issues.append("web_protocol_failed")
    running = ownership == "owned" and process_status == "alive"
    healthy = running and listening and protocol_healthy
    return {
        "state": state_status,
        "process": process_status,
        "ownership": ownership,
        "port_state": "listening" if listening else "closed",
        "protocol": protocol,
        "ready": healthy,
        "running": running,
        "healthy": healthy,
        "pid": owned_pid,
        "port": port,
        "issues": issues,
    }


def bootstrap_service_facts(
    project_root: Path, data_home: Path | None = None
) -> dict[str, dict[str, Any]]:
    """Return bounded, read-only service facts without authentication or secrets."""
    root = Path(project_root).resolve()
    selected_data_home = (
        _absolute(Path(data_home)) if data_home is not None else _data_home(os.environ)
    )
    return {
        "runtime": _service_fact(
            role="runtime",
            port=RUNTIME_PORT,
            project_root=root,
            data_home=selected_data_home,
        ),
        "web": _service_fact(
            role="web",
            port=WEB_PORT,
            project_root=root,
            data_home=selected_data_home,
        ),
    }


def _python_issue(project_root: Path, environment: Mapping[str, str]) -> str:
    override = environment.get("RWB_BOOTSTRAP_PYTHON_ISSUE")
    if override in PYTHON_ISSUES:
        return override
    return classify_python_environment(project_root).issue or "python_environment_unusable"


def diagnose(project_root: Path, environment: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Build the schema-2 safe diagnosis available without project dependencies."""
    selected_environment = os.environ if environment is None else environment
    root = Path(project_root).resolve()
    services = bootstrap_service_facts(root, _data_home(selected_environment))
    return {
        "schema_version": 2,
        "ok": False,
        "installation_ok": False,
        "product_ready": False,
        "model_ready": False,
        "issues": [_python_issue(root, selected_environment)],
        "warnings": proxy_warnings(selected_environment),
        "services": services,
    }


def format_status(status: Mapping[str, Any]) -> str:
    """Render the safe bootstrap status without paths or process commands."""
    lines = []
    services = status.get("services", {})
    for role in ("runtime", "web"):
        item = services.get(role, {})
        lines.append(
            f"{role}: {'ready' if item.get('ready') else 'not ready'} "
            f"state={item.get('state', 'invalid')} "
            f"process={item.get('process', 'inaccessible')} "
            f"ownership={item.get('ownership', 'unknown')} "
            f"port={item.get('port_state', 'closed')} "
            f"protocol={item.get('protocol', 'not_run')}"
        )
        role_issues = item.get("issues", [])
        if role_issues:
            lines.append(f"{role} issues: {', '.join(role_issues)}")
    lines.append("issues: " + (", ".join(status.get("issues", [])) or "none"))
    lines.append("warnings: " + (", ".join(status.get("warnings", [])) or "none"))
    return "\n".join(lines)


def format_doctor(status: Mapping[str, Any]) -> str:
    """Render the safe bootstrap Doctor result."""
    return "\n".join(
        [
            "overall: needs attention",
            "installation: unavailable",
            "product: unavailable",
            "model: unavailable",
            format_status(status),
            "repair: ./setup-web.sh --repair --no-start",
            "windows repair: setup-web.cmd --repair --no-start",
        ]
    )


def _rejection_message(issue: str) -> str:
    return (
        f"{issue}\nRun ./setup-web.sh --repair --no-start "
        "(Windows: setup-web.cmd --repair --no-start)."
    )


def run(argv: Sequence[str], project_root: Path | None = None) -> int:
    """Run only the exact read-only commands allowed during bootstrap failure."""
    root = (project_root or Path(__file__).resolve().parents[1]).resolve()
    command = tuple(argv)
    if command not in ALLOWED_COMMANDS:
        print(_rejection_message(_python_issue(root, os.environ)), file=sys.stderr)
        return 1
    report = diagnose(root)
    if command == ("web", "doctor", "--json"):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif command == ("web", "doctor"):
        print(format_doctor(report))
    else:
        print(format_status(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
