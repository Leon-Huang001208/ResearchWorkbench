"""Fixed-purpose private stdio bridge for Native Keychain or Docker encryption.

Launched with the managed product Python in isolated mode. No fallback, arbitrary
namespace, record access, or secret-bearing diagnostics are supported.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import logging
import os
import secrets
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

MODEL_REF = "RESEARCH_DSH_API_KEY"
COMPATIBLE_REF = "RESEARCH_COMPAT_API_KEY"
MODEL_REFS = frozenset({MODEL_REF, COMPATIBLE_REF})
MAX_REQUEST = 8192
log = logging.getLogger(__name__)


class DockerModelStore:
    """Encrypted fixed model accounts in a separate, guarded credential subtree.

    The master key shares the private credential mount; this protects against
    plaintext API-key persistence, not an administrator or same-UID attacker.
    It is created once under the existing interprocess lock and never rotated
    implicitly, including when encrypted records outlive a missing key.
    """

    source = "docker-encrypted-file"
    KEY_SERVICE = "org.research-workbench.model-encryption"
    KEY_ACCOUNT = "master-v1"

    def __init__(self, credential_home: Path | str) -> None:
        if sys.platform != "linux":
            raise RuntimeError("model_credential_backend_unavailable")
        from app.research_web.credential_backend import PrivateFileCredentialBackend

        parent = PrivateFileCredentialBackend(credential_home)
        # The installation already owns the private mount. Serialize creation
        # of its model subtree with other cooperating credential consumers.
        with parent._locked_directory():
            self.backend = PrivateFileCredentialBackend(parent.root / "models")

    def _master(self, *, create: bool) -> Fernet:
        from cryptography.fernet import Fernet

        name = self.backend._name(self.KEY_SERVICE, self.KEY_ACCOUNT)
        with self.backend._locked_directory() as directory:
            record = self.backend._read(directory, name)
            if record is None:
                if not create or any(value.endswith(".json") for value in os.listdir(directory)):
                    log.warning("model_credential_key_unavailable")
                    raise RuntimeError("model_credential_key_unavailable")
                encoded = Fernet.generate_key().decode("ascii")
                raw = json.dumps({"version": 1, "password": encoded}).encode("utf-8")
                temporary = f".{secrets.token_hex(16)}.tmp"
                descriptor = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=directory,
                )
                identity = os.fstat(descriptor)
                try:
                    with os.fdopen(descriptor, "wb", closefd=False) as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(descriptor)
                    self.backend._verify_root(directory)
                    os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
                    os.fsync(directory)
                    record = self.backend._read(directory, name)
                    if record is None or record[0] != raw:
                        raise RuntimeError("model_credential_key_unavailable")
                    log.info("docker_model_master_key_created")
                finally:
                    os.close(descriptor)
                    try:
                        leftover = os.stat(temporary, dir_fd=directory, follow_symlinks=False)
                        if (leftover.st_dev, leftover.st_ino) == (identity.st_dev, identity.st_ino):
                            os.unlink(temporary, dir_fd=directory)
                    except FileNotFoundError:
                        pass
            try:
                payload = json.loads(record[0])
                if (
                    set(payload) != {"version", "password"}
                    or type(payload["version"]) is not int
                    or payload["version"] != 1
                ):
                    raise ValueError("invalid master record")
                return Fernet(payload["password"].encode("ascii"))
            except (ValueError, TypeError, KeyError, AttributeError):
                log.warning("model_credential_key_unavailable")
                raise RuntimeError("model_credential_key_unavailable") from None

    @staticmethod
    def _reference(service: str, account: str) -> None:
        if not isinstance(service, str) or not service or account not in MODEL_REFS:
            raise ValueError("model_credential_request_invalid")

    def get_password(self, service: str, account: str) -> str | None:
        self._reference(service, account)
        encoded = self.backend.get_password(service, account)
        if encoded is None:
            return None
        cipher = self._master(create=False)
        try:
            if not encoded.startswith("model:v1:"):
                raise ValueError("invalid model record")
            raw = cipher.decrypt(encoded.removeprefix("model:v1:").encode("ascii"))
            payload = json.loads(raw)
            if (
                set(payload) != {"service", "account", "value"}
                or payload["service"] != service
                or payload["account"] != account
                or not isinstance(payload["value"], str)
                or not payload["value"]
                or len(payload["value"]) > 1024
            ):
                raise ValueError("invalid model binding")
            return payload["value"]
        except Exception:  # noqa: BLE001 - never expose cryptography/vendor secret details.
            log.warning("model_credential_record_invalid")
            raise RuntimeError("model_credential_record_invalid") from None

    def set_password(self, service: str, account: str, value: str) -> None:
        self._reference(service, account)
        if not isinstance(value, str) or not value or len(value) > 1024:
            raise ValueError("model_credential_request_invalid")
        # An unreadable prior record cannot be silently replaced or re-keyed.
        self.get_password(service, account)
        cipher = self._master(create=True)
        raw = json.dumps({"service": service, "account": account, "value": value}).encode("utf-8")
        self.backend.set_password(
            service, account, "model:v1:" + cipher.encrypt(raw).decode("ascii")
        )

    def delete_password(self, service: str, account: str) -> None:
        self._reference(service, account)
        self.backend.delete_password(service, account)


def update_or_add(api, update, service, account, value_data):
    """Replace atomically; only an absent item may be added. Never delete first."""
    query = api.create_query(
        kSecClass=api.k_("kSecClassGenericPassword"),
        kSecAttrService=service,
        kSecAttrAccount=account,
    )
    attributes = api.create_query(kSecValueData=value_data)
    try:
        status = update(query, attributes)
        if status == api.error.item_not_found:
            addition = api.create_query(
                kSecClass=api.k_("kSecClassGenericPassword"),
                kSecAttrService=service,
                kSecAttrAccount=account,
                kSecValueData=value_data,
            )
            try:
                status = api.SecItemAdd(addition, None)
            finally:
                if hasattr(api, "_found"):
                    api._found.CFRelease(addition)
            # An independent writer may have added it since the not-found check.
            if status == -25299:
                status = update(query, attributes)
        api.Error.raise_for_status(status)
    finally:
        if hasattr(api, "_found"):
            api._found.CFRelease(attributes)
            api._found.CFRelease(query)


class MacSystemStore:
    """Use existing keyring reads/removals and Security's atomic replacement."""

    def __init__(self, backend, api):
        self.backend = backend
        self.api = api

    def get_password(self, service, account):
        return self.backend.get_password(service, account)

    def delete_password(self, service, account):
        return self.backend.delete_password(service, account)

    def set_password(self, service, account, value):
        api = self.api
        update = api._sec.SecItemUpdate
        update.restype = ctypes.c_int32
        update.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
        release = api._found.CFRelease
        release.argtypes = (ctypes.c_void_p,)
        release.restype = None
        create_data = api._found.CFDataCreate
        create_data.restype = ctypes.c_void_p
        create_data.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)
        encoded = value.encode("utf-8")
        buffer = ctypes.create_string_buffer(encoded)
        data = create_data(None, buffer, len(encoded))
        if not data:
            raise RuntimeError("model_credential_backend_unavailable")
        try:
            update_or_add(api, update, service, account, ctypes.c_void_p(data))
        finally:
            release(data)


