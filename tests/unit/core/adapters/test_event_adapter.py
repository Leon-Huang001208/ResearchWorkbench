"""Test DB CanonicalEvent → Pydantic CanonicalEvent adapter."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from core.adapters.event_adapter import db_event_to_pydantic
from core.contracts.events import CanonicalEvent


def _make_db_event(**overrides):
    """Create a mock DB CanonicalEvent with default field values."""
    defaults = {
        "event_id": "evt_001",
        "event_type": "earnings",
        "summary": "Company X reported strong Q4 earnings",
        "event_time": datetime(2026, 1, 15, tzinfo=UTC),
        "impact_direction": "positive",
        "confidence": 0.9,
        "needs_review": False,
        "source_doc_id": "doc_001",
        "payload": {
            "source_type": "news",
            "source_name": "Reuters",
            "title": "Company X Q4 Beat",
            "raw_text": "Full article text...",
            "extracted_assertions": [{"assertion": "EPS beat by 10%"}],
            "impacted_industries": ["tech"],
            "impacted_symbols": ["CMPX"],
            "novelty_score": 0.3,
            "entities": [{"name": "Company X", "type": "company"}],
            "assertions": [],
            "evidence_spans": [{"start": 0, "end": 50}],
        },
        "reviewer_status": "approved",
        "reviewer": "analyst1",
        "reviewed_at": datetime(2026, 1, 16, tzinfo=UTC),
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


class TestEventAdapter:
    def test_full_conversion(self):
        db_event = _make_db_event()
        result = db_event_to_pydantic(db_event)

        assert isinstance(result, CanonicalEvent)
        assert result.event_id == "evt_001"
        assert result.event_type == "earnings"
        assert result.summary == "Company X reported strong Q4 earnings"
        assert result.event_time == datetime(2026, 1, 15, tzinfo=UTC)
        assert result.source_type == "news"
        assert result.source_name == "Reuters"
        assert result.title == "Company X Q4 Beat"
        assert result.raw_text == "Full article text..."
        assert len(result.extracted_assertions) == 1
        assert result.impacted_industries == ["tech"]
        assert result.impacted_symbols == ["CMPX"]
        assert result.confidence == 0.9
        assert result.novelty_score == 0.3
        assert result.impact_direction == "positive"
        assert result.needs_review is False
        assert len(result.entities) == 1
        assert result.source_doc_id == "doc_001"
        assert result.reviewer_status == "approved"
        assert result.reviewer == "analyst1"
        assert result.reviewed_at == datetime(2026, 1, 16, tzinfo=UTC)

    def test_payload_none_fallback(self):
        db_event = _make_db_event(payload=None)
        result = db_event_to_pydantic(db_event)
        assert result.source_type == ""
        assert result.source_name == ""
        assert result.extracted_assertions == []
        assert result.impacted_industries == []

    def test_empty_payload_fallback(self):
        db_event = _make_db_event(payload={})
        result = db_event_to_pydantic(db_event)
        assert result.source_type == ""
        assert result.source_name == ""

    def test_title_falls_back_to_summary(self):
        db_event = _make_db_event(payload={"source_type": "report"})
        result = db_event_to_pydantic(db_event)
        assert result.title == "Company X reported strong Q4 earnings"

    def test_invalid_impact_direction_coerced_to_unknown(self):
        db_event = _make_db_event(impact_direction="whatever")
        result = db_event_to_pydantic(db_event)
        assert result.impact_direction == "unknown"

    def test_confidence_numeric_conversion(self):
        db_event = _make_db_event(confidence=0.75)
        result = db_event_to_pydantic(db_event)
        assert result.confidence == 0.75
        assert isinstance(result.confidence, float)

    def test_source_doc_id_empty_string_fallback(self):
        db_event = _make_db_event(source_doc_id=None)
        result = db_event_to_pydantic(db_event)
        assert result.source_doc_id == ""
