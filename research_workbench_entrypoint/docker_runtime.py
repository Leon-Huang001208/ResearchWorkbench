"""Stdlib host controller; all diagnostic output is allowlisted and bounded.

The bootstrap configures stderr logging. No Docker stderr, environment values,
or unrestricted inspect output is ever included in a diagnostic report.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from uuid import uuid4
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from .runtime_mode import RuntimeModeError, RuntimeModeStore, _read_bytes, _unique_object, _same_identity
from .runtime_endpoints import EndpointError, EndpointStore, select_port

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
    '"launch":{{json (index .Config.Labels "io.research-workbench.launch")}},'
    '"working_dir":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},'
    '"running":{{json .State.Running}},"state":{{json .State.Status}},'
    '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}"none"{{end}},'
    '"ports":{{json .NetworkSettings.Ports}},'
    '"mounts":[{{range $i,$m := .Mounts}}{{if $i}},{{end}}'
    '{"Source":{{json $m.Source}},"Destination":{{json $m.Destination}},'
    '"Type":{{json $m.Type}}}{{end}}]}'
)
_PREPARER_FORMAT = (
    '{"id":{{json .Id}},"image":{{json .Image}},'
    '"installation":{{json (index .Config.Labels "io.research-workbench.installation")}},'
    '"runtime":{{json (index .Config.Labels "io.research-workbench.runtime")}},'
    '"launch":{{json (index .Config.Labels "io.research-workbench.launch")}},'
    '"running":{{json .State.Running}},"state":{{json .State.Status}},'
    '"exit_code":{{json .State.ExitCode}},"ports":{{json .NetworkSettings.Ports}},'
    '"entrypoint":{{json .Config.Entrypoint}},"command":{{json .Config.Cmd}},'
    '"mounts":[{{range $i,$m := .Mounts}}{{if $i}},{{end}}'
    '{"Source":{{json $m.Source}},"Destination":{{json $m.Destination}},'
    '"Type":{{json $m.Type}}}{{end}}]}'
)


class ControlError(RuntimeError):
    """Path-free issue code suitable for CLI output."""

    def __init__(self, code: str, *related: str):
        self.code = code
        self.related = related
        super().__init__(code)


def result(*issues: str, **facts: Any) -> dict[str, Any]:
    return {"schema_version": 1, "ok": not issues, "issues": list(issues), **facts}


def safe_log_text(value: str) -> str:
    """Suppress authentication-bearing lines and terminal controls before display."""
    output = []
    value = "".join(c for c in value if c == "\n" or c.isprintable())
    for line in value.splitlines():
        if len(line) > 4096 or re.search(
            r"token|cookie|authorization|bearer|password|secret|api[_ -]?key|credential",
            line, re.IGNORECASE,
        ):
            output.append("[sensitive or oversized log line omitted]\n")
        else:
            output.append(line + "\n")
    return "".join(output)


class _WindowsProcessJob:
    """Own descendants before a suspended command can execute any user code."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("ProcessTime", ctypes.c_longlong), ("JobTime", ctypes.c_longlong),
                ("Flags", wintypes.DWORD), ("MinWorkingSet", ctypes.c_size_t),
                ("MaxWorkingSet", ctypes.c_size_t), ("ActiveProcesses", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("Priority", wintypes.DWORD),
                ("Scheduling", wintypes.DWORD),
            ]

        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("Basic", BasicLimits), ("IO", Counters),
                        ("ProcessMemory", ctypes.c_size_t), ("JobMemory", ctypes.c_size_t),
                        ("PeakProcessMemory", ctypes.c_size_t), ("PeakJobMemory", ctypes.c_size_t)]

        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_longlong) for name in
                        ("TotalUser", "TotalKernel", "PeriodUser", "PeriodKernel")] + [
                            (name, wintypes.DWORD) for name in
                            ("PageFaults", "TotalProcesses", "ActiveProcesses", "TerminatedProcesses")]

        self.accounting_type = Accounting
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                       ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.TerminateJobObject.restype = wintypes.BOOL
        self.kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                         ctypes.c_void_p, wintypes.DWORD,
                                                         ctypes.c_void_p]
        self.kernel.QueryInformationJobObject.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ControlError("runtime_process_tree_unavailable")
        limits = ExtendedLimits()
        limits.Basic.Flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ControlError("runtime_process_tree_unavailable")

    def attach_and_resume(self, process) -> None:
        import ctypes
        from ctypes import wintypes

        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ControlError("runtime_process_tree_unavailable")
        # Popen closes its primary thread handle. Resume the retained process
        # only after job assignment; this avoids a spawn-before-assignment race.
        resume = ctypes.WinDLL("ntdll").NtResumeProcess
        resume.argtypes = [wintypes.HANDLE]
        resume.restype = wintypes.LONG
        if resume(int(process._handle)) < 0:
            raise ControlError("runtime_process_tree_unavailable")

    def terminate(self) -> None:
        import ctypes

        if not self.kernel.TerminateJobObject(self.handle, 1):
            raise ControlError("runtime_process_tree_cleanup_failed")
        deadline = time.monotonic() + 5
        while True:
            accounting = self.accounting_type()
            if not self.kernel.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting),
                                                        ctypes.sizeof(accounting), None):
                raise ControlError("runtime_process_tree_cleanup_failed")
            if accounting.ActiveProcesses == 0:
                break
            if time.monotonic() >= deadline:
                raise ControlError("runtime_process_tree_cleanup_failed")
            time.sleep(0.02)

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _terminate_command_tree(process, job=None) -> None:
    """Gracefully stop only this launch's session/job, then escalate and reap."""
    def signal_group(value) -> bool:
        try:
            os.killpg(process.pid, value)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Darwin reports EPERM, not ESRCH, for an already-dead session;
            # getpgid on its unreaped zombie is ESRCH. Do not reinterpret a
            # permission failure on a live leader or on another platform.
            if sys.platform == "darwin":
                try:
                    os.getpgid(process.pid)
                except ProcessLookupError:
                    return False
            raise

    if job is not None:
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
        except OSError:
            pass  # Detached/non-console Windows children still belong to the job.
    else:
        if not signal_group(signal.SIGTERM):
            process.wait(timeout=5)
            return
    # Descendants may ignore TERM after their parent exits; always escalate the
    # owned group/job after this grace period, not just a still-running parent.
    time.sleep(0.2)
    if job is not None:
        job.terminate()
    else:
        signal_group(signal.SIGKILL)
    process.wait(timeout=5)


