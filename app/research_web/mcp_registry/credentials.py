"""OS-keyring-only secret storage for MCP Registry authentication."""

from __future__ import annotations

import json

from core.observability import get_logger

log = get_logger(__name__)
KEYRING_SERVICE = "ResearchWorkbench.MCPRegistry"


class CredentialError(RuntimeError):
    """Stable credential-store failure without secret content."""


class _SystemKeyring:
    @staticmethod
    def _module():
        try:
            import keyring
        except (ImportError, RuntimeError) as exc:
            raise CredentialError("credential_store_unavailable") from exc
        return keyring

    def get_password(self, service: str, account: str):
        return self._module().get_password(service, account)

    def set_password(self, service: str, account: str, password: str):
        return self._module().set_password(service, account, password)

    def delete_password(self, service: str, account: str):
        return self._module().delete_password(service, account)


class RegistryCredentialStore:
    def __init__(self, keyring_backend=None) -> None:
        self.keyring = keyring_backend or _SystemKeyring()

    @staticmethod
    def account(registry_id: str, auth_type: str) -> str:
        return f"{registry_id}:{auth_type}"

    def read(self, registry_id: str, auth_type: str) -> dict[str, str]:
        if auth_type == "none":
            return {}
        try:
            value = self.keyring.get_password(KEYRING_SERVICE, self.account(registry_id, auth_type))
        except Exception as exc:
            log.warning("mcp_registry_credential_read_failed", registry_id=registry_id)
            raise CredentialError("credential_store_unavailable") from exc
        if not value:
            return {}
        if auth_type == "bearer" and not value.startswith("{"):
            return {"token": value}
        try:
            payload = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise CredentialError("credential_record_invalid") from exc
        if not isinstance(payload, dict) or any(
            not isinstance(key, str) or not isinstance(item, str) for key, item in payload.items()
        ):
            raise CredentialError("credential_record_invalid")
        return payload

    def write(self, registry_id: str, auth_type: str, payload: dict[str, str]) -> None:
        try:
            value = (
                payload["token"]
                if auth_type == "bearer" and set(payload) == {"token"}
                else json.dumps(payload, separators=(",", ":"))
            )
            self.keyring.set_password(
                KEYRING_SERVICE,
                self.account(registry_id, auth_type),
                value,
            )
        except Exception as exc:
            log.warning("mcp_registry_credential_write_failed", registry_id=registry_id)
            raise CredentialError("credential_store_unavailable") from exc

    def delete(self, registry_id: str, auth_type: str) -> None:
        if auth_type == "none":
            return
        account = self.account(registry_id, auth_type)
        try:
            if self.keyring.get_password(KEYRING_SERVICE, account):
                self.keyring.delete_password(KEYRING_SERVICE, account)
        except Exception as exc:
            log.warning("mcp_registry_credential_delete_failed", registry_id=registry_id)
            raise CredentialError("credential_store_unavailable") from exc

    def configured(self, registry_id: str, auth_type: str) -> bool:
        if auth_type == "none":
            return False
        try:
            return bool(self.read(registry_id, auth_type))
        except CredentialError:
            return False

    def authorization(self, registry_id: str, auth_type: str) -> str | None:
        payload = self.read(registry_id, auth_type)
        token = payload.get("token") or payload.get("access_token")
        return f"Bearer {token}" if token else None

    def replace(
        self,
        registry_id: str,
        old_type: str,
        new_type: str,
        payload: dict[str, str] | None,
    ) -> None:
        if old_type == new_type:
            if payload:
                self.write(registry_id, new_type, payload)
            return

        previous_new = self.read(registry_id, new_type)
        if payload:
            self.write(registry_id, new_type, payload)
        try:
            self.delete(registry_id, old_type)
        except CredentialError:
            try:
                if previous_new:
                    self.write(registry_id, new_type, previous_new)
                else:
                    self.delete(registry_id, new_type)
            except CredentialError:
                log.error("mcp_registry_credential_compensation_failed", registry_id=registry_id)
            raise
