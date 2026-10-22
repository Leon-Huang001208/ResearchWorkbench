"""Bounded, privately authenticated Web/DSH pairs owned by this server process."""

from __future__ import annotations

import asyncio
import fcntl
import http.client
import json
import os
import re
import secrets
import signal
import socket
import stat
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx

from core.observability import get_logger

from .. import PINNED_DSH_COMMIT
from ..process_spec import build_process_specs
from ..runtime_auth import RuntimeAuthFileError, read_runtime_auth_record
from ..tenant_policy import GATEWAY_HEADER

log = get_logger(__name__)
START_TIMEOUT = 60.0


class RuntimeErrorSafe(RuntimeError):
    """Stable status without raw subprocess output, paths or credentials."""

    def __init__(self, code: str, status: int = 503):
        super().__init__(code)
        self.code, self.status = code, status


@dataclass(frozen=True)
class RuntimeConfig:
    root: Path
    project: Path
    source: Path
    python: str
    node: str
    max_instances: int = 2


@dataclass(frozen=True)
class Backend:
    url: str
    key: str = field(repr=False)
    generation: str = ""
    runtime_pid: int | None = None


@dataclass
class _Instance:
    user: str
    state: Path
    backend: Backend
    children: list
    generation: str = field(default_factory=lambda: uuid4().hex)


def _directory(path: Path, *, create=True) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise RuntimeErrorSafe("runtime_path_unsafe")
    try:
        for ancestor in (*reversed(path.parents), path):
            if ancestor.is_symlink():
                raise RuntimeErrorSafe("runtime_path_unsafe")
        if create:
            path.mkdir(mode=0o700, exist_ok=True)
        item = path.lstat()
        if (
            not stat.S_ISDIR(item.st_mode)
            or item.st_uid != os.getuid()
            or stat.S_IMODE(item.st_mode) != 0o700
        ):
            raise RuntimeErrorSafe("runtime_path_unsafe")
    except OSError as exc:
        raise RuntimeErrorSafe("runtime_path_unsafe") from exc


