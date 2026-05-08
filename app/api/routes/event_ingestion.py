from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from core.contracts import CanonicalEvent
from core.services.event_ingestion_service import EventIngestionService, EventQueryResponse, IngestionResult
from data_layer.repositories.event_repository import EventRepositoryImpl
from core.observability import get_logger
from data_layer.db import get_db_session

logger = get_logger(__name__)

router = APIRouter(prefix="/api/events", tags=["event_ingestion"])


def get_service():
    """Dependency injection for event ingestion service"""
    session = get_db_session()
    repo = EventRepositoryImpl(session)
    return EventIngestionService(repo)


@router.post("/ingest", response_model=IngestionResult)
def ingest_event(
    raw_event: Dict[str, Any],
    service: EventIngestionService = Depends(get_service)
):
    """Ingest a single structured alpha event"""
    result = service.ingest_event(raw_event)
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.message)
    return result


@router.post("/ingest/bulk", response_model=List[IngestionResult])
def bulk_ingest_events(
    raw_events: List[Dict[str, Any]],
    service: EventIngestionService = Depends(get_service)
):
    """Bulk ingest multiple structured alpha events"""
    results = service.bulk_ingest_events(raw_events)
    return results


@router.get("/{event_id}", response_model=CanonicalEvent)
def get_event(
    event_id: str,
    service: EventIngestionService = Depends(get_service)
):
    """Get a canonical event by id"""
    event = service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/list", response_model=EventQueryResponse)
def list_events(
    limit: int = 100,
    offset: int = 0,
    service: EventIngestionService = Depends(get_service)
):
    """List all events"""
    return service.list_events(limit, offset)


@router.get("/type/{event_type}", response_model=List[CanonicalEvent])
def list_events_by_type(
    event_type: str,
    limit: int = 100,
    service: EventIngestionService = Depends(get_service)
):
    """List events by event type"""
    return service.list_events_by_type(event_type, limit)


@router.get("/symbol/{symbol}", response_model=List[CanonicalEvent])
def list_events_by_symbol(
    symbol: str,
    limit: int = 100,
    service: EventIngestionService = Depends(get_service)
):
    """List events impacting a specific symbol"""
    return service.list_events_by_symbol(symbol, limit)


@router.post("/extract-assertions", response_model=List[Dict[str, Any]])
def extract_assertions(
    raw_text: str,
    context: Dict[str, Any] = None,
    service: EventIngestionService = Depends(get_service)
):
    """Extract assertions from raw text with evidence linking"""
    return service.extract_assertions(raw_text, context)
