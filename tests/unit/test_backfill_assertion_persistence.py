"""
Test backfill assertion persistence: end-to-end test for factual layer recovery.

Tests cover:
- Source document restoration
- Assertion extraction and persistence
- Idempotency (repeated runs don't create duplicates)
- Linkage between assertions and source documents
"""
import tempfile
from pathlib import Path
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_layer.repositories.base import Base
from data_layer.repositories.models import Assertion
from scripts.backfill_from_objects import (
    upsert_source_document,
    run_extraction,
    generate_assertion_id,
    load_artifact,
)
from ingestion.structured_event_ingestion import AssertionExtractor, StructuredEventIngestor


@pytest.fixture(scope="function")
def temp_db():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def assertion_extractor():
    return AssertionExtractor()


@pytest.fixture
def event_ingestor():
    # For testing, we don't need a real event repo
    from unittest.mock import Mock
    mock_repo = Mock()
    mock_repo.get.return_value = None
    mock_repo.save.return_value = Mock(event_id="test_event_1")
    return StructuredEventIngestor(mock_repo)


def test_generate_assertion_id_is_deterministic():
    """Test that assertion ids are stable across runs for same content"""
    doc_id = "doc_test123"
    content_hash = "abcdef1234567890"
    id1 = generate_assertion_id(doc_id, 0, content_hash)
    id2 = generate_assertion_id(doc_id, 0, content_hash)
    id3 = generate_assertion_id(doc_id, 1, content_hash)
    
    assert id1 == id2
    assert id1 != id3


def test_assertion_persistence_after_backfill(temp_db, assertion_extractor, event_ingestor):
    """Test that after backfill processing, assertions are persisted and linked to source doc"""
    # Create a test artifact
    test_content = """
    Apple Inc. is expected to increase revenue in 2025 due to strong iPhone sales.
    The impact on AAPL stock should be positive over the next 12 months.
    """
    artifact = {
        "raw_text": test_content,
        "source_type": "test_report",
        "source_name": "test_apple_report.txt",
        "title": "Apple 2025 Forecast"
    }
    
    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(artifact, f)
        temp_path = Path(f.name)
    
    try:
        # Load artifact
        loaded = load_artifact(temp_path)
        assert loaded is not None
        
        # Upsert source document
        changed, source_doc = upsert_source_document(temp_db, temp_path, loaded, force_reextract=False)
        assert changed is True
        assert source_doc.doc_id is not None
        temp_db.commit()
        
        # Run extraction
        extracted, persisted, events, failed = run_extraction(
            temp_db, source_doc, loaded, assertion_extractor, event_ingestor, force_reextract=False
        )
        
        assert failed is False
        assert extracted >= 2
        assert persisted == extracted  # all should be new
        assert events == 0  # No event_type in this artifact
        
        temp_db.commit()
        
        # Check that assertions are persisted in DB
        all_assertions = temp_db.query(Assertion).filter_by(source_doc_id=source_doc.doc_id).all()
        assert len(all_assertions) == persisted
        
        for assertion in all_assertions:
            assert assertion.assertion_id is not None
            assert assertion.source_doc_id == source_doc.doc_id
            assert assertion.predicate is not None
            assert assertion.extractor_version is not None
            
    finally:
        temp_path.unlink()


def test_backfill_idempotency(temp_db, assertion_extractor, event_ingestor):
    """Test that repeated backfill runs do not create duplicate assertions"""
    # Create test artifact
    test_content = "Microsoft will increase cloud revenue next quarter, boosting MSFT stock."
    artifact = {
        "raw_text": test_content,
        "source_type": "test_note",
        "source_name": "msft_note.txt",
        "title": "MSFT Note"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(artifact, f)
        temp_path = Path(f.name)
    
    try:
        loaded = load_artifact(temp_path)
        
        # First run
        changed1, source_doc = upsert_source_document(temp_db, temp_path, loaded, force_reextract=False)
        temp_db.commit()
        extracted1, persisted1, events1, failed1 = run_extraction(
            temp_db, source_doc, loaded, assertion_extractor, event_ingestor, force_reextract=False
        )
        temp_db.commit()
        
        count_after_first = temp_db.query(Assertion).filter_by(source_doc_id=source_doc.doc_id).count()
        
        # Second run - should skip existing assertions
        changed2, source_doc2 = upsert_source_document(temp_db, temp_path, loaded, force_reextract=False)
        assert changed2 is False  # content same, so source doc not changed
        
        extracted2, persisted2, events2, failed2 = run_extraction(
            temp_db, source_doc2, loaded, assertion_extractor, event_ingestor, force_reextract=False
        )
        
        temp_db.commit()
        count_after_second = temp_db.query(Assertion).filter_by(source_doc_id=source_doc.doc_id).count()
        
        # No new assertions added on second run
        assert persisted2 == 0
        assert count_after_first == count_after_second
        
        # But with force_reextract, it should re-persist
        extracted3, persisted3, events3, failed3 = run_extraction(
            temp_db, source_doc2, loaded, assertion_extractor, event_ingestor, force_reextract=True
        )
        
        # Should re-persist same count
        assert persisted3 == extracted1
        assert temp_db.query(Assertion).count() == count_after_first  # still same count, just updated
        
    finally:
        temp_path.unlink()


def test_full_source_to_event_recovery(temp_db, assertion_extractor, event_ingestor):
    """Test end-to-end: source doc -> assertions -> canonical event all persisted"""
    artifact = {
        "raw_text": "Tesla announced that gigafactory Mexico will open in 2025, increasing production capacity.",
        "event_type": "facility_opening",
        "source_type": "news",
        "source_name": "tesla_news.json",
        "title": "Tesla Gigafactory Mexico Opening",
        "event_time": "2024-01-01T00:00:00",
        "confidence": 0.8
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(artifact, f)
        temp_path = Path(f.name)
    
    try:
        loaded = load_artifact(temp_path)
        changed, source_doc = upsert_source_document(temp_db, temp_path, loaded, False)
        temp_db.commit()
        
        assert changed is True
        extracted, persisted, events, failed = run_extraction(
            temp_db, source_doc, loaded, assertion_extractor, event_ingestor
        )
        
        temp_db.commit()
        
        assert failed is False
        assert extracted >= 1
        assert persisted >= 1
        assert events == 1  # should ingest one canonical event
        
        # Verify assertions exist and are linked
        assertions = temp_db.query(Assertion).filter_by(source_doc_id=source_doc.doc_id).all()
        assert len(assertions) == persisted
        
        # All assertions have correct metadata provenance
        for a in assertions:
            assert a.source_doc_id == source_doc.doc_id
            assert "backfill" in a.extractor_version
            
    finally:
        temp_path.unlink()
