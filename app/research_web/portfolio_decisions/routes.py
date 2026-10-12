"""Explicit user-triggered engineering paper replay over bounded JSON inputs."""

from __future__ import annotations

import json

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from core.observability import get_logger

from .models import ReplayRequest
from .store import MAX_BYTES, DecisionStore

router = APIRouter(prefix="/api/research/portfolio-decisions")
log = get_logger(__name__)


def failure(code, status=400):
    log.warning("etf_paper_request_rejected", code=code)
    return JSONResponse(
        {"error": {"code": code, "message": f"ETF 模拟请求未执行：{code}"}}, status_code=status
    )


def store(request, *, initialize=False):
    return DecisionStore(request.app.state.research.store.root, initialize=initialize)


@router.get("/readiness")
async def readiness(request: Request):
    catalog = request.app.state.research.datahub.catalog()
    required = {"search_assets", "trading_calendar", "market_bars", "fund_data"}
    return {
        "status": "BLOCKED",
        "engineering_replay": "implemented_unverified",
        "capabilities": [
            item for item in catalog.get("capabilities", []) if item["id"] in required
        ],
        "gaps": [
            "ETF历史资格、逐日交易规则与公司行动尚缺完整准入适配",
            "ETF二级市场价格及总回报可知时间等价未认证",
            "必要计算的真实版本比较证据待完成",
        ],
        "uploaded_data_grants_admission": False,
    }


@router.get("/runs")
async def runs(request: Request):
    try:
        return {"items": await run_in_threadpool(lambda: store(request).list_runs())}
    except (ValueError, OSError):
        return failure("decision_store_unavailable", 503)


@router.get("/runs/{run_id}")
async def run_detail(run_id: str, request: Request):
    try:
        return await run_in_threadpool(lambda: store(request).get(run_id))
    except ValueError as exc:
        return failure(str(exc), 404 if str(exc) == "run_not_found" else 400)
    except OSError:
        return failure("decision_store_unavailable", 503)


@router.post("/runs", status_code=201)
async def run_create(request: Request, idempotency_key: str = Header(min_length=8, max_length=128)):
    # Deliberately unavailable to tools/Automation until a separate admission design.
    if request.headers.get("X-Research-User-Action") != "?1":
        return failure("explicit_user_action_required", 403)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_BYTES:
            return failure("snapshot_budget_exceeded", 413)
    try:
        body = ReplayRequest.model_validate(json.loads(raw))
        return await run_in_threadpool(
            lambda: store(request, initialize=True).run(body, idempotency_key)
        )
    except (ValidationError, json.JSONDecodeError, UnicodeError):
        return failure("invalid_paper_contract", 422)
    except (ValueError, ArithmeticError) as exc:
        code = (
            str(exc)
            if str(exc)
            in {
                "idempotency_conflict",
                "immutable_strategy_version_conflict",
                "invalid_idempotency_key",
                "snapshot_budget_exceeded",
                "result_budget_exceeded",
                "run_storage_budget_exceeded",
                "fractional_corporate_action_unsupported",
                "manual_decision_outside_plan_window",
                "calendar_not_known",
            }
            else "paper_run_failed"
        )
        return failure(code, 409 if code.endswith("conflict") else 400)
    except OSError:
        return failure("decision_store_unavailable", 503)
