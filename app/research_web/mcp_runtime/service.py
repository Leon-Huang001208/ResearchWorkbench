"""Feature-gated orchestration for MCP installation, authorization and execution."""

from __future__ import annotations

import asyncio
import copy
import functools
import inspect
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.research_web.datahub.security import atomic_json, directory, read_file
from app.research_web.mcp_registry.service import RegistryError
from app.research_web.store import StoreError
from core.observability import get_logger

from .authorization import AuthorizationError, AuthorizationManager, ExactToolAllowlist
from .control import authenticate
from .installation_store import INSTALLATION_ID
from .package_planner import PackagePlanner
from .sdk_host import MCPHostError, SDKHost

log = get_logger(__name__)


def sdk_operation(function):
    """Track pending SDK work so a tenant restart cannot race a process birth."""

    @functools.wraps(function)
    async def tracked(self, *args, **kwargs):
        token = uuid4().hex
        self.operations.add(token)
        try:
            return await function(self, *args, **kwargs)
        finally:
            if getattr(self.host, "managed_cleanup_blocked", False):
                log.error("mcp_operation_retained_cleanup_blocked")
            else:
                self.operations.discard(token)

    return tracked


class MCPRuntimeError(RegistryError):
    """Stable, non-secret API failure handled by the existing MCP error boundary."""

    def __init__(
        self,
        code: str = "mcp_runtime_error",
        status: int = 400,
        message: str = "MCP Runtime 请求失败",
    ) -> None:
        super().__init__(message, code, status)


