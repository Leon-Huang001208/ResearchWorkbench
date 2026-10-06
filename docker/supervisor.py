"""Foreground container PID 1: DSH-first startup and bounded group shutdown."""

from __future__ import annotations

import json
import argparse
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from contextlib import ExitStack
from pathlib import Path
from typing import Protocol
from uuid import uuid4

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research_web.process_spec import build_process_specs
from app.research_web.runtime_auth import read_runtime_auth_record
from app.research_web.runtime_state import (
    RuntimeStateError, _identity, _validate_directory, runtime_state_directory,
)
from app.research_web.service_manager import RUNTIME_TOKEN_PATTERN
from core.observability import get_logger, setup_logging
from core.settings import settings
from docker.healthcheck import ContainerHealth

log = get_logger(__name__)
ROLE_ENVIRONMENT_KEY = "RWB_SUPERVISOR_ROLE"
MAX_ROLE_ENVIRONMENT_BYTES = 64 * 1024
_DOCKER_PRIVATE_LEAVES = frozenset({
    Path("/state/runtime"), Path("/run/rwb-secrets/private"), Path("/data/research-web/logs"),
})
_DOCKER_STATE_LEAF = Path("/state/runtime")


def prepare_controls(data_root: Path, previous_origin: str) -> None:
    """Use normal guest creators before consumers, preserving every existing token."""
    from app.research_web.control_origin import _checked_origin, _decode
    from app.research_web.datahub.security import load_control
    from app.research_web.mcp_runtime.control import load_control as load_mcp_control
    from research_workbench_entrypoint.runtime_mode import _read_bytes

    try:
        origin = _checked_origin(previous_origin)
        for name in ("datahub.json", "mcp-runtime.json"):
            try:
                raw, _ = _read_bytes(data_root / ".control" / name)
            except FileNotFoundError:
                continue
            _decode(name, raw, origin)
        load_control(data_root, origin)
        load_mcp_control(data_root, origin)
        log.info("container_controls_prepared")
    except Exception as exc:
        log.warning("container_controls_prepare_failed")
        raise RuntimeError("control_origin_prepare_failed") from exc


