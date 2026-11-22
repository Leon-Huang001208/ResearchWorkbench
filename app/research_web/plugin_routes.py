"""Plugin APIs; native local boundary or authenticated manager owns mutations."""

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from core.observability import get_logger

from .mcp_runtime.routes import ToolPolicyRequest
from .plugins.packages import MAX_ARCHIVE, PluginError, safe_path
from .plugins.proof import verify
from .tenant_policy import _gateway_key
from .tenant_policy import enabled as tenant_enabled

router = APIRouter(prefix="/api/research/plugins")
log = get_logger(__name__)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    permissions: list[str] = Field(max_length=512)


class MCPConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmation_token: str = Field(min_length=16, max_length=4096)
    environment_values: dict[str, SecretStr] = Field(default_factory=dict, max_length=128)


class NativeReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected: dict[str, str] = Field(min_length=3, max_length=4)

    @field_validator("expected")
    @classmethod
    def exact_fingerprint_shape(cls, value):
        keys = set(value)
        base = {"manifest", "artifacts", "schemas"}
        if keys not in (base, base | {"sandbox"}):
            log.warning("plugin_native_review_shape_rejected")
            raise ValueError("native_fingerprint_keys_invalid")
        return value


class PluginSession(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")


class PluginAuthorization(PluginSession):
    version: str = Field(min_length=1, max_length=255)
    tool_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
    schema_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class StaticCredential(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    resource: str = Field(min_length=1, max_length=2048)
    slot: str = "static_bearer"
    token: SecretStr | None = None


class EvaluationPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    cutoff: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class EvaluationBudget(PluginSession):
    version: str = Field(min_length=1, max_length=255)
    catalog_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    entries: list[dict] = Field(min_length=18, max_length=18)
    max_credits: int = Field(ge=1, le=54, strict=True)
    confirmed: bool = False


class EvaluationCall(PluginSession):
    budget_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    entry_id: str = Field(min_length=1, max_length=128)


class PluginDecision(PluginSession):
    approval_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
    approve: bool


def management(request):
    if tenant_enabled():
        raise PluginError("plugin_manager_administration_required", 403)
    return request.app.state.research


async def mcp_management(request, *, admin=False):
    service = request.app.state.research
    if tenant_enabled():
        from .plugins.packages import read_json
        from .plugins.service import _atomic

        replay_path = service.plugins.root / "gateway-proofs.json"
        if replay_path.is_symlink():
            raise PluginError("plugin_storage_unsafe", 503)
        consumed = getattr(service.plugins, "_proof_consumed", None)
        if consumed is None:
            consumed = read_json(replay_path.read_bytes()) if replay_path.exists() else {}
        service.plugins._proof_consumed = consumed
        _actor, role = verify(
            _gateway_key(),
            request.method,
            request.url.path,
            await request.body(),
            request.headers,
            consumed,
        )
        _atomic(replay_path, consumed)
        if admin and role != "admin":
            raise PluginError("administrator_required", 403)
        async with service.lock:
            import os
            from pathlib import Path

            if not request.url.path.endswith("/disable"):
                await service.plugins.synchronize(
                    [
                        Path(value)
                        for name in ("RWB_SHARED_PLUGINS_ROOT", "RWB_PERSONAL_PLUGINS_ROOT")
                        if (value := os.environ.get(name))
                    ]
                )
    return service


@router.get("")
def catalog(request: Request):
    return request.app.state.research.plugins.list()


@router.get("/{digest}")
def detail(digest: str, request: Request):
    return request.app.state.research.plugins.detail(digest)


@router.get("/{digest}/files/{name:path}")
def source_file(digest: str, name: str, request: Request):
    package = request.app.state.research.plugins._archive(digest)
    name = safe_path(name)
    if name not in package["files"]:
        raise PluginError("plugin_file_not_found", 404)
    return Response(
        package["files"][name],
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/preview", status_code=201)
async def preview(request: Request, file: UploadFile):
    service = management(request)
    try:
        raw = await file.read(MAX_ARCHIVE + 1)
        async with service.lock:
            return service.plugins.preview(raw)
    finally:
        await file.close()


@router.post("/{digest}/review")
async def review(digest: str, body: Review, request: Request):
    service = management(request)
    async with service.lock:
        return service.plugins.review(digest, body.permissions, "local-owner")


@router.post("/{digest}/enable")
async def enable(digest: str, request: Request):
    service = management(request)
    async with service.lock:
        return await service.plugins.enable(digest)


@router.post("/{digest}/disable")
async def disable(digest: str, request: Request):
    service = management(request)
    await service.plugins.disable_mcp(digest)
    async with service.lock:
        return await service.plugins.disable(digest)


@router.delete("/{digest}")
async def uninstall(digest: str, request: Request):
    service = management(request)
    await service.plugins.disable_mcp(digest)
    async with service.lock:
        return await service.plugins.uninstall(digest)


@router.post("/{digest}/mcp/{key}/preview")
async def mcp_preview(digest: str, key: str, request: Request):
    service = await mcp_management(request)
    async with service.lock:
        return await service.plugins.mcp_preview(digest, key)


@router.post("/{digest}/mcp/{key}/install")
async def mcp_install(digest: str, key: str, body: MCPConfirmation, request: Request):
    service = await mcp_management(request)
    async with service.lock:
        return await service.plugins.mcp_install(
            digest,
            key,
            body.confirmation_token,
            {name: value.get_secret_value() for name, value in body.environment_values.items()},
        )


@router.post("/{digest}/mcp/{key}/probe")
async def mcp_probe(digest: str, key: str, request: Request):
    service = await mcp_management(request)
    row = service.plugins._reviewed(digest)
    installation = row["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    return await service.mcp_runtime.probe(installation)


@router.post("/{digest}/mcp/{key}/review")
async def mcp_review(digest: str, key: str, body: NativeReview, request: Request):
    service = await mcp_management(request, admin=True)
    async with service.lock:
        return service.plugins.mcp_review(digest, key, body.expected)


@router.post("/{digest}/mcp/{key}/status")
async def mcp_status(digest: str, key: str, request: Request):
    service = await mcp_management(request)
    async with service.lock:
        return service.plugins.mcp_review_snapshot(digest, key)


@router.post("/{digest}/mcp/{key}/enable")
async def mcp_enable(digest: str, key: str, request: Request):
    service = await mcp_management(request)
    row = service.plugins._reviewed(digest)
    installation = row["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    if tenant_enabled():
        return await service.mcp_runtime.stage_managed_enable(installation)
    return await service.mcp_runtime.enable(installation)


@router.post("/{digest}/mcp/{key}/disable")
async def mcp_disable(digest: str, key: str, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    if tenant_enabled():
        return await service.mcp_runtime.stage_managed_enable(installation, disable=True)
    return await service.mcp_runtime.disable(installation)


@router.post("/{digest}/mcp/{key}/classify")
async def mcp_classify(digest: str, key: str, body: ToolPolicyRequest, request: Request):
    service = await mcp_management(request, admin=True)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    return service.mcp_runtime.classify_tool(installation, **body.model_dump())


@router.post("/{digest}/mcp/{key}/authorize")
async def mcp_authorize(digest: str, key: str, body: PluginAuthorization, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    # Preserve the native ownership and exact version/schema/session grant.
    return service.mcp_runtime.authorize_session(installation_id=installation, **body.model_dump())


@router.post("/{digest}/mcp/{key}/approvals")
async def mcp_approvals(digest: str, key: str, body: PluginSession, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    return {
        "items": [
            item
            for item in service.mcp_runtime.approvals(session_id=body.session_id)["items"]
            if item["installation_id"] == installation
        ]
    }


@router.post("/{digest}/mcp/{key}/decide")
async def mcp_decide(digest: str, key: str, body: PluginDecision, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    approvals = service.mcp_runtime.approvals(session_id=body.session_id)["items"]
    if not installation or not any(
        item["id"] == body.approval_id and item["installation_id"] == installation
        for item in approvals
    ):
        raise PluginError("plugin_mcp_approval_not_found", 404)
    return await service.mcp_runtime.decide_approval(
        body.approval_id, session_id=body.session_id, approve=body.approve
    )


@router.post("/{digest}/mcp/{key}/credential-status")
async def mcp_credential_status(digest: str, key: str, body: StaticCredential, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    if body.token is not None:
        raise PluginError("plugin_credential_status_body_invalid", 422)
    return service.mcp_runtime.static_credential(
        installation, resource=body.resource, slot=body.slot
    )


@router.post("/{digest}/mcp/{key}/credential-save")
async def mcp_credential_save(digest: str, key: str, body: StaticCredential, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    if body.token is None:
        raise PluginError("plugin_credential_missing", 422)
    return service.mcp_runtime.static_credential(
        installation, resource=body.resource, slot=body.slot, token=body.token.get_secret_value()
    )


@router.post("/{digest}/mcp/{key}/credential-delete")
async def mcp_credential_delete(digest: str, key: str, body: StaticCredential, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    if body.token is not None:
        raise PluginError("plugin_credential_delete_body_invalid", 422)
    return service.mcp_runtime.static_credential(
        installation, resource=body.resource, slot=body.slot, delete=True
    )


@router.post("/{digest}/mcp/{key}/evaluation-candidate")
async def mcp_evaluation_candidate(digest: str, key: str, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    return service.mcp_runtime.evaluation_candidate(installation)


@router.post("/{digest}/mcp/{key}/evaluation-authorize")
async def mcp_evaluation_authorize(digest: str, key: str, body: EvaluationBudget, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    return await service.mcp_runtime.authorize_evaluation(installation, **body.model_dump())


@router.post("/{digest}/mcp/{key}/evaluation-preview")
async def mcp_evaluation_preview(digest: str, key: str, body: EvaluationPreview, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    return await service.mcp_runtime.evaluation_preview(installation, cutoff=body.cutoff)


@router.post("/{digest}/mcp/{key}/evaluation-call")
async def mcp_evaluation_call(digest: str, key: str, body: EvaluationCall, request: Request):
    service = await mcp_management(request)
    installation = service.plugins._reviewed(digest)["mcp_bindings"].get(key)
    if not installation:
        raise PluginError("plugin_mcp_component_not_found", 404)
    return await service.mcp_runtime.evaluation_call(installation, **body.model_dump())


@router.get("/candidates/seek-alpha")
def seek_alpha_candidate():
    from .plugins.seek_alpha_candidate import candidate_archive

    return Response(
        candidate_archive(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="seek-alpha-candidate-0.1.0.zip"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
