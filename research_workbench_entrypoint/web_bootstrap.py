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

log = logging.getLogger("research_workbench.web_bootstrap")


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _data_home(environment: Mapping[str, str]) -> Path:
    configured = environment.get("RESEARCH_DATA_HOME")
    if configured:
        return _absolute(Path(configured))
    return _absolute(Path.home() / ".research-workbench" / "research-web")


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
    if any(type(item) is not str or not item or len(item) > 4096 for item in value):
        return None
    return value


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
    expected_signature = (
        _expected_signature(role, command, project_root, data_home) if command else None
    )
    valid = (
        type(value.get("version")) is int
        and value["version"] == 1
        and type(value.get("role")) is str
        and value["role"] == role
        and type(value.get("pid")) is int
        and value["pid"] > 1
        and type(value.get("port")) is int
        and value["port"] == port
        and type(started_at) in {int, float}
        and math.isfinite(started_at)
        and started_at >= 0
        and type(value.get("project_root")) is str
        and value["project_root"] == str(project_root)
        and type(value.get("data_root")) is str
        and value["data_root"] == str(data_home)
        and command is not None
        and type(value.get("fingerprint")) is str
        and value["fingerprint"] == _fingerprint(command)
        and signature is not None
        and expected_signature is not None
        and signature == expected_signature
    )
    return value if valid else None


def _read_state(
    path: Path,
    *,
    role: str,
    port: int,
    project_root: Path,
    data_home: Path,
) -> tuple[str, dict[str, Any] | None]:
    try:
        identity = path.lstat()
    except FileNotFoundError:
        return "missing", None
    except OSError:
        return "invalid", None
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not stat.S_ISREG(identity.st_mode)
        or stat.S_ISLNK(identity.st_mode)
        or bool(getattr(identity, "st_file_attributes", 0) & reparse_flag)
        or identity.st_size > STATE_LIMIT_BYTES
    ):
        return "invalid", None
    try:
        with path.open("rb") as stream:
            raw = stream.read(STATE_LIMIT_BYTES + 1)
        if len(raw) > STATE_LIMIT_BYTES:
            return "invalid", None
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return "invalid", None
    state = _valid_state(
        value,
        role=role,
        port=port,
        project_root=project_root,
        data_home=data_home,
    )
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
            ownership = "owned"
            owned_pid = state["pid"]
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
