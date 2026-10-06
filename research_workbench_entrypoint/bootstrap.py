"""Stdlib routing before Click, with fail-closed sequential runtime switching.

Diagnostics use stderr logging. Read-only commands never create log directories;
Native lifecycle logging remains owned by the existing service manager.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from .docker_runtime import (
    MAX_OUTPUT, ControlError, DockerRuntime, minimal_environment, port_busy,
    result, run_bounded,
)
from .runtime_mode import RuntimeModeError, RuntimeModeStore
from .runtime_endpoints import EndpointError, EndpointStore
from .web_contract import classify_python_environment, listener_pids, probe_process

log = logging.getLogger(__name__)


def native_python(project_root: Path) -> Path:
    """Keep the existing checkout/worktree venv lookup without PATH fallback."""
    suffix = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    candidate = project_root / ".venv" / suffix
    if candidate.exists() or candidate.is_symlink() or (project_root / ".venv").exists():
        return candidate
    try:
        completed = run_bounded(
            ["git", "rev-parse", "--git-common-dir"], cwd=project_root,
            env=minimal_environment(), timeout=5, max_output=4096,
        )
        if completed.returncode == 0:
            common = Path(completed.stdout.strip())
            if not common.is_absolute():
                common = project_root / common
            shared = common.resolve().parent / ".venv" / suffix
            if shared.is_file():
                return shared
    except (OSError, ControlError):
        log.debug("native_environment_lookup_unavailable")
    return candidate


def native_environment(project_root: Path, *, minimal: bool = False) -> dict[str, str]:
    env = minimal_environment() if minimal else dict(os.environ)
    # Native launch must preserve the caller's environment and existing Node choice.
    if os.environ.get("RESEARCH_NODE_BINARY"):
        env["RESEARCH_NODE_BINARY"] = os.environ["RESEARCH_NODE_BINARY"]
    elif os.environ.get("HOME"):
        node = Path(os.environ["HOME"]) / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
        if os.access(node, os.X_OK):
            env["RESEARCH_NODE_BINARY"] = str(node)
    previous = env.get("PYTHONPATH")
    if not previous or previous.split(os.pathsep)[0] != str(project_root):
        env["PYTHONPATH"] = str(project_root) + (os.pathsep + previous if previous else "")
    if minimal:
        # The ownership bridge must not load .env or let legacy settings create
        # directories at import time. These existing paths are never log targets:
        # the bridge uses only stderr and never configures legacy file logging.
        env["RESEARCH_RUN_MODE"] = "web-prod"
        for key in ("LOG_DIR", "OBJECT_STORAGE_PATH", "PDF_MARKDOWN_DIR", "PDF_RAW_TEXT_DIR"):
            env[key] = str(project_root)
    return env


def _native_probe(operation: str, project_root: Path, home: Path, ports: tuple[int, int]) -> dict:
    """Called only inside the exact Native venv; status never calls mutating status()."""
    from app.research_web.service_manager import ServiceManagerError, WebServiceManager

    manager = WebServiceManager(
        project_root=project_root, data_root=home / "research-web",
        web_port=ports[0], runtime_port=ports[1],
    )
    if operation == "preflight":
        diagnosis = manager._installation_diagnosis()
        return result(*diagnosis["issues"], mode="native")

    def states() -> dict:
        services = {}
        for probe in manager._service_probes():
            # Switch preflight is read-only: never normalize invalid/stale files.
            if probe.state == "invalid":
                raise ControlError("runtime_ownership_unknown")
            try:
                if probe.state == "missing" and probe.process == "missing":
                    process = next(item for item in manager._processes() if item.role == probe.role)
                    if not manager._absent_listener_safe(process):
                        raise ControlError("runtime_ownership_unknown")
                else:
                    manager._probe_action(probe)
            except ServiceManagerError as exc:
                raise ControlError("runtime_ownership_unknown") from exc
            services[probe.role] = probe.public()
        if set(services) != {"web", "runtime"}:
            raise ControlError("runtime_ownership_unknown")
        return services

    services = states()  # Validate both roles before any stop operation.
    if operation == "stop":
        # The Native manager owns locking and final identity revalidation.
        manager.stop()
        services = states()
    return result(mode="native", services=services)


def native_probe_main() -> None:
    """Fixed subprocess entry, returning no exception text or process arguments."""
    try:
        operation, root, home, web, runtime = sys.argv[1:]
        if operation not in ("status", "stop", "preflight"):
            raise ControlError("native_probe_failed")
        with contextlib.redirect_stdout(sys.stderr):
            value = _native_probe(operation, Path(root), Path(home), (int(web), int(runtime)))
    except Exception:
        log.warning("native_probe code=runtime_ownership_unknown")
        value = result("runtime_ownership_unknown", mode="native")
    print(json.dumps(value))


class NativeRuntime:
    """Bounded bridge to existing Native ownership and stop behavior."""

    def __init__(self, project_root: Path, home: Path, *, runner=run_bounded,
                 ports: tuple[int, int] | None = None):
        self.project_root = project_root
        self.home = home
        self.runner = runner
        from .web_bootstrap import native_endpoint_ports
        self.ports = native_endpoint_ports(Path(project_root), home / "research-web") if ports is None else ports

    def _missing_ledger_listeners_safe(self, data_root: Path) -> bool:
        """Read-only stdlib ownership proof when the Native environment is absent."""
        for port in self.ports:
            listener = listener_pids(port)
            if listener.state == "closed":
                if port_busy(port):
                    return False
                continue
            if listener.state != "listening" or not listener.pids:
                return False
            for pid in listener.pids:
                observed = probe_process(pid)
                if (observed.state != "alive" or observed.issue or not observed.argv
                        or observed.started_at is None
                        or any(str(data_root) in argument or str(self.project_root) in argument
                               for argument in observed.argv)):
                    return False
                checked = probe_process(pid)
                if (checked.state != "alive" or checked.issue or checked.argv != observed.argv
                        or checked.started_at != observed.started_at):
                    return False
            if listener_pids(port) != listener:
                return False
        return True

    def _probe(self, operation: str) -> dict:
        python = native_python(self.project_root)
        environment_issue = (
            classify_python_environment(python.parent.parent.parent).issue
            if python.is_file() else "python_environment_missing"
        )
        if environment_issue is not None:
            if operation == "status" and not any(
                (self.home / "run" / (role + ".json")).exists()
                or (self.home / "run" / (role + ".json")).is_symlink()
                for role in ("web", "runtime")
            ):
                data_root = self.home / "research-web"
                if (data_root.is_symlink() or (data_root.exists() and
                        (not data_root.is_dir() or not self._missing_ledger_listeners_safe(data_root)))):
                    log.warning("native_probe code=runtime_ownership_unknown")
                    return result("runtime_ownership_unknown", mode="native")
                return result(mode="native", services={
                    role: {"running": False, "port": port}
                    for role, port in zip(("web", "runtime"), self.ports)
                })
            return result(
                ("native_environment_missing" if environment_issue == "python_environment_missing"
                 else "native_environment_unusable") if operation == "preflight"
                else "runtime_ownership_unknown", mode="native",
            )
        try:
            completed = self.runner(
                [str(python), "-c", "from research_workbench_entrypoint.bootstrap import native_probe_main; native_probe_main()",
                 operation, str(self.project_root), str(self.home), *map(str, self.ports)],
                cwd=self.project_root, env=native_environment(self.project_root, minimal=True),
                timeout=90 if operation == "preflight" else 40, max_output=MAX_OUTPUT,
            )
            value = json.loads(completed.stdout)
            if completed.returncode or not isinstance(value, dict) or type(value.get("ok")) is not bool:
                raise ControlError("native_probe_failed")
            return value
        except (OSError, ValueError, ControlError, subprocess.SubprocessError):
            log.warning("native_probe code=native_probe_failed")
            return result("native_probe_failed", mode="native")

    def preflight(self) -> dict:
        return self._probe("preflight")

    def status(self) -> dict:
        return self._probe("status")

    def stop(self) -> dict:
        return self._probe("stop")


def _running(report: dict) -> bool:
    try:
        values = [report["services"][role]["running"] for role in ("web", "runtime")]
        if any(type(value) is not bool for value in values):
            raise ValueError
        return any(values)
    except (KeyError, TypeError, ValueError):
        raise ControlError("runtime_ownership_unknown") from None


def switch_runtime(store, target, docker, native, *, stop_current=False, wait_timeout=10) -> dict:
    """Preflight, verify both owners, explicitly stop current, then atomically select."""
    from app.research_web.lifecycle_lock import LifecycleLock, LifecycleLockError
    try:
        if target not in ("native", "docker"):
            raise ControlError("runtime_target_invalid")
        before = store.read()
        if before.mode == target:
            return result(mode=target, changed=False)
        controllers = {"native": native, "docker": docker}
        checked = controllers[target].preflight()
        if not checked["ok"]:
            return checked
        reports = {name: controller.status() for name, controller in controllers.items()}
        if any(not report.get("ok") for report in reports.values()):
            raise ControlError("runtime_ownership_unknown" if stop_current else "runtime_stop_current_required")
        running = {name: _running(report) for name, report in reports.items()}
        if any(running.values()) and not stop_current:
            raise ControlError("runtime_stop_current_required")
        if running[target]:
            raise ControlError("runtime_other_running")
        if running[before.mode]:
            stopped = controllers[before.mode].stop()
            if not stopped.get("ok"):
                return stopped
        # Public stop owns its lock; never hold one across the Native subprocess.
        # Reacquire the shared lock before final state checks and metadata CAS.
        with LifecycleLock(store.home / "run/lifecycle.lock", DockerRuntime._pid_exists,
                           trusted_root=store.home):
            if store.read() != before:
                raise ControlError("runtime_mode_changed")
            for controller in controllers.values():
                report = controller.status()
                if not report.get("ok") or _running(report):
                    raise ControlError("runtime_stop_failed")
            record = store.write(target, expected=before)
        log.info("runtime_switch mode=%s code=ok", target)
        return result(mode=record.mode, installation_id=record.installation_id, changed=True)
    except (RuntimeModeError, ControlError, EndpointError, LifecycleLockError) as error:
        log.warning("runtime_switch code=%s", error.code)
        return result(error.code)


def _emit(value: dict) -> int:
    print(json.dumps(value, sort_keys=True))
    return 0 if value["ok"] else 1


def _command_arguments(argv: list[str]) -> list[str]:
    """Locate the command after only the two existing Click root options.

    The original list is retained for Native exec. Docker diagnostics continue
    using their stderr-only logging contract, independent of legacy file logging.
    Unknown options are left to the existing CLI rather than guessed/skipped.
    """
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--":
            return argv[index + 1:]
        option, equals, value = token.partition("=")
        if option not in ("--log-level", "--log-file"):
            break
        if not equals:
            index += 1
            if index >= len(argv) or argv[index].startswith("-"):
                raise ControlError("runtime_root_option_invalid")
            value = argv[index]
        if not value or "\0" in value:
            raise ControlError("runtime_root_option_invalid")
        if option == "--log-level" and not isinstance(getattr(logging, value.upper(), None), int):
            raise ControlError("runtime_root_option_invalid")
        index += 1
    return argv[index:]


def dispatch(argv: list[str], project_root: Path) -> int | None:
    """Return None only when already executing the selected Native entrypoint."""
    home = Path.home() / ".research-workbench"
    store = RuntimeModeStore(home)
    try:
        command_argv = _command_arguments(argv)
        record = store.read() if command_argv[:1] in (["runtime"], ["web"]) else None
        if command_argv[:1] == ["runtime"]:
            assert record is not None
            parser = argparse.ArgumentParser(prog="rwb runtime")
            sub = parser.add_subparsers(dest="command", required=True)
            sub.add_parser("status").add_argument("--json", action="store_true")
            use = sub.add_parser("use")
            use.add_argument("target", choices=("native", "docker"))
            use.add_argument("--stop-current", action="store_true")
            use.add_argument("--json", action="store_true")
            args = parser.parse_args(command_argv[1:])
            if args.command == "status":
                return _emit(result(mode=record.mode, installation_id=record.installation_id or None))
            return _emit(switch_runtime(store, args.target, DockerRuntime(project_root, home),
                                       NativeRuntime(project_root, home), stop_current=args.stop_current))
        if command_argv[:1] == ["web"] and record is not None and record.mode == "docker":
            parser = argparse.ArgumentParser(prog="rwb web")
            sub = parser.add_subparsers(dest="command", required=True)
            for command in ("install", "start", "stop", "restart", "status", "doctor", "logs"):
                child = sub.add_parser(command)
                if command != "logs":
                    child.add_argument("--json", action="store_true")
                if command in ("start", "restart"):
                    child.add_argument("--no-open", action="store_true")
                    child.add_argument("--web-port", type=int)
                    child.add_argument("--runtime-port", type=int)
                if command == "restart":
                    child.add_argument("--force", action="store_true")
                if command == "logs":
                    child.add_argument("--follow", action="store_true")
                    child.add_argument("--tail", type=int, default=100)
            args = parser.parse_args(command_argv[1:])
            controller = DockerRuntime(project_root, home)
            if args.command in ("start", "restart"):
                if args.runtime_port is not None:
                    raise ControlError("docker_runtime_port_unsupported")
                if args.web_port is not None:
                    if not 1 <= args.web_port <= 65535:
                        raise ControlError("endpoint_invalid_port")
                    controller.requested_web_port = args.web_port
            if args.command == "logs":
                return controller.logs(args.follow, args.tail)
            options = {}
            if args.command in ("start", "restart"):
                options["open_browser"] = not args.no_open
            if args.command == "restart":
                options["force"] = args.force
            return _emit(getattr(controller, args.command)(**options))
        python = native_python(project_root)
        environment_issue = classify_python_environment(python.parent.parent.parent).issue
        if environment_issue is None:
            try:
                checked = run_bounded(
                    [str(python), "-c", "import click; import app.cli.main"],
                    cwd=project_root, env=native_environment(project_root, minimal=True),
                    timeout=10, max_output=4096,
                )
                if checked.returncode:
                    environment_issue = "python_environment_unusable"
            except (OSError, ControlError, subprocess.SubprocessError):
                environment_issue = "python_environment_unusable"
        if environment_issue is not None:
            from .web_bootstrap import run

            log.warning("native_environment code=%s", environment_issue)
            os.environ["RWB_BOOTSTRAP_PYTHON_ISSUE"] = environment_issue
            return run(command_argv, project_root)
        if Path(sys.executable).absolute() == python.absolute():
            os.environ.update(native_environment(project_root))
            return None
        log.debug("runtime_delegate mode=native")
        os.chdir(project_root)
        os.execve(str(python), [str(python), "-m", "research_workbench_entrypoint", *argv],
                  native_environment(project_root))
    except (RuntimeModeError, ControlError, EndpointError) as error:
        return _emit(result(error.code))
    except OSError:
        log.warning("runtime_bootstrap code=runtime_io")
        return _emit(result("runtime_io"))


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    from . import main as entrypoint
    entrypoint()


if __name__ == "__main__":
    main()
