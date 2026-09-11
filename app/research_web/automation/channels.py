"""Delivery-channel metadata with operational configuration in the OS keyring."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from urllib.parse import urlsplit
from uuid import uuid4

from core.observability import get_logger

from .models import AutomationError, DeliveryChannelPut

log = get_logger(__name__)
KEYRING_SERVICE = "ResearchWorkbench.Delivery"


class _SystemKeyring:
    @staticmethod
    def _module():
        try:
            import keyring
        except (ImportError, RuntimeError) as exc:
            raise AutomationError(
                "系统凭据库不可用", "delivery_credential_store_unavailable", 503
            ) from exc
        return keyring

    def get_password(self, service: str, account: str):
        return self._module().get_password(service, account)

    def set_password(self, service: str, account: str, value: str):
        return self._module().set_password(service, account, value)

    def delete_password(self, service: str, account: str):
        return self._module().delete_password(service, account)


def _safe_endpoint(value: str) -> str:
    parsed = urlsplit(value)
    try:
        literal = ipaddress.ip_address(parsed.hostname or "")
    except ValueError:
        literal = None
    loopback = literal is not None and literal.is_loopback
    if parsed.username or parsed.password or not parsed.hostname or parsed.fragment:
        raise AutomationError("交付地址格式不安全", "delivery_endpoint_invalid", 422)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise AutomationError(
            "交付地址必须使用 HTTPS 或字面 loopback", "delivery_endpoint_invalid", 422
        )
    return value


class DeliveryChannelStore:
    def __init__(self, store, *, keyring_backend=None) -> None:
        self.store = store
        self.keyring = keyring_backend or _SystemKeyring()
        self.store.data.setdefault("delivery_channels", {})

    _validated_endpoint = staticmethod(_safe_endpoint)

    @staticmethod
    def _account(channel_id: str) -> str:
        return f"channel:{channel_id}:configuration"

    def list(self) -> dict:
        rows = sorted(
            self.store.data["delivery_channels"].values(),
            key=lambda item: (item["name"].casefold(), item["id"]),
        )
        return {"items": [dict(row) for row in rows]}

    def get(self, channel_id: str) -> dict:
        try:
            return dict(self.store.data["delivery_channels"][channel_id])
        except KeyError as exc:
            raise AutomationError("交付渠道不存在", "delivery_channel_not_found", 404) from exc

    def configuration(self, channel_id: str) -> dict:
        self.get(channel_id)
        try:
            raw = self.keyring.get_password(KEYRING_SERVICE, self._account(channel_id))
            value = json.loads(raw) if raw else None
        except Exception as exc:
            log.warning(
                "delivery_credential_read_failed",
                channel_id_digest=hashlib.sha256(channel_id.encode()).hexdigest()[:16],
                error_type=type(exc).__name__,
            )
            raise AutomationError(
                "交付渠道凭据不可读取", "delivery_credential_store_unavailable", 503
            ) from exc
        if not isinstance(value, dict):
            raise AutomationError("交付渠道尚未配置", "delivery_channel_unconfigured", 409)
        return value

    def put(self, body: DeliveryChannelPut) -> dict:
        channel_id = body.id or f"delivery-{uuid4().hex}"
        existing = self.store.data["delivery_channels"].get(channel_id)
        previous_row = dict(existing) if existing else None
        previous_configuration = self.configuration(channel_id) if existing else None
        payload = body.model_dump(mode="json", exclude_none=True)
        endpoint = payload.get("endpoint")
        if endpoint:
            payload["endpoint"] = _safe_endpoint(endpoint)
        if body.secret is None and previous_configuration and previous_configuration.get("secret"):
            payload["secret"] = previous_configuration["secret"]
        if body.kind == "webhook" and not payload.get("secret"):
            raise AutomationError("Webhook 签名秘密未配置", "delivery_channel_unconfigured", 422)
        account = self._account(channel_id)
        try:
            self.keyring.set_password(
                KEYRING_SERVICE,
                account,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )
        except Exception as exc:
            log.warning(
                "delivery_credential_write_failed",
                channel_id_digest=hashlib.sha256(channel_id.encode()).hexdigest()[:16],
                error_type=type(exc).__name__,
            )
            raise AutomationError(
                "交付渠道凭据无法保存", "delivery_credential_store_unavailable", 503
            ) from exc
        row = {
            "id": channel_id,
            "name": body.name,
            "kind": body.kind,
            "enabled": body.enabled,
            "configured": True,
            "credential_ref": {"service": KEYRING_SERVICE, "account": account},
        }
        self.store.data["delivery_channels"][channel_id] = row
        try:
            self.store.save()
        except Exception:
            if previous_row is None:
                self.store.data["delivery_channels"].pop(channel_id, None)
            else:
                self.store.data["delivery_channels"][channel_id] = previous_row
            try:
                if previous_configuration is None:
                    self.keyring.delete_password(KEYRING_SERVICE, account)
                else:
                    self.keyring.set_password(
                        KEYRING_SERVICE,
                        account,
                        json.dumps(
                            previous_configuration,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
            except Exception as cleanup_exc:  # noqa: BLE001 - keyring backends vary.
                log.warning(
                    "delivery_credential_cleanup_failed",
                    channel_id_digest=hashlib.sha256(channel_id.encode()).hexdigest()[:16],
                    error_type=type(cleanup_exc).__name__,
                )
            raise
        log.info(
            "delivery_channel_saved",
            channel_id_digest=hashlib.sha256(channel_id.encode()).hexdigest()[:16],
            status="configured",
        )
        return dict(row)

    def delete(self, channel_id: str) -> dict:
        existing = self.get(channel_id)
        configuration = self.configuration(channel_id)
        account = self._account(channel_id)
        try:
            self.keyring.delete_password(KEYRING_SERVICE, account)
        except Exception as exc:
            raise AutomationError(
                "交付渠道凭据无法删除", "delivery_credential_store_unavailable", 503
            ) from exc
        self.store.data["delivery_channels"].pop(channel_id)
        try:
            self.store.save()
        except Exception:
            self.store.data["delivery_channels"][channel_id] = existing
            try:
                self.keyring.set_password(
                    KEYRING_SERVICE,
                    account,
                    json.dumps(configuration, ensure_ascii=False, separators=(",", ":")),
                )
            except Exception as cleanup_exc:  # noqa: BLE001 - preserve original failure.
                log.warning(
                    "delivery_credential_restore_failed",
                    channel_id_digest=hashlib.sha256(channel_id.encode()).hexdigest()[:16],
                    error_type=type(cleanup_exc).__name__,
                )
            raise
        return {"deleted": True, "id": channel_id}
