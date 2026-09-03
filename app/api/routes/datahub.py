"""DataHub management API; research tools consume the separate read-only service."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.configuration_security import require_configuration_csrf_token
from core.contracts.datahub import DataHubCitationRequest, DataHubQuery, DataHubSyncRequest
from core.observability import get_logger
from data_layer.repositories.base import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/api/datahub", tags=["datahub"])


def get_datahub(db: Session = Depends(get_db)):
    from services.datahub_service import DataHubService

    return DataHubService(db)


@router.post("/research-evidence", dependencies=[Depends(require_configuration_csrf_token)])
def cite(request: DataHubCitationRequest, db: Session = Depends(get_db)):
    from app.api.routes.research_runs import get_research_run_service
    from services.datahub_service import DataHubService
    from services.research_tool_registry import datahub_evidence, record_datahub_tool_evidence

    try:
        query = DataHubQuery(dataset=request.dataset, fact_id=request.fact_id, limit=1)
        result = DataHubService(db).query(query)
        if not result["records"]:
            raise HTTPException(404, "Validated fact not found")
        research = get_research_run_service(db)
        research.add_evidence(
            request.run_id,
            datahub_evidence(result["records"][0], request.dataset),
            project_id=request.project_id,
            workspace_id=request.workspace_id,
        )
        record_datahub_tool_evidence(
            db, request.run_id, "internal:data_query", query.model_dump(mode="json"), result
        )
        return {"run_id": request.run_id, "evidence_ref": result["records"][0]["evidence_ref"]}
    except ValueError as exc:
        logger.warning("DataHub research citation rejected", error_type=type(exc).__name__)
        raise HTTPException(422, "Run scope, state, or fact query is invalid") from None


@router.get("/sources")
def sources(service=Depends(get_datahub)):
    return service.sources()


@router.get("/catalog")
def catalog(dataset: str | None = None, service=Depends(get_datahub)):
    try:
        return service.catalog(dataset)
    except ValueError as exc:
        raise HTTPException(422, "Unknown catalog") from exc


@router.get("/records")
def records(
    dataset: str,
    snapshot_id: str | None = None,
    symbol: str | None = None,
    fact_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    cycle: str | None = None,
    adjustment: Literal["forward", "backward", "none"] | None = None,
    table_name: str | None = None,
    indicator: str | None = None,
    fields: list[str] | None = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    include_quarantined: bool = False,
    service=Depends(get_datahub),
):
    try:
        return service.query(
            DataHubQuery(
                dataset=dataset,
                snapshot_id=snapshot_id,
                symbol=symbol,
                fact_id=fact_id,
                start_date=start_date,
                end_date=end_date,
                cycle=cycle,
                adjustment=adjustment,
                table_name=table_name,
                indicator=indicator,
                fields=fields,
                limit=limit,
                offset=offset,
            ),
            include_quarantined=include_quarantined,
        )
    except ValueError as exc:
        raise HTTPException(422, "Invalid data query") from exc


@router.post("/runs", status_code=202, dependencies=[Depends(require_configuration_csrf_token)])
def sync(request: DataHubSyncRequest, service=Depends(get_datahub)):
    try:
        return service.sync(request)
    except ValueError as exc:
        raise HTTPException(409, "Sync request conflicts with existing idempotency key") from exc
    except Exception as exc:
        logger.error("datahub sync failed", error_type=type(exc).__name__)
        raise HTTPException(503, "DataHub database unavailable") from exc


@router.get("/runs")
def runs(service=Depends(get_datahub)):
    return service.runs()


@router.get("/runs/{job_id}")
def run(job_id: str, service=Depends(get_datahub)):
    try:
        return service.runs(job_id)
    except LookupError as exc:
        raise HTTPException(404, "Run not found") from exc


@router.post("/sources/cjpy/health", dependencies=[Depends(require_configuration_csrf_token)])
def health():
    from data_layer.adapters.cjpy_adapter import CjpyAdapter

    return CjpyAdapter(timeout=10).health()
