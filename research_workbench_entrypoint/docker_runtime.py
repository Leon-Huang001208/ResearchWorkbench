"""Stdlib host controller; all diagnostic output is allowlisted and bounded.

The bootstrap configures stderr logging. No Docker stderr, environment values,
or unrestricted inspect output is ever included in a diagnostic report.
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import stat
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from .runtime_mode import RuntimeModeError, RuntimeModeStore

log = logging.getLogger(__name__)
MAX_OUTPUT = 65536
IMAGE = "research-workbench:local"
_ID = re.compile(r"[a-f0-9]{64}")
_IMAGE_ID = re.compile(r"sha256:[a-f0-9]{64}")
_IMAGE_FORMAT = (
    '{"id":{{json .Id}},"runtime":'
    '{{json (index .Config.Labels "io.research-workbench.runtime")}}}'
)
_CONTAINER_FORMAT = (
    '{"id":{{json .Id}},"image":{{json .Image}},'
    '"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
    '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
    '"installation":{{json (index .Config.Labels "io.research-workbench.installation")}},'
    '"runtime":{{json (index .Config.Labels "io.research-workbench.runtime")}},'
    '"working_dir":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},'
    '"running":{{json .State.Running}},"state":{{json .State.Status}},'
    '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}"none"{{end}},'
    '"mounts":[{{range $i,$m := .Mounts}}{{if $i}},{{end}}'
    '{"Source":{{json $m.Source}},"Destination":{{json $m.Destination}},'
    '"Type":{{json $m.Type}}}{{end}}]}'
)


class ControlError(RuntimeError):
    """Path-free issue code suitable for CLI output."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def result(*issues: str, **facts: Any) -> dict[str, Any]:
    return {"schema_version": 1, "ok": not issues, "issues": list(issues), **facts}


def run_bounded(
    argv: list[str], *, cwd: Path, env: dict[str, str], timeout: float,
    max_output: int = MAX_OUTPUT, stream: bool = False,
) -> subprocess.CompletedProcess:
    """Drain both pipes with hard caps; kill and reap on timeout/overflow.

    Follow is still bounded by timeout and byte count. It cannot silently grow
    memory or fill a temporary file when an untrusted daemon prints endlessly.
    """
    process = subprocess.Popen(
        argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
    )
    buffers = [bytearray(), bytearray()]
    overflow = threading.Event()

    def drain(index: int) -> None:
        pipe = process.stdout if index == 0 else process.stderr
        assert pipe is not None
        try:
            while chunk := pipe.read1(4096):
                available = max_output - len(buffers[index])
                buffers[index].extend(chunk[:max(0, available)])
                if len(chunk) > available:
                    overflow.set()
                    process.kill()
                    return
                if stream:
                    destination = sys.stdout if index == 0 else sys.stderr
                    destination.write(chunk.decode("utf-8", "replace"))
                    destination.flush()
        except (OSError, ValueError):
            overflow.set()
        finally:
            pipe.close()

    threads = [threading.Thread(target=drain, args=(index,), daemon=True) for index in (0, 1)]
    for thread in threads:
        thread.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise ControlError("runtime_command_timeout") from None
    finally:
        for thread in threads:
            thread.join(timeout=1)
    if any(thread.is_alive() for thread in threads):
        raise ControlError("runtime_command_timeout")
    if overflow.is_set():
        raise ControlError("runtime_output_limit")
    return subprocess.CompletedProcess(
        argv, process.returncode, *(bytes(value).decode("utf-8", "replace") for value in buffers)
    )


def minimal_environment() -> dict[str, str]:
    # Docker CLI discovers Desktop context under HOME. Do not inherit Docker
    # endpoint/TLS/Compose overrides or arbitrary credential-valued variables.
    keys = ("PATH", "HOME", "USERPROFILE", "SystemRoot", "WINDIR", "PATHEXT")
    return {**{key: os.environ[key] for key in keys if key in os.environ}, "LC_ALL": "C"}


def port_busy(port: int) -> bool:
    # Bind also detects non-listening reservations; connect-only checks miss them.
    for family, address in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.bind((address, port))
        except OSError as error:
            import errno
            if error.errno in (errno.EAFNOSUPPORT, errno.EADDRNOTAVAIL):
                continue
            return True
    return False


