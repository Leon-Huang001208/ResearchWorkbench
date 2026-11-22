"""Explicit authenticated event actions; generic trusted records remain server-only."""

from fastapi import APIRouter, Query, Request

from ..store import StoreError
from . import initial_batch, models, sources

router = APIRouter(prefix="/api/research/events", tags=["events"])


def _service(request):
    return request.app.state.research.event_timeline


def _action(request):
    if request.headers.get("X-Research-User-Action") != "?1":
        raise StoreError("事件写入需要明确用户动作", "event_user_action_required", 403)


@router.get("")
@router.get("/timeline")
async def timeline(
    request: Request,
    start: str = "1990-01-01",
    end: str | None = None,
    market: str | None = None,
    category: str | None = None,
    admission_state: str | None = None,
    lifecycle: str | None = None,
    q: str = Query("", max_length=120),
    limit: int = Query(100, ge=1, le=200),
    cursor: str | None = Query(None, pattern="^[0-9]{1,9}$"),
):
    return _service(request).timeline(
        start=start,
        end=end,
        market=market,
        category=category,
        admission_state=admission_state,
        lifecycle=lifecycle,
        q=q,
        limit=limit,
        cursor=cursor,
    )


@router.get("/coverage")
async def coverage(request: Request):
    return _service(request).coverage()


@router.get("/sources")
async def catalog(request: Request):
    return _service(request).source_catalog()


@router.get("/jobs")
async def jobs(
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    cursor: str | None = Query(None, pattern="^[0-9]{1,9}$"),
):
    return _service(request).records.list("source_job", limit, cursor)


@router.post("/initial-batch/preview")
async def preview_initial_batch(request: Request):
    _action(request)
    return await initial_batch.preview(_service(request))


@router.post("/initial-batch")
async def run_initial_batch(body: models.Key, request: Request):
    _action(request)
    return await initial_batch.execute(_service(request), body.idempotency_key)


@router.post("/sources/refresh")
@router.post("/sources/backfill")
async def refresh(body: models.Refresh, request: Request):
    _action(request)
    return await _service(request).refresh(body.model_dump(mode="json"))


@router.post("/sources/{source}/schedule")
async def schedule(source: str, body: models.Schedule, request: Request):
    _action(request)
    if sources.CATALOG.get(source, {}).get("manual_only"):
        raise StoreError("该交易所来源仅支持一次性导入", "event_source_manual_only", 409)
    research = request.app.state.research
    if body.enabled:
        await research.ensure_event_scheduler()
    result = _service(request).schedule(source, body.model_dump(mode="json", exclude_unset=True))
    research.automations.arm_collection()
    return result


@router.post("")
async def create(body: models.Create, request: Request):
    _action(request)
    return _service(request).create(body.model_dump(mode="json"))


@router.post("/decisions")
async def decide(body: models.Decision, request: Request):
    _action(request)
    return _service(request).decide(body.model_dump(mode="json"))


@router.post("/freeze")
async def freeze(body: models.Freeze, request: Request):
    _action(request)
    return _service(request).freeze(body.model_dump(mode="json"))


@router.post("/merge")
async def merge(body: models.Merge, request: Request):
    _action(request)
    return _service(request).merge(body.model_dump(mode="json"))


@router.get("/frozen/{identifier}")
async def frozen(identifier: str, request: Request):
    service = _service(request)
    row = service.records.get("freeze", identifier)
    for ref in row["payload"]["evidence_refs"]:
        service.read_evidence(ref)
    return row


@router.get("/{identifier}")
async def detail(identifier: str, request: Request, revision: int | None = Query(None, ge=1)):
    return _service(request).detail(identifier, revision)


@router.get("/{identifier}/versions")
async def versions(identifier: str, request: Request):
    return {"items": _service(request).records.versions("event", identifier)}


@router.patch("/{identifier}")
async def revise(identifier: str, body: models.Revise, request: Request):
    _action(request)
    return _service(request).revise(identifier, body.model_dump(mode="json"))


@router.post("/{identifier}/split")
async def split(identifier: str, body: models.Split, request: Request):
    _action(request)
    return _service(request).split(identifier, body.model_dump(mode="json"))
