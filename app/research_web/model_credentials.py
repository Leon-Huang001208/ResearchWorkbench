"""Fixed-purpose private stdio bridge for explicit Native/Docker model stores.

Launched with the managed product Python in isolated mode. No fallback, arbitrary
namespace, record access, or secret-bearing diagnostics are supported.
"""

import argparse
import ctypes
import hashlib
import json
import logging
import os
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

MODEL_REF = "RESEARCH_DSH_API_KEY"
COMPATIBLE_REF = "RESEARCH_COMPAT_API_KEY"
MODEL_REFS = frozenset({MODEL_REF, COMPATIBLE_REF})
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


def docker_backend(root, installation_id):
    """Lazy trusted-product import; accepts temporary POSIX roots for unit tests.

    The private CLI separately requires Linux and the exact managed leaf. The
    product root comes from this managed script, never PYTHONPATH or data home.
    Native uses no project imports and retains its standalone lazy behavior.
    """
    if (
        not isinstance(installation_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", installation_id) is None
    ):
        raise RuntimeError("model_credential_binding_invalid")
    product_root = Path(__file__).resolve(strict=True).parents[2]
    sys.path.insert(0, str(product_root))
    try:
        from app.research_web import model_file_store

        if (
            Path(model_file_store.__file__).resolve()
            != product_root / "app/research_web/model_file_store.py"
        ):
            raise RuntimeError("model_credential_backend_unavailable")
        return model_file_store.DockerModelStore(root, installation_id)
    except Exception as error:
        if (
            type(error).__module__ == "app.research_web.model_file_store"
            and type(error).__name__ == "ModelStoreError"
        ):
            raise error from None
        raise RuntimeError("model_credential_backend_unavailable") from None
    finally:
        sys.path.remove(str(product_root))


def select_backend(backend, root=None, installation_id=None):
    """Explicit private CLI selection, never an ambient file/env fallback."""
    if backend == "system-keychain":
        if root is not None or installation_id is not None:
            raise ValueError("model_credential_binding_invalid")
        return None
    if (
        backend != "docker-private-file"
        or sys.platform != "linux"
        or not isinstance(installation_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", installation_id) is None
        or root != "/run/rwb-secrets/private/models/" + installation_id
    ):
        raise ValueError("model_credential_binding_invalid")
    if __name__ == "__main__" and __package__ in (None, ""):
        # The private child has a stripped environment and a read-only image.
        # Legacy logger imports still ensure four directories unconditionally;
        # bind them to the existing managed root, never caller paths or .env.
        product_root = str(Path(__file__).resolve(strict=True).parents[2])
        os.environ["RESEARCH_RUN_MODE"] = "web-prod"
        os.environ.pop("RESEARCH_CONFIG_FILE", None)
        for key in ("LOG_DIR", "OBJECT_STORAGE_PATH", "PDF_MARKDOWN_DIR", "PDF_RAW_TEXT_DIR"):
            os.environ[key] = product_root
    return docker_backend(root, installation_id)


def execute(data_home: Path, request: object, backend=None) -> dict:
    """Operate only on this canonical data home's two fixed model accounts."""
    if (
        not isinstance(request, dict)
        or not isinstance(request.get("ref"), str)
        or request.get("ref") not in MODEL_REFS
        or request.get("op") not in ("resolve", "describe", "set", "unset")
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
    namespace = getattr(store, "namespace", namespace)
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


def _log_bridge_failure() -> None:
    try:
        log.warning("model_credential_bridge_failed")
    except Exception:  # noqa: BLE001 - Diagnostics cannot hide an uncertain commit.
        return


def main() -> int:
    class PrivateParser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError("model_credential_binding_invalid")

    parser = PrivateParser(description="Private model credential bridge")
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument("--backend", default="system-keychain")
    parser.add_argument("--credential-root")
    parser.add_argument("--installation-id")
    try:
        args = parser.parse_args()
        # Third-party/shared lazy-import loggers may default to stdout. Include
        # imports, operations and final lock/ancestor verification in this
        # private scope; the parent only receives one JSON stdout response.
        with redirect_stdout(sys.stderr):
            backend = select_backend(args.backend, args.credential_root, args.installation_id)
            raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
            if len(raw) > MAX_REQUEST:
                raise ValueError("model_credential_request_invalid")
            result = execute(args.data_home, json.loads(raw), backend)
        # stdout is exclusively the private parent pipe, never a log sink.
        sys.stdout.write(json.dumps({"ok": True, **result}))
        return 0
    except Exception as error:  # noqa: BLE001 - The private pipe exposes only stable errors.
        # Never expose backend exceptions, request contents, or a secret hash.
        _log_bridge_failure()
        code = (
            str(error)
            if type(error) is ValueError and str(error) == "model_credential_binding_invalid"
            else "model_credential_bridge_failed"
        )
        if (
            type(error).__name__ == "ModelStoreError"
            and str(error) == "model_credential_commit_uncertain"
        ):
            code = "model_credential_commit_uncertain"
        sys.stdout.write(json.dumps({"ok": False, "error": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
