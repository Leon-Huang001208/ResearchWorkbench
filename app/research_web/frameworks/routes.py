"""FastAPI routes for versioned framework data and page-scoped DSH sessions."""

from typing import Literal

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, ConfigDict, Field

from ..store import StoreError

router = APIRouter(prefix="/api/research/frameworks")


class ExplainSessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    focus_section: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    gap_ids: list[str] = Field(default_factory=list, max_length=20)


class FrameworkMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=20000)
    expected_snapshot_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    mode: Literal["explain"] = "explain"


class VerifyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_snapshot_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    question: str = Field(min_length=1, max_length=20000)


@router.get("")
async def frameworks(request: Request):
    return request.app.state.research.frameworks.catalog()


@router.get("/{slug}/data")
async def framework_data(slug: str, request: Request):
    return request.app.state.research.frameworks.data(slug)


@router.post("/{slug}/sessions", status_code=201)
async def create_framework_session(slug: str, body: ExplainSessionInput, request: Request):
    return await request.app.state.research.frameworks.create_session(
        slug,
        body.snapshot_revision,
        focus_section=body.focus_section,
        gap_ids=body.gap_ids,
    )


@router.post("/{slug}/sessions/{sid}/messages", status_code=202)
async def send_framework_message(
    slug: str,
    sid: str,
    body: FrameworkMessageInput,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    if not body.text.strip():
        raise StoreError("问题不能为空")
    return await request.app.state.research.frameworks.send_message(
        slug, sid, body.expected_snapshot_revision, body.text.strip(), idempotency_key
    )


@router.post("/{slug}/sessions/{sid}/verify", status_code=202)
async def verify_framework_session(
    slug: str,
    sid: str,
    body: VerifyInput,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    return await request.app.state.research.frameworks.verify(
        slug, sid, body.expected_snapshot_revision, body.question.strip(), idempotency_key
    )
