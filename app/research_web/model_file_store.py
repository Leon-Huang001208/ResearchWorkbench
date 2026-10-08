"""Fixed model-only Docker store; private files are not encrypted.

Reuse the audited descriptor, root, lock and bounded reader primitives without
changing DataHub records. Cooperating processes serialize on the persistent
lock inode. Arbitrary same-UID code and the Docker administrator are outside
this isolation boundary. Once publication is attempted, failure is uncertain;
the destination is never deleted or restored by a guessed rollback.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import stat
from pathlib import Path
from typing import NoReturn

from .credential_backend import PrivateFileCredentialBackend, _file_state, _identity
from .runtime_state import runtime_state_directory

# Match the private bridge/runtime-state logging path. The full app's default
# structlog sink can be stdout, which is reserved for the private JSON response.
log = logging.getLogger(__name__)
MODEL_REF = "RESEARCH_DSH_API_KEY"
MAX_MODEL_RECORD_BYTES = 8192


class ModelStoreError(RuntimeError):
    """Stable model-only error, without secret or filesystem details."""


def _log_stage(stage: str) -> None:
    try:
        log.warning("model_credential_store_rejected stage=%s", stage)
    except Exception:  # noqa: BLE001 - Diagnostics cannot change a commit outcome.
        return


def validate_installation_id(value: object) -> str:
    """Only the stable installation identity, never a container ID or path hash."""
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{32}", value) is None:
        raise ModelStoreError("model_credential_binding_invalid")
    return value


class DockerModelStore(PrivateFileCredentialBackend):
    """One installation, one model ref, no generic credential fallback."""

    source = "docker-private-file"

    def __init__(self, root: Path | str, installation_id: str) -> None:
        self.installation_id = validate_installation_id(installation_id)
        self.namespace = "org.research-workbench.model.docker." + self.installation_id
        try:
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
                raise ModelStoreError("model_credential_binding_invalid")
            # Pin and check the model parent before the audited initializer can
            # create the installation leaf. Unsafe existing parents stay intact.
            if path.parent == Path("/run/rwb-secrets/private/models"):
                self._verify_private_directory(path.parents[1])
            with runtime_state_directory(path.parent, create=True):
                self._verify_model_parents(path)
                super().__init__(root)
            with self._locked_directory():
                pass
        except Exception:  # noqa: BLE001 - The private boundary cannot expose low-level failures.
            _log_stage("initialize")
            raise ModelStoreError("model_credential_store_unavailable") from None

    def _verify_root(self, directory: int) -> None:
        super()._verify_root(directory)
        self._verify_model_parents(self.root)

    @staticmethod
    def _verify_model_parents(root: Path) -> None:
        # The dedicated model parent is private too; the shared ancestor guard
        # intentionally allows read-only system ancestors with broader modes.
        parents = [root.parent]
        if root.parent == Path("/run/rwb-secrets/private/models"):
            parents.append(root.parents[1])
        for parent in parents:
            DockerModelStore._verify_private_directory(parent)

    @staticmethod
    def _verify_private_directory(path: Path) -> None:
        info = path.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise ModelStoreError("model_credential_store_unavailable")

    def _record_name(self, service: str, account: str) -> str:
        if service != self.namespace or account != MODEL_REF:
            raise ModelStoreError("model_credential_reference_invalid")
        # Hash only the fixed public namespace/ref, never secret material.
        return super()._name(service, account)

    def _encode_model(self, value: str) -> bytes:
        if not isinstance(value, str) or not value or len(value) > 1024:
            raise ModelStoreError("model_credential_value_invalid")
        raw = json.dumps(
            {
                "version": 1,
                "installation_id": self.installation_id,
                "ref": MODEL_REF,
                "password": value,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(raw) > MAX_MODEL_RECORD_BYTES:
            raise ModelStoreError("model_credential_value_invalid")
        return raw

    def _decode_model(self, raw: bytes) -> str:
        payload = json.loads(raw.decode("utf-8"))
        if (
            not isinstance(payload, dict)
            or set(payload) != {"version", "installation_id", "ref", "password"}
            or type(payload["version"]) is not int
            or payload["version"] != 1
            or payload["installation_id"] != self.installation_id
            or payload["ref"] != MODEL_REF
            or self._encode_model(payload["password"]) != raw
        ):
            raise ModelStoreError("model_credential_record_invalid")
        return payload["password"]

    @staticmethod
    def _read(directory: int, name: str) -> tuple[bytes, os.stat_result] | None:
        record = PrivateFileCredentialBackend._read(directory, name)
        if record is not None and len(record[0]) > MAX_MODEL_RECORD_BYTES:
            raise ModelStoreError("model_credential_record_invalid")
        return record

    @staticmethod
    def _reject(stage: str, attempted: bool, error: Exception) -> NoReturn:
        # No exception text, path, value or secret hash reaches diagnostics.
        _log_stage(stage)
        if attempted:
            raise ModelStoreError("model_credential_commit_uncertain") from None
        if isinstance(error, ModelStoreError):
            raise error from None
        raise ModelStoreError("model_credential_store_unavailable") from None

    def get_password(self, service: str, account: str) -> str | None:
        try:
            name = self._record_name(service, account)
            with self._locked_directory() as directory:
                record = self._read(directory, name)
                return None if record is None else self._decode_model(record[0])
        except Exception as error:  # noqa: BLE001 - Sanitize decoder/descriptor errors.
            self._reject("read", False, error)

    def _clean_temporary(self, directory: int, name: str, identity: tuple[int, int]) -> None:
        try:
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if _identity(info) == identity:
                os.unlink(name, dir_fd=directory)
                os.fsync(directory)
        except FileNotFoundError:
            pass
        except Exception:  # noqa: BLE001 - Cleanup must preserve the original outcome.
            _log_stage("temporary_cleanup")

    def set_password(self, service: str, account: str, password: str) -> None:
        attempted = False
        try:
            name, raw = self._record_name(service, account), self._encode_model(password)
            with self._locked_directory() as directory:
                previous = self._read(directory, name)
                if previous is not None:
                    self._decode_model(previous[0])
                temporary = f".{secrets.token_hex(16)}.tmp"
                descriptor = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=directory,
                )
                identity = _identity(os.fstat(descriptor))
                try:
                    with os.fdopen(descriptor, "wb", closefd=False) as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(descriptor)
                    staged = self._read(directory, temporary)
                    if staged is None or staged[0] != raw or _identity(staged[1]) != identity:
                        raise ModelStoreError("model_credential_readback_failed")
                    current = self._read(directory, name)
                    if (current is None) != (previous is None) or (
                        current is not None
                        and previous is not None
                        and _file_state(current[1]) != _file_state(previous[1])
                    ):
                        raise ModelStoreError("model_credential_record_changed")
                    self._verify_root(directory)
                    attempted = True
                    os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
                    os.fsync(directory)
                    persisted = self._read(directory, name)
                    if (
                        persisted is None
                        or persisted[0] != raw
                        or _identity(persisted[1]) != identity
                    ):
                        raise ModelStoreError("model_credential_readback_failed")
                except BaseException:
                    # Even an ambiguous replace may have published. Only this
                    # owned temporary name can be removed, never the destination.
                    self._clean_temporary(directory, temporary, identity)
                    raise
                finally:
                    os.close(descriptor)
        except Exception as error:  # noqa: BLE001 - All post-publication failures are uncertain.
            # Includes final lock/ancestor verification and descriptor close.
            self._reject("write", attempted, error)

    def delete_password(self, service: str, account: str) -> None:
        attempted = False
        try:
            name = self._record_name(service, account)
            with self._locked_directory() as directory:
                existing = self._read(directory, name)
                if existing is None:
                    return
                self._decode_model(existing[0])
                self._verify_root(directory)
                current = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if _file_state(current) != _file_state(existing[1]):
                    raise ModelStoreError("model_credential_record_changed")
                attempted = True
                os.unlink(name, dir_fd=directory)
                os.fsync(directory)
                if self._read(directory, name) is not None:
                    raise ModelStoreError("model_credential_readback_failed")
        except Exception as error:  # noqa: BLE001 - All post-unlink failures are uncertain.
            self._reject("delete", attempted, error)
