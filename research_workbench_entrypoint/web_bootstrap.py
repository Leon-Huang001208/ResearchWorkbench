"""Read-only Research Web diagnostics when the product environment is broken."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sys
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import Any, cast

from .platform_capabilities import platform_capabilities
from .runtime_endpoints import EndpointError, EndpointStore
from .web_contract import (
    CONTROL_JSON_MAX_BYTES,
    PROCESS_START_TOLERANCE_SECONDS,
    PrivateJsonFact,
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
    ("--help",),
    ("web", "status"),
    ("web", "status", "--json"),
    ("web", "doctor"),
    ("web", "doctor", "--json"),
}
BOOTSTRAP_HELP = """Usage: rwb [OPTIONS] COMMAND [ARGS]...

Web environment unavailable; these read-only commands remain available:
  web status            Show service facts
  web doctor [--json]   Diagnose installation and service health

Install or repair: ./setup-web.sh --repair --no-start
Windows: setup-web.cmd --repair --no-start"""
ENVIRONMENT_EXIT_CODES = {
    None: 0,
    "python_environment_missing": 41,
    "python_environment_incomplete": 42,
    "python_environment_unusable": 43,
}

log = logging.getLogger("research_workbench.web_bootstrap")


def _standard_native_data_root() -> Path | None:
    """One OS-user candidate; HOME and product overrides are not discovery authority."""
    if sys.platform != "darwin":
        return None
    import pwd

    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir) / ".research-workbench/research-web"
    except (KeyError, OSError):
        log.warning("foreign_native_ledger code=runtime_ownership_unknown")
        return None


class _ForeignNativeLedger:
    """Call-local existing-ledger observation, optionally bound to an actual lease.

    Web's data association is the private launch ledger, not process-environment
    attestation. No records, process arguments or authentication are logged.
    """

    def __init__(self, target: Path, scope: ExitStack, *, owner=None, lease=None):
        from .runtime_mode import (
            _open_posix_directory,
            _pin_posix_parents,
            _validate_posix_private_directory,
            _validate_posix_private_file,
        )

        self.owner, self.lease, self.scope = owner, lease, scope
        self._invalid = False
        self.target = Path(target).absolute()
        candidate = _standard_native_data_root()
        if candidate is None:
            raise ValueError("foreign_native_ledger_unverified")
        self.candidate = Path(candidate).absolute()
        if (
            self.target.resolve() != self.target
            or self.candidate.resolve() != self.candidate
            or self.candidate == self.target
            or self.candidate.parent == self.target.parent
        ):
            raise ValueError("foreign_native_ledger_unverified")
        self.nodes = []
        self.ancestors = {}
        for role in ("web", "runtime"):
            try:
                (self.target.parent / "run" / (role + ".json")).lstat()
            except FileNotFoundError:
                pass
            else:
                raise ValueError("foreign_native_ledger_unverified")
        for root in (self.target, self.candidate):
            parent = scope.enter_context(_pin_posix_parents(root, node_only=True))
            _validate_posix_private_directory(os.fstat(parent))
            for ancestor in root.parents:
                self.ancestors[ancestor] = self._identity(ancestor.lstat())
            descriptor, identity = _open_posix_directory(parent, root.name)
            scope.callback(os.close, descriptor)
            _validate_posix_private_directory(identity)
            self.nodes.append((root, descriptor, self._identity(identity)))
        for role in ("web", "runtime"):
            path = self.candidate.parent / "run" / (role + ".json")
            parent = scope.enter_context(_pin_posix_parents(path, node_only=True))
            _validate_posix_private_directory(os.fstat(parent))
            self.ancestors[path.parent] = self._identity(path.parent.lstat())
            before = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            _validate_posix_private_file(before)
            if before.st_size > STATE_LIMIT_BYTES:
                raise ValueError("foreign_native_ledger_unverified")
            descriptor = os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            scope.callback(os.close, descriptor)
            identity = os.fstat(descriptor)
            _validate_posix_private_file(identity)
            if self._identity(identity, file=True) != self._identity(before, file=True):
                raise ValueError("foreign_native_ledger_unverified")
            self.nodes.append((path, descriptor, self._identity(identity, file=True)))
        self.before = self._facts()
        if self.before is None or not self.current():
            raise ValueError("foreign_native_ledger_unverified")

    @staticmethod
    def _identity(info, *, file=False):
        node = info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid
        return (*node, info.st_size, info.st_mtime_ns, info.st_ctime_ns) if file else node

    def _facts(self):
        """Reuse the exact private reader and service validator, with exact PID sets."""
        values = {}
        for role in ("web", "runtime"):
            fact = read_private_json(
                self.candidate.parent / "run" / (role + ".json"),
                trusted_root=self.candidate.parent,
                max_bytes=STATE_LIMIT_BYTES,
            )
            if fact.state != "valid" or type(fact.value) is not dict:
                return None
            values[role] = fact.value
        project = _bounded_string(values["web"].get("project_root"))
        if (
            project is None
            or not Path(project).is_absolute()
            or str(Path(project).resolve()) != project
        ):
            return None
        services = bootstrap_service_facts(Path(project), self.candidate)
        pids = []
        processes, listeners = {}, {}
        for role, service in services.items():
            if (
                _valid_state(
                    values[role],
                    role=role,
                    port=service["port"],
                    project_root=Path(project),
                    data_home=self.candidate,
                    web_port=services["web"]["port"],
                )
                is None
                or values[role]["pid"] != service["pid"]
                or service["state"] != "valid"
                or service["ownership"] != "owned"
                or service["process"] != "alive"
                or service["port_state"] != "listening"
                or service["issues"]
            ):
                return None
            pid = service["pid"]
            listener = listener_pids(service["port"])
            process = probe_process(pid)
            if (
                listener.issue
                or listener.pids != (pid,)
                or process.state != "alive"
                or process.issue
                or not process.argv
                or process.started_at is None
                or not signature_matches_argv(tuple(values[role]["signature"]), process.argv)
                or abs(process.started_at - values[role]["started_at"])
                > PROCESS_START_TOLERANCE_SECONDS
            ):
                return None
            pids.append(pid)
            processes[pid] = process
            listeners[service["port"]] = listener
        if len(set(pids)) != 2 or len(listeners) != 2:
            return None
        return values, services, processes, listeners

    def current(self) -> bool:
        from .runtime_mode import RuntimeModeError

        if self._invalid:
            return False
        try:
            valid = (
                all(
                    self._identity(path.lstat()) == before
                    for path, before in self.ancestors.items()
                )
                and all(
                    self._identity(os.fstat(fd), file=path.suffix == ".json") == before
                    and self._identity(path.lstat(), file=path.suffix == ".json") == before
                    for path, fd, before in self.nodes
                )
                and self._facts() == self.before
            )
            self._invalid = not valid
            return valid
        except (OSError, ValueError, TypeError, EndpointError, RuntimeModeError):
            self._invalid = True
            log.warning("foreign_native_ledger code=runtime_ownership_unknown")
            return False

    def _snapshot(self):
        """Private RAM facts for comparison only; contains no lease or authority."""
        return (
            self.before,
            tuple((path, identity) for path, _fd, identity in self.nodes),
            self.ancestors,
        )

    def _invalidate(self):
        """Observed refusal is permanent for this call's retained witness."""
        self._invalid = True

    def permits(self, owner, scope, lease, port, listener) -> bool:
        from app.research_web.lifecycle_lock import LifecycleLock, LifecycleLockError

        if (
            owner is not self.owner
            or scope is not self.scope
            or lease is not self.lease
            or type(lease) is not LifecycleLock
            or getattr(owner, "_foreign_scope", None) is not scope
            or getattr(owner, "_foreign_scope_lease", None) is not lease
            or getattr(owner, "_lifecycle_lease", None) is not lease
        ):
            return False
        selected_lease = cast(LifecycleLock, lease)
        if selected_lease.path != self.target.parent / "run/lifecycle.lock":
            return False
        try:
            selected_lease.assert_held()
            return self.current() and self.before[3].get(port) == listener
        except LifecycleLockError:
            self._invalid = True
            return False


