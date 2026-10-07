"""Owned Native Hot process lifecycle. Credentials stay in backend and private stdin."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import selectors
import signal
import socket
import re
import secrets
import subprocess
import time
import stat
try:
    import fcntl
except ImportError:
    fcntl = None
import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .hot import HotError, _node, _no_alias, _read, normalize, save_settings

log = logging.getLogger(__name__)


def rpc(port: int, owner: dict, key: str, operation: str) -> dict | list:
    request_id = str(uuid4())
    body = {"protocol": "rwb-hot/v1", "id": request_id, **owner, "op": operation, "params": {}, "sentAt": int(time.time() * 1000)}
    data = base64.urlsafe_b64encode(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()).decode().rstrip("=")
    proof = hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as peer:
            peer.sendall(json.dumps({"data": data, "proof": proof}).encode() + b"\n")
            received = b""
            while b"\n" not in received:
                chunk = peer.recv(65536)
                if not chunk or len(received) + len(chunk) > 1048576:
                    raise HotError("hot_rpc_incomplete")
                received += chunk
        frame = json.loads(received.split(b"\n")[0])
        expected = hmac.new(key.encode(), frame["data"].encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, frame["proof"]):
            raise HotError("hot_rpc_denied")
        result = json.loads(base64.urlsafe_b64decode(frame["data"] + "=" * (-len(frame["data"]) % 4)))
        if result.get("id") != request_id or result.get("protocol") != "rwb-hot/v1":
            raise HotError("hot_rpc_invalid")
        if not result.get("ok"):
            raise HotError("hot_rpc_unavailable")
        return result["result"]
    except HotError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise HotError("hot_rpc_unavailable") from None


class HotManager:
    """One project-owned process. Never stops a database or deletes a volume."""

    def __init__(self, project: Path, home: Path, credentials):
        self.project = project
        self.home = home
        self.credentials = credentials
        self.directory = home / "hot"
        self.state_path = self.directory / "process.json"
        self.service = "ResearchWorkbench.Hot." + hashlib.sha256(str(home).encode()).hexdigest()[:24]

    def _config(self) -> dict:
        record = _read(self.directory / "settings.json", private=True)
        if record.get("projectRoot") != str(self.project):
            raise HotError("hot_foreign_config")
        return normalize(self.project, record["config"])

    def _secret(self, account: str) -> str:
        try:
            value = self.credentials.get_password(self.service, account)
        except Exception:
            raise HotError("hot_credentials_unavailable") from None
        if not isinstance(value, str) or not value or len(value) > 4096:
            raise HotError("hot_credentials_missing")
        return value

    def _ensure_secret(self, account: str) -> str:
        try:
            value = self.credentials.get_password(self.service, account)
            if value is None:
                value = secrets.token_hex(32)
                self.credentials.set_password(self.service, account, value)
            if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
                raise HotError("hot_generated_secret_invalid")
            return value
        except HotError:
            raise
        except Exception:
            raise HotError("hot_credentials_unavailable") from None

    def setup(self, migration_user: str = "postgres", migration_account: str = "hot-migration-database") -> dict:
        with self._lock():
            if self._state() is not None:
                raise HotError("hot_setup_requires_stopped")
            config = self._config()
            self._dependencies()
            identity_path = self.directory / "identity.json"
            _no_alias(identity_path)
            if identity_path.exists():
                identity = _read(identity_path, private=True)
                if identity.get("projectRoot") != str(self.project):
                    raise HotError("hot_process_foreign")
            else:
                identity = {"projectRoot": str(self.project), "instanceId": str(uuid4())}
                descriptor = os.open(identity_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(descriptor, "w") as stream:
                    json.dump(identity, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
            controller_key = self._ensure_secret("rpc-controller")
            self._ensure_secret("rpc-reader")
            managed = config["database"]["mode"] == "managed"
            if managed:
                from .hot_postgres import ManagedPostgres

                admin_password = self._ensure_secret("hot-postgres-admin")
                server = ManagedPostgres(self.home, identity["instanceId"]).start(admin_password)
                config["database"].update({key: server[key] for key in ("host", "port")})
                worker_password = self._ensure_secret(config["database"]["secretRef"])
                controller_password = self._ensure_secret(config["database"]["controllerSecretRef"])
                migration_user = "postgres"
            else:
                admin_password = self._secret(migration_account)
                worker_password = self._secret(config["database"]["secretRef"])
                controller_password = self._secret(config["database"]["controllerSecretRef"])
            payload = {"config": config, "instanceId": identity["instanceId"], "controllerToken": controller_key,
                       "migrationUser": migration_user, "migrationPassword": admin_password,
                       "createRoles": managed, "workerPassword": worker_password, "controllerPassword": controller_password}
            try:
                result = subprocess.run([_node(), str(self.project / "services/hot/scripts/setup.ts")], input=json.dumps(payload),
                                        capture_output=True, text=True, timeout=60, cwd=self.project)
                value = json.loads(result.stdout)
                if result.returncode or value.get("state") != "configured":
                    phase = value.get("phase")
                    raise HotError("hot_setup_failed_" + phase if phase in ("input", "ownership", "roles", "migration", "identity", "queue", "grants") else "hot_setup_failed")
            except (OSError, ValueError, subprocess.SubprocessError):
                raise HotError("hot_setup_failed") from None
            saved = save_settings(self.project, self.home, config)
            if saved.get("logging") == "unavailable":
                raise HotError("hot_config_saved_log_unavailable")
            log.info("hot_setup_completed")
            return {"state": "configured", "databaseMode": config["database"]["mode"], "schema": config["database"]["schema"]}

    def _dependencies(self) -> None:
        package = self.project / "services" / "hot"
        expected = {"postgres": "3.4.9", "pg-boss": "12.34.0", "fast-xml-parser": "5.11.1"}
        try:
            ready = all(_read(package / "node_modules" / name / "package.json").get("version") == version for name, version in expected.items())
        except HotError:
            ready = False
        if ready:
            return
        npm = shutil.which("npm")
        if not npm:
            raise HotError("hot_dependency_installer_missing")
        environment = {key: value for key, value in os.environ.items() if key in {"HOME", "PATH", "TMPDIR", "TEMP", "TMP", "http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"}}
        environment["PATH"] = str(Path(_node()).parent) + os.pathsep + environment.get("PATH", "")
        try:
            result = subprocess.run([npm, "ci", "--ignore-scripts", "--no-fund", "--no-audit"], cwd=package,
                                    env=environment, capture_output=True, timeout=180)
            if result.returncode:
                raise HotError("hot_dependencies_failed")
        except (OSError, subprocess.SubprocessError):
            raise HotError("hot_dependencies_failed") from None
        log.info("hot_dependencies_installed")

    def _fingerprint(self, pid: int) -> str | None:
        try:
            result = subprocess.run(["ps", "-ww", "-p", str(pid), "-o", "stat=", "-o", "lstart=", "-o", "command="], capture_output=True, text=True, timeout=3)
            fields = result.stdout.strip().split(maxsplit=1)
            output = fields[1] if len(fields) == 2 and "Z" not in fields[0] else ""
            return output if result.returncode == 0 and output and "<defunct>" not in output else None
        except (OSError, subprocess.SubprocessError):
            raise HotError("hot_process_probe_failed") from None

    def _state(self) -> dict | None:
        _no_alias(self.state_path)
        if not self.state_path.exists():
            return None
        state = _read(self.state_path, private=True)
        if state.get("projectRoot") != str(self.project) or state.get("version") != 1:
            raise HotError("hot_process_foreign")
        if not isinstance(state.get("pid"), int) or state["pid"] <= 1 or not isinstance(state.get("fingerprint"), str):
            raise HotError("hot_process_invalid")
        current = self._fingerprint(state["pid"])
        if current is None:
            return None
        launch_id = state.get("launchId")
        expected = str(self.project / "services/hot/scripts/serve.ts")
        if not isinstance(launch_id, str) or not re.fullmatch(r"[0-9a-f]{32}", launch_id):
            raise HotError("hot_process_invalid")
        if current != state["fingerprint"] or not current.endswith(" " + expected + " " + launch_id):
            raise HotError("hot_process_identity_mismatch")
        return state

    def status(self) -> dict:
        state = self._state()
        if state is None:
            return {"state": "stopped"}
        value = rpc(state["port"], state["owner"], self._secret("rpc-reader"), "status")
        if not isinstance(value, dict):
            raise HotError("hot_rpc_invalid")
        return {"state": "initialized", "pid": state["pid"], **value}

    def sources(self) -> list:
        """Read source coverage without scheduling or launching collection."""
        state = self._state()
        if state is None:
            raise HotError("hot_service_stopped")
        value = rpc(state["port"], state["owner"], self._secret("rpc-reader"), "sources")
        if not isinstance(value, list):
            raise HotError("hot_rpc_invalid")
        return value

    @contextmanager
    def _lock(self):
        if fcntl is None:
            raise HotError("hot_platform_not_verified")
        path = self.directory / "lifecycle.lock"
        _no_alias(path)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise HotError("hot_lock_unsafe")
            deadline = time.monotonic() + 5
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise HotError("hot_lifecycle_busy") from None
                    time.sleep(0.05)
            yield
        finally:
            os.close(descriptor)

    def start(self) -> dict:
        with self._lock():
            return self._start()

    def archive(self, operation: str, directory: Path | None = None, target_database: str | None = None,
                migration_user: str = "postgres", migration_account: str = "hot-migration-database") -> dict:
        """Backup a stopped installation; restore only into another database's absent schema."""
        with self._lock():
            if self._state() is not None:
                raise HotError("hot_archive_requires_stopped")
            journal = self.directory / "archive-attempt.json"
            _no_alias(journal)
            if journal.exists() and _read(journal, private=True).get("state") in ("running", "outcome_unknown"):
                raise HotError("hot_archive_outcome_unknown")
            config = self._config()
            identity = _read(self.directory / "identity.json", private=True)
            if identity.get("projectRoot") != str(self.project):
                raise HotError("hot_process_foreign")
            if config["database"]["mode"] == "managed":
                from .hot_postgres import ManagedPostgres

                password = self._secret("hot-postgres-admin")
                server = ManagedPostgres(self.home, identity["instanceId"]).start(password)
                config["database"].update({key: server[key] for key in ("host", "port")})
                migration_user = "postgres"
            else:
                password = self._secret(migration_account)
            if operation == "backup":
                parent = self.home / config["retention"]["backupDirectory"]
                _no_alias(parent)
                parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                info = parent.stat()
                if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                    raise HotError("hot_archive_unsafe")
                directory = parent / ("backup-" + uuid4().hex)
            elif operation != "restore" or directory is None:
                raise HotError("hot_archive_input_invalid")
            _no_alias(directory)
            payload = {"operation": operation, "config": config, "instanceId": identity["instanceId"],
                       "controllerToken": self._secret("rpc-controller"), "directory": str(directory),
                       "targetDatabase": target_database, "migrationUser": migration_user,
                       "migrationPassword": password}
            attempt = {"version": 1, "state": "running", "operation": operation,
                       "targetDatabase": target_database, "directory": str(directory)}
            def record(state):
                attempt["state"] = state
                fd = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
                with os.fdopen(fd, "w") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                        raise HotError("hot_archive_journal_unsafe")
                    stream.truncate(0)
                    json.dump(attempt, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
            record("running")
            child = None
            try:
                child = subprocess.Popen([_node(), str(self.project / "services/hot/scripts/archive.ts")],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True, cwd=self.project, start_new_session=True)
                try:
                    output, _ = child.communicate(json.dumps(payload), timeout=240)
                except subprocess.TimeoutExpired:
                    child.send_signal(signal.SIGTERM)
                    try:
                        child.communicate(timeout=90)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.communicate(timeout=5)
                    record("outcome_unknown")
                    raise HotError("hot_archive_outcome_unknown") from None
                value = json.loads(output)
                if value.get("code") == "hot_archive_outcome_unknown":
                    record("outcome_unknown")
                    raise HotError("hot_archive_outcome_unknown")
                record("completed" if child.returncode == 0 else "failed")
                if child.returncode or value.get("state") not in ("backed_up", "restored_paused"):
                    phase = value.get("phase")
                    allowed = ("input", "tools", "backup", "verify", "target", "restore", "inventory")
                    raise HotError("hot_archive_failed_" + phase if phase in allowed else "hot_archive_failed")
            except (OSError, ValueError, subprocess.SubprocessError):
                record("outcome_unknown")
                raise HotError("hot_archive_outcome_unknown") from None
            except BaseException:
                # Ctrl-C must also cancel the independent Node session and wait for cleanup.
                if child is not None and child.poll() is None:
                    child.send_signal(signal.SIGTERM)
                    try:
                        child.communicate(timeout=90)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.communicate(timeout=5)
                    record("outcome_unknown")
                elif attempt["state"] == "running":
                    record("outcome_unknown")
                raise
            finally:
                if child is not None and child.poll() is None:
                    child.send_signal(signal.SIGTERM)
                    try:
                        child.communicate(timeout=90)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.communicate(timeout=5)
                    record("outcome_unknown")
            log.info("hot_archive_completed operation=%s", operation)
            return value

    def _start(self) -> dict:
        if os.name != "posix":
            raise HotError("hot_platform_not_verified")
        if self._state() is not None:
            return self.status()
        config = self._config()
        if not config["enabled"]:
            raise HotError("hot_disabled")
        identity = _read(self.directory / "identity.json", private=True)
        if identity.get("projectRoot") != str(self.project):
            raise HotError("hot_process_foreign")
        if config["database"]["mode"] == "managed":
            from .hot_postgres import ManagedPostgres

            server = ManagedPostgres(self.home, identity["instanceId"]).start(self._secret("hot-postgres-admin"))
            actual = {key: server[key] for key in ("host", "port")}
            if any(config["database"][key] != value for key, value in actual.items()):
                config["database"].update(actual)
                save_settings(self.project, self.home, config)
        payload = {"config": config, "instanceId": identity["instanceId"], "mode": "native",
                   "workerPassword": self._secret(config["database"]["secretRef"]),
                   "controllerUser": config["database"]["controllerUser"],
                   "controllerPassword": self._secret(config["database"]["controllerSecretRef"]),
                   "controllerToken": self._secret("rpc-controller"), "readerToken": self._secret("rpc-reader")}
        launch_id = uuid4().hex
        path = self.project / "logs" / "hot" / "runtime.log"
        _no_alias(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        child = None
        try:
            with os.fdopen(descriptor, "wb") as errors:
                info = os.fstat(errors.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                    raise HotError("hot_log_unsafe")
                child = subprocess.Popen([_node(), str(self.project / "services/hot/scripts/serve.ts"), launch_id],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                                         cwd=self.project, start_new_session=True)
                packet = json.dumps(payload).encode()
                if len(packet) > 65536:
                    raise HotError("hot_bootstrap_limit")
                os.set_blocking(child.stdin.fileno(), False)
                os.set_blocking(child.stdout.fileno(), False)
                written = 0
                received = b""
                deadline = time.monotonic() + 15
                with selectors.DefaultSelector() as selector:
                    selector.register(child.stdout, selectors.EVENT_READ)
                    selector.register(child.stdin, selectors.EVENT_WRITE)
                    while b"\n" not in received:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise HotError("hot_start_timeout")
                        events = selector.select(remaining)
                        if not events:
                            raise HotError("hot_start_timeout")
                        for selected, _ in events:
                            if selected.fileobj is child.stdin:
                                try:
                                    written += os.write(child.stdin.fileno(), packet[written:])
                                except BlockingIOError:
                                    continue
                                if written == len(packet):
                                    selector.unregister(child.stdin)
                                    child.stdin.close()
                            else:
                                chunk = os.read(child.stdout.fileno(), 4096)
                                if not chunk or len(received) + len(chunk) > 65536:
                                    raise HotError("hot_start_failed")
                                received += chunk
                    ready = json.loads(received.split(b"\n")[0])
                if ready.get("state") != "initialized" or ready.get("pid") != child.pid or ready.get("launchId") != launch_id:
                    raise HotError("hot_start_failed")
                state = {"version": 1, "projectRoot": str(self.project), "pid": child.pid, "port": ready["port"],
                         "owner": ready["owner"], "launchId": launch_id, "fingerprint": self._fingerprint(child.pid)}
                temporary = self.directory / ("process-" + uuid4().hex + ".tmp")
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "w") as output:
                    json.dump(state, output)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.state_path)
                result = self.status()
                child.stdout.close()
                log.info("hot_process_started")
                return result
        except BaseException:
            if child is not None:
                child.kill()
                child.wait(timeout=5)
            raise HotError("hot_start_failed") from None

    def stop(self) -> dict:
        if not self.directory.exists():
            return {"state": "stopped"}
        with self._lock():
            return self._stop()

    def _stop(self) -> dict:
        state = self._state()
        if state is None:
            return {"state": "stopped"}
        os.kill(state["pid"], signal.SIGTERM)
        for _ in range(100):
            current = self._fingerprint(state["pid"])
            if current is None:
                log.info("hot_process_stopped")
                return {"state": "stopped"}
            # Exiting argv may briefly change before the PID vanishes. Do not signal
            # a changed identity; only observe until the bounded escalation recheck.
            time.sleep(0.05)
        # Revalidate the exact original process immediately before escalation.
        final = self._fingerprint(state["pid"])
        if final is None:
            log.info("hot_process_stopped")
            return {"state": "stopped"}
        if final != state["fingerprint"]:
            raise HotError("hot_process_identity_mismatch")
        os.kill(state["pid"], signal.SIGKILL)
        raise HotError("hot_stop_requires_recheck")

    def restart(self) -> dict:
        with self._lock():
            self._stop()
            return self._start()