def _prepare_private_leaf(path: Path, *, initialize_state: bool = False) -> None:
    """Create only fixed Docker bind children, then apply the unchanged strict guard.

    Desktop can change a bind root's displayed owner on its first write. Keep
    creation separate from runtime access: no auth/credential reads occur here.
    Only normal managed startup explicitly initializes the fixed state leaf.
    """
    if os.name != "posix" or path not in _DOCKER_PRIVATE_LEAVES:
        with runtime_state_directory(path, create=True):
            return
    initialize_state = initialize_state and path == _DOCKER_STATE_LEAF
    existing = None
    try:
        existing = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if not initialize_state:
            with runtime_state_directory(path):
                return
    with ExitStack() as stack:
        records = []
        parent = None
        for component in reversed(path.parents):
            name = str(component) if parent is None else component.name
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _validate_directory(before, leaf=False, platform_name=os.name)
            descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            stack.callback(os.close, descriptor)
            if _identity(os.fstat(descriptor)) != _identity(before):
                raise RuntimeStateError("runtime_state_unsafe")
            if component == path.parent and (
                stat.S_IMODE(before.st_mode) != 0o700
                or (before.st_uid, before.st_gid) not in {(0, 0), (os.getuid(), os.getgid())}
            ):
                raise RuntimeStateError("runtime_state_unsafe")
            records.append((component, descriptor, parent, name, before))
            parent = descriptor
        # mkdirat refuses an existing racing leaf; openat never follows aliases.
        if existing is None:
            os.mkdir(path.name, mode=0o700, dir_fd=parent)
        leaf = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        stack.callback(os.close, leaf)
        created = os.fstat(leaf)
        _validate_directory(created, leaf=True, platform_name=os.name)
        if stat.S_IMODE(created.st_mode) != 0o700:
            raise RuntimeStateError("runtime_state_unsafe")
        if existing is not None and _identity(created) != _identity(existing):
            raise RuntimeStateError("runtime_state_unsafe")
        if initialize_state and (created.st_uid, created.st_gid) != (os.getuid(), os.getgid()):
            raise RuntimeStateError("runtime_state_unsafe")

        def verify_parents(*, creation_mapping=False):
            updated = []
            for component, descriptor, ancestor, name, before in records:
                after = os.fstat(descriptor)
                named = os.stat(name, dir_fd=ancestor, follow_symlinks=False)
                _validate_directory(after, leaf=False, platform_name=os.name)
                expected = _identity(before)
                if (creation_mapping and (os.getuid(), os.getgid()) != (0, 0)
                        and component == path.parent
                        and (before.st_uid, before.st_gid) == (0, 0)
                        and (after.st_uid, after.st_gid) == (os.getuid(), os.getgid())):
                    expected = (*expected[:3], os.getuid(), os.getgid())
                if _identity(after) != expected or _identity(named) != expected:
                    raise RuntimeStateError("runtime_state_unsafe")
                updated.append((component, descriptor, ancestor, name, after))
            return updated

        def verify_leaf():
            if (_identity(path.lstat()) != _identity(created)
                    or _identity(os.fstat(leaf)) != _identity(created)
                    or _identity(os.stat(path.name, dir_fd=parent, follow_symlinks=False)) != _identity(created)):
                raise RuntimeStateError("runtime_state_unsafe")

        records = verify_parents(creation_mapping=existing is None)
        verify_leaf()
        if initialize_state:
            # Only the managed fixed-layout startup calls this writable phase.
            # It carries no auth or persistent marker; host ownership checks
            # remain necessary and are not established by these directory FDs.
            name = ".rwb-state-init-" + uuid4().hex
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                 | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=leaf)
            stack.callback(os.close, descriptor)
            temporary = os.fstat(descriptor)

            def verify_temporary():
                held = os.fstat(descriptor)
                named = os.stat(name, dir_fd=leaf, follow_symlinks=False)
                for value in (temporary, held, named):
                    if (not stat.S_ISREG(value.st_mode)
                            or stat.S_IMODE(value.st_mode) != 0o600
                            or (value.st_uid, value.st_gid) != (os.getuid(), os.getgid())
                            or value.st_nlink != 1 or value.st_size != 0
                            or _identity(value) != _identity(temporary)):
                        raise RuntimeStateError("runtime_state_unsafe")

            try:
                verify_temporary()
                records = verify_parents(creation_mapping=True)
                verify_leaf()
            except (OSError, RuntimeStateError):
                # Recover only our exact empty inode through the held leaf FD;
                # an unknown replacement is retained and never unlinked.
                try:
                    verify_temporary()
                    os.unlink(name, dir_fd=leaf)
                except (OSError, RuntimeStateError):
                    log.warning("container_state_initialization_cleanup_failed")
                raise
            verify_temporary()
            os.unlink(name, dir_fd=leaf)
            verify_parents()
            verify_leaf()
        # Re-pin with the original complete validator after the creation phase;
        # the fresh leaf must still be the object held by our retained fd.
        with runtime_state_directory(path):
            verify_leaf()
        verify_parents()
    log.info("container_private_leaf_prepared")


@dataclass(frozen=True, slots=True)
class SupervisorConfig:
    data_root: Path
    state_root: Path
    project_root: Path
    runtime_source: Path
    python: str
    node: str
    web_port: int = 8088
    runtime_port: int = 3081
    startup_timeout: float = 35.0
    shutdown_timeout: float = 8.0
    credential_root: Path | None = None


class HealthProbe(Protocol):
    def __call__(
        self, config: SupervisorConfig, role: str, timeout: float,
        *, launch_token: str | None = None,
    ) -> bool: ...


def real_probe(config, role, timeout, *, launch_token=None):
    with runtime_state_directory(config.state_root):
        health = ContainerHealth(
            timeout=timeout, launch_token=launch_token, data_root=config.data_root,
            runtime_state_root=config.state_root, runtime_source=config.runtime_source,
            project_root=config.project_root, runtime_port=config.runtime_port,
            web_port=config.web_port, python=config.python, node=config.node,
        )
        return health._runtime_healthy() if role == "runtime" else health._web_healthy()


