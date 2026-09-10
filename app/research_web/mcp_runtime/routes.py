"""Strict FastAPI contracts for the Research Web MCP runtime."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from .models import InstallationSelection

router = APIRouter()
public_router = APIRouter(prefix="/api/research/mcp")
session_router = APIRouter(prefix="/api/research/sessions")
internal_router = APIRouter(prefix="/api/research/internal")

INSTALLATION_PATTERN = r"^mcp-installation-[a-f0-9]{32}$"
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"
ENVIRONMENT_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]{0,127}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


InstallPreviewRequest = InstallationSelection


class InstallConfirmRequest(StrictModel):
    confirmation_token: str = Field(min_length=16, max_length=4096)
    environment_values: dict[str, SecretStr] = Field(default_factory=dict, max_length=128)

    @field_validator("environment_values")
    @classmethod
    def validate_environment_values(cls, values: dict[str, SecretStr]):
        if any(re.fullmatch(ENVIRONMENT_NAME_PATTERN, name) is None for name in values):
            raise ValueError("environment_name_invalid")
        return values


class ToolPolicyRequest(StrictModel):
    tool_name: str = Field(pattern=IDENTIFIER_PATTERN)
    risk_tier: Literal["read_only", "private_data", "external_write_high_risk"]
    allow_unattended: bool = False


class SessionAuthorizationRequest(StrictModel):
    installation_id: str = Field(pattern=INSTALLATION_PATTERN)
    version: str = Field(pattern=IDENTIFIER_PATTERN)
    tool_name: str = Field(pattern=IDENTIFIER_PATTERN)
    schema_sha256: str = Field(pattern=DIGEST_PATTERN)


class ResourceReadRequest(StrictModel):
    installation_id: str = Field(pattern=INSTALLATION_PATTERN)
    uri: str = Field(min_length=1, max_length=4096)


class PromptGetRequest(StrictModel):
    installation_id: str = Field(pattern=INSTALLATION_PATTERN)
    name: str = Field(pattern=IDENTIFIER_PATTERN)
    arguments: dict[str, str] | None = Field(default=None, max_length=128)


class ApprovalDecisionRequest(StrictModel):
    session_id: str = Field(pattern=IDENTIFIER_PATTERN)


class OAuthStartRequest(StrictModel):
    resource: str = Field(min_length=1, max_length=2048)


class InternalToolCallRequest(StrictModel):
    call_id: str = Field(pattern=IDENTIFIER_PATTERN)
    session_id: str = Field(pattern=IDENTIFIER_PATTERN)
    installation_id: str = Field(pattern=INSTALLATION_PATTERN)
    version: str = Field(pattern=IDENTIFIER_PATTERN)
    tool_name: str = Field(pattern=IDENTIFIER_PATTERN)
    schema_sha256: str = Field(pattern=DIGEST_PATTERN)
    arguments: dict[str, Any]
    approval_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    unattended: bool = False
    automation_lock: dict[str, str] | None = None


InstallationId = Annotated[str, Field(pattern=INSTALLATION_PATTERN)]
SessionId = Annotated[str, Field(pattern=IDENTIFIER_PATTERN)]
ApprovalId = Annotated[str, Field(pattern=IDENTIFIER_PATTERN)]


def service(request: Request):
    return request.app.state.research.mcp_runtime


@public_router.post("/installations/preview")
async def preview(body: InstallPreviewRequest, request: Request):
    return await service(request).preview(body)


@public_router.post("/installations", status_code=201)
async def install(body: InstallConfirmRequest, request: Request):
    values = {name: value.get_secret_value() for name, value in body.environment_values.items()}
    return await service(request).install(body.confirmation_token, values)


@public_router.get("/installations")
def installations(request: Request):
    return service(request).list_installations()


@public_router.get("/installations/{installation_id}")
def installation(installation_id: InstallationId, request: Request):
    return service(request).installation(installation_id)


@public_router.patch("/installations/{installation_id}")
def classify(
    installation_id: InstallationId,
    body: ToolPolicyRequest,
    request: Request,
):
    return service(request).classify_tool(
        installation_id,
        body.tool_name,
        risk_tier=body.risk_tier,
        allow_unattended=body.allow_unattended,
    )


@public_router.delete("/installations/{installation_id}")
async def delete_installation(installation_id: InstallationId, request: Request):
    return await service(request).delete(installation_id)


@public_router.get("/installations/{installation_id}/status")
def installation_status(installation_id: InstallationId, request: Request):
    return service(request).status(installation_id)


@public_router.get("/installations/{installation_id}/capabilities")
def installation_capabilities(installation_id: InstallationId, request: Request):
    return service(request).capabilities(installation_id)


@public_router.post("/installations/{installation_id}/probe")
async def probe(installation_id: InstallationId, request: Request):
    return await service(request).probe(installation_id)


@public_router.post("/installations/{installation_id}/enable")
async def enable(installation_id: InstallationId, request: Request):
    return await service(request).enable(installation_id)


@public_router.post("/installations/{installation_id}/disable")
async def disable(installation_id: InstallationId, request: Request):
    return await service(request).disable(installation_id)


@public_router.post("/installations/{installation_id}/update")
async def update(installation_id: InstallationId, request: Request):
    return await service(request).update(installation_id)


@session_router.post("/{session_id}/mcp-authorizations", status_code=201)
def authorize_session(
    session_id: SessionId,
    body: SessionAuthorizationRequest,
    request: Request,
):
    return service(request).authorize_session(session_id, **body.model_dump())


@session_router.post("/{session_id}/mcp/resources/read")
async def read_resource(
    session_id: SessionId,
    body: ResourceReadRequest,
    request: Request,
):
    return await service(request).read_resource(session_id, body.installation_id, body.uri)


@session_router.post("/{session_id}/mcp/prompts/get")
async def get_prompt(
    session_id: SessionId,
    body: PromptGetRequest,
    request: Request,
):
    return await service(request).get_prompt(
        session_id,
        body.installation_id,
        body.name,
        body.arguments,
    )


@public_router.get("/approvals")
def approvals(
    request: Request,
    session_id: str | None = Query(default=None, pattern=IDENTIFIER_PATTERN),
):
    return service(request).approvals(session_id=session_id)


@public_router.post("/approvals/{approval_id}/approve")
async def approve(approval_id: ApprovalId, body: ApprovalDecisionRequest, request: Request):
    return await service(request).decide_approval(
        approval_id, session_id=body.session_id, approve=True
    )


@public_router.post("/approvals/{approval_id}/deny")
async def deny(approval_id: ApprovalId, body: ApprovalDecisionRequest, request: Request):
    return await service(request).decide_approval(
        approval_id, session_id=body.session_id, approve=False
    )


@public_router.post("/installations/{installation_id}/oauth/start")
async def oauth_start(
    installation_id: InstallationId,
    body: OAuthStartRequest,
    request: Request,
):
    return await service(request).oauth_start(installation_id, body.resource)


@public_router.get("/oauth/callback")
async def oauth_callback(
    request: Request,
    state: str = Query(min_length=16, max_length=4096),
    code: str = Query(min_length=1, max_length=8192),
    issuer: str | None = Query(default=None, min_length=1, max_length=2048),
):
    return await service(request).oauth_callback(state=state, code=code, issuer=issuer)


@internal_router.post("/mcp/tools/call")
async def internal_tool_call(
    body: InternalToolCallRequest,
    request: Request,
    runtime_key: str | None = Header(default=None, alias="X-Research-MCP-Key"),
):
    runtime = service(request)
    runtime.authenticate_internal(runtime_key)
    return await runtime.call_tool(**body.model_dump())


router.include_router(public_router)
router.include_router(session_router)
router.include_router(internal_router)
