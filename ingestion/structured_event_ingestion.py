import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from core.contracts import CanonicalEvent
from core.observability import get_logger
from data_layer.repositories.event_repository import EventRepositoryImpl

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    """Result of structured event ingestion"""
    event: CanonicalEvent
    is_duplicate: bool
    status: str
    message: str = ""


class StructuredEventIngestor:
    """
    Standardized structured event ingestion pipeline for A-share alpha events
    """

    def __init__(self, event_repository: EventRepositoryImpl):
        self.repo = event_repository
        logger.info("StructuredEventIngestor initialized")

    def _generate_event_id(self, source_type: str, source_name: str, event_time: datetime, title: str) -> str:
        """Generate deterministic event id for deduplication"""
        content = f"{source_type}:{source_name}:{event_time.isoformat()}:{title}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"event_{hash_val}"

    def normalize_event(self, raw_event: Dict[str, Any]) -> CanonicalEvent:
        """
        Normalize raw event input into canonical event schema
        """
        # Extract required fields with defaults
        event_type = raw_event.get("event_type", "unknown")
        event_time_str = raw_event.get("event_time")
        event_time = None
        if event_time_str:
            try:
                event_time = datetime.fromisoformat(event_time_str)
            except ValueError:
                logger.warning("Failed to parse event_time, keeping as None", event_time=event_time_str)

        source_type = raw_event.get("source_type", "unknown")
        source_name = raw_event.get("source_name", "unknown")
        title = raw_event.get("title", "Untitled event")
        raw_text = raw_event.get("raw_text")

        # Extract assertions
        extracted_assertions = raw_event.get("extracted_assertions", [])
        # Ensure each assertion has evidence ref
        for idx, assertion in enumerate(extracted_assertions):
            if "evidence_start" not in assertion:
                assertion["evidence_start"] = 0
            if "evidence_end" not in assertion:
                assertion["evidence_end"] = len(raw_text) if raw_text else 0
            if "assertion_id" not in assertion:
                assertion["assertion_id"] = f"{self._generate_event_id(source_type, source_name, event_time or datetime.now(), title)}_assertion_{idx}"

        impacted_industries = raw_event.get("impacted_industries", [])
        impacted_symbols = raw_event.get("impacted_symbols", [])
        confidence = raw_event.get("confidence", 0.5)
        novelty_score = raw_event.get("novelty_score", 0.0)

        # Generate event id if not exists
        event_id = raw_event.get("event_id")
        if not event_id:
            event_id = self._generate_event_id(source_type, source_name, event_time or datetime.now(), title)

        # Create canonical event
        canonical_event = CanonicalEvent(
            event_id=event_id,
            event_type=event_type,
            event_time=event_time,
            source_type=source_type,
            source_name=source_name,
            title=title,
            raw_text=raw_text,
            extracted_assertions=extracted_assertions,
            impacted_industries=impacted_industries,
            impacted_symbols=impacted_symbols,
            confidence=confidence,
            novelty_score=novelty_score
        )

        logger.debug(
            "Event normalized",
            event_id=canonical_event.event_id,
            event_type=canonical_event.event_type,
            num_assertions=len(canonical_event.extracted_assertions)
        )

        return canonical_event

    def ingest(self, raw_event: Dict[str, Any]) -> IngestionResult:
        """
        Ingest a single raw event, handle deduplication, normalize and save
        """
        try:
            # Normalize to canonical schema
            canonical = self.normalize_event(raw_event)

            # Check for duplicate
            existing = self.repo.get(canonical.event_id)
            if existing is not None:
                logger.info("Duplicate event detected, skipping save", event_id=canonical.event_id)
                return IngestionResult(
                    event=existing,
                    is_duplicate=True,
                    status="skipped",
                    message="Duplicate event already exists"
                )

            # Save to repository
            saved = self.repo.save(canonical)
            logger.info("New event ingested successfully", event_id=saved.event_id, is_duplicate=False)

            return IngestionResult(
                event=saved,
                is_duplicate=False,
                status="success",
                message="Event ingested successfully"
            )

        except Exception as e:
            logger.error("Failed to ingest event", error=str(e), exc_info=True)
            return IngestionResult(
                event=None,
                is_duplicate=False,
                status="error",
                message=f"Failed to ingest: {str(e)}"
            )

    def bulk_ingest(self, raw_events: List[Dict[str, Any]]) -> List[IngestionResult]:
        """
        Bulk ingest multiple events
        """
        results = []
        for raw_event in raw_events:
            result = self.ingest(raw_event)
            results.append(result)

        total_success = sum(1 for r in results if r.status == "success")
        total_duplicates = sum(1 for r in results if r.is_duplicate)
        total_errors = sum(1 for r in results if r.status == "error")

        logger.info(
            "Bulk ingestion complete",
            total=len(raw_events),
            success=total_success,
            duplicates=total_duplicates,
            errors=total_errors
        )

        return results


class AssertionExtractor:
    """
    Extract assertions from raw text with evidence linking
    """

    def __init__(self):
        self.logger = get_logger(__name__)

    def extract_assertions(self, raw_text: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Extract actionable assertions from raw text, link to evidence spans
        This is a placeholder implementation - you can extend this with LLM extraction later
        """
        assertions = []
        context = context or {}

        # Simple rule-based extraction for common patterns
        # In production this would use an LLM to extract structured assertions
        lines = raw_text.split("\n")
        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Look for statements that make claims about impact
            has_impact = any(kw in line.lower() for kw in ["will", "expected", "impact", "increase", "decrease", "benefit", "hurt"])
            if has_impact or len(line) > 20:
                start = raw_text.find(line)
                end = start + len(line)
                assertion = {
                    "assertion_id": f"assertion_{idx}",
                    "text": line,
                    "impact_direction": self._detect_impact_direction(line),
                    "evidence_start": start,
                    "evidence_end": end,
                    "metadata": context
                }
                assertions.append(assertion)

        self.logger.debug("Extracted assertions", count=len(assertions))
        return assertions

    def _detect_impact_direction(self, text: str) -> str:
        """Detect impact direction from assertion text"""
        text_lower = text.lower()
        positive = ["increase", "rise", "growth", "benefit", "positive", "good", "up", "gain", "improve"]
        negative = ["decrease", "fall", "drop", "hurt", "negative", "bad", "down", "loss", "decline", "worsen"]

        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)

        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        elif pos_count > 0 and neg_count > 0:
            return "mixed"
        else:
            return "unknown"