def _foreign_native_listener_safe(
    target: Path, port: int, listener, *, owner=None, observation=None
) -> bool:
    """Read-only current facts or one retained mutation observation; never transfer it."""
    from .runtime_mode import RuntimeModeError

    try:
        if owner is None:
            with ExitStack() as scope:
                proof = _ForeignNativeLedger(target, scope)
                if not proof.current() or proof.before[3].get(port) != listener:
                    return False
                if observation is not None:
                    hint = getattr(observation, "_foreign_hint", None)
                    if hint is not None and hint != proof._snapshot():
                        return False
                    observation._foreign_hint = proof._snapshot()
                return True
        scope = getattr(owner, "_foreign_scope", None)
        lease = getattr(owner, "_foreign_scope_lease", None)
        if type(scope) is not ExitStack or lease is None:
            return False
        if not getattr(owner, "_foreign_attempted", False):
            owner._foreign_attempted = True
            owner._foreign_ledger = _ForeignNativeLedger(target, scope, owner=owner, lease=lease)
        proof = getattr(owner, "_foreign_ledger", None)
        return type(proof) is _ForeignNativeLedger and proof.permits(
            owner, scope, lease, port, listener
        )
    except (OSError, ValueError, TypeError, EndpointError, RuntimeModeError):
        log.warning("foreign_native_ledger code=runtime_ownership_unknown")
        return False


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
    *,
    port: int | None = None,
    web_port: int = WEB_PORT,
) -> list[str] | None:
    selected_port = port if port is not None else (RUNTIME_PORT if role == "runtime" else WEB_PORT)
    if role == "runtime":
        source = _argument(command, "--source")
        if (
            source is None
            or _argument(command, "--data") != str(data_home)
            or _argument(command, "--port") != str(selected_port)
            or _argument(command, "--datahub-url") != f"http://127.0.0.1:{web_port}"
            or "app.research_web.launch_runtime" not in command
        ):
            return None
        return [
            str(Path(source) / "apps/cli/lib/bin.js"),
            str((data_home / "runtime/overlay.yml").resolve()),
            str(selected_port),
        ]
    if (
        _argument(command, "--app-dir") != str(project_root)
        or _argument(command, "--host") != "127.0.0.1"
        or _argument(command, "--port") != str(selected_port)
        or "uvicorn" not in command
        or "app.research_web.main:app" not in command
    ):
        return None
    return ["app.research_web.main:app", str(project_root), str(selected_port)]