class ChildOutput:
    """Drain nonblocking pipes without retaining unbounded lines or secret tokens."""

    def __init__(self, runtime_port):
        self.selector = selectors.DefaultSelector()
        self.buffers = {}
        self.discarding = set()
        self.token = None
        self.runtime_port = runtime_port
        self.secrets = [
            value for key, value in os.environ.items()
            if value and re.search(r"SECRET|PASSWORD|TOKEN|COOKIE|AUTH|API_KEY", key, re.I)
        ]

    def remember_secret(self, value):
        if isinstance(value, str) and value and value not in self.secrets:
            if len(self.secrets) >= 1024:
                raise RuntimeError("redaction_capacity_exceeded")
            self.secrets.append(value)

    def remember_auth(self, state_root):
        with runtime_state_directory(state_root):
            cookie = read_runtime_auth_record(state_root / "auth.json").get("cookie")
            self.remember_secret(cookie)
            if isinstance(cookie, str) and "=" in cookie:
                self.remember_secret(cookie.split("=", 1)[1])

    def register(self, child, role):
        os.set_blocking(child.stdout.fileno(), False)
        self.selector.register(child.stdout, selectors.EVENT_READ, role)
        self.buffers[role] = b""

    def _line(self, role, raw):
        line = raw.decode("utf-8", errors="replace")
        match = RUNTIME_TOKEN_PATTERN.search(line)
        if match and role == "runtime" and int(match[1]) == self.runtime_port:
            self.token = match[2]
            self.remember_secret(self.token)
            return
        # Learn explicit credential fields, then redact values wherever repeated.
        # Plain messages such as "cookie cache ready" do not contain a field.
        for field in re.finditer(
            r"(?:dsh-auth-[\w-]+|token|credential|password|api[_-]?key|cookie|RWB_SUPERVISOR_ROLE)"
            r"[\"']?\s*[=:]\s*"
            r"[\"']?([^\s;\"',}]+)", line, re.I,
        ):
            self.remember_secret(field[1])
        cookie_header = re.search(r"(?:set-cookie|cookie)[\"']?\s*:\s*(.+)", line, re.I)
        if cookie_header:
            self.remember_secret(cookie_header[1].strip().strip("\"'"))
            for item in cookie_header[1].split(";"):
                if "=" in item:
                    self.remember_secret(item.split("=", 1)[1].strip())
        for secret in sorted(self.secrets, key=len, reverse=True):
            line = line.replace(secret, "[redacted]")
        if line:
            log.info(json.dumps({
                "event": "container_child", "role": role, "state": "output",
                "code": "child_output", "output": line,
            }))

    def drain(self, wait=0):
        for key, _ in self.selector.select(wait):
            chunk = os.read(key.fileobj.fileno(), 4096)
            role = key.data
            if not chunk:
                self.selector.unregister(key.fileobj)
                key.fileobj.close()
                # Incomplete final lines are not forwarded: they may split a secret.
                self.buffers.pop(role, None)
                continue
            value = self.buffers[role] + chunk
            parts = value.split(b"\n")
            for line in parts[:-1]:
                if role in self.discarding:
                    self.discarding.remove(role)
                elif len(line) <= 4096:
                    self._line(role, line)
            tail = parts[-1]
            if len(tail) > 4096:
                self.discarding.add(role)
                tail = b""
            self.buffers[role] = tail

    def close(self):
        for key in list(self.selector.get_map().values()):
            key.fileobj.close()
        self.selector.close()
        self.token = None
        self.secrets.clear()


def _event(role, state, code):
    log.info(f"container_supervisor role={role} state={state} code={code}")


_FAILURE_STAGES = frozenset({
    "private_directories", "logging_setup", "config_validation", "ownership_init", "auth_reset", "process_specs",
    "runtime_spawn", "runtime_wait", "runtime_probe", "web_spawn", "web_wait", "web_probe", "running",
})
_FAILURE_CLASSES = frozenset({
    "RuntimeStateError", "PermissionError", "FileNotFoundError", "ProcessLookupError",
    "OSError", "ValueError", "RuntimeError", "TimeoutExpired", "SubprocessError",
})


