from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from core.contracts import CanonicalEvent
from core.observability import get_logger
from data_layer.repositories.event_repository import EventRepositoryImpl
from ingestion.structured_event_ingestion import StructuredEventIngestor, IngestionResult, AssertionExtractor

logger = get_logger(__name__)


@dataclass
class EventIngestionRequest:
    """Request for event ingestion"""
    raw_event: Dict[str, Any]


@dataclass
class EventQueryResponse:
    """Response for event query"""
    events: List[CanonicalEvent]
    total: int
    offset: int
    limit: int


class EventIngestionService:
    """
    High level API for standardized alpha event ingestion
    """

    def __init__(self, event_repository: EventRepositoryImpl):
        self.repo = event_repository
        self.ingestor = StructuredEventIngestor(event_repository)
        self.assertion_extractor = AssertionExtractor()
        logger.info("EventIngestionService initialized")

    def ingest_event(self, raw_event: Dict[str, Any]) -> IngestionResult:
        """Ingest a single event"""
        if "raw_text" in raw_event and (not raw_event.get("extracted_assertions")):
            # Auto extract assertions if not provided
            raw_text = raw_event["raw_text"]
            assertions = self.assertion_extractor.extract_assertions(raw_text, raw_event.get("context"))
            raw_event["extracted_assertions"] = assertions

        return self.ingestor.ingest(raw_event)

    def bulk_ingest_events(self, raw_events: List[Dict[str, Any]]) -> List[IngestionResult]:
        """Bulk ingest multiple events"""
        for event in raw_events:
            if "raw_text" in event and (not event.get("extracted_assertions")):
                raw_text = event["raw_text"]
                assertions = self.assertion_extractor.extract_assertions(raw_text, event.get("context"))
                event["extracted_assertions"] = assertions

        return self.ingestor.bulk_ingest(raw_events)

    def get_event(self, event_id: str) -> Optional[CanonicalEvent]:
        """Get a single event by id"""
        return self.repo.get(event_id)

    def list_events(self, limit: int = 100, offset: int = 0) -> EventQueryResponse:
        """List all events"""
        events = self.repo.list(limit, offset)
        return EventQueryResponse(
            events=events,
            total=len(events),
            offset=offset,
            limit=limit
        )

    def list_events_by_type(self, event_type: str, limit: int = 100) -> List[CanonicalEvent]:
        """List events by type"""
        if hasattr(self.repo, "list_by_event_type"):
            return self.repo.list_by_event_type(event_type, limit)
        # Fallback to filtering all events
        all_events = self.repo.list(limit=limit)
        return [e for e in all_events if e.event_type == event_type]

    def list_events_by_symbol(self, symbol: str, limit: int = 100) -> List[CanonicalEvent]:
        """List events impacting a specific symbol"""
        if hasattr(self.repo, "list_by_impacted_symbol"):
            return self.repo.list_by_impacted_symbol(symbol, limit)
        # Fallback to filtering
        all_events = self.repo.list(limit=limit)
        return [e for e in all_events if symbol in e.impacted_symbols]

    def extract_assertions(self, raw_text: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract assertions from raw text"""
        return self.assertion_extractor.extract_assertions(raw_text, context)
