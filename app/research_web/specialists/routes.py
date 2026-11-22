"""Owned-session views and authenticated native-only specialist control."""

import time
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from core.observability import get_logger

from .contracts import SpecialistError
from .registry import catalog
from .service import ledger, qualify_terminal, reconcile, resume, verify_cached

router = APIRouter(prefix="/api/research")
log = get_logger(__name__)


class NativeControl(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation: Literal[
        "guard",
        "status",
        "plan",
        "reserve",
        "dispatch",
        "accepted",
        "submission_unknown",
        "terminal",
        "cancel",
        "model_request",
        "model_usage",
    ]
    session_id: str = Field(pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
    payload: dict = Field(default_factory=dict)
    agent_id: str = Field(min_length=1, max_length=200)
    call_id: str = Field(min_length=1, max_length=200)


class Resume(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmed: Literal[True]


@router.get("/specialists")
async def roles():
    return catalog()


@router.get("/sessions/{sid}/specialist")
async def status(sid: str, request: Request):
    service = request.app.state.research
    await service.ensure_owned()
    service.store.session(sid)
    return await reconcile(service, sid)


@router.post("/sessions/{sid}/specialist/resume", status_code=202)
async def resume_task(sid: str, body: Resume, request: Request):
    service = request.app.state.research
    await service.ensure_owned()
    return await resume(service, sid, body.confirmed)


@router.post("/internal/data/specialist-control")
async def control(body: NativeControl, request: Request):
    sid = body.session_id
    service = request.app.state.research
    if not service.datahub.authenticate(request.headers.get("X-Research-Data-Key")):
        log.warning("research_specialist_control_denied")
        raise SpecialistError("仅可信原生插件可登记协作执行", "specialist_auth_denied", 403)
    await service.ensure_owned()
    row = service.store.session(sid)
    async with service.lock:
        state = ledger(service).read(sid)
        if body.operation == "guard":
            collaboration = row.get("research_mode") == "specialist"
            frozen_model = {
                "model_provider": row.get("model_provider"),
                "model": row.get("model"),
                "model_profile_id": row.get("model_profile_id"),
            }
            model_matches = state is not None and all(
                state["model"].get(key) == value for key, value in frozen_model.items()
            )
            admitted = bool(
                model_matches
                and state
                and not state["cancel_requested"]
                and state["status"] not in {"cancelled", "needs_attention"}
                and time.time() < state["deadline"]
            )
            return {
                "collaboration": collaboration,
                "admitted": admitted,
                "model": state["model"] if state else None,
                "remaining_ms": (
                    max(0, int((state["deadline"] - time.time()) * 1000)) if state else 0
                ),
            }
        if body.operation == "status":
            return state or {"collaboration": False}
        if body.operation in {"plan", "reserve", "model_request"}:
            await verify_cached(service, sid)
        payload = dict(body.payload)
        if body.operation == "terminal" and payload.get("result") is not None:
            try:
                payload = await qualify_terminal(service, sid, payload)
            except (ValueError, SpecialistError) as exc:
                log.warning("research_specialist_result_unbound", error_type=type(exc).__name__)
                payload.pop("result", None)
                payload["stop_reason"] = "invalid_output"
        value = ledger(service).apply(
            sid,
            body.operation,
            payload,
            agent_id=body.agent_id,
            call_id=body.call_id,
        )
        service.notify()
        return value