def _failure_diagnostics(stage, error, children):
    """Return fixed startup facts without exception text, paths or process data."""
    name = type(error).__name__
    number = error.errno if isinstance(error, OSError) else None
    def returncode(role):
        value = getattr(children.get(role), "returncode", None)
        return value if type(value) is int and -255 <= value <= 255 else None
    return {
        "stage": stage if stage in _FAILURE_STAGES else "unknown",
        "exception_class": name if name in _FAILURE_CLASSES else "Other",
        "errno": number if type(number) is int and 0 <= number <= 4095 else None,
        "runtime_returncode": returncode("runtime"), "web_returncode": returncode("web"),
    }


def _emit_failure_diagnostics(value):
    log.error("container_startup_failure " + json.dumps(value, sort_keys=True))


class _ExternalShutdown(Exception):
    """Transfer control to cleanup without freezing the return status first."""


@dataclass(frozen=True, slots=True)
class _ProcessIdentity:
    parent: int
    group: int
    birth: str
    zombie: bool


def _read_role_environment(pid):
    """Read a bounded Linux proc environment solely for exact role selection."""
    if sys.platform != "linux":
        return b""
    with (Path("/proc") / str(pid) / "environ").open("rb") as stream:
        return stream.read(MAX_ROLE_ENVIRONMENT_BYTES + 1)


def _adopted_role(pid, identity):
    try:
        raw = _read_role_environment(pid)
        if len(raw) > MAX_ROLE_ENVIRONMENT_BYTES:
            return "unknown"
        prefix = ROLE_ENVIRONMENT_KEY.encode() + b"="
        markers = [item[len(prefix):] for item in raw.split(b"\0") if item.startswith(prefix)]
        current = _process_snapshot().get(pid)
        if current is None or current.birth != identity.birth:
            return "unknown"
        if len(markers) == 1 and markers[0] in {b"runtime", b"web"}:
            return markers[0].decode("ascii")
    except OSError:
        pass
    return "unknown"


def _process_snapshot():
    """Read ancestry and birth identity only; never inspect commands or env."""
    result = {}
    if sys.platform == "linux":
        for path in Path("/proc").iterdir():
            if not path.name.isdecimal():
                continue
            try:
                raw = (path / "stat").read_text()
            except (FileNotFoundError, ProcessLookupError):
                continue
            fields = raw.rsplit(")", 1)[1].split()
            result[int(path.name)] = _ProcessIdentity(
                int(fields[1]), int(fields[2]), fields[19], fields[0] == "Z"
            )
    elif sys.platform == "darwin":
        # This is a test/development fallback; the image uses Linux /proc.
        process = subprocess.run(
            ["/bin/ps", "-axo", "pid=,ppid=,pgid=,lstart=,stat="],
            capture_output=True, text=True, timeout=.5, check=True,
        )
        for line in process.stdout.splitlines():
            fields = line.split()
            if len(fields) != 9:
                raise RuntimeError("process_snapshot_invalid")
            result[int(fields[0])] = _ProcessIdentity(
                int(fields[1]), int(fields[2]), " ".join(fields[3:8]), "Z" in fields[8]
            )
    else:
        raise RuntimeError("supervisor_platform_unsupported")
    return result


