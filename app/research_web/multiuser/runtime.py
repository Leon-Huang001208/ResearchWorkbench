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


@dataclass
class _Instance:
    user: str
    state: Path
    backend: Backend
    children: list


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


def _reserve_port() -> socket.socket:
    reserved = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        reserved.bind(("127.0.0.1", 0))
        return reserved
    except BaseException:
        reserved.close()
        raise


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

    def __init__(self, config: RuntimeConfig):
        if type(config.max_instances) is not int or not 1 <= config.max_instances <= 2:
            raise RuntimeErrorSafe("runtime_capacity_invalid", 400)
        if any(
            not Path(value).is_absolute()
            for value in (config.root, config.project, config.source, config.python, config.node)
        ):
            raise RuntimeErrorSafe("runtime_configuration_invalid", 400)
        self.config, self.instance = config, uuid4().hex
        self._lock = asyncio.Lock()
        self._instances: dict[str, _Instance] = {}
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
            "RESEARCH_AUTOMATIONS_ENABLED": "0",
            "RESEARCH_MCP_RUNTIME_ENABLED": "0",
        }

    async def backend_for(self, user_id: str) -> Backend:
        user = self._user(user_id)
        async with self._lock:
            if self._closed or self._closing:
                raise RuntimeErrorSafe("runtime_pool_closed")
            self._assert_pool()
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
            sockets = [_reserve_port(), _reserve_port()]
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
            self._audit(user, "runtime_starting")
            sockets[1].close()
            entry.children.append(self._spawn(specs.runtime.command, environment))
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

    async def stop(self, user_id: str) -> None:
        user = self._user(user_id)
        async with self._lock:
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
