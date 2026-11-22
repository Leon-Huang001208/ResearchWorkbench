"""Explicit account actions for strictly offline research validation."""

from collections.abc import Callable
from contextlib import contextmanager
from threading import Lock

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from core.observability import get_logger

from ..store import StoreError
from .models import Rule, ValidationConfig
from .storage import MAX_EVENTS, MAX_ZIP_BYTES, StrategyStore, reject
from .storage import active as computation_active

router = APIRouter(prefix="/api/research/strategy-validation")
log = get_logger(__name__)
RECEIVE_LOCK = Lock()


def active() -> bool:
    return RECEIVE_LOCK.locked() or computation_active()


@contextmanager
def receive_slot():
    if not RECEIVE_LOCK.acquire(blocking=False):
        raise reject("strategy_validation_busy", 409)
    try:
        yield
    finally:
        RECEIVE_LOCK.release()


async def _body(request: Request, media_type: str, limit: int) -> bytes:
    if request.headers.get("X-Research-User-Action") != "?1":
        raise reject("explicit_user_action_required", 403)
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != media_type:
        raise reject("strategy_content_type_invalid", 415)
    length = request.headers.get("content-length", "")
    if request.headers.get("transfer-encoding") or not length.isdecimal():
        raise reject("strategy_request_length_required", 411)
    if len(length) > 10 or int(length) > limit:
        raise reject("strategy_request_too_large", 413)
    if computation_active():
        raise reject("strategy_validation_busy", 409)
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > limit:
            raise reject("strategy_request_too_large", 413)
        raw.extend(chunk)
    if not raw or len(raw) != int(length):
        raise reject("strategy_request_invalid")
    return bytes(raw)


def _failure(exc: StoreError) -> JSONResponse:
    return JSONResponse({"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status)


async def _operation(request: Request, func: Callable):
    try:
        root = request.app.state.research.store.root
        return await run_in_threadpool(lambda: func(StrategyStore(root)))
    except StoreError as exc:
        return _failure(exc)
    except (ValueError, KeyError, ArithmeticError, OSError, RuntimeError) as exc:
        log.error("strategy_validation_runtime_failed", error_type=type(exc).__name__)
        return _failure(reject("strategy_calculation_unavailable", 503))


@router.get("")
async def list_records(request: Request):
    return await _operation(request, lambda store: store.list())


@router.post("/datasets", status_code=201)
async def import_dataset(request: Request):
    try:
        with receive_slot():
            raw = await _body(request, "application/zip", MAX_ZIP_BYTES)
            return await _operation(request, lambda store: store.import_dataset(raw))
    except StoreError as exc:
        return _failure(exc)


@router.post("/runs", status_code=201)
async def create_run(request: Request):
    try:
        with receive_slot():
            raw = await _body(request, "application/json", 16 * 1024)
            body = ValidationConfig.model_validate_json(raw)
            key = request.headers.get("Idempotency-Key", "")
            return await _operation(request, lambda store: store.create_run(body, key))
    except StoreError as exc:
        return _failure(exc)
    except ValidationError:
        return _failure(reject("strategy_configuration_invalid"))


@router.get("/runs/{run_id}")
async def get_run(request: Request, run_id: str):
    return await _operation(request, lambda store: store.run(run_id))


@router.get("/runs/{run_id}/events")
async def get_events(
    request: Request,
    run_id: str,
    rule: Rule,
    offset: int = Query(default=0, ge=0, le=MAX_EVENTS),
    limit: int = Query(default=50, ge=1, le=100),
):
    return await _operation(request, lambda store: store.events(run_id, rule, offset, limit))
