"""Foreground container PID 1: DSH-first startup and bounded group shutdown."""

from __future__ import annotations

import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research_web.process_spec import build_process_specs
from app.research_web.runtime_state import runtime_state_directory
from app.research_web.service_manager import RUNTIME_TOKEN_PATTERN
from core.observability import get_logger, setup_logging
from core.settings import settings
from docker.healthcheck import ContainerHealth

log = get_logger(__name__)


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

    def register(self, child, role):
        os.set_blocking(child.stdout.fileno(), False)
        self.selector.register(child.stdout, selectors.EVENT_READ, role)
        self.buffers[role] = b""

    def _line(self, role, raw):
        line = raw.decode("utf-8", errors="replace")
        match = RUNTIME_TOKEN_PATTERN.search(line)
        if match and role == "runtime" and int(match[1]) == self.runtime_port:
            self.token = match[2]
        if re.search(r"token=|cookie|dsh-auth-", line, re.I):
            return
        for secret in self.secrets:
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


def _event(role, state, code):
    log.info(f"container_supervisor role={role} state={state} code={code}")


class _ExternalShutdown(Exception):
    """Transfer control to cleanup without freezing the return status first."""


def _group_exists(child):
    child.poll()
    try:
        os.killpg(child.pid, 0)
        return True
    except ProcessLookupError:
        return False


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


def _stop(child, role, timeout, output, children):
    _reap_children(children)
    if not _group_exists(child):
        return
    _event(role, "stopping", "signal_term")
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + timeout
    while _group_exists(child) and time.monotonic() < deadline:
        output.drain(min(.025, max(0, deadline - time.monotonic())))
        _reap_children(children)
    if _group_exists(child):
        _event(role, "stopping", "signal_kill")
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
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

    def shutdown(signum, frame):
        nonlocal requested
        requested = True

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, shutdown)
        with runtime_state_directory(config.data_root / "logs", create=True) as log_root:
            settings.LOG_DIR = str(log_root)
            setup_logging()
        if config.startup_timeout <= 0 or config.shutdown_timeout <= 0:
            raise ValueError("invalid timeout")
        with runtime_state_directory(config.state_root):
            (config.state_root / "auth.json").unlink(missing_ok=True)
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
        for spec in (specs.runtime, specs.web):
            if requested:
                raise _ExternalShutdown
            if any(child.poll() is not None for child in children.values()):
                raise RuntimeError("child exited")
            with runtime_state_directory(config.state_root):
                child = subprocess.Popen(
                    spec.command, cwd=config.project_root, env=environment,
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, start_new_session=True, close_fds=True,
                )
                # Retain cleanup ownership even if the guard's exit recheck fails.
                children[spec.role] = child
            output.register(child, spec.role)
            _event(spec.role, "starting", "child_started")
            deadline = time.monotonic() + config.startup_timeout
            while True:
                output.drain(.025)
                _reap_children(children)
                if requested:
                    raise _ExternalShutdown
                if any(item.poll() is not None for item in children.values()):
                    raise RuntimeError("child exited")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _event(spec.role, "failed", "startup_timeout")
                    raise RuntimeError("startup timeout")
                if probe(config, spec.role, min(.25, remaining), launch_token=output.token):
                    _event(spec.role, "healthy", "health_ready")
                    break
        while not requested:
            output.drain(.05)
            _reap_children(children)
            if any(child.poll() is not None for child in children.values()):
                _event("stack", "failed", "unexpected_child_exit")
                raise RuntimeError("child exited")
        status = 0
    except _ExternalShutdown:
        status = 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        _event("stack", "failed", "supervisor_failed")
    finally:
        for role in ("web", "runtime"):
            if role in children:
                try:
                    _stop(children[role], role, config.shutdown_timeout, output, children)
                except (OSError, subprocess.SubprocessError):
                    _event(role, "failed", "cleanup_failed")
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
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        _event("stack", "stopped", "shutdown_complete" if status == 0 else "shutdown_failed")
    return status


def main():
    data = Path(os.environ.get("RWB_DATA_ROOT", "/data/research-web"))
    try:
        return run(SupervisorConfig(
            data_root=data, state_root=Path(os.environ.get("RWB_RUNTIME_STATE", "/state")),
            project_root=Path("/opt/rwb"), runtime_source=Path("/opt/dsh"),
            python=sys.executable, node="/usr/local/bin/node",
        ))
    except (OSError, ValueError, RuntimeError):
        _event("stack", "failed", "supervisor_configuration_failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
