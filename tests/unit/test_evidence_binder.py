"""Tests for EvidenceBinder."""
import pytest

from reporting.composer.evidence_binder import BoundEvidence, EvidenceBinder


class TestEvidenceBinder:
    """Test suite for EvidenceBinder."""

    def test_add_evidence(self):
        """Test adding evidence to the binder."""
        binder = EvidenceBinder()
        binder.add_evidence(
            evidence_id="doc1",
            source="Research Report",
            content="This is evidence content",
            relevance_score=0.9,
        )

        evidence = binder.get_evidence_by_id("doc1")
        assert evidence is not None
        assert evidence.id == "doc1"
        assert evidence.source == "Research Report"
        assert evidence.content == "This is evidence content"
        assert evidence.relevance_score == 0.9

    def test_bind_to_section_by_keyword(self):
        """Test binding evidence to a section by keyword matching."""
        binder = EvidenceBinder()
        binder.add_evidence("doc1", "Source 1", "Content about AAPL stock", 0.8)
        binder.add_evidence("doc2", "Source 2", "Content about interest rates", 0.7)
        binder.add_evidence("doc3", "Source 3", "Content about gold prices", 0.6)

        bound = binder.bind_to_section("section1", "AAPL stock", top_k=2)

        assert len(bound) == 1
        assert bound[0].id == "doc1"
        assert bound[0].section_key == "section1"

    def test_get_evidence_for_section(self):
        """Test getting evidence already bound to a section."""
        binder = EvidenceBinder()
        binder.add_evidence("doc1", "Source 1", "Content 1", 0.8)
        binder.add_evidence("doc2", "Source 2", "Content 2", 0.7)

        # Bind to section
        binder.bind_to_section("section1", "Content")

        evidence = binder.get_evidence_for_section("section1")
        assert len(evidence) == 2

    def test_to_dict_list(self):
        """Test converting bound evidence to dict list."""
        binder = EvidenceBinder()
        binder.add_evidence("doc1", "Source 1", "Content 1", 0.8)

        bound = binder.bind_to_section("section1", "Content")
        dict_list = binder.to_dict_list(bound)

        assert len(dict_list) == 1
        assert dict_list[0]["id"] == "doc1"
        assert dict_list[0]["source"] == "Source 1"
        assert dict_list[0]["content"] == "Content 1"
        assert dict_list[0]["relevance_score"] == 0.8

    def test_clear_evidence(self):
        """Test clearing all evidence."""
        binder = EvidenceBinder()
        binder.add_evidence("doc1", "Source 1", "Content 1", 0.8)
        binder.add_evidence("doc2", "Source 2", "Content 2", 0.7)

        assert binder.get_evidence_by_id("doc1") is not None

        binder.clear()

        assert binder.get_evidence_by_id("doc1") is None

    def test_get_nonexistent_evidence(self):
        """Test getting evidence that doesn't exist."""
        binder = EvidenceBinder()
        assert binder.get_evidence_by_id("nonexistent") is None

    def test_bind_no_matching_evidence(self):
        """Test binding when no evidence matches the query."""
        binder = EvidenceBinder()
        binder.add_evidence("doc1", "Source 1", "Content about XYZ", 0.8)

        bound = binder.bind_to_section("section1", "AAPL", top_k=5)
        assert len(bound) == 0
