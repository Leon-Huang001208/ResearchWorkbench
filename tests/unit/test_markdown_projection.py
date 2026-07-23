"""Tests for MarkdownProjection."""

from core.contracts import SectionOutput
from reporting.projections.markdown import MarkdownProjection


class TestMarkdownProjection:
    """Test suite for MarkdownProjection."""

    def test_render_basic_report(self):
        """Test rendering a basic report."""
        projection = MarkdownProjection()
        sections = [
            SectionOutput(
                key="summary",
                title="Summary",
                content="This is the summary content",
                evidence_refs=[],
                warnings=[],
            ),
            SectionOutput(
                key="analysis",
                title="Analysis",
                content="This is the analysis content",
                evidence_refs=[],
                warnings=[],
            ),
        ]

        markdown = projection.render("Test Report", sections)

        assert "# Test Report" in markdown
        assert "## Summary" in markdown
        assert "This is the summary content" in markdown
        assert "## Analysis" in markdown
        assert "This is the analysis content" in markdown

    def test_render_with_metadata(self):
        """Test rendering with metadata."""
        projection = MarkdownProjection()
        sections = [
            SectionOutput(
                key="test",
                title="Test Section",
                content="Test content",
                evidence_refs=[],
                warnings=[],
            )
        ]
        metadata = {"author": "Test Author", "date": "2026-05-03"}

        markdown = projection.render("Test Report", sections, metadata=metadata)

        assert "---" in markdown
        assert "author: Test Author" in markdown
        assert "date: 2026-05-03" in markdown

    def test_render_with_evidence_refs(self):
        """Test rendering with evidence references."""
        projection = MarkdownProjection()
        sections = [
            SectionOutput(
                key="test",
                title="Test Section",
                content="Content with evidence",
                evidence_refs=["doc1", "doc2"],
                warnings=[],
            )
        ]

        markdown = projection.render("Test Report", sections)

        assert "**参考文献:**" in markdown
        assert "- [doc1]" in markdown
        assert "- [doc2]" in markdown

    def test_render_with_warnings(self):
        """Test rendering with warnings."""
        projection = MarkdownProjection()
        sections = [
            SectionOutput(
                key="test",
                title="Test Section",
                content="Content",
                evidence_refs=[],
                warnings=["Warning 1", "Warning 2"],
            )
        ]

        markdown = projection.render("Test Report", sections)

        assert "⚠️ **警告:**" in markdown
        assert "- Warning 1" in markdown
        assert "- Warning 2" in markdown

    def test_save_to_file(self, tmp_path):
        """Test saving markdown to a file."""
        projection = MarkdownProjection()
        sections = [
            SectionOutput(
                key="test",
                title="Test Section",
                content="Test content",
                evidence_refs=[],
                warnings=[],
            )
        ]
        output_file = tmp_path / "report.md"

        projection.save(output_file, "Test Report", sections)

        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "# Test Report" in content

    def test_render_generated_time(self):
        """Test that generated time is included."""
        projection = MarkdownProjection()
        sections = [
            SectionOutput(
                key="test",
                title="Test Section",
                content="Content",
                evidence_refs=[],
                warnings=[],
            )
        ]

        markdown = projection.render("Test Report", sections)

        assert "生成时间:" in markdown
