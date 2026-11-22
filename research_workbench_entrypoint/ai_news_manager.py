"""Explicit local AI news lifecycle. Status and Doctor never start resources."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import signal
import socket
import stat
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from .ai_news_postgres import AiNewsPostgres
from .ai_news_transport import AiNewsConnection, AiNewsError, private_bytes, private_json, safe_path
from .hot import _node

log = logging.getLogger(__name__)
UPSTREAM_COMMIT = "26d436497d9ddba9e7dd88eed255cfe0105ce368"


def installation_facts(project: Path) -> dict:
    """Read only source bytes and installed package manifests, never config or secrets."""
    root = project / "services/ai_news"
    vendor = root / "vendor/aihot"
    facts = {
        "upstreamCommit": UPSTREAM_COMMIT,
        "pinIntegrity": False,
        "dependenciesInstalled": False,
        "upstreamFiles": 0,
    }
    try:
        manifest = json.loads((root / "upstream.json").read_bytes())
        expected = manifest["files"]
        if (
            manifest.get("commit") != UPSTREAM_COMMIT
            or manifest.get("license") != "MIT"
            or manifest.get("upstream") != "https://github.com/KKKKhazix/AIHOT"
            or not isinstance(expected, dict)
            or len(expected) != 652
        ):
            raise AiNewsError("ai_news_pin_invalid")
        observed = set()
        for directory, dirs, files in os.walk(vendor, followlinks=False):
            dirs[:] = [name for name in dirs if name != "node_modules"]
            for name in dirs:
                safe_path(Path(directory) / name)
            for name in files:
                path = Path(directory) / name
                safe_path(path)
                relative = path.relative_to(vendor).as_posix()
                if relative not in expected:
                    raise AiNewsError("ai_news_pin_invalid")
                with path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != expected[relative]:
                        raise AiNewsError("ai_news_pin_invalid")
                observed.add(relative)
        if observed != set(expected):
            raise AiNewsError("ai_news_pin_invalid")
        facts["pinIntegrity"] = True
        facts["upstreamFiles"] = len(observed)
        lock = json.loads((vendor / "package-lock.json").read_bytes())
        if (
            lock.get("lockfileVersion") != 3
            or not (vendor / "node_modules/.package-lock.json").is_file()
        ):
            return facts
        for name in ("fastify", "postgres", "pg-boss", "zod"):
            path = vendor / "node_modules" / name / "package.json"
            safe_path(path)
            installed = json.loads(path.read_bytes())
            if (
                installed.get("name") != name
                or installed.get("version") != lock["packages"]["node_modules/" + name]["version"]
            ):
                return facts
        facts["dependenciesInstalled"] = True
    except (AiNewsError, OSError, ValueError, TypeError, KeyError):
        log.warning("ai_news_installation_files_invalid")
    return facts


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _fingerprint(pid: int) -> str | None:
    if type(pid) is not int or pid <= 1:
        raise AiNewsError("ai_news_process_identity_invalid")
    try:
        value = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat=,lstart=,command="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if value.returncode == 1 and not value.stdout.strip():
            return None
        if value.returncode or not value.stdout.strip():
            raise AiNewsError("ai_news_process_check_failed")
        if value.stdout.strip().split()[0].startswith("Z"):
            return None
        # Process state changes (R/S) are liveness observations, never identity.
        return hashlib.sha256(value.stdout.strip().split(maxsplit=1)[1].encode()).hexdigest()
    except (OSError, subprocess.SubprocessError):
        raise AiNewsError("ai_news_process_check_failed") from None


def _owned_group_live(group: int) -> bool:
    """Every live member must remain in the session created for this Popen child."""
    value = subprocess.run(
        ["ps", "-axo", "pid=,pgid=,stat="], capture_output=True, text=True, timeout=5, check=False
    )
    if value.returncode or len(value.stdout) > 262144:
        raise AiNewsError("ai_news_command_group_unverified")
    live = False
    for line in value.stdout.splitlines():
        parts = line.split()
        if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
            raise AiNewsError("ai_news_command_group_unverified")
        if int(parts[1]) != group or parts[2].startswith("Z"):
            continue
        pid = int(parts[0])
        try:
            if os.getpgid(pid) != group or os.getsid(pid) != group:
                raise AiNewsError("ai_news_command_group_unverified")
        except ProcessLookupError:
            continue
        live = True
    return live


def _terminate_command_tree(proc, group: int, *, grace: float = 2):
    """The direct Popen child stays unreaped until its private process group is empty."""
    if (
        os.name != "posix"
        or group != proc.pid
        or proc.returncode is not None
        or os.getpgid(proc.pid) != group
        or os.getsid(proc.pid) != group
    ):
        raise AiNewsError("ai_news_command_group_unverified")
    for signum in (signal.SIGTERM, signal.SIGKILL):
        if not _owned_group_live(group):
            proc.wait(timeout=2)
            return
        # The unreaped direct child pins this numeric group/session identity against reuse.
        os.killpg(group, signum)
        deadline = time.monotonic() + grace
        while _owned_group_live(group):
            if time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        else:
            proc.wait(timeout=2)
            return
    raise AiNewsError("ai_news_command_cleanup_timeout")


def _write(path: Path, value: bytes, *, exclusive=False):
    safe_path(path)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
        flags |= os.O_EXCL if exclusive else 0
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise AiNewsError("ai_news_storage_unsafe")
            stream.truncate()
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        log.error("ai_news_private_write_failed")
        raise AiNewsError("ai_news_storage_write_failed") from None


def _json(path, value, **kwargs):
    data = json.dumps(value, sort_keys=True).encode()
    if kwargs.get("exclusive"):
        _write(path, data, exclusive=True)
        return
    safe_path(path)
    original = None
    if path.exists():
        private_bytes(path)
        info = path.stat()
        original = (info.st_dev, info.st_ino)
    temporary = path.with_name("." + path.name + "." + uuid4().hex + ".tmp")
    _write(temporary, data, exclusive=True)
    if path.exists():
        current = path.lstat()
        if (current.st_dev, current.st_ino) != original:
            raise AiNewsError("ai_news_storage_changed")
    elif original is not None:
        raise AiNewsError("ai_news_storage_changed")
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


class AiNewsManager:
    """Owns an isolated database, API and worker; never adopts unknown processes."""

    def __init__(self, project: Path, home: Path, credentials=None, *, database_name="rwb_ai_news"):
        self.project = Path(project).absolute()
        self.home = Path(home).absolute()
        self.directory = self.home / "ai-news"
        self.config_path = self.directory / "bootstrap.json"
        self.identity_path = self.directory / "identity.json"
        self.state_path = self.directory / "processes.json"
        self.setup_path = self.directory / "setup.json"
        self.restore_path = self.directory / "restore.json"
        self.runtime = self.project / "services/ai_news/runtime.mjs"
        self.credentials = credentials
        if database_name not in {"rwb_ai_news", "rwb_ai_news_test"}:
            raise AiNewsError("ai_news_database_name_invalid")
        self.database_name = database_name

    def _database(self):
        return AiNewsPostgres(self.home, self._identity()["instanceId"], self.database_name)

    def _directories(self):
        safe_path(self.directory)
        for path in (self.directory, self.directory / "secrets", self.directory / "logs"):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = path.stat()
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise AiNewsError("ai_news_storage_unsafe")

    @contextmanager
    def _lock(self):
        from app.research_web.lifecycle_lock import LifecycleLock, LifecycleLockError

        try:
            with LifecycleLock(
                self.directory / "lifecycle.lock", _alive, trusted_root=self.directory
            ):
                if (self.directory / "command-recovery.json").exists():
                    raise AiNewsError("ai_news_command_recovery_required")
                yield
        except LifecycleLockError:
            log.warning("ai_news_lifecycle_busy")
            raise AiNewsError("ai_news_lifecycle_busy") from None

    def _identity(self):
        value = private_json(self.identity_path)
        if (
            value.get("projectRoot") != str(self.project)
            or value.get("home") != str(self.home)
            or str(UUID(value.get("instanceId", ""))) != value.get("instanceId")
            or value.get("databaseName") not in {"rwb_ai_news", "rwb_ai_news_test"}
        ):
            raise AiNewsError("ai_news_foreign_identity")
        return value

    def connection(self) -> AiNewsConnection:
        identity = self._identity()
        config = private_json(self.config_path)
        port = config.get("port")
        if type(port) is not int or not 1024 <= port <= 65535:
            raise AiNewsError("ai_news_config_invalid")
        token_file = self.directory / "secrets/token"
        if config.get("tokenFile") != str(token_file) or config.get("dataDir") != str(
            self.directory
        ):
            raise AiNewsError("ai_news_foreign_config")
        database = config.get("database", {})
        if (
            database.get("host") != "127.0.0.1"
            or database.get("name") != identity["databaseName"]
            or database.get("user") != "postgres"
            or database.get("passwordFile") != str(self.directory / "secrets/database")
            or type(database.get("port")) is not int
            or not 1 <= database["port"] <= 65535
        ):
            raise AiNewsError("ai_news_foreign_database")
        for field, account in (
            ("adminPasswordFile", "admin"),
            ("sessionSecretFile", "session"),
            ("imageSecretFile", "image"),
        ):
            if config.get(field) != str(self.directory / "secrets" / account):
                raise AiNewsError("ai_news_foreign_config")
        return AiNewsConnection(f"http://127.0.0.1:{port}", token_file)

    def _command(self, action):
        if action not in {"api", "worker", "migrate", "seed", "doctor", "stage"}:
            raise AiNewsError("ai_news_action_invalid")
        return [_node(), str(self.runtime), action, "--config", str(self.config_path)]

    def _run(self, action, *, timeout: float = 120):
        recovery_path = self.directory / "command-recovery.json"
        if recovery_path.exists():
            raise AiNewsError("ai_news_command_recovery_required")
        if os.name != "posix":
            raise AiNewsError("ai_news_command_platform_not_verified")
        proc = None
        try:
            proc = subprocess.Popen(
                self._command(action),
                cwd=self.project,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self._environment(),
                start_new_session=True,
            )
            proc.wait(timeout=timeout)
            if proc.returncode:
                raise AiNewsError("ai_news_" + action + "_failed")
            log.info("ai_news_command_completed action=%s", action)
        except subprocess.TimeoutExpired:
            if proc is None:
                raise AiNewsError("ai_news_command_failed") from None
            try:
                _terminate_command_tree(proc, proc.pid)
            except (AiNewsError, OSError, subprocess.SubprocessError):
                _json(
                    recovery_path,
                    {
                        "version": 1,
                        "action": action,
                        "pid": proc.pid,
                        "pgid": proc.pid,
                        "state": "cleanup_blocked",
                    },
                )
                log.error("ai_news_command_cleanup_blocked action=%s", action)
                raise AiNewsError("ai_news_command_recovery_required") from None
            log.warning("ai_news_command_timeout_cleaned action=%s", action)
            raise AiNewsError("ai_news_command_timeout") from None
        except (OSError, subprocess.SubprocessError):
            if proc is not None and proc.returncode is None:
                try:
                    _terminate_command_tree(proc, proc.pid)
                except (AiNewsError, OSError, subprocess.SubprocessError):
                    _json(
                        recovery_path,
                        {
                            "version": 1,
                            "action": action,
                            "pid": proc.pid,
                            "pgid": proc.pid,
                            "state": "cleanup_blocked",
                        },
                    )
                    log.error("ai_news_command_cleanup_blocked action=%s", action)
                    raise AiNewsError("ai_news_command_recovery_required") from None
            raise AiNewsError("ai_news_command_failed") from None

    @staticmethod
    def _environment():
        # Vendor must never inherit ambient paid API/model credentials or proxy settings.
        allowed = {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT"}
        return {key: value for key, value in os.environ.items() if key in allowed}

    def _states(self):
        if not self.state_path.exists():
            return []
        value = private_json(self.state_path)
        identity = self._identity()
        if value.get("instanceId") != identity["instanceId"] or not isinstance(
            value.get("processes"), list
        ):
            raise AiNewsError("ai_news_process_foreign")
        for row in value["processes"]:
            if (
                set(row) != {"pid", "fingerprint", "role"}
                or row["role"] not in {"api", "worker"}
                or not isinstance(row["fingerprint"], str)
            ):
                raise AiNewsError("ai_news_process_foreign")
            observed = _fingerprint(row["pid"])
            if observed is not None and observed != row["fingerprint"]:
                raise AiNewsError("ai_news_process_foreign")
        return value["processes"]

    def status(self):
        if not self.identity_path.exists():
            return {
                "configured": False,
                "state": "not_configured",
                "modelCallsEnabled": False,
                "productionDeployed": False,
            }
        try:
            if (self.directory / "command-recovery.json").exists():
                return {
                    "configured": False,
                    "state": "blocked",
                    "code": "ai_news_command_recovery_required",
                    "modelCallsEnabled": False,
                    "productionDeployed": False,
                }
            if self.setup_path.exists():
                setup = self._setup_journal()
                if setup["phase"] != "complete":
                    return {
                        "configured": False,
                        "state": "setup_incomplete",
                        "phase": setup["phase"],
                        "modelCallsEnabled": False,
                        "productionDeployed": False,
                    }
            self.connection().headers()
            states = self._states()
            running = [row["role"] for row in states if _fingerprint(row["pid"]) is not None]
            return {
                "configured": True,
                "state": (
                    "running"
                    if set(running) == {"api", "worker"}
                    else "degraded" if running else "stopped"
                ),
                "processes": running,
                "modelCallsEnabled": False,
                "productionDeployed": False,
            }
        except (AiNewsError, ValueError, TypeError, KeyError):
            log.warning("ai_news_status_invalid")
            return {
                "configured": False,
                "state": "invalid",
                "code": "ai_news_identity_invalid",
                "modelCallsEnabled": False,
                "productionDeployed": False,
            }

    def doctor(self):
        result = self.status()
        result.update(installation_facts(self.project))
        result["runtimeAvailable"] = self.runtime.is_file()
        result["modelAcceptance"] = "NOT_RUN"
        result["readOnly"] = True
        return result

    def setup(self, *, authorized=False):
        if not authorized:
            raise AiNewsError("ai_news_setup_authorization_required")
        if self.credentials is None:
            raise AiNewsError("ai_news_credential_backend_required")
        self._directories()
        with self._lock():
            if self.setup_path.exists():
                journal = self._setup_journal()
                if journal["phase"] == "complete":
                    raise AiNewsError("ai_news_already_configured")
                identity = journal["identity"]
                if not self.identity_path.exists():
                    if journal["phase"] != "identity":
                        raise AiNewsError("ai_news_setup_identity_missing")
                    _json(self.identity_path, identity, exclusive=True)
                if self._identity() != identity:
                    raise AiNewsError("ai_news_setup_foreign")
                if any(_fingerprint(row["pid"]) is not None for row in self._states()):
                    raise AiNewsError("ai_news_setup_requires_stopped")
            else:
                if self.identity_path.exists() or self.config_path.exists():
                    raise AiNewsError("ai_news_already_configured")
                identity = {
                    "projectRoot": str(self.project),
                    "home": str(self.home),
                    "instanceId": str(uuid4()),
                    "databaseName": self.database_name,
                }
                journal = {"version": 1, "identity": identity, "phase": "identity"}
                _json(self.setup_path, journal, exclusive=True)
                _json(self.identity_path, identity, exclusive=True)
            journal["phase"] = "secrets"
            _json(self.setup_path, journal)
            service = (
                "ResearchWorkbench.AiNews."
                + hashlib.sha256(str(self.home).encode()).hexdigest()[:24]
            )
            try:
                backend = self.credentials() if callable(self.credentials) else self.credentials
            except Exception:  # noqa: BLE001
                log.error("ai_news_credential_backend_failed")
                raise AiNewsError("ai_news_credentials_unavailable") from None
            for account in ("token", "database", "admin", "session", "image"):
                try:
                    secret = backend.get_password(service, account)
                    if secret is None:
                        secret = secrets.token_hex(32)
                        backend.set_password(service, account, secret)
                    if not isinstance(secret, str) or len(secret) < 32 or len(secret) > 4096:
                        raise AiNewsError("ai_news_secret_invalid")
                    path = self.directory / "secrets" / account
                    if path.exists():
                        if not secrets.compare_digest(private_bytes(path), secret.encode()):
                            raise AiNewsError("ai_news_secret_changed")
                    else:
                        _write(path, secret.encode(), exclusive=True)
                except AiNewsError:
                    raise
                except Exception:  # noqa: BLE001
                    log.error("ai_news_credential_backend_failed")
                    raise AiNewsError("ai_news_credentials_unavailable") from None
            with socket.socket() as peer:
                peer.bind(("127.0.0.1", 0))
                port = peer.getsockname()[1]
            journal["phase"] = "database"
            _json(self.setup_path, journal)
            database = self._database().start()
            database["passwordFile"] = str(self.directory / "secrets/database")
            config = {
                "port": port,
                "dataDir": str(self.directory),
                "database": database,
                "tokenFile": str(self.directory / "secrets/token"),
                "adminPasswordFile": str(self.directory / "secrets/admin"),
                "sessionSecretFile": str(self.directory / "secrets/session"),
                "imageSecretFile": str(self.directory / "secrets/image"),
            }
            if self.config_path.exists():
                self.connection().headers()
                previous = private_json(self.config_path)
                config["port"] = previous["port"]
                _json(self.config_path, config)
            else:
                _json(self.config_path, config, exclusive=True)
            journal["phase"] = "migrate"
            _json(self.setup_path, journal)
            self._run("migrate")
            journal["phase"] = "seed"
            _json(self.setup_path, journal)
            self._run("seed")
            journal["phase"] = "complete"
            _json(self.setup_path, journal)
            log.info("ai_news_setup_completed")
            return self.status()

    def _setup_journal(self):
        journal = private_json(self.setup_path)
        identity = journal.get("identity", {})
        if (
            journal.get("version") != 1
            or journal.get("phase")
            not in {"identity", "secrets", "database", "migrate", "seed", "complete"}
            or identity.get("projectRoot") != str(self.project)
            or identity.get("home") != str(self.home)
            or identity.get("databaseName") != self.database_name
            or str(UUID(identity.get("instanceId", ""))) != identity.get("instanceId")
        ):
            raise AiNewsError("ai_news_setup_foreign")
        return journal

    def _healthy(self):
        connection = self.connection()
        request = urllib.request.Request(
            connection.endpoint + "/internal/rwb/status", headers=connection.headers()
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        try:
            with opener.open(request, timeout=2) as response:
                data = response.read(65537)
                if len(data) > 65536:
                    raise AiNewsError("ai_news_health_invalid")
                value = json.loads(data)
            if (
                not isinstance(value, dict)
                or value.get("ok") is not True
                or value.get("modelCallsEnabled") is not False
            ):
                raise AiNewsError("ai_news_health_invalid")
            return value
        except (OSError, ValueError, urllib.error.URLError):
            raise AiNewsError("ai_news_not_ready") from None

    def start(self):
        self.connection().headers()
        with self._lock():
            states = self._states()
            if any(_fingerprint(row["pid"]) is not None for row in states):
                raise AiNewsError("ai_news_already_running")
            identity = self._identity()
            database = self._database().start()
            config = private_json(self.config_path)
            config["database"].update(database)
            _json(self.config_path, config)
            self._run("stage")
            states = []
            spawned = []
            try:
                for role in ("api", "worker"):
                    path = self.directory / "logs" / (role + ".log")
                    safe_path(path)
                    descriptor = os.open(
                        path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600
                    )
                    with os.fdopen(descriptor, "ab") as stream:
                        proc = subprocess.Popen(
                            self._command(role),
                            cwd=self.project,
                            stdout=stream,
                            stderr=stream,
                            env=self._environment(),
                            start_new_session=True,
                        )
                        spawned.append(proc)
                    fingerprint = _fingerprint(proc.pid)
                    if fingerprint is None:
                        raise AiNewsError("ai_news_start_failed")
                    states.append({"pid": proc.pid, "fingerprint": fingerprint, "role": role})
                    _json(
                        self.state_path, {"instanceId": identity["instanceId"], "processes": states}
                    )
                deadline = time.monotonic() + 30
                while True:
                    try:
                        self._healthy()
                        if not all(
                            _fingerprint(row["pid"]) == row["fingerprint"] for row in states
                        ):
                            raise AiNewsError("ai_news_worker_failed")
                        break
                    except AiNewsError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.2)
                log.info("ai_news_started")
            except (AiNewsError, OSError):
                self._stop_spawned(spawned)
                log.error("ai_news_start_failed")
                raise AiNewsError("ai_news_start_failed") from None
        return self.status()

    @staticmethod
    def _stop_spawned(spawned):
        # These are unreaped Popen handles created in this invocation, not recovered PIDs.
        # poll/wait retain child ownership even if fingerprint or journal persistence failed.
        failed = False
        for proc in reversed(spawned):
            try:
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=15)
            except (OSError, subprocess.SubprocessError):
                failed = True
                log.error("ai_news_spawn_cleanup_failed")
        if failed:
            raise AiNewsError("ai_news_spawn_cleanup_failed")

    def _stop_processes(self, states):
        for row in reversed(states):
            observed = _fingerprint(row["pid"])
            if observed is not None:
                if observed != row["fingerprint"]:
                    raise AiNewsError("ai_news_process_foreign")
                os.kill(row["pid"], signal.SIGTERM)
        deadline = time.monotonic() + 15
        while any(_fingerprint(row["pid"]) == row["fingerprint"] for row in states):
            if time.monotonic() >= deadline:
                raise AiNewsError("ai_news_stop_timeout")
            time.sleep(0.1)

    def stop(self):
        self._identity()
        with self._lock():
            self._stop_processes(self._states())
            self._database().stop()
            log.info("ai_news_stopped")
        return self.status()

    def backup(self, destination: Path):
        """Custom pg_dump archive; credentials and token files never enter backup."""
        self._identity()
        with self._lock():
            database = self._database()
            row = database.inspect()
            safe_path(destination)
            descriptor = os.open(
                destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    result = subprocess.run(
                        [
                            "docker",
                            "exec",
                            row["Id"],
                            "pg_dump",
                            "-U",
                            "postgres",
                            "-d",
                            self.database_name,
                            "-Fc",
                        ],
                        stdout=stream,
                        stderr=subprocess.PIPE,
                        timeout=120,
                        check=False,
                    )
                    stream.flush()
                    os.fsync(stream.fileno())
                if result.returncode:
                    raise AiNewsError("ai_news_backup_failed")
                with destination.open("rb") as source:
                    digest = hashlib.file_digest(source, "sha256").hexdigest()
                _json(
                    destination.with_suffix(destination.suffix + ".json"),
                    {"sha256": digest, "kind": "rwb-ai-news-pg-dump/v1"},
                    exclusive=True,
                )
                log.info("ai_news_backup_completed")
                return {"ok": True, "sha256": digest}
            except (OSError, subprocess.SubprocessError):
                log.error("ai_news_backup_failed")
                raise AiNewsError("ai_news_backup_failed") from None

    def restore(self, source: Path, *, authorized=False):
        if not authorized:
            raise AiNewsError("ai_news_restore_authorization_required")
        self._identity()
        with self._lock():
            if any(_fingerprint(row["pid"]) is not None for row in self._states()):
                raise AiNewsError("ai_news_restore_requires_stopped")
            metadata = private_json(source.with_suffix(source.suffix + ".json"))
            safe_path(source)
            descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600
                ):
                    raise AiNewsError("ai_news_backup_invalid")
                if metadata.get("kind") != "rwb-ai-news-pg-dump/v1" or hashlib.file_digest(
                    stream, "sha256"
                ).hexdigest() != metadata.get("sha256"):
                    raise AiNewsError("ai_news_backup_invalid")
                stream.seek(0)
                database = self._database()
                database.start()
                row = database.inspect()
                if self.restore_path.exists():
                    previous = private_json(self.restore_path)
                    if previous.get("phase") not in {"complete", "failed"}:
                        raise AiNewsError("ai_news_restore_outcome_unknown")
                token = uuid4().hex[:12]
                staging = "rwb_ai_news_restore_" + token + "_test"
                retained = "rwb_ai_news_previous_" + token + "_test"
                journal = {
                    "instanceId": self._identity()["instanceId"],
                    "phase": "preparing",
                    "database": self.database_name,
                    "staging": staging,
                    "retained": retained,
                    "sha256": metadata["sha256"],
                }
                _json(self.restore_path, journal)
                database.call(
                    ["exec", row["Id"], "createdb", "-U", "postgres", "-T", "template0", staging]
                )
                journal["phase"] = "restoring"
                _json(self.restore_path, journal)
                try:
                    result = subprocess.run(
                        [
                            "docker",
                            "exec",
                            "-i",
                            row["Id"],
                            "pg_restore",
                            "-U",
                            "postgres",
                            "-d",
                            staging,
                            "--no-owner",
                            "--no-privileges",
                            "--single-transaction",
                            "--exit-on-error",
                        ],
                        stdin=stream,
                        capture_output=True,
                        timeout=120,
                        check=False,
                    )
                    if result.returncode:
                        journal["phase"] = "failed"
                        _json(self.restore_path, journal)
                        raise AiNewsError("ai_news_restore_failed")
                except (OSError, subprocess.SubprocessError):
                    journal["phase"] = "failed"
                    _json(self.restore_path, journal)
                    raise AiNewsError("ai_news_restore_failed") from None
                journal["phase"] = "cutover"
                _json(self.restore_path, journal)
                # This connects to postgres, never either renamed database. The original is retained.
                # RENAME refuses active connections; there is no pg_terminate_backend call.
                query = (
                    "BEGIN; ALTER DATABASE "
                    + self.database_name
                    + " RENAME TO "
                    + retained
                    + "; ALTER DATABASE "
                    + staging
                    + " RENAME TO "
                    + self.database_name
                    + "; COMMIT;"
                )
                database.call(
                    [
                        "exec",
                        row["Id"],
                        "psql",
                        "-U",
                        "postgres",
                        "-d",
                        "postgres",
                        "-v",
                        "ON_ERROR_STOP=1",
                        "-c",
                        query,
                    ]
                )
                journal["phase"] = "complete"
                _json(self.restore_path, journal)
            log.info("ai_news_restore_completed")
            return {"ok": True, "previousDatabaseRetained": True}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AiNewsError("ai_news_redirect_denied")