def runtime_feature_enabled() -> bool:
    return os.environ.get("RESEARCH_MCP_RUNTIME_ENABLED", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        result = value.model_dump(mode="json")
    elif isinstance(value, dict):
        result = copy.deepcopy(value)
    else:
        result = copy.deepcopy(vars(value))
    if not isinstance(result, dict):
        raise MCPRuntimeError("mcp_runtime_projection_invalid", 503)
    return result


class MCPRuntimeService:
    """Coordinate trusted MCP components while keeping public requests declarative."""

    def __init__(
        self,
        data_root: Path | None = None,
        *,
        enabled: bool | None = None,
        registry: Any = None,
        resolver: Any = None,
        planner: Any = None,
        tokens: Any = None,
        store: Any = None,
        installer: Any = None,
        host: Any = None,
        authorization: Any = None,
        idle_gate: Callable[[], Any] | None = None,
        restart_callback: Callable[[list[dict[str, Any]]], Any] | None = None,
        control: dict[str, Any] | None = None,
        oauth: Any = None,
        oauth_exchange: Callable[..., Any] | None = None,
        approval_timeout_seconds: float = 900,
        managed_only: bool | None = None,
        evidence_store: Any = None,
    ) -> None:
        self.enabled = runtime_feature_enabled() if enabled is None else enabled
        self.managed_only = (
            os.environ.get("RWB_TENANT_MODE") == "1" if managed_only is None else managed_only
        )
        self.registry = registry
        self.resolver = resolver
        self.planner = planner if planner is not None else PackagePlanner()
        self.tokens = tokens
        self.store = store
        self.installer = installer
        self.host = host if host is not None else SDKHost()
        self.authorization = authorization
        self._data_root = Path(data_root) if data_root is not None else None
        if self.enabled and self._data_root is not None and self.authorization is None:
            self.authorization = AuthorizationManager(self._data_root)
        self.idle_gate = idle_gate
        self.restart_callback = restart_callback
        self.control = copy.deepcopy(control)
        self.evidence_store = evidence_store
        self.oauth = oauth
        self.oauth_exchange = oauth_exchange
        if not isinstance(approval_timeout_seconds, (int, float)) or not (
            1 <= approval_timeout_seconds <= 900
        ):
            raise ValueError("approval_timeout_invalid")
        self.approval_timeout_seconds = float(approval_timeout_seconds)
        self._pending: dict[str, Any] = {}
        self._states: dict[str, str] = {}
        self._capabilities: dict[str, dict[str, Any]] = {}
        self._targets: dict[str, Any] = {}
        self._active: set[str] = set()
        self.operations: set[str] = set()
        self._approval_waiters: dict[str, asyncio.Event] = {}
        self._approval_decisions: dict[str, str] = {}
        self._automation_locks: dict[str, dict[tuple[str, str], dict[str, str]]] = {}
        if self.enabled:
            self._load_runtime_state()
            if self.managed_only:
                pending = self._plugin_activation()
                if pending and pending.get("state") == "staged":
                    self._active = set(pending["previous"])

    async def start(self) -> None:
        """Rebuild active targets from immutable manifests without persisting secrets."""

        if not self.enabled:
            log.info("mcp_runtime_service_started", enabled=False)
            return
        for installation_id in sorted(self._active):
            manifest = self._manifest(installation_id)
            await self._managed_guard(manifest, require_schema=False)
            self._targets[installation_id] = await self._resolve_target(manifest)
        log.info("mcp_runtime_service_started", enabled=True)

    async def close(self) -> None:
        """Close optional Host resources; disabled runtime shutdown is always safe."""

        if not self.enabled:
            return
        self._automation_locks.clear()
        closer = getattr(self.host, "close", None)
        if closer is not None:
            try:
                await _await(closer())
            except Exception as exc:  # noqa: BLE001
                log.warning("mcp_runtime_close_failed", error_type=type(exc).__name__)

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise MCPRuntimeError("mcp_runtime_disabled", 404, "MCP Runtime 功能未启用")

    def _require_components(self, *names: str) -> None:
        for name in names:
            if getattr(self, name, None) is None:
                raise MCPRuntimeError(f"mcp_{name}_unavailable", 503)

    async def preview(self, request: Any) -> dict[str, Any]:
        self._ensure_enabled()
        self._require_components("registry", "resolver", "tokens")
        try:
            detail = await _await(
                self.registry.version_detail(
                    request.registry_id,
                    request.server_name,
                    request.server_version,
                    refresh=True,
                )
            )
            resolved = await _await(self.resolver.resolve(request, copy.deepcopy(detail)))
            plan = await _await(self.planner.plan(resolved))
            token = self.tokens.issue(plan)
        except MCPRuntimeError:
            raise
        except Exception as exc:
            log.warning("mcp_installation_preview_failed", error_type=type(exc).__name__)
            raise MCPRuntimeError("mcp_installation_preview_failed", 422) from exc
        if len(self._pending) >= 128:
            self._pending.pop(next(iter(self._pending)))
        self._pending[token] = plan
        return {"plan": _dump(plan), "confirmation_token": token}

    async def install(
        self,
        confirmation_token: str,
        environment_values: dict[str, str],
    ) -> dict[str, Any]:
        self._ensure_enabled()
        self._require_components("tokens", "store", "installer")
        plan = self._pending.get(confirmation_token)
        if plan is None:
            raise MCPRuntimeError("confirmation_token_invalid", 409)
        if self.managed_only:
            self._require_managed_process_isolation({"plan": plan})
        expected_names = set(_field(plan, "environment_names", []))
        if set(environment_values) != expected_names or any(
            not isinstance(value, str)
            or not value
            or "\x00" in value
            or len(value.encode("utf-8")) > 16 * 1024
            for value in environment_values.values()
        ):
            raise MCPRuntimeError("mcp_environment_values_invalid", 422)
        manifest = None
        try:
            manifest = self.store.create(plan, confirmation_token, self.tokens)
            installation_id = str(_field(manifest, "id"))
            self._set_state(installation_id, "installing")
            await _await(self.installer.install(manifest, dict(environment_values)))
        except Exception as exc:
            if manifest is not None:
                self._set_state(str(_field(manifest, "id")), "install_failed")
            log.warning("mcp_installation_failed", error_type=type(exc).__name__)
            raise MCPRuntimeError("mcp_installation_failed", 503) from exc
        self._pending.pop(confirmation_token, None)
        installation_id = str(_field(manifest, "id"))
        self._set_state(installation_id, "installed")
        return {"installation": self._project_manifest(manifest), "status": "installed"}

    def list_installations(self) -> dict[str, Any]:
        self._ensure_enabled()
        self._require_components("store")
        try:
            manifests = self.store.list()
        except Exception as exc:
            raise MCPRuntimeError("mcp_installation_store_unavailable", 503) from exc
        return {"items": [self._installation_projection(item) for item in manifests]}

    def installation(self, installation_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        return self._installation_projection(self._manifest(installation_id))

    def status(self, installation_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        manifest = self._manifest(installation_id)
        return {
            "id": str(_field(manifest, "id")),
            "status": self._state(installation_id),
            "active": installation_id in self._active,
            "capabilities_available": installation_id in self._capabilities,
        }

    def capabilities(self, installation_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        self._manifest(installation_id)
        value = self._capabilities.get(installation_id)
        if value is None:
            raise MCPRuntimeError("mcp_capabilities_unavailable", 409)
        return self._capability_projection(installation_id, value)

    @sdk_operation
    async def probe(self, installation_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        self._require_components("host", "authorization", "installer")
        manifest = self._manifest(installation_id)
        await self._managed_guard(manifest, require_schema=False)
        target = await self._target(manifest)
        try:
            capabilities = await _await(self.host.capabilities(target))
            tools = capabilities.get("tools") if isinstance(capabilities, dict) else None
            if not isinstance(tools, list):
                raise TypeError("invalid capabilities")
            version = str(_field(_field(manifest, "plan"), "server_version"))
            for tool in tools:
                if not isinstance(tool, dict):
                    raise TypeError("invalid tool")
                self.authorization.register_tool(
                    installation_id=installation_id,
                    version=version,
                    tool_name=tool.get("name"),
                    input_schema=tool.get("inputSchema", tool.get("input_schema")),
                    output_schema=tool.get("outputSchema", tool.get("output_schema")),
                    annotations=tool.get("annotations"),
                    description="" if tool.get("description") is None else tool["description"],
                )
        except Exception as exc:
            self._set_state(installation_id, "health_failed")
            log.warning("mcp_installation_probe_failed", error_type=type(exc).__name__)
            raise MCPRuntimeError("mcp_probe_failed", 503) from exc
        self._capabilities[installation_id] = copy.deepcopy(capabilities)
        self._set_state(installation_id, "ready")
        return self._capability_projection(installation_id, capabilities)

    async def enable(self, installation_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        self._require_components("authorization", "restart_callback", "idle_gate")
        await self.probe(installation_id)
        await self._managed_guard(
            self._manifest(installation_id), capabilities=self._capabilities.get(installation_id)
        )
        await self._require_idle()
        previous = set(self._active)
        candidate = previous | {installation_id}
        await self._activate(candidate, previous, installation_id)
        self._active = candidate
        self._set_state(installation_id, "enabled")
        return self.status(installation_id)

    def _plugin_activation(self):
        if self._data_root is None:
            return None
        path = self._data_root / "mcp-runtime/plugin-activation.json"
        if not path.exists() and not path.is_symlink():
            return None
        with directory(self._data_root, ("mcp-runtime",), private=True) as folder:
            return json.loads(
                read_file(folder, "plugin-activation.json", private=True, limit=65536)
            )

    def _save_plugin_activation(self, value):
        if self._data_root is None:
            raise MCPRuntimeError("mcp_managed_approval_unavailable", 403)
        with directory(self._data_root, ("mcp-runtime",), private=True) as folder:
            atomic_json(folder, "plugin-activation.json", value)

    async def stage_managed_enable(self, installation_id, *, disable=False):
        """Prepare next DSH bindings without claiming the current Host activated."""
        if not self.managed_only:
            return (
                await self.disable(installation_id)
                if disable
                else await self.enable(installation_id)
            )
        self._ensure_enabled()
        pending = self._plugin_activation()
        if pending and pending.get("state") == "staged":
            if (
                pending["installation_id"] != installation_id
                or pending.get("disable", False) != disable
            ):
                raise MCPRuntimeError("mcp_activation_pending", 409)
            return {
                "status": "restart_required",
                "transaction_id": pending["id"],
                "installation_id": installation_id,
            }
        self._manifest(installation_id)
        if not disable:
            await self.probe(installation_id)
            await self._managed_guard(
                self._manifest(installation_id), capabilities=self._capabilities[installation_id]
            )
        await self._require_idle()
        previous = sorted(self._active)
        candidate = sorted(
            self._active - {installation_id} if disable else self._active | {installation_id}
        )
        if candidate == previous:
            return {
                "status": "ready",
                "installation_id": installation_id,
                "active": installation_id in self._active,
            }
        transaction = {
            "id": uuid4().hex,
            "installation_id": installation_id,
            "previous": previous,
            "candidate": candidate,
            "state": "staged",
            "disable": disable,
        }
        self._save_plugin_activation(transaction)
        self._write_active(set(candidate))
        return {
            "status": "restart_required",
            "transaction_id": transaction["id"],
            "installation_id": installation_id,
        }

    async def commit_managed_activation(self, transaction_id):
        transaction = self._plugin_activation()
        if not transaction or transaction["id"] != transaction_id:
            raise MCPRuntimeError("mcp_activation_transaction_changed", 409)
        if transaction["state"] == "committed":
            return {"status": "ready", "transaction_id": transaction_id}
        if transaction["state"] != "staged":
            raise MCPRuntimeError("mcp_activation_transaction_changed", 409)
        for installation in transaction["candidate"]:
            await self.probe(installation)
            await self._managed_guard(
                self._manifest(installation), capabilities=self._capabilities[installation]
            )
        self._active = set(transaction["candidate"])
        self._set_state(
            transaction["installation_id"], "disabled" if transaction.get("disable") else "enabled"
        )
        transaction["state"] = "committed"
        self._save_plugin_activation(transaction)
        return {"status": "ready", "transaction_id": transaction_id}

    def rollback_managed_activation(self, transaction_id):
        transaction = self._plugin_activation()
        if not transaction or transaction["id"] != transaction_id:
            raise MCPRuntimeError("mcp_activation_transaction_changed", 409)
        if transaction["state"] == "rolled_back":
            return {"status": "rolled_back", "transaction_id": transaction_id}
        if transaction["state"] != "staged":
            raise MCPRuntimeError("mcp_activation_already_committed", 409)
        self._write_active(set(transaction["previous"]))
        self._active = set(transaction["previous"])
        transaction["state"] = "rolled_back"
        self._save_plugin_activation(transaction)
        return {"status": "rolled_back", "transaction_id": transaction_id}

    async def disable(self, installation_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        self._manifest(installation_id)
        self._require_components("authorization", "restart_callback", "idle_gate")
        await self._require_idle()
        previous = set(self._active)
        candidate = previous - {installation_id}
        await self._activate(candidate, previous, installation_id)
        self._active = candidate
        self._set_state(installation_id, "disabled")
        return self.status(installation_id)

    async def update(self, installation_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        self._manifest(installation_id)
        # An immutable installation cannot be updated in place. A new Registry
        # version must pass the same preview and explicit confirmation flow as a
        # first install so changed argv, artifacts and schemas remain visible.
        raise MCPRuntimeError(
            "mcp_update_requires_preview",
            409,
            "MCP 更新必须从新版本的完整安装预览开始",
        )

    async def delete(self, installation_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        manifest = self._manifest(installation_id)
        if installation_id in self._active:
            raise MCPRuntimeError("mcp_installation_active", 409)
        self._require_components("installer", "store")
        remover = getattr(self.installer, "remove", None)
        delete = getattr(self.store, "delete", None)
        if remover is None or delete is None:
            raise MCPRuntimeError("mcp_installation_delete_unavailable", 503)
        try:
            await _await(remover(manifest))
            await _await(delete(installation_id))
        except Exception as exc:
            raise MCPRuntimeError("mcp_installation_delete_failed", 503) from exc
        self._states.pop(installation_id, None)
        self._targets.pop(installation_id, None)
        self._capabilities.pop(installation_id, None)
        return {"id": installation_id, "deleted": True}

    def classify_tool(
        self,
        installation_id: str,
        tool_name: str,
        *,
        risk_tier: str,
        allow_unattended: bool,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        self._manifest(installation_id)
        self._require_components("authorization")
        try:
            return self.authorization.classify_tool(
                installation_id,
                tool_name,
                risk_tier=risk_tier,
                allow_unattended=allow_unattended,
            )
        except AuthorizationError as exc:
            raise self._authorization_error(exc) from exc

    def authorize_session(self, session_id: str, **binding: Any) -> dict[str, Any]:
        self._ensure_enabled()
        installation_id = binding.get("installation_id")
        if installation_id not in self._active:
            raise MCPRuntimeError("mcp_installation_not_active", 409)
        self._require_components("authorization")
        try:
            return self.authorization.authorize_session(session_id=session_id, **binding)
        except AuthorizationError as exc:
            raise self._authorization_error(exc) from exc

    def register_automation_session(self, session_id: str, locks: list[dict[str, Any]]) -> None:
        """Bind exact unattended locks from the trusted Automation service."""

        self._ensure_enabled()
        self._require_components("authorization")
        exact: dict[tuple[str, str], dict[str, str]] = {}
        for lock in locks:
            key = (str(lock.get("installation_id") or ""), str(lock.get("tool_name") or ""))
            snapshots = [
                item
                for item in self.authorization.list_tools()
                if (item.get("installation_id"), item.get("tool_name")) == key
                and item.get("status") == "active"
            ]
            if (
                len(snapshots) != 1
                or snapshots[0].get("risk_tier") != "read_only"
                or snapshots[0].get("allow_unattended") is not True
                or snapshots[0].get("version") != lock.get("version")
                or snapshots[0].get("schema_sha256") != lock.get("schema_sha256")
            ):
                raise MCPRuntimeError("mcp_unattended_denied", 403)
            exact[key] = {
                field: str(lock[field])
                for field in ("installation_id", "version", "tool_name", "schema_sha256")
            }
        self._automation_locks[session_id] = exact

    def _deny_candidate_auxiliary(self, installation_id, verb):
        from .seek_alpha import ENDPOINT

        manifest = self._manifest(installation_id)
        if _field(_field(manifest, "plan"), "endpoint") == ENDPOINT:
            log.warning("mcp_candidate_auxiliary_denied", verb=verb)
            raise MCPRuntimeError(f"mcp_candidate_{verb}_denied", 403)

    @sdk_operation
    async def read_resource(
        self, session_id: str, installation_id: str, uri: str
    ) -> dict[str, Any]:
        self._require_session_installation(session_id, installation_id)
        self._deny_candidate_auxiliary(installation_id, "resource")
        manifest, target = await self._active_target(installation_id)
        del manifest
        try:
            return await _await(self.host.read_resource(target, uri))
        except Exception as exc:
            raise MCPRuntimeError("mcp_resource_read_failed", 502) from exc

    @sdk_operation
    async def get_prompt(
        self,
        session_id: str,
        installation_id: str,
        name: str,
        arguments: dict[str, str] | None,
    ) -> dict[str, Any]:
        self._require_session_installation(session_id, installation_id)
        self._deny_candidate_auxiliary(installation_id, "prompt")
        manifest, target = await self._active_target(installation_id)
        del manifest
        try:
            return await _await(self.host.get_prompt(target, name, arguments))
        except Exception as exc:
            raise MCPRuntimeError("mcp_prompt_get_failed", 502) from exc

    def static_credential_capability(self, installation_id):
        from .seek_alpha import CREDENTIAL_SLOT, ENDPOINT

        manifest = self._manifest(installation_id)
        if _field(_field(manifest, "plan"), "endpoint") != ENDPOINT:
            return None
        return {"provider": "seek_alpha", "resource": ENDPOINT, "slot": CREDENTIAL_SLOT}

    def _static_binding(self, installation_id, resource, slot):
        from ..plugins.mcp_policy import managed_binding
        from .seek_alpha import CREDENTIAL_SLOT, ENDPOINT

        self._ensure_enabled()
        manifest = self._manifest(installation_id)
        if (
            slot != CREDENTIAL_SLOT
            or resource != ENDPOINT
            or _field(_field(manifest, "plan"), "endpoint") != ENDPOINT
            or self._data_root is None
        ):
            raise MCPRuntimeError("mcp_static_credential_binding_invalid", 403)
        try:
            managed_binding(self._data_root, manifest, require_schema=False)
        except (StoreError, OSError, ValueError, KeyError, TypeError) as exc:
            raise MCPRuntimeError("mcp_managed_approval_required", 403) from exc
        if getattr(self.host, "credentials", None) is None:
            raise MCPRuntimeError("mcp_credential_store_unavailable", 503)
        return manifest

    def static_credential(
        self, installation_id, *, resource, slot="static_bearer", token=None, delete=False
    ):
        """Only a fixed, reviewed remote installation can receive a Bearer token."""
        from .credentials import RuntimeCredentialError

        self._static_binding(installation_id, resource, slot)
        credentials = self.host.credentials
        try:
            if delete:
                credentials.delete(installation_id, slot)
            elif token is not None:
                if (
                    not isinstance(token, str)
                    or not token
                    or len(token.encode("utf-8")) > 8192
                    or any(ord(character) < 33 or ord(character) > 126 for character in token)
                ):
                    raise MCPRuntimeError("mcp_static_credential_invalid", 422)
                credentials.write(
                    installation_id,
                    slot,
                    {"resource": resource, "token_type": "Bearer", "access_token": token},
                )
            configured = bool(credentials.read(installation_id, slot, expected_resource=resource))
        except RuntimeCredentialError as exc:
            raise MCPRuntimeError("mcp_credential_store_unavailable", 503) from exc
        self._targets.pop(installation_id, None)
        log.info(
            (
                "mcp_static_credential_changed"
                if token is not None or delete
                else "mcp_static_credential_status"
            ),
            status="configured" if configured else "missing",
        )
        return {"configured": configured, "resource": resource, "slot": slot}

    def evaluation_candidate(self, installation_id):
        from .seek_alpha import candidate

        self._static_binding(
            installation_id, candidate()["endpoint"], candidate()["credential_slot"]
        )
        return candidate()

    async def evaluation_preview(self, installation_id, *, cutoff):
        from .seek_alpha import ENDPOINT, evaluation_preview

        manifest, _target = await self._active_target(installation_id)
        if _field(_field(manifest, "plan"), "endpoint") != ENDPOINT:
            raise MCPRuntimeError("mcp_evaluation_provider_invalid", 403)
        tools = [
            tool
            for tool in self.authorization.list_tools()
            if tool["installation_id"] == installation_id
        ]
        try:
            return evaluation_preview(tools, cutoff)
        except AuthorizationError as exc:
            raise self._authorization_error(exc) from exc

    async def authorize_evaluation(
        self,
        installation_id,
        *,
        session_id,
        version,
        entries,
        catalog_sha256,
        max_credits,
        confirmed=False,
    ):
        from .seek_alpha import ENDPOINT

        if self.evidence_store is None:
            raise MCPRuntimeError("mcp_evidence_store_required", 503)
        self.evidence_store.session(session_id)
        manifest, _target = await self._active_target(installation_id)
        if _field(_field(manifest, "plan"), "endpoint") != ENDPOINT:
            raise MCPRuntimeError("mcp_evaluation_provider_invalid", 403)
        try:
            from .seek_alpha import evaluation_preview, validate_evaluation

            validated = validate_evaluation(entries, catalog_sha256, max_credits)
            consensus = next(item for item in validated["entries"] if item["query"] == "consensus")
            raw_date = consensus["arguments"]["date"]
            cutoff = raw_date[:4] + "-" + raw_date[4:6] + "-" + raw_date[6:]
            preview = evaluation_preview(
                [
                    tool
                    for tool in self.authorization.list_tools()
                    if tool["installation_id"] == installation_id
                ],
                cutoff,
            )
            if preview["catalog_sha256"] != catalog_sha256:
                raise AuthorizationError("mcp_schema_drift")
            return self.authorization.authorize_budget(
                session_id=session_id,
                installation_id=installation_id,
                version=version,
                entries=entries,
                catalog_sha256=catalog_sha256,
                max_credits=max_credits,
                confirmed=confirmed,
            )
        except AuthorizationError as exc:
            raise self._authorization_error(exc) from exc

    async def evaluation_call(self, installation_id, *, session_id, budget_id, entry_id):
        """One explicit UI action; fixed id makes a repeated click recovery-only."""
        if self.evidence_store is None:
            raise MCPRuntimeError("mcp_evidence_store_required", 503)
        self.evidence_store.session(session_id)
        try:
            request = self.authorization.evaluation_call_request(
                budget_id=budget_id,
                session_id=session_id,
                installation_id=installation_id,
                entry_id=entry_id,
            )
        except AuthorizationError as exc:
            raise self._authorization_error(exc) from exc
        result = await self.call_tool(**request)
        # The gateway receives a bounded receipt; originals remain in session datasets.
        return {key: value for key, value in result.items() if key != "result"}

    def assert_frozen_result_authorized(self, session_id, dataset_id, metadata=None):
        """Offline authorization only: no provider request, model or credential read."""
        from ..plugins.mcp_policy import managed_binding, requires_managed
        from .evidence import MCPResultEvidence

        if self.evidence_store is None:
            raise MCPRuntimeError("mcp_evidence_store_required", 503)
        self.evidence_store.session(session_id, include_deleted=True)
        snapshot = MCPResultEvidence(self.evidence_store, retained=True).snapshots.detail(
            session_id, dataset_id
        )
        if snapshot.get("snapshot_kind") != "mcp_evidence":
            raise MCPRuntimeError("mcp_evidence_invalid", 404)
        binding = snapshot["provider_metadata"]
        if metadata is not None and metadata != binding:
            raise MCPRuntimeError("mcp_evidence_binding_invalid", 409)
        installation = binding["installation_id"]
        if installation not in self._active:
            raise MCPRuntimeError("mcp_installation_not_active", 403)
        native = self._manifest(installation)
        tools = [
            tool
            for tool in self.authorization.list_tools()
            if tool["installation_id"] == installation
        ]
        if self.managed_only or requires_managed(self._data_root, installation):
            try:
                managed_binding(self._data_root, native, {"tools": tools}, require_schema=True)
            except (StoreError, OSError, ValueError, KeyError, TypeError) as exc:
                raise MCPRuntimeError("mcp_managed_approval_required", 403) from exc
        try:
            with self.authorization._transaction():
                current = self.authorization._current(installation, binding["tool_name"])
                if (
                    current["version"] != binding["version"]
                    or current["schema_sha256"] != binding["schema_sha256"]
                ):
                    raise AuthorizationError("mcp_schema_drift")
                self.authorization._require_grant(
                    session_id,
                    installation,
                    binding["version"],
                    binding["tool_name"],
                    binding["schema_sha256"],
                )
        except AuthorizationError as exc:
            raise self._authorization_error(exc) from exc
        return dict(binding)

    async def read_frozen_result(self, session_id, dataset_id):
        """Offline reauthorization followed by hash-verified original read."""
        from .evidence import MCPResultEvidence

        self.assert_frozen_result_authorized(session_id, dataset_id)
        return MCPResultEvidence(self.evidence_store, retained=True).read(session_id, dataset_id)

    @sdk_operation
    async def call_tool(self, **request: Any) -> dict[str, Any]:
        self._ensure_enabled()
        installation_id = str(request["installation_id"])
        tool_name = str(request.get("tool_name") or "")
        session_id = request.get("session_id")
        automation = self._automation_locks.get(session_id) if isinstance(session_id, str) else None
        if automation is not None:
            request = {
                **request,
                "unattended": True,
                "automation_lock": automation.get((installation_id, tool_name)),
            }
        manifest, target = await self._active_target(installation_id)
        version = str(_field(_field(manifest, "plan"), "server_version"))
        if request["version"] != version:
            raise MCPRuntimeError("mcp_version_drift", 409)
        self._require_components("authorization")
        snapshots = [
            tool
            for tool in self.authorization.list_tools()
            if tool.get("installation_id") == installation_id
            and tool.get("tool_name") == tool_name
            and tool.get("status") == "active"
        ]
        if len(snapshots) != 1 or snapshots[0].get("schema_sha256") != request["schema_sha256"]:
            raise MCPRuntimeError("mcp_schema_drift", 409)
        snapshot = snapshots[0]
        allowlist = ExactToolAllowlist(self.authorization.active_bindings(set(self._active)))
        try:
            admission = self.authorization.admit_call(
                call_id=request["call_id"],
                session_id=request["session_id"],
                installation_id=installation_id,
                version=request["version"],
                tool_name=request["tool_name"],
                input_schema=snapshot["input_schema"],
                output_schema=snapshot.get("output_schema"),
                arguments=request["arguments"],
                allowlist=allowlist,
                unattended=request.get("unattended", False),
                automation_lock=request.get("automation_lock"),
                approval_id=request.get("approval_id"),
            )
        except AuthorizationError as exc:
            raise self._authorization_error(exc) from exc
        if admission.get("allowed") is not True:
            approval_id = admission.get("approval_id")
            if not isinstance(approval_id, str):
                raise MCPRuntimeError("mcp_approval_invalid", 503)
            event = asyncio.Event()
            self._approval_waiters[approval_id] = event
            try:
                decision = self._approval_decisions.get(approval_id)
                if decision is None:
                    try:
                        await asyncio.wait_for(event.wait(), timeout=self.approval_timeout_seconds)
                    except TimeoutError as exc:
                        raise MCPRuntimeError("mcp_approval_timeout", 408) from exc
                    decision = self._approval_decisions.get(approval_id)
                if decision != "approved":
                    raise MCPRuntimeError("mcp_approval_denied", 403)
                request = {**request, "approval_id": approval_id}
                try:
                    admission = self.authorization.admit_call(
                        call_id=request["call_id"],
                        session_id=request["session_id"],
                        installation_id=installation_id,
                        version=request["version"],
                        tool_name=request["tool_name"],
                        input_schema=snapshot["input_schema"],
                        output_schema=snapshot.get("output_schema"),
                        arguments=request["arguments"],
                        allowlist=allowlist,
                        unattended=request.get("unattended", False),
                        automation_lock=request.get("automation_lock"),
                        approval_id=approval_id,
                    )
                except AuthorizationError as exc:
                    raise self._authorization_error(exc) from exc
                if admission.get("allowed") is not True:
                    raise MCPRuntimeError("mcp_approval_required", 403)
            finally:
                self._approval_waiters.pop(approval_id, None)
                self._approval_decisions.pop(approval_id, None)
        from .evidence import MCPResultEvidence, raw_result
        from .seek_alpha import ENDPOINT

        endpoint = _field(_field(manifest, "plan"), "endpoint", "")
        paid = endpoint == ENDPOINT
        cost = None
        evidence = (
            MCPResultEvidence(self.evidence_store) if self.evidence_store is not None else None
        )
        if paid:
            if request.get("unattended") or evidence is None:
                raise MCPRuntimeError("mcp_paid_evaluation_explicit_only", 403)
            try:
                cost = self.authorization.reserve_paid_call(
                    budget_id=request.get("budget_id"),
                    call_id=request["call_id"],
                    session_id=request["session_id"],
                    installation_id=installation_id,
                    version=version,
                    tool_name=tool_name,
                    schema_sha256=request["schema_sha256"],
                    arguments=request["arguments"],
                )
                if not cost["dispatch"]:
                    value, reference = evidence.recover(
                        request, endpoint=endpoint, cost_state=cost["status"]
                    )
                    self.assert_frozen_result_authorized(
                        request["session_id"], reference["dataset_id"]
                    )
                    if cost["status"] in {"dispatched", "unknown"}:
                        cost = self.authorization.transition_paid_call(
                            request["call_id"],
                            session_id=request["session_id"],
                            status="completed",
                            evidence=reference,
                        )
                    return {
                        "status": "complete",
                        "result": value,
                        "evidence": reference,
                        "cost": cost,
                        "recovered": True,
                    }
                self.authorization.transition_paid_call(
                    request["call_id"], session_id=request["session_id"], status="dispatched"
                )
            except AuthorizationError as exc:
                raise self._authorization_error(exc) from exc
        try:
            from .sdk_host import reject_credential_echo
            from .seek_alpha import CREDENTIAL_SLOT

            credential_at_dispatch = None
            credentials = getattr(self.host, "credentials", None)
            if endpoint and credentials is not None:
                slot = CREDENTIAL_SLOT if paid else "oauth"
                credential_at_dispatch = credentials.read(
                    installation_id, slot, expected_resource=endpoint
                ).get("access_token")
            result = await _await(
                self.host.call_tool(target, request["tool_name"], request["arguments"])
            )
            result, _raw = raw_result(result)
            reject_credential_echo(result, credential_at_dispatch)
            reference = (
                evidence.freeze(
                    request, result, endpoint=endpoint, cost_state="completed" if paid else None
                )
                if evidence
                else None
            )
            # Freeze the original first; revocation must deny exposure without losing it.
            await self._managed_guard(manifest, target=target, fresh=True)
            if reference is not None:
                self.assert_frozen_result_authorized(request["session_id"], reference["dataset_id"])
            if paid:
                cost = self.authorization.transition_paid_call(
                    request["call_id"],
                    session_id=request["session_id"],
                    status="completed",
                    evidence=reference,
                )
        except (Exception, asyncio.CancelledError) as exc:
            if paid:
                self.authorization.transition_paid_call(
                    request["call_id"], session_id=request["session_id"], status="unknown"
                )
            log.warning("mcp_tool_call_failed", error_type=type(exc).__name__)
            if isinstance(exc, MCPHostError) and str(exc) == "mcp_result_contains_credential":
                raise MCPRuntimeError("mcp_result_contains_credential", 502) from None
            if isinstance(exc, (asyncio.CancelledError, MCPRuntimeError, StoreError)):
                raise
            raise MCPRuntimeError("mcp_tool_call_failed", 502) from exc
        response = {"status": "complete", "result": result}
        if reference is not None:
            response["evidence"] = reference
        if cost is not None:
            response["cost"] = cost
        return response

    def approvals(self, *, session_id: str | None = None) -> dict[str, Any]:
        self._ensure_enabled()
        self._require_components("authorization")
        try:
            return {
                "items": [
                    self._approval_projection(item)
                    for item in self.authorization.list_approvals(session_id=session_id)
                ]
            }
        except AuthorizationError as exc:
            raise self._authorization_error(exc) from exc

    async def decide_approval(
        self, approval_id: str, *, session_id: str, approve: bool
    ) -> dict[str, Any]:
        self._ensure_enabled()
        self._require_components("authorization")
        try:
            operation = self.authorization.approve if approve else self.authorization.deny
            result = operation(approval_id, session_id=session_id)
        except AuthorizationError as exc:
            raise self._authorization_error(exc) from exc
        decision = str(result.get("status", "denied"))
        self._approval_decisions[approval_id] = decision
        waiter = self._approval_waiters.get(approval_id)
        if waiter is not None:
            waiter.set()
        return self._approval_projection(result)

    def authenticate_internal(self, presented: object) -> None:
        self._ensure_enabled()
        if self.control is None:
            raise MCPRuntimeError("mcp_control_unavailable", 503)
        if not authenticate(self.control, presented):
            raise MCPRuntimeError("mcp_control_unauthorized", 403)

    def _require_session_installation(self, session_id: str, installation_id: str) -> None:
        self._ensure_enabled()
        if installation_id not in self._active:
            raise MCPRuntimeError("mcp_installation_not_active", 409)
        self._require_components("authorization")
        checker = getattr(self.authorization, "has_session_authorization", None)
        if checker is not None:
            try:
                allowed = checker(session_id=session_id, installation_id=installation_id)
            except Exception as exc:
                raise MCPRuntimeError("mcp_authorization_check_failed", 503) from exc
            if allowed is True:
                return
        grants = getattr(self.authorization, "grants", None)
        if grants is None:
            state = getattr(self.authorization, "_state", None)
            grants = state.get("grants", {}).values() if isinstance(state, dict) else ()
        if any(
            isinstance(grant, dict)
            and grant.get("status") == "active"
            and grant.get("session_id") == session_id
            and grant.get("installation_id") == installation_id
            for grant in grants
        ):
            return
        raise MCPRuntimeError("mcp_authorization_required", 403)

    async def oauth_start(self, installation_id: str, resource: str) -> dict[str, str]:
        self._ensure_enabled()
        manifest = self._manifest(installation_id)
        self._require_components("oauth")
        plan = _field(manifest, "plan")
        endpoint = str(_field(plan, "endpoint", ""))
        if _field(plan, "target_kind") != "remote" or resource != endpoint:
            raise MCPRuntimeError("mcp_oauth_resource_mismatch", 422)
        try:
            attempt = await _await(self.oauth.start(installation_id, resource))
        except Exception as exc:
            raise MCPRuntimeError("mcp_oauth_start_failed", 502) from exc
        return {"authorization_url": str(attempt.authorization_url)}

    async def oauth_callback(
        self,
        *,
        state: str,
        code: str,
        issuer: str | None = None,
    ) -> dict[str, str]:
        self._ensure_enabled()
        self._require_components("oauth")
        try:
            arguments = (state, state, code)
            if self.oauth_exchange is None:
                await _await(self.oauth.complete(*arguments, issuer=issuer))
            else:
                await _await(
                    self.oauth.complete(
                        *arguments,
                        self.oauth_exchange,
                        issuer=issuer,
                    )
                )
        except Exception as exc:
            raise MCPRuntimeError("mcp_oauth_callback_failed", 400) from exc
        return {"status": "connected"}

    async def _active_target(self, installation_id: str) -> tuple[Any, Any]:
        self._ensure_enabled()
        if installation_id not in self._active:
            raise MCPRuntimeError("mcp_installation_not_active", 409)
        manifest = self._manifest(installation_id)
        target = await self._target(manifest)
        await self._managed_guard(manifest, target=target, fresh=True)
        return manifest, target

    async def _target(self, manifest: Any) -> Any:
        await self._managed_guard(manifest, require_schema=False)
        installation_id = str(_field(manifest, "id"))
        if installation_id in self._targets:
            target = self._targets[installation_id]
            await self._managed_guard(manifest, require_schema=False, target=target)
            return target
        self._require_components("installer")
        target = await self._resolve_target(manifest)
        self._targets[installation_id] = target
        return target

    async def _managed_guard(
        self, manifest, *, require_schema=True, capabilities=None, target=None, fresh=False
    ):
        """Tenant Host never resolves an unmanaged target or trusts stale schemas."""
        from ..plugins.mcp_policy import managed_binding, requires_managed

        installation_id = str(_field(manifest, "id"))
        if not self.managed_only and not requires_managed(self._data_root, installation_id):
            return

        self._require_managed_process_isolation(manifest)

        if self._data_root is None:
            raise MCPRuntimeError("mcp_managed_approval_unavailable", 403)
        try:
            managed_binding(self._data_root, manifest, require_schema=False)
            if target is not None and not _field(_field(manifest, "plan"), "endpoint"):
                from .managed_sandbox import validate_managed_target

                validate_managed_target(target)
                plan = _field(manifest, "plan")
                if (
                    target.package != self._data_root / "mcp-runtime/packages" / installation_id
                    or target.argv != tuple(_field(plan, "argv"))
                    or target.package_type != _field(plan, "package_type")
                ):
                    raise ValueError("mcp_managed_cached_target_mismatch")
            if require_schema:
                if fresh:
                    capabilities = await _await(self.host.capabilities(target))
                managed_binding(self._data_root, manifest, capabilities, require_schema=True)
        except (StoreError, OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("mcp_managed_approval_denied", error_type=type(exc).__name__)
            raise MCPRuntimeError("mcp_managed_approval_required", 403) from exc

    async def _resolve_target(self, manifest: Any) -> Any:
        # Called directly after plugin installation as well as by normal startup.
        # Refuse before reading environment credentials or constructing a launcher.
        self._require_managed_process_isolation(manifest)
        from ..plugins.mcp_policy import requires_managed

        managed_local = (
            self.managed_only or requires_managed(self._data_root, str(_field(manifest, "id")))
        ) and not _field(_field(manifest, "plan"), "endpoint")
        targeter = getattr(self.installer, "managed_target" if managed_local else "target", None)
        if targeter is None:
            raise MCPRuntimeError("mcp_installer_target_unavailable", 503)
        target = await _await(targeter(manifest))
        from .seek_alpha import CREDENTIAL_SLOT, ENDPOINT
        from .transport import RemoteTarget

        if isinstance(target, RemoteTarget) and target.endpoint == ENDPOINT:
            target = RemoteTarget(
                target.endpoint, target.installation_id, target.audience, CREDENTIAL_SLOT
            )
        return target

    def _require_managed_process_isolation(self, manifest: Any) -> None:
        """Only the verified native offline Python contract may launch locally."""
        from ..plugins.mcp_policy import requires_managed

        if not self.managed_only and not requires_managed(
            self._data_root, str(_field(manifest, "id"))
        ):
            return
        plan = _field(manifest, "plan")
        if _field(plan, "target_kind") == "local" or not _field(plan, "endpoint"):
            from .managed_sandbox import validate_plan

            try:
                validate_plan(plan)
            except ValueError as exc:
                log.warning("mcp_managed_local_process_isolation_required")
                raise MCPRuntimeError(
                    "mcp_managed_local_process_isolation_required",
                    403,
                    "仅支持 macOS 离线 Python MCP；禁止网络、子进程与供应商凭据环境",
                ) from exc

    async def _require_idle(self) -> None:
        idle_gate = self.idle_gate
        if idle_gate is None:
            raise MCPRuntimeError("mcp_runtime_idle_check_unavailable", 503)
        try:
            idle = await _await(idle_gate())
        except Exception as exc:
            raise MCPRuntimeError("mcp_runtime_idle_check_failed", 503) from exc
        if idle is not True:
            raise MCPRuntimeError("mcp_runtime_busy", 409)

    async def _activate(
        self,
        candidate: set[str],
        previous: set[str],
        changed_installation: str,
    ) -> None:
        restart_callback = self.restart_callback
        if restart_callback is None:
            raise MCPRuntimeError("mcp_runtime_restart_unavailable", 503)
        candidate_bindings = self.authorization.active_bindings(candidate)
        self._write_active(candidate)
        try:
            await _await(restart_callback(candidate_bindings))
        except Exception as exc:
            self._write_active(previous)
            try:
                await _await(restart_callback(self.authorization.active_bindings(previous)))
            except Exception as rollback_exc:  # noqa: BLE001
                log.error(
                    "mcp_runtime_restart_rollback_failed",
                    error_type=type(rollback_exc).__name__,
                )
            self._set_state(changed_installation, "health_failed")
            raise MCPRuntimeError("mcp_runtime_restart_failed", 503) from exc

    def _manifest(self, installation_id: str) -> Any:
        self._require_components("store")
        try:
            return self.store.get(installation_id)
        except Exception as exc:
            raise MCPRuntimeError("mcp_installation_not_found", 404) from exc

    def _set_state(self, installation_id: str, status: str) -> None:
        setter = getattr(self.store, "set_state", None)
        if setter is not None:
            try:
                setter(installation_id, status)
            except Exception as exc:
                raise MCPRuntimeError("mcp_installation_state_unavailable", 503) from exc
        self._states[installation_id] = status
        self._write_states()

    def _state(self, installation_id: str) -> str:
        getter = getattr(self.store, "state", None)
        if getter is not None:
            try:
                value = getter(installation_id)
                if isinstance(value, dict):
                    return str(value.get("status", "installed"))
                if isinstance(value, str):
                    return value
            except Exception as exc:
                raise MCPRuntimeError("mcp_installation_state_unavailable", 503) from exc
        return self._states.get(installation_id, "installed")

    def _load_runtime_state(self) -> None:
        if self._data_root is None:
            return
        empty_states = {"schema_version": 1, "installations": {}}
        empty_active = {"schema_version": 1, "installation_ids": []}
        try:
            self._data_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            with directory(self._data_root, ("mcp-runtime",), create=True, private=True) as folder:
                names = set(os.listdir(folder))
                states = (
                    json.loads(
                        read_file(folder, "runtime-state.json", private=True, limit=1024 * 1024)
                    )
                    if "runtime-state.json" in names
                    else empty_states
                )
                active = (
                    json.loads(read_file(folder, "active.json", private=True, limit=1024 * 1024))
                    if "active.json" in names
                    else empty_active
                )
            if (
                not isinstance(states, dict)
                or states.get("schema_version") != 1
                or not isinstance(states.get("installations"), dict)
                or not isinstance(active, dict)
                or active.get("schema_version") != 1
                or not isinstance(active.get("installation_ids"), list)
            ):
                raise ValueError("invalid runtime state")
            allowed = {
                "installing",
                "installed",
                "install_failed",
                "ready",
                "enabled",
                "disabled",
                "health_failed",
            }
            raw_installations = states["installations"]
            raw_active_ids = active["installation_ids"]
            assert isinstance(raw_installations, dict)
            assert isinstance(raw_active_ids, list)
            parsed_states: dict[str, str] = {}
            for installation_id, item in raw_installations.items():
                if (
                    not isinstance(installation_id, str)
                    or INSTALLATION_ID.fullmatch(installation_id) is None
                    or not isinstance(item, dict)
                    or item.get("status") not in allowed
                    or set(item) != {"status"}
                ):
                    raise ValueError("invalid runtime state")
                parsed_states[installation_id] = item["status"]
            active_ids = raw_active_ids
            if len(active_ids) != len(set(active_ids)) or any(
                not isinstance(item, str) or INSTALLATION_ID.fullmatch(item) is None
                for item in active_ids
            ):
                raise ValueError("invalid active state")
            if self.store is not None:
                for installation_id in active_ids:
                    self.store.get(installation_id)
            self._states = parsed_states
            self._active = set(active_ids)
        except Exception as exc:
            log.error("mcp_runtime_state_load_failed", error_type=type(exc).__name__)
            raise MCPRuntimeError("mcp_runtime_state_invalid", 503) from exc

    def _write_states(self) -> None:
        if self._data_root is None:
            return
        try:
            with directory(self._data_root, ("mcp-runtime",), create=True, private=True) as folder:
                atomic_json(
                    folder,
                    "runtime-state.json",
                    {
                        "schema_version": 1,
                        "installations": {
                            key: {"status": value} for key, value in sorted(self._states.items())
                        },
                    },
                )
        except (OSError, StoreError) as exc:
            raise MCPRuntimeError("mcp_runtime_state_unavailable", 503) from exc

    def _write_active(self, installation_ids: set[str]) -> None:
        if self._data_root is None:
            return
        try:
            with directory(self._data_root, ("mcp-runtime",), create=True, private=True) as folder:
                atomic_json(
                    folder,
                    "active.json",
                    {
                        "schema_version": 1,
                        "installation_ids": sorted(installation_ids),
                    },
                )
        except (OSError, StoreError) as exc:
            raise MCPRuntimeError("mcp_runtime_active_state_unavailable", 503) from exc

    def _project_manifest(self, manifest: Any) -> dict[str, Any]:
        return _dump(manifest)

    def _installation_projection(self, manifest: Any) -> dict[str, Any]:
        result = self._project_manifest(manifest)
        installation_id = str(_field(manifest, "id"))
        result["runtime_status"] = self._state(installation_id)
        result["active"] = installation_id in self._active
        return result

    def _capability_projection(
        self, installation_id: str, capabilities: dict[str, Any]
    ) -> dict[str, Any]:
        """Attach only Host-owned policy to untrusted tool declarations."""

        result = copy.deepcopy(capabilities)
        lister = getattr(self.authorization, "list_tools", None)
        snapshots = lister() if lister is not None else []
        policy = {
            item.get("tool_name"): item
            for item in snapshots
            if item.get("installation_id") == installation_id and item.get("status") == "active"
        }
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise MCPRuntimeError("mcp_capabilities_invalid", 503)
        for tool in tools:
            if not isinstance(tool, dict):
                raise MCPRuntimeError("mcp_capabilities_invalid", 503)
            snapshot = policy.get(tool.get("name"))
            if snapshot is None:
                continue
            tool["schema_sha256"] = snapshot.get("schema_sha256")
            tool["risk_tier"] = snapshot.get("risk_tier")
            tool["allow_unattended"] = snapshot.get("allow_unattended") is True
        return result

    @staticmethod
    def _approval_projection(value: dict[str, Any]) -> dict[str, Any]:
        safe = {
            "id",
            "call_id",
            "session_id",
            "installation_id",
            "version",
            "tool_name",
            "schema_sha256",
            "status",
        }
        return {key: copy.deepcopy(item) for key, item in value.items() if key in safe}

    @staticmethod
    def _authorization_error(exc: AuthorizationError) -> MCPRuntimeError:
        code = getattr(exc, "code", str(exc))
        if code.endswith("_not_found"):
            return MCPRuntimeError(code, 404)
        if "required" in code or "denied" in code or "mismatch" in code:
            return MCPRuntimeError(code, 403)
        if "drift" in code or "consumed" in code or "not_pending" in code:
            return MCPRuntimeError(code, 409)
        return MCPRuntimeError(code, 422)
