"""Feature-gated orchestration for MCP installation, authorization and execution."""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.research_web.datahub.security import atomic_json, directory, read_file
from app.research_web.mcp_registry.service import RegistryError
from app.research_web.store import StoreError
from core.observability import get_logger

from .authorization import AuthorizationError, AuthorizationManager, ExactToolAllowlist
from .control import authenticate
from .installation_store import INSTALLATION_ID
from .package_planner import PackagePlanner
from .sdk_host import SDKHost

log = get_logger(__name__)


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
    return os.environ.get("RESEARCH_MCP_RUNTIME_ENABLED", "0").strip().lower() in {
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
    ) -> None:
        self.enabled = runtime_feature_enabled() if enabled is None else enabled
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
        self._approval_waiters: dict[str, asyncio.Event] = {}
        self._approval_decisions: dict[str, str] = {}
        self._automation_locks: dict[str, dict[tuple[str, str], dict[str, str]]] = {}
        if self.enabled:
            self._load_runtime_state()

    async def start(self) -> None:
        """Rebuild active targets from immutable manifests without persisting secrets."""

        if not self.enabled:
            log.info("mcp_runtime_service_started", enabled=False)
            return
        for installation_id in sorted(self._active):
            manifest = self._manifest(installation_id)
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

    async def probe(self, installation_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        self._require_components("host", "authorization", "installer")
        manifest = self._manifest(installation_id)
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
                    description=tool.get("description", ""),
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
        await self._require_idle()
        previous = set(self._active)
        candidate = previous | {installation_id}
        await self._activate(candidate, previous, installation_id)
        self._active = candidate
        self._set_state(installation_id, "enabled")
        return self.status(installation_id)

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

    async def read_resource(
        self, session_id: str, installation_id: str, uri: str
    ) -> dict[str, Any]:
        self._require_session_installation(session_id, installation_id)
        manifest, target = await self._active_target(installation_id)
        del manifest
        try:
            return await _await(self.host.read_resource(target, uri))
        except Exception as exc:
            raise MCPRuntimeError("mcp_resource_read_failed", 502) from exc

    async def get_prompt(
        self,
        session_id: str,
        installation_id: str,
        name: str,
        arguments: dict[str, str] | None,
    ) -> dict[str, Any]:
        self._require_session_installation(session_id, installation_id)
        manifest, target = await self._active_target(installation_id)
        del manifest
        try:
            return await _await(self.host.get_prompt(target, name, arguments))
        except Exception as exc:
            raise MCPRuntimeError("mcp_prompt_get_failed", 502) from exc

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
        try:
            result = await _await(
                self.host.call_tool(target, request["tool_name"], request["arguments"])
            )
        except Exception as exc:
            log.warning("mcp_tool_call_failed", error_type=type(exc).__name__)
            raise MCPRuntimeError("mcp_tool_call_failed", 502) from exc
        return {"status": "complete", "result": result}

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
        return manifest, await self._target(manifest)

    async def _target(self, manifest: Any) -> Any:
        installation_id = str(_field(manifest, "id"))
        if installation_id in self._targets:
            return self._targets[installation_id]
        self._require_components("installer")
        target = await self._resolve_target(manifest)
        self._targets[installation_id] = target
        return target

    async def _resolve_target(self, manifest: Any) -> Any:
        targeter = getattr(self.installer, "target", None)
        if targeter is None:
            raise MCPRuntimeError("mcp_installer_target_unavailable", 503)
        return await _await(targeter(manifest))

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
