"""Native keyring or explicitly configured, private Linux-container credentials.

Model API keys remain DSH-owned. This backend never imports or migrates them.
Native Windows uses keyring; POSIX modes cannot establish Windows mount ACLs.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import stat
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from threading import RLock
from typing import Protocol

from .runtime_state import runtime_state_directory

# The Host configures these same standard handlers into logs/. The isolated
# model bridge must not import global settings or create unrelated directories.
log = logging.getLogger(__name__)
_PLATFORM_NAME = os.name
MAX_VALUE_BYTES = 64 * 1024
MAX_RECORD_BYTES = MAX_VALUE_BYTES * 6 + 64
_LOCK_TIMEOUT_SECONDS = 5.0


class CredentialBackend(Protocol):
    def get_password(self, service: str, account: str) -> str | None: ...

    def set_password(self, service: str, account: str, password: str) -> None: ...

    def delete_password(self, service: str, account: str) -> None: ...


class CredentialBackendError(RuntimeError):
    """Stable failure without paths, account names or secret values."""


@contextmanager
def _safe_errors() -> Iterator[None]:
    try:
        yield
    except CredentialBackendError:
        log.warning("credential_backend_operation_rejected")
        raise
    except Exception:  # noqa: BLE001 - vendor keyring exceptions are not standardized.
        log.warning("credential_backend_operation_failed")
        # Backend/JSON/OS exceptions may contain a secret or a private path.
        raise CredentialBackendError("credential_store_unavailable") from None


class SystemKeyringBackend:
    """Lazy adapter: ordinary Native startup never creates a file credential store."""

    def get_password(self, service: str, account: str) -> str | None:
        with _safe_errors():
            import keyring

            return keyring.get_password(service, account)

    def set_password(self, service: str, account: str, password: str) -> None:
        with _safe_errors():
            import keyring

            keyring.set_password(service, account, password)

    def delete_password(self, service: str, account: str) -> None:
        with _safe_errors():
            import keyring

            keyring.delete_password(service, account)


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _file_state(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _validate_file(info: os.stat_result) -> None:
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or getattr(info, "st_file_attributes", 0) & 0x400
        or info.st_size > MAX_RECORD_BYTES
    ):
        raise CredentialBackendError("credential_record_unsafe")


def _encode(password: str) -> bytes:
    if not isinstance(password, str) or len(password.encode("utf-8")) > MAX_VALUE_BYTES:
        raise CredentialBackendError("credential_value_invalid")
    return json.dumps(
        {"version": 1, "password": password}, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


class PrivateFileCredentialBackend:
    """Descriptor-relative, bounded, process-serialized POSIX credential records.

    The configured root is exact and remains pinned to its initial identity.
    Unsafe existing permissions fail closed rather than modifying user files.
    Each operation pins/validates ancestors, locks one persistent inode, and
    rechecks directory and file identities. Cooperating writers use the lock;
    a malicious process with the same OS identity is outside the isolation model.
    """

    def __init__(self, root: Path | str) -> None:
        self._thread_lock = RLock()
        with _safe_errors():
            if _PLATFORM_NAME != "posix":
                raise CredentialBackendError("credential_platform_unsupported")
            raw = os.fspath(root)
            path = Path(raw)
            if (
                not isinstance(raw, str)
                or not path.is_absolute()
                or str(path) != raw
                or raw.startswith("//")
                or ".." in path.parts
                or path == Path(path.anchor)
                or "\x00" in raw
            ):
                raise CredentialBackendError("credential_home_invalid")
            self.root = path
            with runtime_state_directory(path, create=True):
                info = path.lstat()
                if stat.S_IMODE(info.st_mode) != 0o700:
                    raise CredentialBackendError("credential_home_unsafe")
                self._root_identity = _identity(info)

    @staticmethod
    def _name(service: str, account: str) -> str:
        if any(
            not isinstance(value, str) or not value or len(value.encode()) > 4096
            for value in (service, account)
        ):
            raise CredentialBackendError("credential_reference_invalid")
        reference = json.dumps([service, account], ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(reference.encode("utf-8")).hexdigest() + ".json"

    def _verify_root(self, directory: int) -> None:
        current = os.fstat(directory)
        named = self.root.lstat()
        if (
            _identity(current) != self._root_identity
            or _identity(named) != self._root_identity
            or stat.S_IMODE(current.st_mode) != 0o700
            or current.st_uid != os.getuid()
            or not stat.S_ISDIR(named.st_mode)
        ):
            raise CredentialBackendError("credential_home_changed")

    @contextmanager
    def _locked_directory(self) -> Iterator[int]:
        import fcntl

        with self._thread_lock, runtime_state_directory(self.root), ExitStack() as stack:
            directory = None
            for part in (self.root.anchor, *self.root.parts[1:]):
                directory = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                stack.callback(os.close, directory)
            assert directory is not None
            self._verify_root(directory)
            lock_flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
            try:
                # Darwin can return ENOENT for concurrent nonexclusive
                # O_CREAT|O_NOFOLLOW opens. Elect one creator atomically.
                lock = os.open(
                    ".credentials.lock",
                    lock_flags | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=directory,
                )
            except FileExistsError:
                # A loser only opens the winner's inode; disappearance or an
                # unsafe replacement must fail closed, never recreate the lock.
                lock = os.open(".credentials.lock", lock_flags, dir_fd=directory)
            stack.callback(os.close, lock)
            _validate_file(os.fstat(lock))
            deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise CredentialBackendError("credential_store_busy") from None
                    time.sleep(0.01)
            stack.callback(fcntl.flock, lock, fcntl.LOCK_UN)

            def verify() -> None:
                self._verify_root(directory)
                opened = os.fstat(lock)
                named = os.stat(".credentials.lock", dir_fd=directory, follow_symlinks=False)
                _validate_file(opened)
                _validate_file(named)
                if _identity(opened) != _identity(named):
                    raise CredentialBackendError("credential_lock_changed")

            verify()
            try:
                yield directory
            finally:
                verify()

    @staticmethod
    def _read(directory: int, name: str) -> tuple[bytes, os.stat_result] | None:
        try:
            before = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return None
        _validate_file(before)
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try:
            opened = os.fstat(descriptor)
            _validate_file(opened)
            if _file_state(opened) != _file_state(before):
                raise CredentialBackendError("credential_record_changed")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(MAX_RECORD_BYTES + 1)
            after = os.fstat(descriptor)
            named = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if (
                len(raw) > MAX_RECORD_BYTES
                or _file_state(after) != _file_state(before)
                or _file_state(named) != _file_state(before)
            ):
                raise CredentialBackendError("credential_record_changed")
            return raw, before
        finally:
            os.close(descriptor)

    def get_password(self, service: str, account: str) -> str | None:
        with _safe_errors():
            name = self._name(service, account)
            with self._locked_directory() as directory:
                record = self._read(directory, name)
                if record is None:
                    return None
                raw = record[0]
                payload = json.loads(raw.decode("utf-8"))
                if (
                    not isinstance(payload, dict)
                    or set(payload) != {"version", "password"}
                    or type(payload["version"]) is not int
                    or payload["version"] != 1
                    or _encode(payload["password"]) != raw
                ):
                    raise CredentialBackendError("credential_record_invalid")
                return payload["password"]

    def set_password(self, service: str, account: str, password: str) -> None:
        with _safe_errors():
            name, raw = self._name(service, account), _encode(password)
            with self._locked_directory() as directory:
                previous = self._read(directory, name)
                temporary = f".{secrets.token_hex(16)}.tmp"
                descriptor = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=directory,
                )
                published = False
                identity = _identity(os.fstat(descriptor))
                try:
                    with os.fdopen(descriptor, "wb", closefd=False) as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(descriptor)
                    staged = self._read(directory, temporary)
                    if staged is None or staged[0] != raw or _identity(staged[1]) != identity:
                        raise CredentialBackendError("credential_readback_failed")
                    current = self._read(directory, name)
                    if (current is None) != (previous is None) or (
                        current is not None
                        and previous is not None
                        and _file_state(current[1]) != _file_state(previous[1])
                    ):
                        raise CredentialBackendError("credential_record_changed")
                    self._verify_root(directory)
                    os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
                    published = True
                    os.fsync(directory)
                    persisted = self._read(directory, name)
                    if (
                        persisted is None
                        or persisted[0] != raw
                        or _identity(persisted[1]) != identity
                    ):
                        raise CredentialBackendError("credential_readback_failed")
                except BaseException:
                    # Remove only our own inode on failed publication/readback.
                    target = name if published else temporary
                    try:
                        info = os.stat(target, dir_fd=directory, follow_symlinks=False)
                        if _identity(info) == identity:
                            os.unlink(target, dir_fd=directory)
                            os.fsync(directory)
                    except FileNotFoundError:
                        pass
                    except OSError:
                        log.error("credential_write_cleanup_failed")
                    raise
                finally:
                    os.close(descriptor)

    def delete_password(self, service: str, account: str) -> None:
        with _safe_errors():
            name = self._name(service, account)
            with self._locked_directory() as directory:
                existing = self._read(directory, name)
                if existing is None:
                    return
                self._verify_root(directory)
                current = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if _file_state(current) != _file_state(existing[1]):
                    raise CredentialBackendError("credential_record_changed")
                os.unlink(name, dir_fd=directory)
                os.fsync(directory)
                if self._read(directory, name) is not None:
                    raise CredentialBackendError("credential_delete_failed")


def default_credential_backend() -> CredentialBackend:
    """Select private files only for an explicitly present, exact absolute root."""
    root = os.environ.get("RESEARCH_CREDENTIAL_HOME")
    if root is None:
        return SystemKeyringBackend()
    return PrivateFileCredentialBackend(root)


class EncryptedModelCredentialBackend(PrivateFileCredentialBackend):
    """AES-256-GCM model records; a separate read-only instance key is mandatory.

    The parent supplies descriptor checks, process locks and atomic publication.
    Its JSON password field contains a versioned ciphertext envelope, never a Key.
    No failure selects the generic plaintext or operating-system backend.
    """

    source = "docker-encrypted"
    MODEL_REFS = frozenset({"RESEARCH_DSH_API_KEY", "RESEARCH_COMPAT_API_KEY"})

    def __init__(self, root: Path, key_root: Path, instance: str) -> None:
        with _safe_errors():
            if len(instance) != 32 or any(c not in "0123456789abcdef" for c in instance):
                raise CredentialBackendError("model_instance_invalid")
            self.instance = instance
            self.key_root = key_root
            self._key, self._key_identity = self._load_key()
            # Loading is not initialization: absent ciphertext directories fail.
            with runtime_state_directory(root):
                super().__init__(root)
            with self._locked_directory() as directory:
                service = "org.research-workbench.model." + self.instance
                references = {self._name(service, ref): ref for ref in self.MODEL_REFS}
                for name in os.listdir(directory):
                    if not name.endswith(".json"):
                        continue
                    if name not in references:
                        raise CredentialBackendError("model_record_binding_invalid")
                    record = self._read(directory, name)
                    if record is None:
                        raise CredentialBackendError("model_ciphertext_invalid")
                    payload = json.loads(record[0])
                    if (
                        not isinstance(payload, dict)
                        or set(payload) != {"version", "password"}
                        or type(payload["version"]) is not int
                        or payload["version"] != 1
                        or not isinstance(payload["password"], str)
                        or _encode(payload["password"]) != record[0]
                    ):
                        raise CredentialBackendError("model_ciphertext_invalid")
                    # Validate every existing record, not just the requested account.
                    # A foreign tree cannot be masked by an empty current namespace.
                    self._decrypt(payload["password"], service, references[name])

    def _reference(self, service: str, account: str) -> None:
        if (
            service != "org.research-workbench.model." + self.instance
            or account not in self.MODEL_REFS
        ):
            raise CredentialBackendError("model_record_binding_invalid")

    def _load_key(self) -> tuple[bytes, tuple[int, ...]]:
        with runtime_state_directory(self.key_root):
            descriptor = os.open(self.key_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                identity = self._read(descriptor, "identity.json")
                key = self._read(descriptor, "master.key")
                if identity is None or key is None or len(key[0]) != 32:
                    raise CredentialBackendError("model_master_key_unavailable")
                payload = json.loads(identity[0])
                if (
                    not isinstance(payload, dict)
                    or type(payload.get("version")) is not int
                    or payload != {"version": 1, "instance": self.instance}
                ):
                    raise CredentialBackendError("model_instance_mismatch")
                return key[0], _file_state(key[1])
            finally:
                os.close(descriptor)

    def _cipher(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        current, identity = self._load_key()
        if identity != self._key_identity or current != self._key:
            raise CredentialBackendError("model_master_key_changed")
        return AESGCM(current)

    def _aad(self, service: str, account: str) -> bytes:
        return json.dumps(["rwb-model-v1", self.instance, service, account]).encode()

    def _decrypt(self, raw: str, service: str, account: str) -> str:
        payload = json.loads(raw)
        if (
            not isinstance(payload, dict)
            or set(payload) != {"version", "algorithm", "instance", "nonce", "ciphertext"}
            or type(payload["version"]) is not int
            or payload["version"] != 1
            or payload["algorithm"] != "AES-256-GCM"
            or payload["instance"] != self.instance
        ):
            raise CredentialBackendError("model_ciphertext_invalid")
        nonce = base64.b64decode(payload["nonce"], validate=True)
        ciphertext = base64.b64decode(payload["ciphertext"], validate=True)
        if len(nonce) != 12:
            raise CredentialBackendError("model_ciphertext_invalid")
        value = self._cipher().decrypt(nonce, ciphertext, self._aad(service, account)).decode()
        if not value or len(value) > 1024:
            raise CredentialBackendError("model_value_invalid")
        return value

    def get_password(self, service: str, account: str) -> str | None:
        with _safe_errors():
            self._reference(service, account)
            self._cipher()
            raw = super().get_password(service, account)
            return None if raw is None else self._decrypt(raw, service, account)

    def set_password(self, service: str, account: str, password: str) -> None:
        with _safe_errors():
            self._reference(service, account)
            if not isinstance(password, str) or not password or len(password) > 1024:
                raise CredentialBackendError("model_value_invalid")
            # An existing damaged record must not be silently replaced.
            self.get_password(service, account)
            nonce = secrets.token_bytes(12)
            ciphertext = self._cipher().encrypt(
                nonce, password.encode(), self._aad(service, account)
            )
            payload = {
                "version": 1,
                "algorithm": "AES-256-GCM",
                "instance": self.instance,
                "nonce": base64.b64encode(nonce).decode(),
                "ciphertext": base64.b64encode(ciphertext).decode(),
            }
            super().set_password(service, account, json.dumps(payload, sort_keys=True))

    def delete_password(self, service: str, account: str) -> None:
        with _safe_errors():
            self._reference(service, account)
            self.get_password(service, account)
            super().delete_password(service, account)
