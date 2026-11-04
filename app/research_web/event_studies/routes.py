"""Bounded reference-only user endpoints; no provider/model calls from this router."""

import json

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from core.observability import get_logger

from ..store import StoreError
from .contracts import StudyError
from .service import StudyService

router = APIRouter(prefix="/api/research/event-studies")
log = get_logger(__name__)
MAX_REQUEST_BYTES = 64 * 1024


def service(request):
    research = request.app.state.research
    selected = getattr(research, "event_studies", None) or getattr(research, "studies", None)
    if not isinstance(selected, StudyService):
        raise StoreError("事件研究服务尚未就绪", "study_service_unavailable", 503)
    return selected


async def operation(request, fn, *, body=False):
    try:
        selected = service(request)

        def execute(parsed=None):
            with selected.activity():
                return fn(parsed) if body else fn()

        if body:
            if request.headers.get("X-Research-User-Action") != "?1":
                raise StoreError("需要明确的用户操作", "explicit_user_action_required", 403)
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > MAX_REQUEST_BYTES:
                    raise StoreError("研究请求超出上限", "study_request_too_large", 413)
            parsed = json.loads(raw or b"{}")
            if not isinstance(parsed, dict):
                raise StudyError("study_request_invalid")
            return await run_in_threadpool(lambda: execute(parsed))
        return await run_in_threadpool(execute)
    except StoreError as exc:
        log.warning("event_study_request_failed", code=exc.code)
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status
        )
    except (StudyError, ValidationError, json.JSONDecodeError, UnicodeError) as exc:
        code = exc.code if isinstance(exc, StudyError) else "study_contract_invalid"
        log.warning("event_study_request_failed", code=code)
        return JSONResponse(
            {"error": {"code": code, "message": "事件研究请求未执行"}}, status_code=422
        )
    except (OSError, ArithmeticError):
        log.error("event_study_storage_or_calculation_failed")
        return JSONResponse(
            {"error": {"code": "study_calculation_unavailable", "message": "研究暂不可用"}},
            status_code=503,
        )


@router.get("")
async def studies(request: Request):
    return await operation(request, lambda: service(request).list())


@router.post("")
async def create(request: Request, idempotency_key: str = Header(min_length=8, max_length=128)):
    return await operation(
        request, lambda body: service(request).create(body, idempotency_key), body=True
    )


@router.post("/validation-batches")
async def seal(request: Request, idempotency_key: str = Header(min_length=8, max_length=128)):
    def submit(body):
        if set(body) != {"study_ids"}:
            raise StudyError("study_request_invalid")
        return service(request).seal(body["study_ids"], idempotency_key)

    return await operation(request, submit, body=True)


@router.post("/validation-batches/{batch_id}/evaluate")
async def evaluate(
    batch_id: str, request: Request, idempotency_key: str = Header(min_length=8, max_length=128)
):
    def submit(body):
        if body:
            raise StudyError("study_request_invalid")
        return service(request).evaluate(batch_id, idempotency_key)

    return await operation(request, submit, body=True)


@router.get("/runs/{run_id}")
async def run_detail(run_id: str, request: Request):
    return await operation(request, lambda: service(request).run(run_id))


@router.get("/runs/{run_id}/export")
async def export(run_id: str, request: Request, format: str = "json"):
    def render():
        content, media_type = service(request).export(run_id, format)
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="event-study-{run_id}.{format}"'
            },
        )

    return await operation(request, render)


@router.get("/{study_id}")
async def detail(study_id: str, request: Request):
    return await operation(request, lambda: service(request).get(study_id))


@router.get("/{study_id}/preflight")
async def preflight(study_id: str, request: Request):
    return await operation(request, lambda: service(request).preflight(study_id))


@router.get("/{study_id}/runs")
async def runs(study_id: str, request: Request, cursor: str | None = None):
    return await operation(request, lambda: service(request).runs(study_id, cursor=cursor))


@router.post("/{study_id}/analyze")
async def analyze(
    study_id: str, request: Request, idempotency_key: str = Header(min_length=8, max_length=128)
):
    def submit(body):
        if body:
            raise StudyError("study_request_invalid")
        return service(request).analyze(study_id, idempotency_key)

    return await operation(request, submit, body=True)
