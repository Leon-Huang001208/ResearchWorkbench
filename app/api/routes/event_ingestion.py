from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generator, List, TypedDict, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.contracts import CanonicalEvent
from core.observability import get_logger
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.event_repository import EventRepositoryImpl
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from ingestion.structured_event_ingestion import IngestionResult

logger = get_logger(__name__)

router = APIRouter(prefix="/api/events", tags=["event_ingestion"])


@dataclass
class EventQueryResponse:
    """Response for event query"""

    events: List[CanonicalEvent]
    total: int
    offset: int
    limit: int


class ApproveEventResponse(TypedDict):
    """Response for event approval."""

    event_id: str
    status: str
    auto_signal_generated: bool


class AutoGenerateSignalsResponse(TypedDict):
    """Response for manual auto-signal generation."""

    generated_signals_count: int
    status: str


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error("database error", error=str(e))
        db.rollback()
        raise
    finally:
        db.close()


def get_ingestor(db: Session = Depends(get_db_session)) -> StructuredEventIngestor:
    """Dependency injection for structured event ingestor."""
    from ingestion.structured_event_ingestion import StructuredEventIngestor

    repo = EventRepositoryImpl(db)
    return StructuredEventIngestor(repo)


def get_repository(db: Session = Depends(get_db_session)) -> EventRepositoryImpl:
    """Dependency injection for event repository."""
    return EventRepositoryImpl(db)


@router.post("/ingest", response_model=IngestionResult)
def ingest_event(
    raw_event: Dict[str, Any],
    ingestor: StructuredEventIngestor = Depends(get_ingestor),
) -> IngestionResult:
    """Ingest a single structured alpha event."""
    result = ingestor.ingest(raw_event)
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.message)
    return result


@router.post("/ingest/bulk", response_model=List[IngestionResult])
def bulk_ingest_events(
    raw_events: List[Dict[str, Any]],
    ingestor: StructuredEventIngestor = Depends(get_ingestor),
) -> List[IngestionResult]:
    """Bulk ingest multiple structured alpha events."""
    return cast(List[IngestionResult], ingestor.bulk_ingest(raw_events))


@router.get("/list", response_model=EventQueryResponse)
def list_events(
    limit: int = 100,
    offset: int = 0,
    repo: EventRepositoryImpl = Depends(get_repository),
) -> EventQueryResponse:
    """List all events."""
    events = repo.list(limit, offset)
    return EventQueryResponse(events=events, total=len(events), offset=offset, limit=limit)


@router.get("/type/{event_type}", response_model=List[CanonicalEvent])
def list_events_by_type(
    event_type: str,
    limit: int = 100,
    repo: EventRepositoryImpl = Depends(get_repository),
) -> List[CanonicalEvent]:
    """List events by event type."""
    return repo.list_by_event_type(event_type, limit)


@router.get("/symbol/{symbol}", response_model=List[CanonicalEvent])
def list_events_by_symbol(
    symbol: str,
    limit: int = 100,
    repo: EventRepositoryImpl = Depends(get_repository),
) -> List[CanonicalEvent]:
    """List events impacting a specific symbol."""
    return repo.list_by_impacted_symbol(symbol, limit)


@router.get("/{event_id}", response_model=CanonicalEvent)
def get_event(
    event_id: str,
    repo: EventRepositoryImpl = Depends(get_repository),
) -> CanonicalEvent:
    """Get a canonical event by id."""
    event = repo.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/extract-assertions", response_model=List[Dict[str, Any]])
def extract_assertions(
    payload: Dict[str, Any],
    ingestor: StructuredEventIngestor = Depends(get_ingestor),
) -> List[Dict[str, Any]]:
    """Extract assertions from raw text with evidence linking."""
    raw_text = payload.get("raw_text", "")
    context = payload.get("context")
    return cast(List[Dict[str, Any]], ingestor.extract_assertions(raw_text, context))


@router.post("/{event_id}/approve", response_model=dict)
def approve_event(
    event_id: str,
    approved: bool = Query(True, description="是否批准该事件"),
    db: Session = Depends(get_db_session),
) -> ApproveEventResponse:
    """审批事件，批准后自动生成候选信号"""
    from services.event_auto_signal_generator import EventAutoSignalGenerator

    repo = EventRepositoryImpl(db)
    event = repo.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event.reviewer_status = "approved" if approved else "rejected"
    repo.save(event)

    if approved:
        # 审批通过后自动生成信号
        signal_repo = SignalRepositoryImpl(db)
        generator = EventAutoSignalGenerator(
            event_repo=repo,
            signal_repo=signal_repo,
            db_session=db,
        )
        generator.on_event_approved(event_id)

    return {
        "event_id": event_id,
        "status": event.reviewer_status,
        "auto_signal_generated": approved,
    }


@router.post("/auto-generate-signals", response_model=dict)
def trigger_auto_generate_signals(
    db: Session = Depends(get_db_session),
) -> AutoGenerateSignalsResponse:
    """手动触发所有已批准事件的信号生成"""
    from services.event_auto_signal_generator import EventAutoSignalGenerator

    event_repo = EventRepositoryImpl(db)
    signal_repo = SignalRepositoryImpl(db)
    generator = EventAutoSignalGenerator(
        event_repo=event_repo,
        signal_repo=signal_repo,
        db_session=db,
    )
    count = generator.process_approved_events()
    return {"generated_signals_count": count, "status": "success"}
