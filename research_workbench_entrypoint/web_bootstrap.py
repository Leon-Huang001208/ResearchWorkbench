"""Read-only Research Web diagnostics when the product environment is broken."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .web_contract import (
    CONTROL_JSON_MAX_BYTES,
    PROCESS_START_TOLERANCE_SECONDS,
    ProcessFact,
    classify_python_environment,
    listener_pids,
    probe_process,
    proxy_warnings,
    read_private_json,
    signature_matches_argv,
)

STATE_LIMIT_BYTES = CONTROL_JSON_MAX_BYTES
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


def _read_state(
    path: Path,
    *,
    role: str,
    port: int,
    project_root: Path,
    data_home: Path,
    platform_name: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    fact = read_private_json(
        path,
        trusted_root=data_home.parent,
        max_bytes=STATE_LIMIT_BYTES,
        platform_name=platform_name,
    )
    if fact.state != "valid":
        return fact.state, None
    try:
        state = _valid_state(
            fact.value,
            role=role,
            port=port,
            project_root=project_root,
            data_home=data_home,
        )
    except (TypeError, ValueError, OverflowError, RecursionError):
        return "invalid", None
    return ("valid", state) if state is not None else ("invalid", None)


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
    listener = listener_pids(port)
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
        elif process.issue is not None or process.argv is None or process.started_at is None:
            issues.append(f"{role}_ownership_unverified")
        elif not signature_matches_argv(tuple(state["signature"]), process.argv):
            ownership = "foreign"
            issues.append(f"{role}_process_foreign")
        elif abs(process.started_at - float(state["started_at"])) > (
            PROCESS_START_TOLERANCE_SECONDS
        ):
            ownership = "foreign"
            issues.append(f"{role}_pid_reused")
        else:
            ownership = "owned"
            owned_pid = int(state["pid"])
    if listener.state == "unknown":
        ownership = "unknown" if ownership == "owned" else ownership
        owned_pid = None
        issues.append(f"{role}_listener_probe_failed")
    elif listener.state == "listening" and ownership == "owned" and owned_pid not in listener.pids:
        ownership = "foreign"
        owned_pid = None
        issues.append(f"{role}_port_owner_mismatch")
    elif listener.state == "listening" and ownership != "owned":
        issues.append(f"{role}_port_in_use_unknown")
    elif listener.state == "closed" and ownership == "owned":
        issues.append(f"{role}_port_closed")
    return {
        "state": state_status,
        "process": process_status,
        "ownership": ownership,
        "port_state": listener.state,
        "protocol": "not_run",
        "ready": False,
        "running": process_status == "alive" and ownership == "owned",
        "healthy": False,
        "pid": owned_pid if ownership == "owned" else None,
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