def run_bounded(
    argv: list[str], *, cwd: Path, env: dict[str, str], timeout: float,
    max_output: int = MAX_OUTPUT, stream: bool = False,
) -> subprocess.CompletedProcess:
    """Drain both pipes with hard caps; kill and reap on timeout/overflow.

    Follow is still bounded by timeout and byte count. It cannot silently grow
    memory or fill a temporary file when an untrusted daemon prints endlessly.
    """
    try:
        job = _WindowsProcessJob() if os.name == "nt" else None
    except (OSError, ImportError, AttributeError):
        raise ControlError("runtime_process_tree_unavailable") from None
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
            start_new_session=os.name != "nt",
            creationflags=(0x00000004 | subprocess.CREATE_NEW_PROCESS_GROUP) if job else 0,
        )
    except BaseException:
        if job is not None:
            job.close()
        raise
    if job is not None:
        try:
            job.attach_and_resume(process)
        except BaseException:
            job.close()
            process.kill()
            process.wait(timeout=5)
            for pipe in (process.stdout, process.stderr):
                pipe.close()
            raise
    buffers = [bytearray(), bytearray()]
    overflow = threading.Event()

    def drain(index: int) -> None:
        pipe = process.stdout if index == 0 else process.stderr
        assert pipe is not None
        pending = bytearray()
        emitted = 0

        def display(chunk: bytes) -> bool:
            nonlocal emitted
            destination = sys.stdout if index == 0 else sys.stderr
            encoded = safe_log_text(chunk.decode("utf-8", "replace")).encode("utf-8")
            available = max_output - emitted
            destination.write(encoded[:available].decode("utf-8", "ignore"))
            destination.flush()
            emitted += min(len(encoded), available)
            if len(encoded) > available:
                overflow.set()
                return False
            return True

        try:
            while chunk := pipe.read1(4096):
                available = max_output - len(buffers[index])
                buffers[index].extend(chunk[:max(0, available)])
                if len(chunk) > available:
                    overflow.set()
                    return
                if stream:
                    pending.extend(chunk)
                    boundary = pending.rfind(b"\n")
                    if boundary < 0:
                        continue
                    if not display(pending[:boundary + 1]):
                        return
                    del pending[:boundary + 1]
            if stream and pending:
                display(pending)
        except (OSError, ValueError):
            overflow.set()
        finally:
            pipe.close()

    threads = [threading.Thread(target=drain, args=(index,), daemon=True) for index in (0, 1)]
    started = []
    failure = None
    deadline = time.monotonic() + timeout
    cleanup_started = False
    try:
        for thread in threads:
            thread.start()
            started.append(thread)
        while True:
            if overflow.is_set():
                failure = "runtime_output_limit"
                break
            if not any(thread.is_alive() for thread in threads):
                if overflow.is_set():
                    continue
                if process.poll() is not None:
                    break
            if time.monotonic() >= deadline:
                failure = "runtime_command_timeout"
                break
            overflow.wait(min(0.02, max(0, deadline - time.monotonic())))
        if failure:
            cleanup_started = True
            try:
                _terminate_command_tree(process, job)
            except BaseException:
                log.error("runtime_command_cleanup code=runtime_process_tree_cleanup_failed")
                error = ControlError(failure)
                error.add_note("runtime_process_tree_cleanup_failed")
                raise error from None
    except BaseException as interrupted:
        if not cleanup_started:
            try:
                _terminate_command_tree(process, job)
            except BaseException:
                log.error("runtime_command_cleanup code=runtime_process_tree_cleanup_failed")
                interrupted.add_note("runtime_process_tree_cleanup_failed")
        raise
    finally:
        if job is not None:
            job.close()
        for thread in started:
            thread.join(timeout=1)
    if failure:
        raise ControlError(failure)
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
                 ports: tuple[int, int] | None = None):
        self.project_root = Path(project_root).resolve()
        self.home = Path(home).absolute()
        self.runner = runner
        self.requested_web_port = None
        self._legacy_ports_explicit = ports is not None
        self._allocating = False
        self.endpoint_store = EndpointStore(self.home)
        try:
            self.endpoint_snapshot = self.endpoint_store.read("docker")
        except EndpointError as error:
            raise ControlError(error.code) from error
        self.ports = ((self.endpoint_snapshot.web_port, 3081) if self.endpoint_snapshot
                      else ports or (8088, 3081))
        self.store = RuntimeModeStore(self.home)
        self._created_container = None
        self._lifecycle_lease = None
        self._pending_start = None

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

    def _environment(self, image: str = IMAGE) -> dict[str, str]:
        return {
            **minimal_environment(), "RWB_DATA_DIR": str(self.data_dir),
            "RWB_STATE_DIR": str(self.state_dir),
            "RWB_CREDENTIAL_DIR": str(self.credential_dir),
            "RWB_INSTALLATION_ID": self.installation_id,
            "RWB_WEB_PORT": str(self.ports[0]),
            "RWB_IMAGE": image,
            # Explicitly disable implicit .env interpolation even for a trusted
            # project directory; no secrets are imported by the Compose process.
            "COMPOSE_DISABLE_ENV_FILE": "1",
        }

    def _call(self, argv, code, *, timeout=20, stream=False, check=True, image=IMAGE):
        try:
            completed = self.runner(
                list(argv), cwd=self.project_root, env=self._environment(image),
                timeout=timeout, max_output=MAX_OUTPUT, stream=stream,
            )
        except FileNotFoundError:
            raise ControlError("docker_cli_missing") from None
        except (OSError, subprocess.SubprocessError):
            raise ControlError(code) from None
        if len(completed.stdout.encode()) > MAX_OUTPUT or len(completed.stderr.encode()) > MAX_OUTPUT:
            raise ControlError("runtime_output_limit")
        if check and completed.returncode:
            if code == "docker_start_failed" and "up" in argv:
                diagnostic = completed.stderr.lower()
                if ("port is already allocated" in diagnostic
                        or ("bind" in diagnostic and "address already in use" in diagnostic)):
                    raise ControlError("docker_bind_race")
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

    def _manifest(self, *, allow_missing=False, check_contract=True) -> dict | None:
        """Read only a private bounded accepted receipt; never infer it from a tag."""
        try:
            raw, _ = _read_bytes(self.home / "install/docker-manifest.json")
            value = json.loads(raw, object_pairs_hook=_unique_object)
        except FileNotFoundError:
            if allow_missing and self.store.read().mode != "docker":
                return None
            raise ControlError("docker_manifest_missing") from None
        except (OSError, ValueError, RuntimeModeError):
            raise ControlError("docker_manifest_invalid") from None
        self._validate_manifest(value, check_contract=check_contract)
        return value

    def _validate_manifest(self, value, *, check_contract=True) -> None:
        from app.research_web.runtime_contract import RuntimeContractError, load_runtime_contract

        keys = {"schema_version", "status", "runtime", "code_commit", "image_id", "python_version",
                "node_major", "web_lock_sha256", "cjpy_version", "cjpy_sha256", "dsh_commit",
                "compose_sha256", "installed_at"}
        if (not isinstance(value, dict) or set(value) != keys
                or type(value.get("schema_version")) is not int
                or value["schema_version"] != 1
                or value.get("status") != "installed" or value.get("runtime") != "docker"
                or not isinstance(value.get("image_id"), str)
                or not _IMAGE_ID.fullmatch(value["image_id"])):
            raise ControlError("docker_manifest_invalid")
        if (type(value["node_major"]) is not int or value["node_major"] < 1
                or not all(isinstance(value[key], str) and value[key]
                           for key in ("python_version", "cjpy_version", "installed_at"))
                or (value["code_commit"] is not None and
                    (not isinstance(value["code_commit"], str)
                     or not re.fullmatch("[a-f0-9]{40}", value["code_commit"])))):
            raise ControlError("docker_manifest_invalid")
        for key, length in (("web_lock_sha256", 64), ("compose_sha256", 64),
                            ("cjpy_sha256", 64), ("dsh_commit", 40)):
            if not isinstance(value.get(key), str) or not re.fullmatch("[a-f0-9]{%d}" % length, value[key]):
                raise ControlError("docker_manifest_invalid")
        if not check_contract:
            return
        try:
            contract = load_runtime_contract()
        except RuntimeContractError:
            raise ControlError("docker_build_contract_mismatch") from None
        expected = {
            "python_version": f"{contract.python_major}.{contract.python_minor}",
            "node_major": contract.node_major, "cjpy_version": contract.cjpy_version,
            "cjpy_sha256": contract.cjpy_sha256, "dsh_commit": contract.dsh_commit,
        }
        try:
            expected.update({key: hashlib.sha256((self.project_root / path).read_bytes()).hexdigest()
                             for key, path in (("web_lock_sha256", "requirements/web.lock"),
                                               ("compose_sha256", "compose.yaml"))})
        except OSError:
            raise ControlError("docker_build_contract_mismatch") from None
        if any(value.get(key) != expected_value for key, expected_value in expected.items()):
            raise ControlError("docker_build_contract_mismatch")

    def _accepted_image(self) -> dict:
        manifest = self._manifest()
        image = self._image(manifest["image_id"])
        if image["id"] != manifest["image_id"]:
            raise ControlError("docker_image_mismatch")
        return image

    @staticmethod
    def _match_image(containers, image_id):
        if any(container["image"] != image_id for container in containers):
            raise ControlError("docker_image_mismatch")

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
        except (ControlError, RuntimeModeError, EndpointError) as error:
            code = "docker_data_home_unsafe" if isinstance(error, RuntimeModeError) else error.code
            log.warning("docker_runtime operation=%s code=%s", operation, code)
            return result(code, *getattr(error, "related", ()), mode="docker")
        except OSError:
            log.warning("docker_runtime operation=%s code=docker_io", operation)
            return result("docker_io", mode="docker")

    @staticmethod
    def _pid_exists(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _locked_guard(self, operation, function):
        from app.research_web.lifecycle_lock import LifecycleLock, LifecycleLockError
        from app.research_web.control_origin import ControlOriginError
        def locked():
            try:
                if self._lifecycle_lease is not None:
                    self._lifecycle_lease.assert_held()
                    if self._lifecycle_lease.path != self.home / "run/lifecycle.lock":
                        raise ControlError("lifecycle_lock_ownership_lost")
                    return function()
                with LifecycleLock(self.home / "run/lifecycle.lock", self._pid_exists,
                                   trusted_root=self.home) as lease:
                    self._lifecycle_lease = lease
                    try:
                        return function()
                    finally:
                        self._lifecycle_lease = None
            except (LifecycleLockError, ControlOriginError) as error:
                raise ControlError(error.code) from error
        return self._guard(operation, locked)

    def preflight(self, *, require_image=True) -> dict:
        def check():
            self._credential_mount_boundary()
            self._availability()
            image = self._accepted_image() if require_image else None
            containers = self._containers()
            if image:
                self._match_image(containers, image["id"])
            return result(mode="docker", image_id=image["id"] if image else None,
                          container_image_id=containers[0]["image"] if containers else None)
        return self._guard("preflight", check)

    def _status(self, containers) -> dict:
        for container in containers:
            ports = container.get("ports")
            bindings = {key: value for key, value in ports.items() if value} if isinstance(ports, dict) else None
            if (self.endpoint_snapshot is None and not self._legacy_ports_explicit
                    and not self._allocating and bindings):
                web_bindings = bindings.get("8088/tcp")
                if (set(bindings) != {"8088/tcp"} or not isinstance(web_bindings, list)
                        or len(web_bindings) != 1 or not isinstance(web_bindings[0], dict)
                        or set(web_bindings[0]) != {"HostIp", "HostPort"}
                        or web_bindings[0]["HostIp"] != "127.0.0.1"):
                    raise ControlError("docker_ports_mismatch")
                raw_port = web_bindings[0]["HostPort"]
                if not isinstance(raw_port, str) or not raw_port.isascii() or not raw_port.isdecimal():
                    raise ControlError("docker_ports_mismatch")
                actual_port = int(raw_port)
                if not 1 <= actual_port <= 65535 or str(actual_port) != raw_port:
                    raise ControlError("docker_ports_mismatch")
                self.ports = actual_port, 3081
            expected = {"8088/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(self.ports[0])}]}
            if (container["running"] or bindings) and bindings != expected:
                raise ControlError("docker_ports_mismatch")
        running = bool(containers and containers[0]["running"])
        healthy = bool(running and containers[0]["state"] == "running"
                       and containers[0]["health"] == "healthy")
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
        facts = {
            "runtime_mode": "docker", "mode": "docker",
            "engine": {"ready": False}, "compose": {"ready": False},
            "container": {"state": "unknown", "ownership_id": None},
            "image": {"ready": False, "id": None},
            "ports": {"web": self.ports[0], "runtime": self.ports[1], "verified": False},
            "volumes": {"verified": False, "data": "bind", "state": "bind", "credentials": "bind"},
            "data": {"ready": False},
            "python": {"applicable": False}, "node": {"applicable": False},
            "cjpy": {"applicable": False},
            "dsh": {"ready": False, "build_verified": False, "commit": None,
                    "host_applicable": False},
            "services": {role: {"running": False, "healthy": False, "pid": None, "port": port}
                         for role, port in (("web", self.ports[0]), ("runtime", self.ports[1]))},
            "capabilities": {name: {"status": "unavailable_in_docker", "required": False}
                             for name in ("office", "wind", "tabbit")},
        }

        def diagnose():
            self._availability()
            facts["engine"]["ready"] = True
            facts["compose"]["ready"] = True
            image = self._accepted_image()
            facts["image"] = {"ready": True, "id": image["id"]}
            containers = self._containers()
            self._match_image(containers, image["id"])
            status = self._status(containers)
            facts["ports"].update(web=self.ports[0], runtime=3081)
            facts["services"] = status["services"]
            facts["dsh"] = {"ready": status["services"]["runtime"]["healthy"],
                            "build_verified": True, "commit": self._manifest()["dsh_commit"],
                            "host_applicable": False}
            facts["container"] = {
                "state": status["container_state"],
                "ownership_id": hashlib.sha256(
                    (self.installation_id + containers[0]["id"]).encode()
                ).hexdigest() if containers else None,
            }
            facts["volumes"]["verified"] = bool(containers)
            facts["data"]["ready"] = all(path.is_dir() for path in
                (self.data_dir, self.state_dir, self.credential_dir))
            issues = []
            if containers:
                ports = containers[0].get("ports")
                bindings = {key: value for key, value in ports.items() if value} if isinstance(ports, dict) else None
                facts["ports"]["verified"] = bindings == {
                    "8088/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(self.ports[0])}]
                }
                if not facts["ports"]["verified"]:
                    issues.append("docker_ports_mismatch")
            if not containers:
                issues.append("docker_container_absent")
            elif not all(service["healthy"] for service in facts["services"].values()):
                issues.append("docker_services_unhealthy")
            if not facts["data"]["ready"]:
                issues.append("docker_data_unavailable")
            self._credential_mount_boundary()
            return result(*issues)

        report = self._guard("doctor", diagnose)
        return {**report, **facts}

    def _credential_mount_boundary(self) -> None:
        # Windows mode bits do not prove a private ACL. Until a native ACL
        # preparer/verifier is accepted, never mount host credential material.
        if sys.platform == "win32":
            raise ControlError("docker_credentials_acl_unverified")

    def _ports_free(self):
        if port_busy(self.ports[0]):
            raise ControlError("docker_port_8088_occupied")

    def install(self) -> dict:
        def build():
            self._availability()
            self._manifest(allow_missing=True, check_contract=False)
            self._containers()
            if not self.installation_id:
                self.store.write(self.store.read().mode)
            self._safe_home()
            candidate = "research-workbench:build-" + uuid4().hex
            self._call([*self.compose_prefix, "build", "research-web"], "docker_build_failed", timeout=1800, image=candidate)
            return result(mode="docker", image_id=self._image(candidate)["id"])
        return self._guard("install", build)

    def _wait_ready(self, image_id, *, wait_timeout=120) -> dict:
        deadline = time.monotonic() + wait_timeout
        while True:
            containers = self._containers()
            self._match_image(containers, image_id)
            if not containers or not containers[0]["running"]:
                raise ControlError("docker_start_failed")
            report = self._status(containers)
            if all(service["healthy"] for service in report["services"].values()):
                return report
            if containers[0]["health"] != "starting" or containers[0]["state"] != "running":
                raise ControlError("docker_services_unhealthy")
            if time.monotonic() >= deadline:
                raise ControlError("docker_ready_timeout")
            time.sleep(0.25)

    def _start_image(self, image_id, *, open_browser=True, wait_timeout=120, candidate=False) -> dict:
        from app.research_web.control_origin import ControlOriginError
        self._created_container = None
        self._started_container = None
        self._allocating = False
        transaction = None
        committed = False
        endpoint_before = self.endpoint_snapshot
        endpoint_published = None
        initial_ports = self.ports
        mode_snapshot = self.store.read()
        def start_owned():
            nonlocal transaction, committed, endpoint_published
            if self.store.read() != mode_snapshot:
                raise ControlError("runtime_mode_changed")
            if not candidate and mode_snapshot.mode != "docker":
                raise ControlError("runtime_other_selected")
            self._credential_mount_boundary()
            self._availability()
            if self._image(image_id)["id"] != image_id:
                raise ControlError("docker_image_mismatch")
            containers = self._containers()
            self._match_image(containers, image_id)
            from .bootstrap import NativeRuntime, _running
            native = NativeRuntime(self.project_root, self.home).status()
            if not native.get("ok"):
                raise ControlError("runtime_ownership_unknown")
            if _running(native):
                raise ControlError("runtime_other_running")
            if containers and containers[0]["running"]:
                self._status(containers)
                if self.requested_web_port is not None and self.requested_web_port != self.ports[0]:
                    raise ControlError("endpoint_running_conflict")
                return self._wait_ready(image_id, wait_timeout=wait_timeout)
            if self.endpoint_store.read("docker") != self.endpoint_snapshot:
                raise ControlError("endpoint_conflict")
            selected = select_port(self.requested_web_port or self.ports[0],
                                   explicit=self.requested_web_port is not None)
            if containers and selected != self.ports[0]:
                raise ControlError("docker_stopped_port_conflict")
            self.ports = selected, 3081
            self._allocating = True
            self._ports_free()
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
            transaction = self._prepare_control_origin(image_id)
            before = self._containers()
            self._match_image(before, image_id)
            if before:
                if before[0]["running"]:
                    raise ControlError("docker_ownership_mismatch")
                self._started_container = (before[0]["id"], image_id, before[0].get("launch"))
            launch = uuid4().hex if not before else None
            with ExitStack() as cleanup:
                command = list(self.compose_prefix)
                if launch is not None:
                    scratch = cleanup.enter_context(tempfile.TemporaryDirectory(prefix="rwb-launch-"))
                    overlay = Path(scratch) / "launch.json"
                    overlay.write_text(json.dumps({"services": {"research-web": {"labels": {
                        "io.research-workbench.launch": launch,
                    }}}}), encoding="utf-8")
                    command.extend(("-f", str(overlay)))
                try:
                    self._call([*command, "up", "--detach", "--no-build", "--pull", "never", "--no-recreate", "research-web"], "docker_start_failed", timeout=60, image=image_id)
                    if not before:
                        self._record_created(image_id, launch)
                    ready = self._wait_ready(image_id, wait_timeout=wait_timeout)
                    self.endpoint_snapshot = self.endpoint_store.publish("docker", self.ports[0],
                                                                         expected=self.endpoint_snapshot)
                    endpoint_published = self.endpoint_snapshot
                    if candidate:
                        self._pending_start = (transaction, endpoint_before, endpoint_published, initial_ports)
                    elif transaction is not None:
                        transaction.commit()
                    committed = True
                    return ready
                except (ControlError, EndpointError, ControlOriginError, OSError) as error:
                    original = error.code if isinstance(error, (ControlError, EndpointError, ControlOriginError)) else "docker_io"
                    log.warning("docker_runtime code=%s", original)
                    if not before and self._created_container is None:
                        # up may create before returning nonzero or timing out.
                        # One bounded enumeration, never infer ownership merely
                        # from a matching project/image or delete by service name.
                        try:
                            self._record_created(image_id, launch)
                        except (ControlError, OSError):
                            log.warning("docker_runtime code=docker_rollback_unverified")
                            raise ControlError(original, "docker_rollback_unverified") from error
                    if self._created_container is not None:
                        try:
                            self._rollback_created()
                        except (ControlError, OSError):
                            raise ControlError(original, "docker_rollback_failed") from error
                    if self._started_container is not None:
                        try:
                            self._rollback_started()
                        except (ControlError, OSError):
                            raise ControlError(original, "docker_rollback_unverified") from error
                    raise
        def transactional_start():
            nonlocal transaction, committed
            for attempt in range(3):
                transaction, committed = None, False
                try:
                    return start_owned()
                except Exception as error:
                    if endpoint_published is not None and not committed:
                        if not self._control_quiescent():
                            raise ControlError("control_origin_recovery_unverified") from error
                        self.endpoint_snapshot = self.endpoint_store.restore("docker", endpoint_before,
                                                                            expected=endpoint_published)
                    if transaction is not None and not committed:
                        # _start_image's existing exact-ID cleanup runs first.
                        transaction.rollback()
                    retry = (isinstance(error, ControlError) and not error.related
                             and error.code in {"docker_bind_race", "docker_port_8088_occupied"})
                    if retry and self.requested_web_port is not None:
                        raise ControlError("endpoint_port_in_use") from error
                    if not retry or attempt == 2 or not self._control_quiescent() or self._containers():
                        raise
                    log.warning("docker_runtime code=docker_bind_retry")
        report = self._locked_guard("start", transactional_start)
        if not report["ok"]:
            self.ports = initial_ports
        if report["ok"] and open_browser:
            try:
                if not webbrowser.open(report["url"]):
                    log.warning("docker_runtime code=browser_unavailable")
            except (OSError, webbrowser.Error):
                log.warning("docker_runtime code=browser_unavailable")
        return report

    def _control_quiescent(self):
        from .bootstrap import NativeRuntime, _running
        native = NativeRuntime(self.project_root, self.home).status()
        return (native.get("ok") is True and not _running(native)
                and not any(item["running"] for item in self._containers()))

    def _commit_candidate(self):
        if self._pending_start is not None:
            transaction, _previous, _published, _ports = self._pending_start
            if transaction is not None:
                transaction.commit()
            self._pending_start = None

    def _abort_candidate(self):
        self._rollback_created()
        self._rollback_started()
        if self._pending_start is not None:
            transaction, previous, published, ports = self._pending_start
            if not self._control_quiescent():
                raise ControlError("control_origin_recovery_unverified")
            self.endpoint_snapshot = self.endpoint_store.restore("docker", previous, expected=published)
            if transaction is not None:
                transaction.rollback()
            self._pending_start = None
            self.ports = ports

    def _prepare_control_origin(self, image_id):
        """Only existing paired host records are eligible for host rebinding."""
        from app.research_web.control_origin import ControlOriginTransaction
        raws = []
        identities = []
        for name in ("datahub.json", "mcp-runtime.json"):
            try:
                raw, identity = _read_bytes(self.data_dir / ".control" / name)
                raws.append(raw)
                identities.append(identity)
            except FileNotFoundError:
                raws.append(None)
                identities.append(None)
        if raws == [None, None]:
            # First creation belongs to the trusted guest creator, not the host.
            return None
        try:
            previous = json.loads(next(raw for raw in raws if raw is not None),
                                  object_pairs_hook=_unique_object)["url"]
        except (ValueError, KeyError, TypeError, RecursionError):
            raise ControlError("control_origin_schema") from None
        native = self.endpoint_store.read("native")
        allowed = {"http://127.0.0.1:8088"}
        if native is not None:
            allowed.add(f"http://127.0.0.1:{native.web_port}")
        if not isinstance(previous, str) or previous not in allowed:
            raise ControlError("control_origin_unverified")
        if any(raw is None for raw in raws):
            self._prepare_missing_controls(image_id, previous)
            for name, original, identity in zip(("datahub.json", "mcp-runtime.json"), raws, identities):
                current, after = _read_bytes(self.data_dir / ".control" / name)
                if original is not None and (current != original or not _same_identity(identity, after)):
                    raise ControlError("control_origin_recovery_unverified")
        transaction = ControlOriginTransaction(self.data_dir, previous, "http://127.0.0.1:8088",
                                                quiescent=self._control_quiescent)
        transaction.prepare()
        return transaction

    def _inspect_preparer(self, identity, image_id, launch, origin):
        value = self._json(["docker", "container", "inspect", "--format", _PREPARER_FORMAT, identity],
                           "docker_prepare_ownership_unknown")
        expected = {"id": identity, "image": image_id, "installation": self.installation_id,
                    "launch": launch, "runtime": "control-preparer",
                    "entrypoint": ["/opt/rwb/venv/bin/python"],
                    "command": ["/opt/rwb/docker/supervisor.py", "--prepare-controls-only",
                                "--previous-origin", origin]}
        if (not isinstance(value, dict) or any(value.get(key) != item for key, item in expected.items())
                or type(value.get("running")) is not bool
                or type(value.get("exit_code")) is not int
                or value.get("state") not in {"created", "running", "exited", "dead"}
                or value.get("ports") not in ({}, None)):
            raise ControlError("docker_prepare_ownership_unknown")
        mounts = value.get("mounts")
        if not isinstance(mounts, list) or not all(isinstance(item, dict) and all(
            isinstance(item.get(key), str) for key in ("Source", "Destination", "Type")) for item in mounts):
            raise ControlError("docker_prepare_ownership_unknown")
        expected_mounts = {(str(self.data_dir), "/data/research-web", "bind"),
                           *(("", name, "tmpfs") for name in
                             ("/state", "/run/rwb-secrets", "/tmp", "/home/rwb"))}
        actual = {(item.get("Source"), item.get("Destination"), item.get("Type")) for item in mounts}
        if len(mounts) != len(expected_mounts) or actual != expected_mounts:
            raise ControlError("docker_prepare_ownership_unknown")
        return value

    def _prepare_missing_controls(self, image_id, origin):
        """Run fixed creators in an owned, portless guest; never mount credentials."""
        if not self._control_quiescent():
            raise ControlError("control_origin_not_quiescent")
        launch = uuid4().hex
        identity = None
        command = ["docker", "create", "--read-only", "--user", "10001:10001",
            "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--label", "io.research-workbench.installation=" + self.installation_id,
            "--label", "io.research-workbench.runtime=control-preparer",
            "--label", "io.research-workbench.launch=" + launch,
            "--mount", f"type=bind,source={self.data_dir},target=/data/research-web"]
        for path in ("/state", "/run/rwb-secrets", "/tmp", "/home/rwb"):
            command.extend(("--tmpfs", path + ":rw,nosuid,nodev,uid=10001,gid=10001,mode=700"))
        command.extend(("--entrypoint", "/opt/rwb/venv/bin/python", image_id,
                        "/opt/rwb/docker/supervisor.py", "--prepare-controls-only", "--previous-origin", origin))

        def cleanup():
            checked = self._inspect_preparer(identity, image_id, launch, origin)
            if checked["running"]:
                self._call(["docker", "stop", "--time", "5", identity], "docker_prepare_stop_failed", timeout=10)
                checked = self._inspect_preparer(identity, image_id, launch, origin)
            if checked["running"]:
                raise ControlError("docker_prepare_cleanup_unverified")
            self._call(["docker", "rm", identity], "docker_prepare_cleanup_failed")
            remaining = self._call(["docker", "ps", "--all", "--no-trunc", "--filter",
                "label=io.research-workbench.launch=" + launch, "--format", "{{.ID}}"],
                "docker_prepare_cleanup_unverified").stdout.strip()
            if remaining:
                raise ControlError("docker_prepare_cleanup_unverified")

        try:
            raw = self._call(command, "docker_prepare_create_failed", image=image_id).stdout.strip()
            if not _ID.fullmatch(raw):
                raise ControlError("docker_prepare_ownership_unknown")
            identity = raw
            self._inspect_preparer(identity, image_id, launch, origin)
            self._call(["docker", "start", "--attach", identity], "control_origin_prepare_failed", timeout=60)
            checked = self._inspect_preparer(identity, image_id, launch, origin)
            if checked["running"] or checked["state"] != "exited" or checked["exit_code"] != 0:
                raise ControlError("control_origin_prepare_failed")
        except (ControlError, OSError) as error:
            original = error.code if isinstance(error, ControlError) else "docker_io"
            try:
                if identity is None:
                    found = self._call(["docker", "ps", "--all", "--no-trunc", "--filter",
                        "label=io.research-workbench.launch=" + launch, "--format", "{{.ID}}"],
                        "docker_prepare_cleanup_unverified").stdout.splitlines()
                    if len(found) > 1 or any(not _ID.fullmatch(item) for item in found):
                        raise ControlError("docker_prepare_cleanup_unverified")
                    identity = found[0] if found else None
                if identity is not None:
                    cleanup()
            except (ControlError, OSError):
                raise ControlError(original, "docker_prepare_cleanup_unverified") from error
            raise
        cleanup()

    def start(self, *, open_browser=True, wait_timeout=120) -> dict:
        def accepted_start():
            self._credential_mount_boundary()
            image = self._accepted_image()
            return self._start_image(image["id"], open_browser=open_browser, wait_timeout=wait_timeout)
        return self._guard("start", accepted_start)

    def _rollback_created(self):
        if self._created_container is None:
            return
        identity, image_id, launch = self._created_container
        # A caller's outer transaction must not silently repeat a failed delete
        # or replace the original up error with a second cleanup exception.
        self._created_container = None
        try:
            current = self._inspect(identity)
            self._match_image([current], image_id)
            if current.get("launch") != launch:
                raise ControlError("docker_rollback_unverified")
            self._call(["docker", "rm", "--force", identity], "docker_rollback_failed")
        except (ControlError, OSError):
            log.warning("docker_runtime code=docker_rollback_failed")
            raise ControlError("docker_rollback_failed") from None

    def _rollback_started(self):
        """Restore only the exact stopped instance started by this attempt."""
        attempt = getattr(self, "_started_container", None)
        if attempt is None:
            return
        self._started_container = None
        identity, image_id, launch = attempt
        current = self._inspect(identity)
        self._match_image([current], image_id)
        if current.get("launch") != launch:
            raise ControlError("docker_rollback_unverified")
        if current["running"]:
            self._call(["docker", "stop", "--time", "35", identity], "docker_rollback_failed", timeout=45)
        current = self._inspect(identity)
        self._match_image([current], image_id)
        if current.get("launch") != launch or current["running"]:
            raise ControlError("docker_rollback_unverified")
        log.info("docker_runtime operation=rollback_started code=ok")

    def _record_created(self, image_id, launch):
        containers = self._containers()
        self._match_image(containers, image_id)
        if containers:
            if launch is None or containers[0].get("launch") != launch:
                raise ControlError("docker_rollback_unverified")
            self._created_container = (containers[0]["id"], image_id, launch)

    def _start_candidate(self, manifest: dict) -> dict:
        # Private installer transaction entry. Public start always reloads the
        # accepted receipt and cannot inherit this candidate selection.
        self._manifest(allow_missing=True, check_contract=False)
        self._validate_manifest(manifest)
        return self._start_image(manifest["image_id"], open_browser=False, candidate=True)

    def _dispose_stopped_for_repair(self, current) -> None:
        """Explicit repair may remove an owned stopped container, never its image/data."""
        manifest = self._manifest(check_contract=False)
        containers = self._containers()
        self._match_image(containers, manifest["image_id"])
        for container in containers:
            checked = self._inspect(container["id"])
            if checked["running"] or checked["state"] not in ("created", "exited", "dead"):
                raise ControlError("runtime_stop_current_required")
            if self.store.read() != current:
                raise ControlError("runtime_mode_changed")
            # No force and no volume flag: Docker rejects a concurrent start.
            self._call(["docker", "rm", container["id"]], "docker_repair_disposition_failed")
            log.info("docker_runtime operation=repair_disposition code=ok")
        if self._containers():
            raise ControlError("docker_ownership_mismatch")

    def stop(self, *, wait_timeout=10) -> dict:
        def stop_owned():
            self._availability()
            containers = self._containers()
            for container in containers:
                if container["running"]:
                    self._inspect(container["id"])
                    self._call(["docker", "stop", "--time", "35", container["id"]], "docker_stop_failed", timeout=45)
            deadline = time.monotonic() + wait_timeout
            remaining = self._containers()
            while any(container["running"] for container in remaining):
                if time.monotonic() >= deadline:
                    raise ControlError("runtime_ports_not_released")
                time.sleep(0.05)
                remaining = self._containers()
            if any(container["running"] for container in remaining):
                raise ControlError("docker_stop_failed")
            return self._status(remaining)
        return self._locked_guard("stop", stop_owned)

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
            self._inspect(containers[0]["id"])
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
