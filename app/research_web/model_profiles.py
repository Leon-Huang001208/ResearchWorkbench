"""Named model connections; no second credential store or transcript projection."""

from __future__ import annotations

import asyncio
import secrets
from uuid import uuid4

from core.observability import get_logger

from .client import RuntimeFailure
from .delivery import FINAL
from .model_profile_registry import (
    LEGACY_IDS,
    PROFILE_PREFIX,
    bootstrap_profiles,
    validate_registry,
)
from .store import StoreError

log = get_logger(__name__)


class ModelProfilesMixin:
    def model_profile_registry(self):
        try:
            return bootstrap_profiles(self.store.data)
        except (ValueError, KeyError, TypeError):
            raise RuntimeFailure(
                "模型连接索引不可读取；原配置未改动", "model_profile_registry_invalid"
            ) from None

    def model_profile_identity(self, provider):
        registry = self.model_profile_registry()
        identity = registry["routes"].get(provider)
        if identity is None:
            raise RuntimeFailure("此模型服务尚未配置连接", "model_connection_missing")
        return identity

    def assert_session_model_profile(self, row):
        provider = row.get("model_provider", "deepseek-official")
        expected = row.get("model_profile_id") or LEGACY_IDS.get(provider)
        if expected != self.model_profile_identity(provider):
            raise RuntimeFailure(
                "此会话绑定的模型连接当前未激活，请切回原连接后继续", "model_profile_changed"
            )

    async def require_model_profiles_idle(self):
        """Reuse the existing strict admission/receipt/child/delivery idle gate."""
        if self.connected != {"mux", "host"}:
            raise RuntimeFailure("研究连接状态未确认，暂时不能修改连接", "model_activity_unknown")
        native = await self.client.rpc("session.list", {})
        if (
            not isinstance(native, dict)
            or not isinstance(native.get("items"), list)
            or any(
                not isinstance(row, dict) or type(row.get("running")) is not bool
                for row in native["items"]
            )
        ):
            raise RuntimeFailure("研究状态无法确认，暂时不能修改连接", "model_activity_unknown")
        if any(self.running.values()):
            raise RuntimeFailure("研究正在运行，结束后才能修改连接", "model_change_busy")
        if (
            any(row["running"] for row in native["items"])
            or any(self.approvals.values())
            or any(self.questions.values())
        ):
            raise RuntimeFailure("研究或待处理交互尚未结束", "model_change_busy")
        if any(
            not isinstance(receipt, dict) or receipt.get("status") in {None, "pending", "unknown"}
            for receipt in self.store.data["receipts"].values()
        ):
            raise RuntimeFailure("存在未确认的受理请求", "model_activity_unknown")
        for row in self.store.data["sessions"].values():
            if row.get("created") is False:
                continue
            if row.get("created") is not True or row.get("status") not in {
                "idle",
                "completed",
                "failed",
                "cancelled",
            }:
                raise RuntimeFailure("会话活动或恢复状态尚未确认结束", "model_activity_unknown")
            children = await self.client.rpc(
                "subagent.list", {"parentSessionId": row["id"], "activityOnly": True}
            )
            if (
                not isinstance(children, dict)
                or not isinstance(children.get("entries"), list)
                or any(
                    not isinstance(child, dict)
                    or child.get("kind") != "child"
                    or child.get("activity") != "inactive"
                    for child in children["entries"]
                )
            ):
                raise RuntimeFailure("子研究活动尚未确认结束", "model_change_busy")
            delivery = self.delivery.current(row["id"])
            if delivery and delivery.get("status") not in FINAL:
                raise RuntimeFailure("文件交付尚未确认结束", "model_change_busy")

    def model_profile_referenced(self, identity):
        for row in self.store.data["sessions"].values():
            if (
                row.get("model_profile_id")
                or LEGACY_IDS.get(row.get("model_provider", "deepseek-official"))
            ) == identity:
                return True
        for row in self.store.data.get("automations", {}).values():
            task = row.get("research_task")
            if (
                isinstance(task, dict)
                and (row.get("model_profile_id") or LEGACY_IDS.get(task.get("model_provider")))
                == identity
            ):
                return True
        return False

    def _store_model_profiles(self, registry):
        validate_registry(registry)
        old = self.store.data.get("model_profiles")
        self.store.data["model_profiles"] = registry
        try:
            self.store.save()
        except (StoreError, OSError):
            if old is None:
                self.store.data.pop("model_profiles", None)
            else:
                self.store.data["model_profiles"] = old
            raise

    async def list_model_profiles(self):
        registry = self.model_profile_registry()
        items, probes = [], []
        semaphore = asyncio.Semaphore(4)

        async def describe(public, item):
            async with semaphore:
                try:
                    ref = (
                        PROFILE_PREFIX + item["id"]
                        if "model_profiles" in self.store.data
                        else item["credential_ref"]
                    )
                    result = await self.client.rpc("credentials.describe", {"refs": [ref]})
                    configured = result.get("credentials", {}).get(ref, {}).get("configured")
                    public["credential_configured"] = (
                        configured if type(configured) is bool else None
                    )
                except RuntimeFailure:
                    log.warning("research_model_profile_credential_unavailable")

        for item in registry["items"].values():
            if item["archived"]:
                continue
            public = {
                key: item[key]
                for key in (
                    "id",
                    "name",
                    "provider",
                    "model",
                    "credential_mode",
                    "base_url",
                    "protocol",
                    "uncertain",
                )
                if key in item
            }
            public["active"] = item["id"] == registry["active_id"]
            public["credential_configured"] = None
            public["credential_required"] = item["credential_mode"] != "none"
            items.append(public)
            if public["credential_required"]:
                probes.append(describe(public, item))
        try:
            async with asyncio.timeout(15):
                await asyncio.gather(*probes)
        except TimeoutError:
            log.warning("research_model_profile_credential_timeout")
        return {"items": items, "active_id": registry["active_id"]}

    def _sync_profile_flags(self, registry):
        for provider, identity in registry["routes"].items():
            item = registry["items"][identity]
            _, uncertain, cleared = self._model_plane(provider)
            self.store.data[uncertain] = bool(item.get("uncertain"))
            self.store.data[cleared] = bool(item.get("cleared"))

    async def save_model_profile(self, configuration, identity=None):
        await self.ensure_owned()
        if self.model_test_lock.locked():
            raise RuntimeFailure("模型操作正在运行", "model_change_busy")
        async with self.model_test_lock, self.lock:
            await self.require_model_profiles_idle()
            registry = self.model_profile_registry()
            if len(registry["items"]) >= 256 and identity is None:
                raise StoreError("模型连接数量已达上限", "model_profile_limit", 409)
            old = registry["items"].get(identity) if identity else None
            if identity is not None and (old is None or old["archived"]):
                raise StoreError("模型连接不存在", "model_profile_missing", 404)
            provider = configuration.provider
            from .tenant_policy import enabled, enforce_model_configuration

            if enabled():
                enforce_model_configuration({"provider": provider})
            if old and old["provider"] != provider:
                raise StoreError(
                    "已有连接不能更换协议类型，请添加新连接", "model_profile_provider_changed", 409
                )
            if old is not None and identity == registry["routes"].get(provider):
                # Active routes may change name/credentials, but their endpoint and
                # model must be changed via a separate profile and explicit activation.
                fields = ("model", "base_url", "credential_mode")
                if any(getattr(configuration, key) != old.get(key) for key in fields):
                    raise StoreError(
                        "请新建连接并显式切换，以保留已有会话绑定", "model_profile_active_edit", 409
                    )
            if configuration.clear_api_key and configuration.api_key is not None:
                raise StoreError("替换与清除不能同时提交", "invalid_request", 422)
            if (
                old
                and old.get("uncertain")
                and configuration.api_key is None
                and not configuration.clear_api_key
            ):
                raise RuntimeFailure(
                    "凭据回执未知，请重新录入或明确清除", "model_configuration_uncertain"
                )
            if provider == "deepseek-official":
                catalog = await self.client.rpc("llm.models", {})
                if not any(
                    group.get("id") == provider
                    and any(
                        model.get("id") == configuration.model for model in group.get("models", [])
                    )
                    for group in catalog.get("groups", [])
                ):
                    raise RuntimeFailure("固定 Runtime 不支持此模型", "model_unavailable")
            if (
                old
                and provider == "openai-compatible"
                and configuration.credential_mode == "api_key"
                and configuration.api_key is None
                and not configuration.clear_api_key
                and (
                    old.get("base_url") != configuration.base_url
                    or old.get("credential_mode") != "api_key"
                )
            ):
                raise RuntimeFailure(
                    "新端点须重新录入专用 Key", "model_connection_key_reentry_required"
                )
            identity = identity or uuid4().hex
            item = {
                "id": identity,
                "name": configuration.name.strip(),
                "provider": provider,
                "model": configuration.model,
                "credential_mode": configuration.credential_mode,
                "credential_ref": old["credential_ref"] if old else PROFILE_PREFIX + identity,
                "archived": False,
                "revision": secrets.token_hex(16),
            }
            if provider == "openai-compatible":
                item.update(base_url=configuration.base_url, protocol=configuration.protocol)
            changing = configuration.api_key is not None or configuration.clear_api_key
            if changing and identity == registry["active_id"]:
                self.store.data.pop("model_test", None)
                self.store.data.pop("model_application", None)
            if (
                changing
                and provider == "openai-compatible"
                and identity == registry["routes"].get(provider)
            ):
                # Invalidate any prepared compatible adapter which captured the old Key.
                self.store.data["compatible_model_connection_revision"] = item["revision"]
            item["uncertain"] = changing or bool(old and old.get("uncertain"))
            item["cleared"] = bool(old and old.get("cleared"))
            registry["items"][identity] = item
            self._sync_profile_flags(registry)
            self._store_model_profiles(registry)
            if changing:
                try:
                    await self.client.rpc(
                        "credentials.unset" if configuration.clear_api_key else "credentials.set",
                        {
                            "ref": PROFILE_PREFIX + identity,
                            **(
                                {"value": configuration.api_key}
                                if not configuration.clear_api_key
                                else {}
                            ),
                        },
                    )
                except (RuntimeFailure, OSError, asyncio.CancelledError) as exc:
                    # Cancellation also preserves the durable unknown marker.
                    log.warning(
                        "research_model_profile_credential_unknown", error_type=type(exc).__name__
                    )
                    if isinstance(exc, asyncio.CancelledError):
                        raise
                    raise RuntimeFailure(
                        "凭据提交结果未知，请重新录入或明确清除", "model_configuration_uncertain"
                    ) from None
                item["uncertain"] = False
                item["cleared"] = configuration.clear_api_key
                self._sync_profile_flags(registry)
                try:
                    self._store_model_profiles(registry)
                except (StoreError, OSError):
                    item["uncertain"] = True
                    self._sync_profile_flags(registry)
                    log.warning("research_model_profile_commit_unknown")
                    raise RuntimeFailure(
                        "凭据提交结果未知，请刷新后处理", "model_configuration_uncertain"
                    ) from None
            log.info("research_model_profile_saved")
            return {"configured": True, "id": identity}

    async def activate_model_profile(self, identity):
        registry = self.model_profile_registry()
        item = registry["items"].get(identity)
        if item is None or item["archived"]:
            raise StoreError("模型连接不存在", "model_profile_missing", 404)
        from .tenant_policy import enabled, enforce_model_configuration

        if enabled():
            enforce_model_configuration({"provider": item["provider"]})
        return await self.configure_model(
            item["provider"],
            item["model"],
            base_url=item.get("base_url"),
            protocol=item.get("protocol"),
            credential_mode=item["credential_mode"],
            _profile_id=identity,
        )

    async def archive_model_profile(self, identity):
        await self.ensure_owned()
        if self.model_test_lock.locked():
            raise RuntimeFailure("模型操作正在运行", "model_change_busy")
        async with self.model_test_lock, self.lock:
            await self.require_model_profiles_idle()
            registry = self.model_profile_registry()
            item = registry["items"].get(identity)
            if item is None or item["archived"]:
                raise StoreError("模型连接不存在", "model_profile_missing", 404)
            if identity in registry["routes"].values():
                raise StoreError("请先切换此服务商的当前连接", "model_profile_in_use", 409)
            if self.model_profile_referenced(identity):
                raise StoreError(
                    "此连接仍被会话或日程引用，保留连接以便切回后继续",
                    "model_profile_referenced",
                    409,
                )
            # Soft removal retains the credential even without existing bindings.
            item["archived"] = True
            self._store_model_profiles(registry)
            log.info("research_model_profile_archived")
            return {"archived": True, "bindings_preserved": True}