def _read_private(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        item = os.fstat(descriptor)
        if (
            not stat.S_ISREG(item.st_mode)
            or item.st_uid != os.getuid()
            or item.st_nlink != 1
            or stat.S_IMODE(item.st_mode) != 0o600
            or item.st_size > 65536
        ):
            raise RuntimeErrorSafe("runtime_path_unsafe")
        return os.read(descriptor, 65537)
    finally:
        os.close(descriptor)


def _create_private(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _reserve_port(preferred: int = 0) -> socket.socket:
    reserved = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if preferred:
            reserved.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        reserved.bind(("127.0.0.1", preferred))
        if preferred:
            # TIME_WAIT may outlive a graceful Web shutdown. Listening also
            # excludes a second reusable reservation on platforms allowing it.
            reserved.listen(1)
        return reserved
    except OSError as exc:
        reserved.close()
        raise RuntimeErrorSafe("runtime_port_unavailable") from exc
    except BaseException:
        reserved.close()
        raise


def _reserve_web_port(root: Path) -> socket.socket:
    """Reuse the authoritative callback origin without rotating any control token."""
    from ..control_origin import ControlOriginError, _decode

    control = root / ".control"
    if not control.exists() and not control.is_symlink():
        return _reserve_port()
    try:
        _directory(control, create=False)
        journal = control / "origin-transaction.json"
        if journal.exists() or journal.is_symlink():
            raise ValueError("pending_control_transaction")
        origins: list[str] = []
        for name in ("datahub.json", "mcp-runtime.json"):
            path = control / name
            if not path.exists() and not path.is_symlink():
                continue
            raw = _read_private(path)
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise TypeError
            origin = value.get("url")
            if not isinstance(origin, str):
                raise TypeError
            _decode(name, raw, origin)
            origins.append(origin)
        if not origins:
            return _reserve_port()
        if len(set(origins)) != 1:
            raise ValueError("control_origins_differ")
        parsed = urlsplit(origins[0])
        port = parsed.port
        if port is None or origins[0] != f"http://127.0.0.1:{port}":
            raise ValueError("control_origin_not_ipv4")
        return _reserve_port(port)
    except RuntimeErrorSafe:
        raise
    except (OSError, ValueError, TypeError, ControlOriginError) as exc:
        log.warning("multiuser_runtime_control_rejected", error_type=type(exc).__name__)
        raise RuntimeErrorSafe("runtime_control_invalid") from exc


def _group_retired(pid: int) -> bool:
    try:
        os.killpg(pid, 0)
        return False
    except ProcessLookupError:
        return True
    except OSError as exc:
        raise RuntimeErrorSafe("runtime_stop_unverified") from exc


async def _probe_backend(backend: Backend) -> bool:
    try:
        async with httpx.AsyncClient(
            trust_env=False, timeout=2.0, follow_redirects=False
        ) as client:
            response = await client.get(
                backend.url + "/api/research/runtime", headers={GATEWAY_HEADER: backend.key}
            )
        if response.status_code != 200 or len(response.content) > 65536:
            return False
        result = response.json()
        return isinstance(result, dict) and all(
            result.get(key) is True for key in ("health_check_passed", "owned_runtime", "connected")
        )
    except (httpx.HTTPError, ValueError, TypeError):
        return False


def _exchange_auth(port: int, token: str) -> str | None:
    """Use stdlib HTTP so a startup URL containing a token never enters HTTP logs."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", f"/?token={token}")
        response = connection.getresponse()
        response.read(4096)
        raw = response.getheader("Set-Cookie")
        if response.status != 303 or not raw:
            return None
        cookie = raw.split(";", 1)[0]
        if (
            cookie.startswith("dsh-auth-")
            and "\r" not in cookie
            and "\n" not in cookie
            and len(cookie) <= 4096
        ):
            return cookie
        return None
    except (OSError, http.client.HTTPException):
        return None
    finally:
        connection.close()


class RuntimePool:
    """Never adopt old processes or evict an active user's research for capacity."""

    def __init__(self, config: RuntimeConfig, *, recover=None, boot_id: str | None = None):
        if type(config.max_instances) is not int or not 1 <= config.max_instances <= 4:
            raise RuntimeErrorSafe("runtime_capacity_invalid", 400)
        if any(
            not Path(value).is_absolute()
            for value in (config.root, config.project, config.source, config.python, config.node)
        ):
            raise RuntimeErrorSafe("runtime_configuration_invalid", 400)
        self.config, self.instance = config, uuid4().hex
        self.boot_id = boot_id
        self._lock = asyncio.Lock()
        self._instances: dict[str, _Instance] = {}
        self._plugin_frozen: set[str] = set()
        self._request_tickets: dict[str, set[str]] = {}
        self._restart_results: dict[tuple[str, str, str], dict] = {}
        self._closed = False
        self._closing = False
        self._lock_fd = None
        _directory(config.root)
        for folder in ("users", "run", "logs"):
            _directory(config.root / folder)
        self._directories = {
            path: (path.stat().st_dev, path.stat().st_ino)
            for path in (
                config.root,
                *(config.root / folder for folder in ("users", "run", "logs")),
            )
        }
        try:
            descriptor = os.open(
                config.root / "run/runtime-pool.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
            )
            self._lock_fd = descriptor
            item = os.fstat(descriptor)
            if (
                not stat.S_ISREG(item.st_mode)
                or item.st_uid != os.getuid()
                or item.st_nlink != 1
                or stat.S_IMODE(item.st_mode) != 0o600
            ):
                raise RuntimeErrorSafe("runtime_path_unsafe")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeErrorSafe("runtime_pool_locked") from exc
            self._lock_identity = (item.st_dev, item.st_ino)
            for user_root in (config.root / "users").iterdir():
                _directory(user_root, create=False)
                if (user_root / "state/owner.json").exists() or (
                    user_root / "state/owner.json"
                ).is_symlink():
                    if recover is None:
                        raise RuntimeErrorSafe("runtime_stale_owner")
                    recover(user_root)
                    if (user_root / "state/owner.json").exists():
                        raise RuntimeErrorSafe("runtime_stale_owner")
        except BaseException:
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None
            raise

    def _assert_pool(self) -> None:
        for path, identity in self._directories.items():
            _directory(path, create=False)
            actual = path.stat()
            if (actual.st_dev, actual.st_ino) != identity:
                raise RuntimeErrorSafe("runtime_path_unsafe")
        lock = (self.config.root / "run/runtime-pool.lock").lstat()
        if (
            self._lock_fd is None
            or (lock.st_dev, lock.st_ino) != self._lock_identity
            or not stat.S_ISREG(lock.st_mode)
        ):
            raise RuntimeErrorSafe("runtime_pool_lock_changed")

    def _audit(self, user: str, code: str) -> None:
        self._assert_pool()
        log.info("multiuser_runtime_lifecycle", user_id=user, code=code)
        path = self.config.root / "logs/runtime.jsonl"
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            item = os.fstat(descriptor)
            if (
                not stat.S_ISREG(item.st_mode)
                or item.st_uid != os.getuid()
                or item.st_nlink != 1
                or stat.S_IMODE(item.st_mode) != 0o600
            ):
                raise RuntimeErrorSafe("runtime_path_unsafe")
            os.write(
                descriptor,
                (json.dumps({"at": time.time(), "user_id": user, "code": code}) + "\n").encode(),
            )
        finally:
            os.close(descriptor)

    @staticmethod
    def _user(value: str) -> str:
        try:
            if not isinstance(value, str) or str(UUID(value)) != value:
                raise ValueError
        except (ValueError, TypeError, AttributeError) as exc:
            raise RuntimeErrorSafe("user_id_invalid", 400) from exc
        return value

    def _record(self, instance: _Instance, *, create=False) -> None:
        owner = instance.state / "owner.json"
        raw = json.dumps(
            {
                "version": 1,
                "instance": self.instance,
                "user": instance.user,
                "pids": [child.pid for child in instance.children],
                "generation": instance.generation,
                **({"boot_id": self.boot_id} if self.boot_id else {}),
            }
        ).encode()
        if create:
            _create_private(owner, raw)
            return
        if json.loads(_read_private(owner)).get("instance") != self.instance:
            raise RuntimeErrorSafe("runtime_owner_changed")
        temporary = instance.state / f".owner-{self.instance}.tmp"
        _create_private(temporary, raw)
        os.replace(temporary, owner)

    def _environment(
        self, root: Path, state: Path, web_port: int, runtime_port: int
    ) -> dict[str, str]:
        return {
            "PATH": os.pathsep.join(
                dict.fromkeys(
                    (
                        str(Path(self.config.python).parent),
                        str(Path(self.config.node).parent),
                        "/usr/bin",
                        "/bin",
                        "/usr/sbin",
                        "/sbin",
                    )
                )
            ),
            "LANG": "en_US.UTF-8",
            "HOME": str(root / "runtime/home"),
            "TMPDIR": str(root / "runtime/tmp"),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "LOG_DIR": str(root / "logs"),
            "RESEARCH_DATA_HOME": str(root),
            "RESEARCH_RUN_MODE": "web-prod",
            "RESEARCH_PROJECT_ROOT": str(self.config.project),
            "OBJECT_STORAGE_PATH": str(root / "objects"),
            "PDF_MARKDOWN_DIR": str(root / "markdown"),
            "PDF_RAW_TEXT_DIR": str(root / "raw_text"),
            "RESEARCH_RUNTIME_URL": f"http://127.0.0.1:{runtime_port}",
            "RESEARCH_WEB_INTERNAL_URL": f"http://127.0.0.1:{web_port}",
            "RESEARCH_RUNTIME_AUTH": str(state / "auth.json"),
            "RWB_RUNTIME_STATE": str(state),
            "RWB_TENANT_MODE": "1",
            "RWB_TENANT_GATEWAY_KEY_FILE": str(state / "gateway.key"),
            "RWB_SHARED_PLUGINS_ROOT": str(self.config.root / "shared/plugin-approvals"),
            "RWB_PERSONAL_PLUGINS_ROOT": str(root.parent / "plugin-approvals"),
            "RESEARCH_AUTOMATIONS_ENABLED": "0",
            "RESEARCH_MCP_RUNTIME_ENABLED": "1",
        }

    async def backend_for(self, user_id: str) -> Backend:
        user = self._user(user_id)
        async with self._lock:
            if self._closed or self._closing:
                raise RuntimeErrorSafe("runtime_pool_closed")
            self._assert_pool()
            if user in self._plugin_frozen:
                raise RuntimeErrorSafe("runtime_restart_deferred", 409)
            if existing := self._instances.get(user):
                if any(child.poll() is not None for child in existing.children):
                    raise RuntimeErrorSafe("runtime_process_exited")
                return existing.backend
            if len(self._instances) >= self.config.max_instances:
                raise RuntimeErrorSafe("runtime_capacity_exceeded")
            return await self._start(user)

    async def _start(self, user: str) -> Backend:
        sockets = []
        entry = None
        record_owned = False
        try:
            _directory(self.config.root)
            _directory(self.config.root / "users")
            user_root = self.config.root / "users" / user
            _directory(user_root)
            root, state = user_root / "research-web", user_root / "state"
            _directory(root)
            _directory(state)
            if (state / "owner.json").exists() or (state / "owner.json").is_symlink():
                raise RuntimeErrorSafe("runtime_stale_owner")
            for path in (
                root / "runtime",
                root / "runtime/home",
                root / "runtime/tmp",
                root / "logs",
            ):
                _directory(path)
            sockets.append(_reserve_web_port(root))
            sockets.append(_reserve_port())
            web_port, runtime_port = [item.getsockname()[1] for item in sockets]
            entry = _Instance(
                user, state, Backend(f"http://127.0.0.1:{web_port}", secrets.token_urlsafe(32)), []
            )
            self._record(entry, create=True)
            record_owned = True
            self._instances[user] = entry
            _create_private(state / "gateway.key", entry.backend.key.encode("ascii"))
            specs = build_process_specs(
                python=self.config.python,
                node=self.config.node,
                project_root=self.config.project,
                data_root=root,
                runtime_source=self.config.source,
                state_root=state,
                web_host="127.0.0.1",
                web_port=web_port,
                runtime_port=runtime_port,
            )
            environment = self._environment(root, state, web_port, runtime_port)
            environment.update(
                RWB_TENANT_GENERATION=entry.generation,
                RWB_TENANT_MANAGER_INSTANCE=self.instance,
                RWB_TENANT_USER=user,
            )
            self._audit(user, "runtime_starting")
            sockets[1].close()
            entry.children.append(self._spawn(specs.runtime.command, environment))
            entry.backend = Backend(
                entry.backend.url, entry.backend.key, entry.generation, entry.children[0].pid
            )
            self._record(entry)
            deadline = time.monotonic() + START_TIMEOUT
            await self._wait_runtime(entry, runtime_port, root, deadline)
            sockets[0].close()
            entry.children.append(self._spawn(specs.web.command, environment))
            self._record(entry)
            await self._wait_backend(entry, deadline)
            self._instances[user] = entry
            self._audit(user, "runtime_ready")
            return entry.backend
        except BaseException as exc:
            if entry is not None and record_owned:
                cleanup = asyncio.create_task(self._dispose(entry))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await cleanup
                self._instances.pop(user, None)
            if isinstance(exc, (asyncio.CancelledError, RuntimeErrorSafe)):
                raise
            log.warning("multiuser_runtime_start_failed", error_type=type(exc).__name__)
            raise RuntimeErrorSafe("runtime_start_failed") from exc
        finally:
            for reserved in sockets:
                reserved.close()

    def _spawn(self, command, environment):
        # Popen itself is a short atomic ownership boundary: cancellation cannot
        # lose the newly created child between a background spawn and registration.
        return subprocess.Popen(
            command,
            cwd=self.config.project,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    async def _wait_runtime(self, entry: _Instance, port: int, root: Path, deadline: float) -> None:
        while time.monotonic() < deadline:
            if entry.children[0].poll() is not None:
                raise RuntimeErrorSafe("runtime_process_exited")
            try:
                record = read_runtime_auth_record(entry.state / "auth.json")
                expected = {
                    "authority": f"127.0.0.1:{port}",
                    "cwd": str(root / "runtime/work"),
                    "source_commit": PINNED_DSH_COMMIT,
                    "pid": entry.children[0].pid,
                }
                if not isinstance(record, dict) or any(
                    record.get(key) != value for key, value in expected.items()
                ):
                    raise RuntimeErrorSafe("runtime_auth_identity_invalid")
                if (
                    isinstance(record.get("version"), str)
                    and isinstance(record.get("cookie"), str)
                    and record["cookie"].startswith("dsh-auth-")
                ):
                    return
                token = record.get("bootstrap_token")
                if isinstance(token, str) and re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
                    cookie = await asyncio.to_thread(_exchange_auth, port, token)
                    if cookie is not None:
                        # Recheck the exact source bytes and owned PID before the
                        # private bootstrap record is atomically replaced.
                        if (
                            read_runtime_auth_record(entry.state / "auth.json") != record
                            or entry.children[0].poll() is not None
                        ):
                            raise RuntimeErrorSafe("runtime_auth_identity_invalid")
                        final = {
                            key: value for key, value in record.items() if key != "bootstrap_token"
                        }
                        final["cookie"] = cookie
                        temporary = entry.state / f".auth-{self.instance}.tmp"
                        _create_private(temporary, json.dumps(final).encode())
                        os.replace(temporary, entry.state / "auth.json")
                        return
            except (OSError, ValueError, RuntimeAuthFileError):
                pass  # Auth publication is polled only during this bounded owned start.
            await asyncio.sleep(0.1)
        raise RuntimeErrorSafe("runtime_start_timeout")

    async def _wait_backend(self, entry: _Instance, deadline: float) -> None:
        while time.monotonic() < deadline:
            if any(child.poll() is not None for child in entry.children):
                raise RuntimeErrorSafe("runtime_process_exited")
            if await _probe_backend(entry.backend):
                return
            await asyncio.sleep(0.1)
        raise RuntimeErrorSafe("runtime_start_timeout")

    @staticmethod
    async def _stop_child(child) -> None:
        if child.poll() is not None:
            # A reaped group leader does not establish that its tools are gone.
            # Do not signal a now-unverifiable group or erase its durable owner.
            if _group_retired(child.pid):
                return
            raise RuntimeErrorSafe("runtime_stop_unverified")
        try:
            if os.getpgid(child.pid) != child.pid:
                raise RuntimeErrorSafe("runtime_process_identity_changed")
            os.killpg(child.pid, signal.SIGTERM)
            try:
                await asyncio.to_thread(child.wait, timeout=4)
            except subprocess.TimeoutExpired:
                if child.poll() is None and os.getpgid(child.pid) == child.pid:
                    os.killpg(child.pid, signal.SIGKILL)
                await asyncio.to_thread(child.wait, timeout=2)
            for _ in range(10):
                if _group_retired(child.pid):
                    return
                await asyncio.sleep(0.05)
            raise RuntimeErrorSafe("runtime_stop_unverified")
        except ProcessLookupError:
            if child.poll() is None or not _group_retired(child.pid):
                raise RuntimeErrorSafe("runtime_stop_unverified") from None
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeErrorSafe("runtime_stop_unverified") from exc

    async def _dispose(self, entry: _Instance) -> None:
        self._assert_pool()
        for child in reversed(entry.children):
            await self._stop_child(child)
        _directory(entry.state, create=False)
        owner = entry.state / "owner.json"
        if json.loads(_read_private(owner)).get("instance") != self.instance:
            raise RuntimeErrorSafe("runtime_owner_changed")
        key = entry.state / "gateway.key"
        if key.exists() and _read_private(key).decode("ascii") == entry.backend.key:
            key.unlink()
        auth = entry.state / "auth.json"
        if auth.exists():
            record = read_runtime_auth_record(auth)
            if not isinstance(record, dict) or record.get("pid") not in {
                child.pid for child in entry.children
            }:
                raise RuntimeErrorSafe("runtime_auth_identity_invalid")
            auth.unlink()
        owner.unlink()
        self._audit(entry.user, "runtime_stopped")

    async def request_started(self, user_id: str, backend: Backend) -> str:
        """A mutating gateway request holds a birth ticket through its response."""
        user = self._user(user_id)
        async with self._lock:
            entry = self._instances.get(user)
            if user in self._plugin_frozen or entry is None or entry.backend != backend:
                raise RuntimeErrorSafe("runtime_generation_changed", 409)
            ticket = uuid4().hex
            self._request_tickets.setdefault(user, set()).add(ticket)
            return ticket

    async def request_finished(self, user_id: str, ticket: str) -> None:
        user = self._user(user_id)
        async with self._lock:
            self._request_tickets.setdefault(user, set()).discard(ticket)

    def _restart_identity(self, entry):
        self._assert_pool()
        owner = json.loads(_read_private(entry.state / "owner.json"))
        if (
            owner.get("instance") != self.instance
            or owner.get("user") != entry.user
            or owner.get("generation") != entry.generation
            or owner.get("pids") != [child.pid for child in entry.children]
            or _read_private(entry.state / "gateway.key").decode("ascii") != entry.backend.key
            or len(entry.children) != 2
            or any(child.poll() is not None for child in entry.children)
        ):
            raise RuntimeErrorSafe("runtime_restart_identity_unknown", 409)
        auth = read_runtime_auth_record(entry.state / "auth.json")
        if (
            auth.get("pid") != entry.children[0].pid
            or auth.get("source_commit") != PINNED_DSH_COMMIT
        ):
            raise RuntimeErrorSafe("runtime_restart_identity_unknown", 409)
        return auth

    async def _plugin_control(self, entry, action, body):
        from ..plugins.proof import sign

        path = f"/api/research/internal/plugin-runtime/{action}"
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        headers = sign(entry.backend.key, "POST", path, raw, entry.user, "manager")
        headers.update(
            {
                GATEWAY_HEADER: entry.backend.key,
                "Origin": entry.backend.url,
                "Content-Type": "application/json",
            }
        )
        async with httpx.AsyncClient(timeout=30, follow_redirects=False, trust_env=False) as client:
            response = await client.post(entry.backend.url + path, content=raw, headers=headers)
        if response.status_code != 200 or len(response.content) > 65536:
            raise RuntimeErrorSafe("runtime_restart_callback_unverified", 409)
        value = response.json()
        if not isinstance(value, dict):
            raise RuntimeErrorSafe("runtime_restart_callback_unverified", 409)
        return value

    async def _replace_dsh(self, entry, auth, *, allow_missing_auth=False):
        """Only the Pool's verified, idle DSH child; the Web child stays alive."""
        root = self.config.root / "users" / entry.user / "research-web"
        runtime_port = urlsplit("http://" + auth["authority"]).port
        web_port = urlsplit(entry.backend.url).port
        if runtime_port is None or web_port is None:
            raise RuntimeErrorSafe("runtime_restart_identity_unknown", 409)
        old = entry.children[0]
        owner = json.loads(_read_private(entry.state / "owner.json"))
        if (
            owner.get("instance") != self.instance
            or owner.get("generation") != entry.generation
            or owner.get("pids") != [child.pid for child in entry.children]
            or _read_private(entry.state / "gateway.key").decode("ascii") != entry.backend.key
        ):
            raise RuntimeErrorSafe("runtime_restart_identity_unknown", 409)
        await self._stop_child(old)
        if not _group_retired(old.pid):
            raise RuntimeErrorSafe("runtime_restart_retirement_unknown", 409)
        auth_path = entry.state / "auth.json"
        if auth_path.exists() or auth_path.is_symlink():
            current_auth = read_runtime_auth_record(auth_path)
            if current_auth.get("pid") != old.pid:
                raise RuntimeErrorSafe("runtime_auth_identity_invalid", 409)
            auth_path.unlink()
        elif not allow_missing_auth:
            raise RuntimeErrorSafe("runtime_auth_identity_invalid", 409)
        specs = build_process_specs(
            python=self.config.python,
            node=self.config.node,
            project_root=self.config.project,
            data_root=root,
            runtime_source=self.config.source,
            state_root=entry.state,
            web_host="127.0.0.1",
            web_port=web_port,
            runtime_port=runtime_port,
        )
        environment = self._environment(root, entry.state, web_port, runtime_port)
        environment.update(
            RWB_TENANT_GENERATION=entry.generation,
            RWB_TENANT_MANAGER_INSTANCE=self.instance,
            RWB_TENANT_USER=entry.user,
        )
        entry.children[0] = self._spawn(specs.runtime.command, environment)
        entry.backend = Backend(
            entry.backend.url, entry.backend.key, entry.generation, entry.children[0].pid
        )
        self._record(entry)
        deadline = time.monotonic() + START_TIMEOUT
        await self._wait_runtime(entry, runtime_port, root, deadline)
        await self._wait_plugin_guard(entry, root, deadline)
        return entry.children[0].pid

    async def _wait_plugin_guard(self, entry, root, deadline):
        path = root / "plugins/guard-state.json"
        while time.monotonic() < deadline:
            if entry.children[0].poll() is not None:
                raise RuntimeErrorSafe("runtime_process_exited")
            try:
                value = json.loads(_read_private(path))
                if (
                    value.get("pid") == entry.children[0].pid
                    and value.get("freeze_supported") is True
                ):
                    return
            except (OSError, ValueError, RuntimeErrorSafe):
                pass  # Only this newly spawned, owned DSH is polled until deadline.
            await asyncio.sleep(0.05)
        raise RuntimeErrorSafe("runtime_plugin_guard_unverified", 409)

    async def restart_runtime(
        self, user_id: str, expected: Backend, transaction_id: str | None = None
    ):
        """Freeze births, attest full idleness, replace own DSH, then commit.

        A missing/active/ambiguous participant is deferred without sending signals.
        Unknown recovery retains the fence and durable evidence for the operator.
        """
        user = self._user(user_id)
        operation = transaction_id or uuid4().hex
        async with self._lock:
            cache_key = (user, expected.generation, operation)
            if cache_key in self._restart_results:
                return dict(self._restart_results[cache_key])
            entry = self._instances.get(user)
            if entry is None or entry.backend != expected or user in self._plugin_frozen:
                return {"status": "unknown", "reason": "runtime_generation_changed"}
            if self._request_tickets.get(user):
                return {"status": "deferred", "reason": "requests_inflight"}
            try:
                auth = self._restart_identity(entry)
            except (OSError, ValueError, RuntimeErrorSafe, RuntimeAuthFileError):
                return {"status": "unknown", "reason": "runtime_identity_unverified"}
            self._plugin_frozen.add(user)
        body = {
            "generation": entry.generation,
            "manager_instance": self.instance,
            "freeze_id": uuid4().hex,
            "dsh_pid": entry.children[0].pid,
            "new_dsh_pid": None,
            "transaction_id": transaction_id,
        }
        journal = entry.state / "plugin-restart.json"
        from ..plugins.service import _atomic

        frozen, stopped, completed, rolled_back = False, False, False, False
        try:
            _atomic(journal, {"state": "freezing", **body})
            # The request can take effect even if its HTTP acknowledgement is
            # lost. From this boundary onward the backend may already be fenced.
            frozen = True
            reply = await self._plugin_control(entry, "freeze", body)
            if (
                reply.get("status") != "ready"
                or reply.get("freeze_id") != body["freeze_id"]
                or reply.get("dsh_pid") != body["dsh_pid"]
            ):
                if reply.get("status") == "deferred":
                    frozen = False
                    _atomic(journal, {"state": "deferred", **body})
                    return {"status": "deferred", "reason": reply.get("reason", "backend_not_idle")}
                raise RuntimeErrorSafe("runtime_restart_callback_unverified", 409)
            self._restart_identity(entry)  # PID/key/owner rechecked after awaited callback.
            _atomic(journal, {"state": "restarting", **body})
            stopped = True
            body["new_dsh_pid"] = await self._replace_dsh(entry, auth)
            reply = await self._plugin_control(entry, "commit", body)
            if reply.get("status") != "ready":
                raise RuntimeErrorSafe("runtime_restart_commit_unverified", 409)
            released = await self._plugin_control(entry, "unfreeze", body)
            if released.get("status") != "ready":
                raise RuntimeErrorSafe("runtime_restart_unfreeze_unverified", 409)
            frozen = False
            completed = True
            result = {
                "status": "ready",
                "transaction_id": transaction_id,
                "generation": entry.generation,
                "runtime_pid": entry.children[0].pid,
            }
            _atomic(journal, {"state": "committed", **body})
            self._restart_results[cache_key] = result
            self._audit(user, "plugin_runtime_restarted")
            return result
        except BaseException as exc:
            log.warning("tenant_plugin_restart_failed", error_type=type(exc).__name__)
            if frozen:
                try:
                    rollback_reply = await self._plugin_control(entry, "rollback", body)
                    if rollback_reply.get("status") != "rolled_back":
                        raise RuntimeErrorSafe("runtime_restart_rollback_unverified", 409)
                    if stopped:
                        # The same owned slot remains fenced; rollback restores
                        # active bindings before a replacement is allowed to run.
                        body["new_dsh_pid"] = await self._replace_dsh(
                            entry, auth, allow_missing_auth=True
                        )
                    released = await self._plugin_control(entry, "unfreeze", body)
                    if released.get("status") != "ready":
                        raise RuntimeErrorSafe("runtime_restart_unfreeze_unverified", 409)
                    frozen = False
                    rolled_back = True
                    _atomic(journal, {"state": "rolled_back", **body})
                except BaseException as recovery:  # noqa: BLE001
                    log.error(
                        "tenant_plugin_restart_recovery_unknown", error_type=type(recovery).__name__
                    )
                    _atomic(journal, {"state": "unknown", **body})
            if isinstance(exc, asyncio.CancelledError):
                raise
            if frozen:
                return {"status": "unknown", "reason": "restart_recovery_required"}
            if completed:
                return {"status": "unknown", "reason": "restart_receipt_unavailable"}
            return {
                "status": "deferred",
                "reason": "restart_rolled_back" if rolled_back else "restart_not_started",
            }
        finally:
            if not frozen:
                async with self._lock:
                    self._plugin_frozen.discard(user)
            if not completed:
                self._audit(user, "plugin_runtime_restart_deferred")

    async def stop(self, user_id: str) -> None:
        user = self._user(user_id)
        async with self._lock:
            if user in self._plugin_frozen:
                raise RuntimeErrorSafe("runtime_restart_deferred", 409)
            if entry := self._instances.get(user):
                cleanup = asyncio.create_task(self._dispose(entry))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await cleanup
                    del self._instances[user]
                    raise
                except (OSError, ValueError) as exc:
                    raise RuntimeErrorSafe("runtime_stop_unverified") from exc
                del self._instances[user]

    async def close(self) -> None:
        async with self._lock:
            if self._plugin_frozen:
                raise RuntimeErrorSafe("runtime_restart_in_progress", 409)
            if self._closed:
                return
            self._closing = True
            cleanup = asyncio.create_task(self._close_owned())
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup
                raise

    async def _close_owned(self) -> None:
        failures = []
        for user, entry in list(self._instances.items()):
            try:
                await self._dispose(entry)
                del self._instances[user]
            except (RuntimeErrorSafe, OSError, ValueError) as exc:
                failures.append(exc)
                log.error(
                    "multiuser_runtime_stop_failed",
                    code=getattr(exc, "code", "runtime_stop_unverified"),
                )
        if failures:
            raise RuntimeErrorSafe("runtime_shutdown_incomplete")
        self._closed = True
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None
