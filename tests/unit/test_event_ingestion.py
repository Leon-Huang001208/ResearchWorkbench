from datetime import datetime
from unittest.mock import Mock

from core.contracts import CanonicalEvent
from data_layer.repositories.event_repository import EventRepositoryImpl
from ingestion.structured_event_ingestion import AssertionExtractor, StructuredEventIngestor


class TestCanonicalEventSchema:
    """Test that CanonicalEvent has all required fields"""

    def test_required_fields_exist(self):
        """Test all required fields are present and can be instantiated"""
        event = CanonicalEvent(
            event_id="test_event_001",
            event_type="policy_regulatory",
            event_time=datetime.now(),
            source_type="government",
            source_name="test_source",
            title="Test Event Title",
            confidence=0.9,
            novelty_score=0.7,
        )

        assert event.event_id == "test_event_001"
        assert event.event_type == "policy_regulatory"
        assert event.source_type == "government"
        assert event.source_name == "test_source"
        assert event.title == "Test Event Title"
        assert event.confidence == 0.9
        assert event.novelty_score == 0.7
        assert len(event.extracted_assertions) == 0
        assert len(event.impacted_industries) == 0
        assert len(event.impacted_symbols) == 0
        # Backward compatibility - legacy fields still exist
        assert event.needs_review is True

    def test_backward_compatibility(self):
        """Test that existing code can still create events with legacy fields"""
        # Old style creation should still work
        event = CanonicalEvent(
            event_id="test_legacy_001",
            event_type="legacy",
            summary="Legacy summary",
            event_time=datetime.now(),
            impact_direction="positive",
            confidence=0.8,
            source_type="legacy_source",
            source_name="legacy",
            title="Legacy title",
        )
        assert event.summary == "Legacy summary"
        assert event.impact_direction == "positive"


class TestStructuredEventIngestor:
    """Test the structured event ingestion pipeline"""

    def setup_method(self):
        self.mock_repo = Mock(spec=EventRepositoryImpl)
        self.ingestor = StructuredEventIngestor(self.mock_repo)

    def test_event_normalization(self):
        """Test raw event is normalized to canonical schema"""
        raw_event = {
            "event_type": "company_announcement",
            "event_time": "2025-01-01T10:00:00",
            "source_type": "exchange",
            "source_name": "深交所",
            "title": "Test announcement",
            "raw_text": "This is a test announcement with some content that should be processed",
            "impacted_industries": ["tech", "ai"],
            "impacted_symbols": ["000001", "600000"],
            "confidence": 0.95,
            "novelty_score": 0.8,
        }

        canonical = self.ingestor.normalize_event(raw_event)
        assert canonical.event_id is not None
        assert len(canonical.event_id) > 10
        assert canonical.event_type == "company_announcement"
        assert canonical.source_type == "exchange"
        assert canonical.source_name == "深交所"
        assert canonical.title == "Test announcement"
        assert canonical.raw_text == raw_event["raw_text"]
        assert canonical.impacted_industries == ["tech", "ai"]
        assert canonical.impacted_symbols == ["000001", "600000"]
        assert canonical.confidence == 0.95
        assert canonical.novelty_score == 0.8

    def test_deduplication_works(self):
        """Test that duplicate events are detected"""
        raw_event = {
            "event_id": "existing_event_123",
            "event_type": "policy_regulatory",
            "source_type": "government",
            "source_name": "test",
            "title": "test",
            "confidence": 0.8,
        }

        mock_event = Mock()
        self.mock_repo.get.return_value = mock_event

        result = self.ingestor.ingest(raw_event)
        assert result.is_duplicate is True
        assert result.status == "skipped"
        assert self.mock_repo.save.called is False

    def test_new_event_saved(self):
        """Test that new event is saved correctly"""
        raw_event = {
            "event_type": "overseas_ai_semiconductor",
            "event_time": "2025-01-01T10:00:00",
            "source_type": "overseas_news",
            "source_name": "NVIDIA",
            "title": "New GPU launch",
            "raw_text": "New GPU launched with higher performance",
            "impacted_industries": ["semiconductor"],
            "impacted_symbols": ["000977"],
            "confidence": 0.9,
            "novelty_score": 0.85,
        }

        self.mock_repo.get.return_value = None
        saved_event = self.ingestor.normalize_event(raw_event)
        self.mock_repo.save.return_value = saved_event

        result = self.ingestor.ingest(raw_event)
        assert result.is_duplicate is False
        assert result.status == "success"
        assert self.mock_repo.save.called is True


