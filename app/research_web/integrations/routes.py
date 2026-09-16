"""Versioned unified integration status and probe-batch API."""

from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from core.observability import get_logger

router = APIRouter(prefix="/api/research/integrations")
log = get_logger(__name__)


def _require_same_origin_user_action(request: Request) -> None:
    """Reject drive-by mutations without introducing a browser-held secret."""

    origin = request.headers.get("origin")
    own_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
    if origin != own_origin or request.headers.get("x-research-user-action") != "?1":
        log.warning("integration_user_action_rejected", path=request.url.path)
        raise HTTPException(
            status_code=403,
            detail={
                "code": "integration_user_action_required",
                "message": "需要从当前 Research Workbench 页面发起操作",
            },
        )


class ProbeBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scope: Literal["all", "data", "local"] = "all"


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    consent: bool


@router.get("/status")
def integration_status(request: Request, scope: Literal["all", "data", "local"] = "all"):
    return request.app.state.research.integrations.status(scope)


@router.post("/probe-batches", status_code=202)
async def start_probe_batch(
    body: ProbeBatchRequest,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    _require_same_origin_user_action(request)
    return request.app.state.research.integrations.start_batch(
        scope=body.scope,
        trigger="manual",
        idempotency_key=idempotency_key,
    )


@router.get("/probe-batches/{batch_id}")
def probe_batch(batch_id: str, request: Request):
    try:
        return request.app.state.research.integrations.batch(batch_id)
    except KeyError:
        return JSONResponse(
            {"error": {"code": "integration_batch_not_found", "message": "未找到检测批次"}},
            status_code=404,
        )


@router.put("/{item_id}/auto-probe-consent")
def update_auto_probe_consent(item_id: str, body: ConsentRequest, request: Request):
    _require_same_origin_user_action(request)
    try:
        return request.app.state.research.integrations.set_auto_probe_consent(item_id, body.consent)
    except KeyError:
        return JSONResponse(
            {"error": {"code": "integration_item_not_found", "message": "未找到集成项"}},
            status_code=404,
        )
    except ValueError:
        return JSONResponse(
            {
                "error": {
                    "code": "integration_consent_not_supported",
                    "message": "该集成不支持自动探测授权",
                }
            },
            status_code=422,
        )