class _OwnedProcesses:
    """Retain descendant ownership across setsid, reparenting and parent exit.

    Linux PID 1 receives orphans natively. Non-PID-1 Linux fixture runs use a
    process-local subreaper, restored on close. pidfds pin Linux signal targets;
    the macOS fallback rechecks birth identity before each per-PID signal.
    """

    def __init__(self):
        self.owned = {}  # pid -> (role, birth, optional pidfd)
        self.libc = None
        self.was_subreaper = None
        self.unknown_roles_seen = False
        self.adopts = os.getpid() == 1
        if sys.platform == "linux" and not self.adopts:
            import ctypes

            self.libc = ctypes.CDLL(None, use_errno=True)
            previous = ctypes.c_int()
            if self.libc.prctl(37, ctypes.byref(previous), 0, 0, 0) != 0:
                raise RuntimeError("subreaper_query_failed")
            if self.libc.prctl(36, 1, 0, 0, 0) != 0:
                raise RuntimeError("subreaper_enable_failed")
            self.was_subreaper = previous.value
            self.adopts = True
        try:
            self.baseline = {
                (pid, info.birth) for pid, info in _process_snapshot().items()
                if info.parent == os.getpid()
            }
        except Exception:
            self.close()
            raise

    def refresh(self, children):
        snapshot = _process_snapshot()
        for pid, (_, birth, descriptor) in list(self.owned.items()):
            if pid not in snapshot or snapshot[pid].birth != birth:
                if descriptor is not None:
                    os.close(descriptor)
                del self.owned[pid]
        roles = {pid: record[0] for pid, record in self.owned.items()}
        for role, child in children.items():
            if child.returncode is None and child.pid in snapshot:
                roles[child.pid] = role
        if self.adopts:
            for pid, info in snapshot.items():
                if info.parent == os.getpid() and (pid, info.birth) not in self.baseline:
                    if pid not in roles:
                        roles[pid] = _adopted_role(pid, info)
                        if roles[pid] == "unknown":
                            self.unknown_roles_seen = True
                            _event("unknown", "unclassified", "unknown_owned_role")
        # Resolve ancestry to closure even when children appear before parents.
        while True:
            additions = {pid: roles[info.parent] for pid, info in snapshot.items()
                         if pid not in roles and info.parent in roles}
            if not additions:
                break
            roles.update(additions)
        for pid, role in roles.items():
            if pid in self.owned or pid not in snapshot:
                continue
            info = snapshot[pid]
            descriptor = None
            if sys.platform == "linux":
                try:
                    descriptor = os.pidfd_open(pid)
                except ProcessLookupError:
                    continue
                # Pinning can race with PID reuse; do not adopt a new identity.
                current = _process_snapshot().get(pid)
                if current is None or current.birth != info.birth:
                    os.close(descriptor)
                    continue
            self.owned[pid] = (role, info.birth, descriptor)
        return {pid: info for pid, info in snapshot.items()
                if pid in self.owned}

    def send(self, pid, signum):
        _, birth, descriptor = self.owned[pid]
        try:
            if descriptor is not None:
                signal.pidfd_send_signal(descriptor, signum)
            else:
                current = _process_snapshot().get(pid)
                if current is not None and current.birth == birth:
                    os.kill(pid, signum)
        except ProcessLookupError:
            pass

    def close(self):
        for _, _, descriptor in self.owned.values():
            if descriptor is not None:
                os.close(descriptor)
        self.owned.clear()
        if self.was_subreaper is not None:
            if self.libc.prctl(36, self.was_subreaper, 0, 0, 0) != 0:
                raise RuntimeError("subreaper_restore_failed")


def _reap_children(children):
    """Reap adopted descendants as PID 1, preserving direct-child exit status."""
    owned = {child.pid: child for child in children.values()}
    reaped = set()
    for _ in range(64):
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            break
        if pid == 0:
            break
        if pid in owned:
            owned[pid].returncode = os.waitstatus_to_exitcode(status)
        reaped.add(pid)
    return reaped


def _stop(child, role, timeout, output, children, ownership):
    _event(role, "stopping", "signal_term")
    deadline = time.monotonic() + timeout
    signalled = set()
    escalated = False
    while True:
        _reap_children(children)
        live = ownership.refresh(children)
        targets = {pid for pid in live if ownership.owned[pid][0] == role}
        if not targets:
            break
        now = time.monotonic()
        if now >= deadline + 1:
            raise RuntimeError("owned_descendants_survived")
        for pid in targets:
            if live[pid].zombie:
                continue  # Keep waiting/reaping; a zombie is not a signal target.
            identity = (pid, ownership.owned[pid][1])
            if identity not in signalled:
                ownership.send(pid, signal.SIGTERM)
                signalled.add(identity)
            if now >= deadline:
                if not escalated:
                    _event(role, "stopping", "signal_kill")
                    escalated = True
                ownership.send(pid, signal.SIGKILL)
        output.drain(.025)
    if child is not None:
        child.wait(timeout=1)
    output.drain()
    _event(role, "stopped", "child_reaped")


