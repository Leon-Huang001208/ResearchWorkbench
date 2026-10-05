"""Fixed-purpose private stdio bridge for the Native macOS model Keychain.

Launched with the managed product Python in isolated mode. No fallback, arbitrary
namespace, record access, or secret-bearing diagnostics are supported.
"""

import argparse
import ctypes
import hashlib
import json
import logging
import sys
from pathlib import Path

MODEL_REF = "RESEARCH_DSH_API_KEY"
MAX_REQUEST = 8192
log = logging.getLogger(__name__)


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
    """Operate only on this canonical data home's fixed model account."""
    if (
        not isinstance(request, dict)
        or request.get("ref") != MODEL_REF
        or request.get("op") not in {"resolve", "describe", "set", "unset"}
        or set(request) - {"op", "ref", "value"}
    ):
        raise ValueError("model_credential_request_invalid")
    op = request["op"]
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
        store.set_password(namespace, MODEL_REF, request["value"])
        return {}
    if op == "unset":
        if store.get_password(namespace, MODEL_REF) is not None:
            store.delete_password(namespace, MODEL_REF)
        return {}
    value = store.get_password(namespace, MODEL_REF)
    if op == "describe":
        return {"configured": bool(value), "source": "system-keychain", "writable": True}
    return {"value": value if value else None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Private model credential bridge")
    parser.add_argument("--data-home", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST:
            raise ValueError("model_credential_request_invalid")
        result = execute(args.data_home, json.loads(raw))
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
