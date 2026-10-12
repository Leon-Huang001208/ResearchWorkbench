"""Fixed-purpose stdio bridge for Native Keychain or bound Docker model storage.

Launched with the managed product Python in isolated mode. No fallback, arbitrary
namespace, record access, or secret-bearing diagnostics are supported.
"""

import argparse
import ctypes
import hashlib
import json
import logging
import os
import secrets
import sys
from pathlib import Path

MODEL_REF = "RESEARCH_DSH_API_KEY"
COMPATIBLE_REF = "RESEARCH_COMPAT_API_KEY"
MODEL_REFS = frozenset({MODEL_REF, COMPATIBLE_REF})
MAX_REQUEST = 8192
log = logging.getLogger(__name__)


def docker_backend(root: Path, key_root: Path, instance: str):
    # -I intentionally omits the script/project directory. Bind imports to this
    # owned product installation, never PYTHONPATH, cwd or a caller environment.
    product = str(Path(__file__).resolve().parents[2])
    sys.path.insert(0, product)
    from app.research_web.credential_backend import EncryptedModelCredentialBackend

    return EncryptedModelCredentialBackend(root, key_root, instance)


def initialize_docker_store(root: Path, key_root: Path, instance: str) -> None:
    """Admin-only one-time initialization; existing resources are never reset."""
    product = str(Path(__file__).resolve().parents[2])
    sys.path.insert(0, product)
    from app.research_web.credential_backend import CredentialBackendError
    from app.research_web.runtime_state import runtime_state_directory

    with runtime_state_directory(key_root):
        if any(key_root.iterdir()) or root.exists():
            raise CredentialBackendError("model_store_already_initialized")
        if len(instance) != 32 or any(c not in "0123456789abcdef" for c in instance):
            raise CredentialBackendError("model_instance_invalid")
        # The key is generated inside the bounded initializer, never an argv,
        # environment value, stdout or manager-ledger field. Partial init fails closed.
        for name, value in (
            ("master.key", secrets.token_bytes(32)),
            ("identity.json", json.dumps({"version": 1, "instance": instance}).encode()),
        ):
            fd = os.open(
                key_root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            try:
                with os.fdopen(fd, "wb", closefd=False) as stream:
                    stream.write(value)
                    stream.flush()
                os.fsync(fd)
            finally:
                os.close(fd)
        root.mkdir(mode=0o700)
        for folder in (key_root, root.parent):
            descriptor = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        docker_backend(root, key_root, instance)
        log.info("model_store_initialized")


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
    store = backend if backend is not None else system_backend()
    identity = getattr(store, "instance", None)
    namespace = "org.research-workbench.model." + (
        identity if identity is not None else hashlib.sha256(str(root).encode()).hexdigest()
    )
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
    parser.add_argument("--backend", choices=("native", "docker-encrypted"), default="native")
    parser.add_argument("--credential-root", type=Path)
    parser.add_argument("--key-root", type=Path)
    parser.add_argument("--instance")
    parser.add_argument("--initialize", action="store_true")
    args = parser.parse_args()
    try:
        backend = None
        if args.backend == "docker-encrypted":
            if args.credential_root is None or args.key_root is None or args.instance is None:
                raise ValueError("model_credential_binding_missing")
            if args.initialize:
                initialize_docker_store(args.credential_root, args.key_root, args.instance)
                sys.stdout.write('{"ok":true}')
                return 0
            backend = docker_backend(args.credential_root, args.key_root, args.instance)
        elif any((args.credential_root, args.key_root, args.instance, args.initialize)):
            raise ValueError("model_credential_binding_invalid")
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST:
            raise ValueError("model_credential_request_invalid")
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