class TestAssertionExtractor:
    """Test assertion extraction with evidence linking"""

    def setup_method(self):
        self.extractor = AssertionExtractor()

    def test_extract_assertions(self):
        """Test that assertions are extracted with correct evidence positions"""
        text = """NVIDIA launched new GPU that will increase demand for Chinese semiconductor components.
        This is positive for domestic AI server manufacturers."""

        assertions = self.extractor.extract_assertions(text)
        assert len(assertions) >= 1
        for assertion in assertions:
            assert "assertion_id" in assertion
            assert "text" in assertion
            assert "evidence_start" in assertion
            assert "evidence_end" in assertion
            assert "impact_direction" in assertion

    def test_impact_direction_detection(self):
        """Test impact direction detection works correctly"""
        positive_text = "This will increase profits and benefit the industry"
        negative_text = "This will decrease demand and hurt the sector"
        mixed_text = "This will benefit some companies but hurt others"

        positive_assertions = self.extractor.extract_assertions(positive_text)
        negative_assertions = self.extractor.extract_assertions(negative_text)
        mixed_assertions = self.extractor.extract_assertions(mixed_text)

        assert positive_assertions[0]["impact_direction"] == "positive"
        assert negative_assertions[0]["impact_direction"] == "negative"
        # mixed may be mixed or unknown depending on detection, but should not crash
        assert mixed_assertions[0]["impact_direction"] in [
            "mixed",
            "positive",
            "negative",
            "unknown",
        ]


class TestBulkIngestion:
    """Test bulk ingestion"""

    def setup_method(self):
        self.mock_repo = Mock(spec=EventRepositoryImpl)
        self.ingestor = StructuredEventIngestor(self.mock_repo)

    def test_bulk_ingest_returns_correct_counts(self):
        """Test bulk ingestion returns correct success/duplicate counts"""
        events = [
            {
                "event_id": "event1",
                "event_type": "test",
                "source_type": "test",
                "source_name": "test",
                "title": "test1",
                "confidence": 0.8,
            },
            {
                "event_id": "event2",
                "event_type": "test",
                "source_type": "test",
                "source_name": "test",
                "title": "test2",
                "confidence": 0.8,
            },
            {
                "event_id": "event1",
                "event_type": "test",
                "source_type": "test",
                "source_name": "test",
                "title": "test1",
                "confidence": 0.8,
            },
        ]

        # Make event1 exist already, event2 doesn't
        def mock_get(event_id):
            if event_id == "event1":
                return Mock()
            return None

        self.mock_repo.get = mock_get
        self.mock_repo.save = lambda x: x

        results = self.ingestor.bulk_ingest(events)
        assert len(results) == 3
        # Two entries of event1, so two duplicates
        assert sum(1 for r in results if r.is_duplicate) == 2
        assert sum(1 for r in results if r.status == "success") == 1

    def test_auto_extract_assertions_when_not_provided(self):
        """Test that assertions are automatically extracted when raw_text exists but no assertions are provided"""
        raw_event = {
            "event_type": "policy_regulatory",
            "event_time": "2025-01-01T10:00:00",
            "source_type": "government",
            "source_name": "test",
            "title": "Test policy",
            "raw_text": "This policy will increase investment and benefit the tech sector. It will also decrease some costs.",
            "confidence": 0.8,
        }

        self.mock_repo.get.return_value = None
        saved_event = None

        def mock_save(event):
            nonlocal saved_event
            saved_event = event
            return event

        self.mock_repo.save = mock_save

        result = self.ingestor.ingest(raw_event)
        assert result.status == "success"
        assert saved_event is not None
        assert len(saved_event.extracted_assertions) > 0
        for assertion in saved_event.extracted_assertions:
            assert "assertion_id" in assertion
            assert "text" in assertion
            assert "impact_direction" in assertion

    def test_skip_auto_extract_when_assertions_provided(self):
        """Test that auto extraction is skipped when assertions are already provided"""
        raw_event = {
            "event_type": "policy_regulatory",
            "event_time": "2025-01-01T10:00:00",
            "source_type": "government",
            "source_name": "test",
            "title": "Test policy",
            "raw_text": "This policy will increase investment.",
            "extracted_assertions": [
                {
                    "assertion_id": "custom_assertion_1",
                    "text": "Custom assertion text",
                    "impact_direction": "positive",
                }
            ],
            "confidence": 0.8,
        }

        self.mock_repo.get.return_value = None
        saved_event = None

        def mock_save(event):
            nonlocal saved_event
            saved_event = event
            return event

        self.mock_repo.save = mock_save

        result = self.ingestor.ingest(raw_event)
        assert result.status == "success"
        assert saved_event is not None
        assert len(saved_event.extracted_assertions) == 1
        assert saved_event.extracted_assertions[0]["assertion_id"] == "custom_assertion_1"
        assert saved_event.extracted_assertions[0]["text"] == "Custom assertion text"
