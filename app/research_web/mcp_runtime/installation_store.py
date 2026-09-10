"""Short-lived confirmation and atomic immutable MCP installation manifests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Protocol, cast
from uuid import uuid4

from pydantic import TypeAdapter

from core.observability import get_logger

from .models import InstallationManifest, InstallationPlanUnion

log = get_logger(__name__)
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
INSTALLATION_ID = re.compile(r"^mcp-installation-[a-f0-9]{32}$")
PLAN_ADAPTER = TypeAdapter(InstallationPlanUnion)
INTEGRITY_KEY_SERVICE = "ResearchWorkbench.MCPRuntime"
INTEGRITY_KEY_ACCOUNT = "manifest-integrity-v1"


class ConfirmationError(ValueError):
    """A stable confirmation-token validation failure."""


class InstallationStoreError(RuntimeError):
    """A stable local installation-store failure."""


class _KeyringBackend(Protocol):
    def get_password(self, service: str, account: str) -> str | None: ...

    def set_password(self, service: str, account: str, password: str) -> None: ...


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ConfirmationError("confirmation_token_invalid") from exc
    if _encode(raw) != value:
        raise ConfirmationError("confirmation_token_invalid")
    return raw


class ConfirmationTokenManager:
    """Issue HMAC tokens bound to one exact canonical plan summary."""

    def __init__(
        self,
        secret: bytes,
        *,
        replay_root: Path | None = None,
        ttl: timedelta = timedelta(minutes=5),
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if len(secret) < 32:
            raise ValueError("confirmation_secret_too_short")
        if ttl <= timedelta(0) or ttl > timedelta(minutes=10):
            raise ValueError("confirmation_ttl_invalid")
        self._secret = bytes(secret)
        self._replay_root = Path(replay_root) if replay_root is not None else None
        self._ttl = ttl
        self._now = now or (lambda: datetime.now(UTC))
        self._lock = RLock()

    def issue(self, plan: InstallationPlanUnion) -> str:
        try:
            plan.assert_integrity()
        except ValueError as exc:
            raise ConfirmationError("confirmation_summary_mismatch") from exc
        now = self._utc_now()
        payload = {
            "exp": int((now + self._ttl).timestamp()),
            "iat": int(now.timestamp()),
            "nonce": uuid4().hex,
            "summary_sha256": plan.summary_sha256,
        }
        encoded = _encode(_canonical_bytes(payload))
        signature = _encode(hmac.digest(self._secret, encoded.encode("ascii"), "sha256"))
        return f"{encoded}.{signature}"

    def verify(self, token: str, plan: InstallationPlanUnion, *, consume: bool = False) -> None:
        try:
            plan.assert_integrity()
        except ValueError as exc:
            raise ConfirmationError("confirmation_summary_mismatch") from exc
        try:
            encoded, encoded_signature = token.split(".", 1)
            signature = _decode(encoded_signature)
            expected = hmac.digest(self._secret, encoded.encode("ascii"), "sha256")
            if not hmac.compare_digest(signature, expected):
                raise ConfirmationError("confirmation_token_invalid")
            payload = json.loads(_decode(encoded))
            if not isinstance(payload, dict):
                raise TypeError("payload")
            expires = int(payload["exp"])
            issued = int(payload["iat"])
            nonce = str(payload["nonce"])
            summary = str(payload["summary_sha256"])
        except ConfirmationError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ConfirmationError("confirmation_token_invalid") from exc
        now = int(self._utc_now().timestamp())
        if expires <= now or issued > now or expires - issued > int(self._ttl.total_seconds()):
            raise ConfirmationError("confirmation_token_expired")
        if not hmac.compare_digest(summary, plan.summary_sha256):
            raise ConfirmationError("confirmation_summary_mismatch")
        token_id = hashlib.sha256(f"{nonce}.{encoded_signature}".encode("ascii")).hexdigest()
        if consume:
            with self._lock:
                self._consume_once(token_id, summary)

    def _utc_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise ValueError("confirmation_clock_requires_timezone")
        return value.astimezone(UTC)

    def _consume_once(self, token_id: str, summary_sha256: str) -> None:
        if self._replay_root is None:
            raise ConfirmationError("confirmation_replay_store_required")
        try:
            self._replay_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            control = self._private_directory(self._replay_root / ".control")
            replay = self._private_directory(control / "mcp-confirmations")
            path = replay / f"{token_id}.used"
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(_canonical_bytes({"summary_sha256": summary_sha256}))
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:
            raise ConfirmationError("confirmation_token_replayed") from exc
        except ConfirmationError:
            raise
        except OSError as exc:
            raise ConfirmationError("confirmation_replay_store_unavailable") from exc

    @staticmethod
    def _private_directory(path: Path) -> Path:
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        info = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISDIR(info.st_mode)
            or info.st_mode & 0o077
            or (hasattr(os, "getuid") and info.st_uid != os.getuid())
        ):
            raise ConfirmationError("confirmation_replay_store_unsafe")
        return path


class InstallationStore:
    """Persist one immutable manifest per installation using atomic replacement."""

    def __init__(
        self,
        data_root: Path,
        *,
        integrity_key: bytes | None = None,
        keyring_backend: object | None = None,
    ) -> None:
        if integrity_key is None:
            integrity_key = self._persistent_integrity_key(keyring_backend)
        if len(integrity_key) < 32:
            raise InstallationStoreError("installation_integrity_key_invalid")
        self.data_root = Path(data_root)
        self._integrity_key = bytes(integrity_key)
        self.root = self.data_root / "mcp-runtime"
        self.installations = self.root / "installations"
        self._lock = RLock()
        self._ensure_directory(self.data_root, create=True, private=False)
        self._ensure_directory(self.root, create=True, private=True)
        self._ensure_directory(self.installations, create=True, private=True)

    @staticmethod
    def _persistent_integrity_key(keyring_backend: object | None) -> bytes:
        try:
            if keyring_backend is None:
                import keyring

                backend = cast(_KeyringBackend, keyring)
            else:
                backend = cast(_KeyringBackend, keyring_backend)
            encoded = backend.get_password(INTEGRITY_KEY_SERVICE, INTEGRITY_KEY_ACCOUNT)
            if encoded is None:
                generated = secrets.token_bytes(32)
                encoded = _encode(generated)
                backend.set_password(INTEGRITY_KEY_SERVICE, INTEGRITY_KEY_ACCOUNT, encoded)
                persisted = backend.get_password(INTEGRITY_KEY_SERVICE, INTEGRITY_KEY_ACCOUNT)
                if persisted != encoded:
                    raise InstallationStoreError("installation_integrity_key_race")
            key = _decode(encoded)
        except InstallationStoreError:
            raise
        except Exception as exc:
            raise InstallationStoreError("installation_integrity_key_unavailable") from exc
        if len(key) != 32:
            raise InstallationStoreError("installation_integrity_key_invalid")
        return key

    def create(
        self,
        plan: InstallationPlanUnion,
        confirmation_token: str,
        tokens: ConfirmationTokenManager,
        *,
        installation_id: str | None = None,
    ) -> InstallationManifest:
        identifier = installation_id or f"mcp-installation-{uuid4().hex}"
        if INSTALLATION_ID.fullmatch(identifier) is None:
            raise InstallationStoreError("installation_id_invalid")
        folder = self.installations / identifier
        self._assert_contained(folder)
        with self._lock:
            try:
                plan_copy = PLAN_ADAPTER.validate_json(plan.model_dump_json())
                plan_copy.assert_integrity()
            except ValueError as exc:
                raise InstallationStoreError("installation_plan_invalid") from exc
            tokens.verify(confirmation_token, plan_copy, consume=True)
            if folder.is_symlink():
                raise InstallationStoreError("unsafe_installation_path")
            if folder.exists():
                manifest = folder / "manifest.json"
                if manifest.is_symlink():
                    raise InstallationStoreError("unsafe_installation_manifest")
                raise InstallationStoreError("installation_manifest_immutable")
            try:
                folder.mkdir(mode=0o700)
            except OSError as exc:
                raise InstallationStoreError("installation_storage_unavailable") from exc
            created_at = datetime.now(UTC)
            unsigned = {
                "schema_version": 1,
                "id": identifier,
                "created_at": created_at,
                "status": "installed",
                "plan": plan_copy.model_dump(mode="json"),
            }
            persisted_unsigned = {
                **unsigned,
                "created_at": created_at.isoformat().replace("+00:00", "Z"),
            }
            manifest_hash = hmac.digest(
                self._integrity_key, _canonical_bytes(persisted_unsigned), "sha256"
            ).hex()
            manifest = InstallationManifest.model_validate(
                {**unsigned, "manifest_sha256": manifest_hash}
            )
            try:
                self._atomic_manifest(folder / "manifest.json", manifest.model_dump(mode="json"))
            except Exception:
                try:
                    folder.rmdir()
                except OSError:
                    pass
                raise
        log.info(
            "mcp_installation_manifest_created",
            installation_id_digest=hashlib.sha256(identifier.encode("ascii")).hexdigest()[:16],
            status="installed",
        )
        return manifest

    def get(self, installation_id: str) -> InstallationManifest:
        if INSTALLATION_ID.fullmatch(installation_id) is None:
            raise InstallationStoreError("installation_not_found")
        path = self.installations / installation_id / "manifest.json"
        self._assert_contained(path)
        try:
            metadata = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or metadata.st_size > MAX_MANIFEST_BYTES
            ):
                raise InstallationStoreError("unsafe_installation_manifest")
            raw = path.read_bytes()
            manifest = InstallationManifest.model_validate_json(raw)
        except InstallationStoreError:
            raise
        except FileNotFoundError as exc:
            raise InstallationStoreError("installation_not_found") from exc
        except (OSError, ValueError) as exc:
            raise InstallationStoreError("installation_manifest_invalid") from exc
        try:
            manifest.plan.assert_integrity()
        except ValueError as exc:
            raise InstallationStoreError("installation_plan_digest_mismatch") from exc
        unsigned = manifest.model_dump(mode="json", exclude={"manifest_sha256"})
        expected = hmac.digest(self._integrity_key, _canonical_bytes(unsigned), "sha256").hex()
        if not hmac.compare_digest(expected, manifest.manifest_sha256):
            raise InstallationStoreError("installation_manifest_digest_mismatch")
        return manifest

    def list(self) -> list[InstallationManifest]:
        result: list[InstallationManifest] = []
        try:
            entries = sorted(self.installations.iterdir(), key=lambda path: path.name)
        except OSError as exc:
            raise InstallationStoreError("installation_storage_unavailable") from exc
        for path in entries:
            if (
                path.is_symlink()
                or not path.is_dir()
                or INSTALLATION_ID.fullmatch(path.name) is None
            ):
                raise InstallationStoreError("unsafe_installation_path")
            result.append(self.get(path.name))
        return result

    def delete(self, installation_id: str) -> None:
        """Delete one exact inactive manifest after the runtime service removes its payload."""

        if INSTALLATION_ID.fullmatch(installation_id) is None:
            raise InstallationStoreError("installation_not_found")
        folder = self.installations / installation_id
        self._assert_contained(folder)
        manifest = folder / "manifest.json"
        with self._lock:
            try:
                info = manifest.lstat()
                if manifest.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise InstallationStoreError("unsafe_installation_manifest")
                manifest.unlink()
                folder.rmdir()
            except InstallationStoreError:
                raise
            except FileNotFoundError as exc:
                raise InstallationStoreError("installation_not_found") from exc
            except OSError as exc:
                raise InstallationStoreError("installation_storage_unavailable") from exc
        log.info(
            "mcp_installation_manifest_deleted",
            installation_id_digest=hashlib.sha256(installation_id.encode("ascii")).hexdigest()[:16],
            status="deleted",
        )

    def _ensure_directory(self, path: Path, *, create: bool, private: bool) -> None:
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_dir():
                raise InstallationStoreError("unsafe_installation_directory")
            info = path.stat()
            if private and (
                info.st_mode & 0o077 or (hasattr(os, "getuid") and info.st_uid != os.getuid())
            ):
                raise InstallationStoreError("installation_directory_not_private")
            return
        if not create:
            raise InstallationStoreError("installation_storage_unavailable")
        try:
            path.mkdir(parents=True, mode=0o700)
        except OSError as exc:
            raise InstallationStoreError("installation_storage_unavailable") from exc
        if path.is_symlink() or not path.is_dir():
            raise InstallationStoreError("unsafe_installation_directory")
        info = path.stat()
        if private and (
            info.st_mode & 0o077 or (hasattr(os, "getuid") and info.st_uid != os.getuid())
        ):
            raise InstallationStoreError("installation_directory_not_private")

    def _assert_contained(self, path: Path) -> None:
        try:
            root = self.installations.resolve(strict=True)
            parent = path.parent.resolve(strict=True)
        except OSError as exc:
            raise InstallationStoreError("unsafe_installation_path") from exc
        if parent != root and not parent.is_relative_to(root):
            raise InstallationStoreError("unsafe_installation_path")

    @staticmethod
    def _atomic_manifest(path: Path, value: dict[str, object]) -> None:
        if path.exists() or path.is_symlink():
            raise InstallationStoreError("installation_manifest_immutable")
        raw = _canonical_bytes(value)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise InstallationStoreError("installation_manifest_too_large")
        descriptor: int | None = None
        temporary: Path | None = None
        try:
            descriptor, name = tempfile.mkstemp(prefix=".manifest-", dir=path.parent)
            temporary = Path(name)
            os.chmod(temporary, 0o600)
            stream = os.fdopen(descriptor, "wb")
            descriptor = None
            with stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if path.exists() or path.is_symlink():
                raise InstallationStoreError("installation_manifest_immutable")
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError as exc:
                raise InstallationStoreError("installation_manifest_immutable") from exc
            temporary.unlink()
            temporary = None
            try:
                directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except OSError as exc:
                log.warning(
                    "mcp_installation_directory_fsync_failed",
                    path_name="manifest.json",
                    error_type=type(exc).__name__,
                )
        except InstallationStoreError:
            raise
        except OSError as exc:
            log.error(
                "mcp_installation_manifest_write_failed",
                error_type=type(exc).__name__,
                status="failed",
            )
            raise InstallationStoreError("installation_storage_unavailable") from exc
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as exc:
                    log.warning(
                        "mcp_installation_temporary_cleanup_failed",
                        path_name="manifest.json",
                        error_type=type(exc).__name__,
                    )