def run(config: SupervisorConfig, *, probe: HealthProbe = real_probe) -> int:
    """Own both process groups until external shutdown or a nonzero failure."""
    children = {}
    output = ChildOutput(config.runtime_port)
    requested = False
    status = 1
    previous = {}
    ownership = None
    stage = "private_directories"

    def shutdown(signum, frame):
        nonlocal requested
        requested = True

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, shutdown)
        # Desktop bind roots can be presented as root-owned. Create and pin
        # private children as the container user before auth, probes or spawn;
        # never chmod/chown the mount roots or weaken the shared validator.
        for private_root in (config.state_root, config.credential_root):
            if private_root is not None:
                _prepare_private_leaf(private_root)
        _event("stack", "prepared", "private_directories_ready")
        _prepare_private_leaf(config.data_root / "logs")
        stage = "logging_setup"
        with runtime_state_directory(config.data_root / "logs") as log_root:
            settings.LOG_DIR = str(log_root)
            setup_logging()
        stage = "config_validation"
        if config.startup_timeout <= 0 or config.shutdown_timeout <= 0:
            raise ValueError("invalid timeout")
        if (config.data_root == Path("/data/research-web")
                and config.state_root == _DOCKER_STATE_LEAF
                and config.credential_root == Path("/run/rwb-secrets/private")
                and config.project_root == Path("/opt/rwb")
                and config.runtime_source == Path("/opt/dsh")):
            _prepare_private_leaf(config.state_root, initialize_state=True)
        stage = "control_preparation"
        prepare_controls(config.data_root, f"http://127.0.0.1:{config.web_port}")
        stage = "ownership_init"
        ownership = _OwnedProcesses()
        stage = "auth_reset"
        with runtime_state_directory(config.state_root):
            (config.state_root / "auth.json").unlink(missing_ok=True)
        stage = "process_specs"
        specs = build_process_specs(
            python=config.python, node=config.node, project_root=config.project_root,
            data_root=config.data_root, runtime_source=config.runtime_source,
            state_root=config.state_root, web_host="0.0.0.0", web_port=config.web_port,
            runtime_port=config.runtime_port,
        )
        environment = {
            **os.environ,
            "RESEARCH_DATA_HOME": str(config.data_root),
            "RESEARCH_RUNTIME_URL": f"http://127.0.0.1:{config.runtime_port}",
            "RESEARCH_RUNTIME_AUTH": str(config.state_root / "auth.json"),
            "RESEARCH_DSH_SOURCE": str(config.runtime_source),
            "RESEARCH_WEB_INTERNAL_URL": f"http://127.0.0.1:{config.web_port}",
            "PYTHONUNBUFFERED": "1",
        }
        environment.pop("RWB_DSH_STAGED", None)
        if config.credential_root is not None:
            environment["RESEARCH_CREDENTIAL_HOME"] = str(config.credential_root)
        for spec in (specs.runtime, specs.web):
            stage = "runtime_spawn" if spec.role == "runtime" else "web_spawn"
            if requested:
                raise _ExternalShutdown
            if any(child.poll() is not None for child in children.values()):
                raise RuntimeError("child exited")
            with runtime_state_directory(config.state_root):
                child_environment = {**environment, ROLE_ENVIRONMENT_KEY: spec.role}
                if spec.role == "runtime" and os.environ.get("RWB_DSH_STAGED") == "1":
                    child_environment["RWB_DSH_STAGED"] = "1"
                output.remember_secret(f"{ROLE_ENVIRONMENT_KEY}={spec.role}")
                child = subprocess.Popen(
                    spec.command, cwd=config.project_root, env=child_environment,
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, start_new_session=True, close_fds=True,
                )
                # Retain cleanup ownership even if the guard's exit recheck fails.
                children[spec.role] = child
                ownership.refresh(children)
            output.register(child, spec.role)
            _event(spec.role, "starting", "child_started")
            deadline = time.monotonic() + config.startup_timeout
            while True:
                stage = "runtime_wait" if spec.role == "runtime" else "web_wait"
                output.drain(.025)
                ownership.refresh(children)
                _reap_children(children)
                if requested:
                    raise _ExternalShutdown
                if any(item.poll() is not None for item in children.values()):
                    raise RuntimeError("child exited")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _event(spec.role, "failed", "startup_timeout")
                    raise RuntimeError("startup timeout")
                stage = "runtime_probe" if spec.role == "runtime" else "web_probe"
                if probe(config, spec.role, min(.25, remaining), launch_token=output.token):
                    if spec.role == "runtime" and probe is real_probe:
                        output.remember_auth(config.state_root)
                    _event(spec.role, "healthy", "health_ready")
                    break
        stage = "running"
        while not requested:
            output.drain(.05)
            ownership.refresh(children)
            _reap_children(children)
            if any(child.poll() is not None for child in children.values()):
                _event("stack", "failed", "unexpected_child_exit")
                raise RuntimeError("child exited")
        status = 0
    except _ExternalShutdown:
        status = 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _emit_failure_diagnostics(_failure_diagnostics(stage, error, children))
        _event("stack", "failed", "supervisor_failed")
    finally:
        for role in ("web", "runtime"):
            if role in children:
                try:
                    _stop(children[role], role, config.shutdown_timeout, output, children, ownership)
                except (OSError, RuntimeError, subprocess.SubprocessError):
                    _event(role, "failed", "cleanup_failed")
                    status = 1
        if ownership is not None:
            try:
                # Unproven adoptees never participate in Web/DSH role ordering.
                _stop(None, "unknown", config.shutdown_timeout, output, children, ownership)
                if ownership.unknown_roles_seen:
                    status = 1
            except (OSError, RuntimeError, subprocess.SubprocessError):
                _event("unknown", "failed", "cleanup_failed")
                status = 1
        try:
            with runtime_state_directory(config.state_root):
                (config.state_root / "auth.json").unlink(missing_ok=True)
        except (OSError, ValueError, RuntimeError):
            _event("stack", "failed", "auth_cleanup_failed")
            status = 1
        output.close()
        for child in children.values():
            if child.stdout is not None and not child.stdout.closed:
                child.stdout.close()
        _reap_children(children)
        if ownership is not None:
            try:
                if ownership.refresh(children):
                    _event("stack", "failed", "owned_descendants_survived")
                    status = 1
                ownership.close()
            except (OSError, RuntimeError, subprocess.SubprocessError):
                _event("stack", "failed", "ownership_cleanup_failed")
                status = 1
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        _event("stack", "stopped", "shutdown_complete" if status == 0 else "shutdown_failed")
    return status


def main(argv=()):
    data = Path(os.environ.get("RWB_DATA_ROOT", "/data/research-web"))
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--prepare-controls-only", action="store_true")
        parser.add_argument("--previous-origin")
        arguments = parser.parse_args(argv)
        if arguments.prepare_controls_only:
            if not arguments.previous_origin:
                raise ValueError("missing origin")
            prepare_controls(data, arguments.previous_origin)
            return 0
        if arguments.previous_origin is not None:
            raise ValueError("unexpected origin")
        return run(SupervisorConfig(
            data_root=data, state_root=Path(os.environ.get("RWB_RUNTIME_STATE", "/state/runtime")),
            credential_root=Path(os.environ.get("RESEARCH_CREDENTIAL_HOME", "/run/rwb-secrets/private")),
            project_root=Path("/opt/rwb"), runtime_source=Path("/opt/dsh"),
            python=sys.executable, node="/usr/local/bin/node",
        ))
    except (OSError, ValueError, RuntimeError):
        _event("stack", "failed", "supervisor_configuration_failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
