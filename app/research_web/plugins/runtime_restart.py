"""Backend half of the Pool-owned tenant DSH restart birth fence.

Only fixed, signed manager callbacks enter this router. No route accepts a
command, source path, executable, arbitrary upstream, or selected user identity.
"""

import os

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from core.observability import get_logger

from ..capabilities.catalog import CapabilityCatalog
from ..tenant_policy import _gateway_key, enabled
from .packages import PluginError, read_json
from .proof import verify
from .service import PluginService, _atomic

log = get_logger(__name__)
router = APIRouter(prefix="/api/research/internal/plugin-runtime")


class ManagerControl(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    generation: str = Field(pattern=r"^[a-f0-9]{32}$")
    manager_instance: str = Field(pattern=r"^[a-f0-9]{32}$")
    freeze_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    dsh_pid: int = Field(gt=1)
    new_dsh_pid: int | None = Field(default=None, gt=1)
    transaction_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


async def authenticated(request, body):
    if not enabled():
        raise PluginError("plugin_manager_callback_disabled", 403)
    service = request.app.state.research
    consumed_path = service.plugins.root / "manager-proofs.json"
    if consumed_path.is_symlink():
        raise PluginError("plugin_storage_unsafe", 503)
    consumed = read_json(consumed_path.read_bytes()) if consumed_path.exists() else {}
    actor, role = verify(
        _gateway_key(),
        request.method,
        request.url.path,
        await request.body(),
        request.headers,
        consumed,
    )
    if (
        role != "manager"
        or actor != os.environ.get("RWB_TENANT_USER")
        or body.generation != os.environ.get("RWB_TENANT_GENERATION")
        or body.manager_instance != os.environ.get("RWB_TENANT_MANAGER_INSTANCE")
    ):
        raise PluginError("plugin_manager_generation_changed", 409)
    _atomic(consumed_path, consumed)
    return service


def _guard(service):
    path = service.plugins.root / "guard-state.json"
    if path.is_symlink() or not path.is_file():
        raise PluginError("plugin_runtime_guard_unknown", 409)
    guard = read_json(path.read_bytes())
    if guard.get("freeze_supported") is not True or type(guard.get("pid")) is not int:
        raise PluginError("plugin_runtime_guard_unknown", 409)
    return guard


def _fence(service, body):
    path = service.plugins.root / "runtime-freeze.json"
    if path.is_symlink() or not path.is_file():
        raise PluginError("plugin_runtime_fence_missing", 409)
    fence = read_json(path.read_bytes())
    if any(
        fence.get(key) != getattr(body, key)
        for key in ("generation", "manager_instance", "freeze_id", "dsh_pid", "transaction_id")
    ):
        raise PluginError("plugin_runtime_fence_changed", 409)
    return path


def _background_idle(service):
    owners = [
        (service.datahub, "tasks"),
        (service.datahub, "probe_tasks"),
        (service.asset_workspace.history_jobs, "tasks"),
        (service.automations, "tasks"),
    ]
    if any(not isinstance(getattr(owner, name, None), dict) for owner, name in owners):
        return False
    if any(
        any(not task.done() for task in getattr(owner, name).values()) for owner, name in owners
    ):
        return False
    native = service.mcp_runtime.runtime
    return (
        not getattr(native, "operations", {"unknown"})
        and not service.plugins.hook_cancellations
        and not service.model_test_lock.locked()
    )


@router.post("/freeze")
async def freeze(body: ManagerControl, request: Request):
    service = await authenticated(request, body)
    async with service.lock:
        guard = _guard(service)
        if guard["pid"] != body.dsh_pid:
            return {"status": "unknown", "reason": "runtime_pid_changed"}
        path = service.plugins.root / "runtime-freeze.json"
        if path.exists() or path.is_symlink():
            _fence(service, body)
        else:
            _atomic(path, body.model_dump())
        service.plugin_runtime_frozen = True
        try:
            if service.plugin_inflight or not _background_idle(service):
                raise PluginError("plugin_runtime_busy", 409)
            await service._capability_idle()
        except Exception as exc:  # noqa: BLE001 - unknown activity is deferred, never stopped
            path.unlink()
            service.plugin_runtime_frozen = False
            log.info("plugin_runtime_restart_deferred", error_type=type(exc).__name__)
            return {"status": "deferred", "reason": "activity_or_state_unknown"}
        log.info("plugin_runtime_birth_frozen", generation=body.generation)
        return {"status": "ready", "freeze_id": body.freeze_id, "dsh_pid": body.dsh_pid}


@router.post("/rollback")
async def rollback(body: ManagerControl, request: Request):
    service = await authenticated(request, body)
    async with service.lock:
        _fence(service, body)
        if body.transaction_id:
            return service.mcp_runtime.rollback_managed_activation(body.transaction_id)
        return {"status": "rolled_back"}


@router.post("/commit")
async def commit(body: ManagerControl, request: Request):
    service = await authenticated(request, body)
    async with service.lock:
        _fence(service, body)
        guard = _guard(service)
        if (
            body.new_dsh_pid is None
            or guard["pid"] != body.new_dsh_pid
            or body.new_dsh_pid == body.dsh_pid
        ):
            raise PluginError("plugin_runtime_new_generation_unverified", 409)
        if body.transaction_id:
            native = service.mcp_runtime.runtime
            pending = native._plugin_activation()
            if not pending or pending["id"] != body.transaction_id:
                raise PluginError("plugin_runtime_transaction_changed", 409)
            expected = sorted(
                item["name"]
                for item in native.authorization.active_bindings(set(pending["candidate"]))
            )
            if sorted(guard.get("mcp_tools", [])) != expected:
                raise PluginError("plugin_runtime_binding_drift", 409)
            result = await native.commit_managed_activation(body.transaction_id)
        else:
            result = {"status": "ready"}
        # Startup projection ran in the owned launcher. Reload the shared native
        # catalog without overwriting any session/version/credential namespace.
        service.capabilities = CapabilityCatalog(service.store.root)
        service.plugins = PluginService(
            service.store.root,
            service.capabilities,
            service.mcp_runtime,
            idle_gate=service._plugin_idle_gate,
        )
        return result


@router.post("/unfreeze")
async def unfreeze(body: ManagerControl, request: Request):
    service = await authenticated(request, body)
    async with service.lock:
        path = _fence(service, body)
        path.unlink()
        service.plugin_runtime_frozen = False
        return {"status": "ready"}
