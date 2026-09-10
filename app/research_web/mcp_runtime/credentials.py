"""OS-keyring-only storage for MCP server credentials."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from core.observability import get_logger

log = get_logger(__name__)
KEYRING_SERVICE = "ResearchWorkbench.MCPRuntime"
_INSTALLATION = re.compile(r"^mcp-installation-[a-f0-9]{32}$")
_SLOT = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_MAX_CREDENTIAL_BYTES = 64 * 1024


def _id_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


class RuntimeCredentialError(RuntimeError):
    """Stable failure that never contains credential content."""


class _SystemKeyring:
    @staticmethod
    def _module():
        try:
            import keyring
        except (ImportError, RuntimeError) as exc:
            raise RuntimeCredentialError("credential_store_unavailable") from exc
        return keyring

    def get_password(self, service: str, account: str):
        return self._module().get_password(service, account)

    def set_password(self, service: str, account: str, value: str):
        return self._module().set_password(service, account, value)

    def delete_password(self, service: str, account: str):
        return self._module().delete_password(service, account)


class RuntimeCredentialStore:
    """Persist bounded JSON credential records under installation-scoped keys."""

    def __init__(self, keyring_backend=None) -> None:
        self.keyring = keyring_backend or _SystemKeyring()

    @staticmethod
    def account(installation_id: str, slot: str) -> str:
        if not _INSTALLATION.fullmatch(installation_id) or not _SLOT.fullmatch(slot):
            raise RuntimeCredentialError("credential_reference_invalid")
        return f"{installation_id}:{slot}"

    def reference(self, installation_id: str, slot: str) -> dict[str, str]:
        return {
            "service": KEYRING_SERVICE,
            "account": self.account(installation_id, slot),
        }

    def write(self, installation_id: str, slot: str, payload: dict[str, Any]) -> None:
        account = self.account(installation_id, slot)
        if not isinstance(payload, dict) or not payload:
            raise RuntimeCredentialError("credential_record_invalid")
        try:
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise RuntimeCredentialError("credential_record_invalid") from exc
        if len(raw.encode("utf-8")) > _MAX_CREDENTIAL_BYTES:
            raise RuntimeCredentialError("credential_record_too_large")
        try:
            self.keyring.set_password(KEYRING_SERVICE, account, raw)
        except Exception as exc:
            log.warning(
                "mcp_runtime_credential_write_failed",
                installation_id_digest=_id_digest(installation_id),
                error_type=type(exc).__name__,
            )
            raise RuntimeCredentialError("credential_store_unavailable") from exc

    def read(
        self,
        installation_id: str,
        slot: str,
        *,
        expected_resource: str | None = None,
    ) -> dict[str, Any]:
        account = self.account(installation_id, slot)
        try:
            raw = self.keyring.get_password(KEYRING_SERVICE, account)
        except Exception as exc:
            log.warning(
                "mcp_runtime_credential_read_failed",
                installation_id_digest=_id_digest(installation_id),
                error_type=type(exc).__name__,
            )
            raise RuntimeCredentialError("credential_store_unavailable") from exc
        if not raw:
            return {}
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > _MAX_CREDENTIAL_BYTES:
            raise RuntimeCredentialError("credential_record_invalid")
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeCredentialError("credential_record_invalid") from exc
        if not isinstance(payload, dict):
            raise RuntimeCredentialError("credential_record_invalid")
        if expected_resource is not None and payload.get("resource") != expected_resource:
            # Imported lazily to keep the credential layer independently reusable.
            from .oauth import OAuthError

            raise OAuthError("oauth_token_audience_mismatch")
        return payload

    def delete(self, installation_id: str, slot: str) -> None:
        account = self.account(installation_id, slot)
        try:
            if self.keyring.get_password(KEYRING_SERVICE, account):
                self.keyring.delete_password(KEYRING_SERVICE, account)
        except Exception as exc:
            log.warning(
                "mcp_runtime_credential_delete_failed",
                installation_id_digest=_id_digest(installation_id),
                error_type=type(exc).__name__,
            )
            raise RuntimeCredentialError("credential_store_unavailable") from exc