def system_backend():
    """Select the approved backend directly, bypassing keyring configuration."""
    if sys.platform != "darwin":
        raise RuntimeError("model_credential_backend_unavailable")
    # Deliberately lazy: other platforms can start the Host/settings page.
    from keyring.backends.macOS import Keyring, api

    backend = Keyring()
    if type(backend) is not Keyring or backend.priority <= 0:
        raise RuntimeError("model_credential_backend_unavailable")
    return MacSystemStore(backend, api)


def execute(data_home: Path, request: object, backend=None) -> dict:
    """Operate only on this canonical data home's two fixed model accounts."""
    if (
        not isinstance(request, dict)
        or not isinstance(request.get("ref"), str)
        or request.get("ref") not in MODEL_REFS
        or request.get("op") not in {"resolve", "describe", "set", "unset"}
        or set(request) - {"op", "ref", "value"}
    ):
        raise ValueError("model_credential_request_invalid")
    op = request["op"]
    account = request["ref"]
    if op == "set":
        value = request.get("value")
        if not isinstance(value, str) or not value or len(value) > 1024:
            raise ValueError("model_credential_request_invalid")
    elif "value" in request:
        raise ValueError("model_credential_request_invalid")
    root = data_home.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("model_credential_request_invalid")
    # This is a public path identity, never a hash of secret material.
    namespace = "org.research-workbench.model." + hashlib.sha256(str(root).encode()).hexdigest()
    store = backend if backend is not None else system_backend()
    if op == "set":
        store.set_password(namespace, account, request["value"])
        return {}
    if op == "unset":
        if store.get_password(namespace, account) is not None:
            store.delete_password(namespace, account)
        return {}
    value = store.get_password(namespace, account)
    if op == "describe":
        return {
            "configured": bool(value),
            "source": getattr(store, "source", "system-keychain"),
            "writable": True,
        }
    return {"value": value if value else None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Private model credential bridge")
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument(
        "--backend", choices=("native-keychain", "docker-encrypted-file"), default="native-keychain"
    )
    parser.add_argument("--credential-home")
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST:
            raise ValueError("model_credential_request_invalid")
        if args.backend == "docker-encrypted-file":
            if args.credential_home is None:
                raise ValueError("model_credential_binding_invalid")
            # The shared filesystem guard imports the project's logger/settings.
            # Keep that isolated import read-only and unable to load legacy .env.
            source = str(Path(__file__).resolve().parent)
            os.environ.clear()
            os.environ.update(
                {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "RESEARCH_RUN_MODE": "web-prod"}
            )
            for name in ("LOG_DIR", "OBJECT_STORAGE_PATH", "PDF_MARKDOWN_DIR", "PDF_RAW_TEXT_DIR"):
                os.environ[name] = source
            backend = DockerModelStore(args.credential_home)
        else:
            if args.credential_home is not None:
                raise ValueError("model_credential_binding_invalid")
            backend = None
        result = execute(args.data_home, json.loads(raw), backend)
        # stdout is exclusively the private parent pipe, never a log sink.
        sys.stdout.write(json.dumps({"ok": True, **result}))
        return 0
    except Exception:
        # Never expose backend exceptions, request contents, or a secret hash.
        log.exception("model_credential_bridge_failed", exc_info=False)
        sys.stdout.write('{"ok":false,"error":"model_credential_bridge_failed"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
