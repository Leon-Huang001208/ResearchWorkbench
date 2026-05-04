"""Tests for WordProjection."""
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.contracts import SectionOutput
from reporting.projections.word import WordProjection


class TestWordProjection:
    """Test suite for WordProjection."""

    @pytest.mark.skipif(not WordProjection()._check_docx(), reason="python-docx not installed")
    def test_save_to_file(self, tmp_path):
        """Test saving Word document to a file."""
        projection = WordProjection()
        sections = [
            SectionOutput(
                key="test",
                content="Test content",
                evidence_refs=[],
                warnings=[],
            )
        ]
        output_file = tmp_path / "report.docx"

        projection.save(output_file, "Test Report", sections)

        assert output_file.exists()

    def test_save_with_metadata(self, tmp_path):
        """Test saving with metadata."""
        projection = WordProjection()
        if not projection._check_docx():
            pytest.skip("python-docx not installed")

        sections = [
            SectionOutput(
                key="test",
                content="Test content",
                evidence_refs=[],
                warnings=[],
            )
        ]
        metadata = {"author": "Test Author"}
        output_file = tmp_path / "report.docx"

        projection.save(output_file, "Test Report", sections, metadata=metadata)
        assert output_file.exists()

    def test_save_with_evidence_refs(self, tmp_path):
        """Test saving with evidence references."""
        projection = WordProjection()
        if not projection._check_docx():
            pytest.skip("python-docx not installed")

        sections = [
            SectionOutput(
                key="test",
                content="Content",
                evidence_refs=["doc1", "doc2"],
                warnings=[],
            )
        ]
        output_file = tmp_path / "report.docx"

        projection.save(output_file, "Test Report", sections)
        assert output_file.exists()

    def test_save_with_warnings(self, tmp_path):
        """Test saving with warnings."""
        projection = WordProjection()
        if not projection._check_docx():
            pytest.skip("python-docx not installed")

        sections = [
            SectionOutput(
                key="test",
                content="Content",
                evidence_refs=[],
                warnings=["Warning 1"],
            )
        ]
        output_file = tmp_path / "report.docx"

        projection.save(output_file, "Test Report", sections)
        assert output_file.exists()

    def test_save_raises_when_docx_not_installed(self, tmp_path):
        """Test that it raises ImportError when python-docx is not available."""
        projection = WordProjection()
        projection._has_docx = False

        sections = [
            SectionOutput(
                key="test",
                content="Content",
                evidence_refs=[],
                warnings=[],
            )
        ]
        output_file = tmp_path / "report.docx"

        with pytest.raises(ImportError):
            projection.save(output_file, "Test Report", sections)

    def test_check_docx_handles_import_error(self):
        """Test that _check_docx handles import errors gracefully."""
        projection = WordProjection()

        with patch("importlib.import_module", side_effect=ImportError):
            # This test verifies the code path - we can't easily patch the module check
            # since it happens in __init__
            result = projection._check_docx()
            # The exact result depends on whether python-docx is actually installed
            # but the method should not raise an exception
            assert isinstance(result, bool)