def _valid_state(
    value: object,
    *,
    role: str,
    port: int,
    project_root: Path,
    data_home: Path,
    web_port: int = WEB_PORT,
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
        _expected_signature(role, command, project_root, data_home, port=port, web_port=web_port)
        if command
        else None
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
    web_port: int = WEB_PORT,
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
            web_port=web_port,
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
    web_port: int = WEB_PORT,
    raw_fact=None,
) -> dict[str, Any]:
    if raw_fact is None:
        state_status, state = _read_state(
            data_home.parent / "run" / f"{role}.json",
            role=role,
            port=port,
            project_root=project_root,
            data_home=data_home,
            web_port=web_port,
        )
    else:
        state_status, state = raw_fact.state, None
        if state_status == "valid":
            try:
                state = _valid_state(
                    raw_fact.value,
                    role=role,
                    port=port,
                    project_root=project_root,
                    data_home=data_home,
                    web_port=web_port,
                )
            except (TypeError, ValueError, OverflowError, RecursionError):
                state = None
            if state is None:
                state_status = "invalid"
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
    read_facts: dict[str, PrivateJsonFact] = {}
    web_port, runtime_port = native_endpoint_ports(root, selected_data_home, read_facts=read_facts)
    return {
        "runtime": _service_fact(
            role="runtime",
            port=runtime_port,
            project_root=root,
            data_home=selected_data_home,
            web_port=web_port,
            raw_fact=read_facts.get("runtime"),
        ),
        "web": _service_fact(
            role="web",
            port=web_port,
            project_root=root,
            data_home=selected_data_home,
            raw_fact=read_facts.get("web"),
        ),
    }


def native_endpoint_ports(
    project_root: Path, data_home: Path, *, read_facts=None
) -> tuple[int, int]:
    """Read saved ports or mutually consistent private legacy state, without writes."""
    store = EndpointStore(data_home.parent)
    try:
        store.path.lstat()
    except FileNotFoundError:
        saved = None  # Legacy state retains its own private read/identity validation.
    else:
        saved = store.read("native")
    if saved:
        # EndpointStore validates that native records always contain both ports.
        return saved.web_port, cast(int, saved.runtime_port)
    values = {}
    ports = {"web": WEB_PORT, "runtime": RUNTIME_PORT}
    for role in ("web", "runtime"):
        fact = read_private_json(
            data_home.parent / "run" / f"{role}.json",
            trusted_root=data_home.parent,
            max_bytes=STATE_LIMIT_BYTES,
        )
        if read_facts is not None:
            read_facts[role] = fact
        if fact.state == "missing":
            continue
        if fact.state != "valid" or type(fact.value) is not dict:
            return WEB_PORT, RUNTIME_PORT  # Individual state probes retain the refusal.
        port = fact.value.get("port")
        if type(port) is not int or not 1 <= port <= 65535:
            return WEB_PORT, RUNTIME_PORT
        ports[role] = port
        values[role] = fact.value
    if "runtime" in values and "web" not in values:
        from urllib.parse import urlsplit

        command = _safe_string_list(values["runtime"].get("command"), limit=64)
        try:
            origin = urlsplit(_argument(command, "--datahub-url") or "") if command else None
            if (
                origin is not None
                and origin.scheme == "http"
                and origin.hostname == "127.0.0.1"
                and origin.port
            ):
                ports["web"] = origin.port
        except ValueError:
            return WEB_PORT, RUNTIME_PORT
    if ports["web"] == ports["runtime"] or any(
        _valid_state(
            value,
            role=role,
            port=ports[role],
            project_root=project_root,
            data_home=data_home,
            web_port=ports["web"],
        )
        is None
        for role, value in values.items()
    ):
        return WEB_PORT, RUNTIME_PORT
    return ports["web"], ports["runtime"]


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
        "runtime_mode": "native",
        "capabilities": platform_capabilities("native"),
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
    if command == ("--help",):
        log.debug("research_web_bootstrap_help_requested")
        print(BOOTSTRAP_HELP)
        return 0
    report = diagnose(root)
    if command in {("web", "doctor", "--json"), ("web", "status", "--json")}:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif command == ("web", "doctor"):
        print(format_doctor(report))
    else:
        print(format_status(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