class DockerRuntime:
    """Only an installation's exact owned containers may be stopped or logged."""

    def __init__(self, project_root: Path, home: Path, *, runner=run_bounded,
                 ports: tuple[int, int] = (8088, 3081)):
        self.project_root = Path(project_root).resolve()
        self.home = Path(home).absolute()
        self.runner = runner
        self.ports = ports
        self.store = RuntimeModeStore(self.home)

    @property
    def installation_id(self) -> str:
        return self.store.read().installation_id

    @property
    def project_name(self) -> str:
        identity = self.installation_id
        if not identity:
            raise ControlError("docker_installation_missing")
        return "rwb-" + identity[:12]

    @property
    def compose_prefix(self) -> tuple[str, ...]:
        return ("docker", "compose", "--project-name", self.project_name,
                "--project-directory", str(self.project_root), "-f",
                str(self.project_root / "compose.yaml"))

    @property
    def data_dir(self) -> Path:
        return self.home / "research-web"

    @property
    def state_dir(self) -> Path:
        return self.home / "run" / "docker" / self.installation_id

    @property
    def credential_dir(self) -> Path:
        return self.home / "secrets" / "docker" / self.installation_id

    def _environment(self) -> dict[str, str]:
        return {
            **minimal_environment(), "RWB_DATA_DIR": str(self.data_dir),
            "RWB_STATE_DIR": str(self.state_dir),
            "RWB_CREDENTIAL_DIR": str(self.credential_dir),
            "RWB_INSTALLATION_ID": self.installation_id,
            "RWB_WEB_PORT": str(self.ports[0]),
            "RWB_IMAGE": IMAGE,
            # Explicitly disable implicit .env interpolation even for a trusted
            # project directory; no secrets are imported by the Compose process.
            "COMPOSE_DISABLE_ENV_FILE": "1",
        }

    def _call(self, argv, code, *, timeout=20, stream=False, check=True):
        try:
            completed = self.runner(
                list(argv), cwd=self.project_root, env=self._environment(),
                timeout=timeout, max_output=MAX_OUTPUT, stream=stream,
            )
        except FileNotFoundError:
            raise ControlError("docker_cli_missing") from None
        except (OSError, subprocess.SubprocessError):
            raise ControlError(code) from None
        if len(completed.stdout.encode()) > MAX_OUTPUT or len(completed.stderr.encode()) > MAX_OUTPUT:
            raise ControlError("runtime_output_limit")
        if check and completed.returncode:
            raise ControlError(code)
        return completed

    def _json(self, argv, code):
        try:
            return json.loads(self._call(argv, code).stdout)
        except (ValueError, TypeError):
            raise ControlError(code) from None

    def _safe_home(self) -> None:
        # Existing components must not alias another installation or allow
        # another user to replace state. Missing components stay missing on reads.
        self.store.read()
        for path in (self.home, self.data_dir, self.state_dir, self.credential_dir):
            for component in (*reversed(path.parents), path):
                try:
                    identity = component.lstat()
                except FileNotFoundError:
                    break
                if not stat.S_ISDIR(identity.st_mode) or getattr(identity, "st_file_attributes", 0) & 0x400:
                    raise ControlError("docker_data_home_unsafe")
                if os.name == "posix":
                    sticky = identity.st_uid == 0 and identity.st_mode & stat.S_ISVTX
                    if identity.st_uid not in (0, os.getuid()) or (identity.st_mode & 0o022 and not sticky):
                        raise ControlError("docker_data_home_unsafe")
                    if component == path and (identity.st_uid != os.getuid() or identity.st_mode & 0o077):
                        raise ControlError("docker_data_home_unsafe")

    def _availability(self) -> None:
        self._safe_home()
        self._call(["docker", "--version"], "docker_cli_missing")
        architecture = self._json(["docker", "info", "--format", "{{json .Architecture}}"], "docker_daemon_unavailable")
        if architecture not in ("x86_64", "amd64", "aarch64", "arm64"):
            raise ControlError("docker_architecture_unsupported")
        self._call(["docker", "compose", "version", "--short"], "docker_compose_missing")

    def _image(self, reference=IMAGE) -> dict:
        value = self._json(["docker", "image", "inspect", "--format", _IMAGE_FORMAT, reference], "docker_build_not_ready")
        if not isinstance(value, dict) or not _IMAGE_ID.fullmatch(str(value.get("id", ""))):
            raise ControlError("docker_build_not_ready")
        if value.get("runtime") != "docker":
            raise ControlError("docker_ownership_mismatch")
        return value

    def _containers(self) -> list[dict]:
        if not self.installation_id:
            return []
        ids: set[str] = set()
        for label in ("com.docker.compose.project=" + self.project_name,
                      "io.research-workbench.installation=" + self.installation_id):
            raw = self._call(["docker", "ps", "--all", "--no-trunc", "--filter", "label=" + label, "--format", "{{.ID}}"], "docker_status_failed").stdout
            for identity in raw.splitlines():
                if not _ID.fullmatch(identity):
                    raise ControlError("docker_ownership_mismatch")
                ids.add(identity)
        if len(ids) > 1:
            raise ControlError("docker_ownership_mismatch")
        return [self._inspect(identity) for identity in sorted(ids)]

    def _inspect(self, identity: str) -> dict:
        value = self._json(["docker", "container", "inspect", "--format", _CONTAINER_FORMAT, identity], "docker_ownership_mismatch")
        expected = {
            "id": identity, "project": self.project_name, "service": "research-web",
            "installation": self.installation_id, "runtime": "docker",
            "working_dir": str(self.project_root),
        }
        if not isinstance(value, dict) or any(value.get(key) != item for key, item in expected.items()):
            raise ControlError("docker_ownership_mismatch")
        if type(value.get("running")) is not bool or value.get("state") not in ("created", "running", "paused", "restarting", "removing", "exited", "dead") or value.get("health") not in ("none", "starting", "healthy", "unhealthy"):
            raise ControlError("docker_ownership_mismatch")
        mounts = value.get("mounts")
        expected_mounts = {
            "/data/research-web": str(self.data_dir), "/state": str(self.state_dir),
            "/run/rwb-secrets": str(self.credential_dir),
        }
        if not isinstance(mounts, list) or any(
            not isinstance(item, dict)
            or any(not isinstance(item.get(key), str) for key in ("Source", "Destination", "Type"))
            for item in mounts
        ):
            raise ControlError("docker_ownership_mismatch")
        binds = [item for item in mounts if item.get("Type") == "bind"]
        ephemeral = [item for item in mounts if item.get("Type") != "bind"]
        actual = {item.get("Destination"): item.get("Source") for item in binds}
        if len(binds) != len(expected_mounts) or actual != expected_mounts:
            raise ControlError("docker_ownership_mismatch")
        if any(item.get("Type") != "tmpfs" or item.get("Destination") not in ("/tmp", "/home/rwb")
               for item in ephemeral) or len({item.get("Destination") for item in ephemeral}) != len(ephemeral):
            raise ControlError("docker_ownership_mismatch")
        image = value.get("image")
        if not isinstance(image, str) or not _IMAGE_ID.fullmatch(image) or self._image(image)["id"] != image:
            raise ControlError("docker_ownership_mismatch")
        return value

    def _guard(self, operation, function):
        try:
            value = function()
            log.info("docker_runtime operation=%s code=ok", operation)
            return value
        except (ControlError, RuntimeModeError) as error:
            code = error.code if isinstance(error, ControlError) else "docker_data_home_unsafe"
            log.warning("docker_runtime operation=%s code=%s", operation, code)
            return result(code, mode="docker")
        except OSError:
            log.warning("docker_runtime operation=%s code=docker_io", operation)
            return result("docker_io", mode="docker")

    def preflight(self, *, require_image=True) -> dict:
        def check():
            self._availability()
            image = self._image() if require_image else None
            self._containers()
            return result(mode="docker", image_id=image["id"] if image else None)
        return self._guard("preflight", check)

    def _status(self, containers) -> dict:
        running = bool(containers and containers[0]["running"])
        healthy = bool(running and containers[0]["health"] == "healthy")
        return result(mode="docker", ownership="verified" if containers else "absent",
            url=f"http://127.0.0.1:{self.ports[0]}/#/fingpt",
            container_state=containers[0]["state"] if containers else "absent",
            services={role: {"running": running, "healthy": healthy, "pid": None, "port": port}
                      for role, port in (("web", self.ports[0]), ("runtime", self.ports[1]))})

    def status(self) -> dict:
        def inspect():
            self._availability()
            return self._status(self._containers())
        return self._guard("status", inspect)

    def doctor(self) -> dict:
        checked = self.preflight()
        if not checked["ok"]:
            return checked
        status = self.status()
        return {**status, "image_id": checked["image_id"]}

    def _ports_free(self):
        for port, code in zip(self.ports, ("docker_port_8088_occupied", "docker_port_3081_conflict")):
            if port_busy(port):
                raise ControlError(code)

    def install(self) -> dict:
        def build():
            self._availability()
            self._containers()
            if not self.installation_id:
                self.store.write(self.store.read().mode)
            self._safe_home()
            self._call([*self.compose_prefix, "build", "research-web"], "docker_build_failed", timeout=1800)
            return result(mode="docker", image_id=self._image()["id"])
        return self._guard("install", build)

    def start(self, *, open_browser=True) -> dict:
        def start_owned():
            self._availability()
            self._image()
            containers = self._containers()
            if containers and containers[0]["running"]:
                return self._status(containers)
            self._ports_free()
            from .bootstrap import NativeRuntime, _running
            native = NativeRuntime(self.project_root, self.home, ports=self.ports).status()
            if not native.get("ok"):
                raise ControlError("runtime_ownership_unknown")
            if _running(native):
                raise ControlError("runtime_other_running")
            if not self.installation_id:
                raise ControlError("docker_installation_missing")
            for path in (self.data_dir, self.state_dir, self.credential_dir):
                # Mount setup is explicit; readonly queries never create paths.
                from app.research_web.runtime_state import RuntimeStateError, runtime_state_directory
                try:
                    with runtime_state_directory(path, create=True):
                        pass
                except RuntimeStateError:
                    raise ControlError("docker_data_home_unsafe") from None
            self._safe_home()
            self._containers()
            self._call([*self.compose_prefix, "up", "--detach", "--no-build", "--pull", "never", "research-web"], "docker_start_failed", timeout=60)
            report = self._status(self._containers())
            if not report["services"]["web"]["running"]:
                raise ControlError("docker_start_failed")
            return report
        report = self._guard("start", start_owned)
        if report["ok"] and open_browser:
            try:
                if not webbrowser.open(report["url"]):
                    log.warning("docker_runtime code=browser_unavailable")
            except (OSError, webbrowser.Error):
                log.warning("docker_runtime code=browser_unavailable")
        return report

    def stop(self, *, wait_timeout=10) -> dict:
        def stop_owned():
            self._availability()
            containers = self._containers()
            for container in containers:
                if container["running"]:
                    self._inspect(container["id"])
                    self._call(["docker", "stop", "--time", "35", container["id"]], "docker_stop_failed", timeout=45)
            deadline = time.monotonic() + wait_timeout
            while any(port_busy(port) for port in self.ports):
                if time.monotonic() >= deadline:
                    raise ControlError("runtime_ports_not_released")
                time.sleep(0.05)
            remaining = self._containers()
            if any(container["running"] for container in remaining):
                raise ControlError("docker_stop_failed")
            return self._status(remaining)
        return self._guard("stop", stop_owned)

    def restart(self, *, force=False, open_browser=True) -> dict:
        checked = self.preflight()
        if not checked["ok"]:
            return checked
        # Container health is insufficient evidence that research is idle.
        # Without an authenticated session probe, require explicit interruption.
        current = self.status()
        if not current["ok"]:
            return current
        if current["services"]["web"]["running"] and not force:
            return result("runtime_force_required", mode="docker")
        stopped = self.stop()
        return self.start(open_browser=open_browser) if stopped["ok"] else stopped

    def logs(self, follow=False, tail=100) -> int:
        def read_logs():
            if type(tail) is not int or not 0 <= tail <= 10000:
                raise ControlError("docker_logs_tail_invalid")
            self._availability()
            containers = self._containers()
            if not containers:
                return result()
            # Immutable container ID prevents a concurrent Compose replacement
            # from redirecting logs after the ownership check.
            argv = ["docker", "logs", "--tail", str(tail)]
            if follow:
                argv.append("--follow")
            argv.append(containers[0]["id"])
            completed = self._call(argv, "docker_logs_failed", timeout=300 if follow else 20,
                                   stream=True, check=False)
            return result(*(["docker_logs_failed"] if completed.returncode else []),
                          exit_code=completed.returncode)
        report = self._guard("logs", read_logs)
        return report.get("exit_code", 0 if report["ok"] else 1)
