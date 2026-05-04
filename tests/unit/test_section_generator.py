"""Tests for SectionGenerator."""
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from core.contracts import SectionOutput, SectionSpec
from reporting.composer.section_generator import SectionGenerator


class TestSectionGenerator:
    """Test suite for SectionGenerator."""

    def test_load_template(self, tmp_path):
        """Test loading a template from YAML."""
        template_content = """
name: test_template
title: Test Template
sections:
  - key: summary
    title: Summary
    target_words: 100
    required_facets: [overview]
    evidence_policy: allow_synthesis
  - key: analysis
    title: Analysis
    target_words: 200
    required_facets: []
    evidence_policy: strict
"""
        template_file = tmp_path / "test_template.yaml"
        template_file.write_text(template_content)

        generator = SectionGenerator(Mock(), templates_dir=tmp_path)
        sections = generator.load_template("test_template")

        assert len(sections) == 2
        assert sections[0].key == "summary"
        assert sections[0].title == "Summary"
        assert sections[1].key == "analysis"

    def test_generate_section(self, mock_model_gateway):
        """Test generating a single section."""
        generator = SectionGenerator(mock_model_gateway)
        spec = SectionSpec(
            key="test",
            title="Test Section",
            target_words=100,
            required_facets=["overview"],
            evidence_policy="allow_synthesis",
        )

        result = generator.generate_section(spec, context={"asset": "600000.SH"})

        assert isinstance(result, SectionOutput)
        assert result.key == "test"
        assert result.content == "Generated content"
        mock_model_gateway.chat.assert_called_once()

    def test_generate_section_with_evidence(self, mock_model_gateway):
        """Test generating a section with evidence."""
        generator = SectionGenerator(mock_model_gateway)
        spec = SectionSpec(
            key="test",
            title="Test Section",
            target_words=100,
            required_facets=[],
            evidence_policy="strict",
        )

        evidence = [
            {"source": "doc1", "content": "Evidence content 1"},
            {"source": "doc2", "content": "Evidence content 2"},
        ]

        result = generator.generate_section(spec, context={}, evidence=evidence)

        assert isinstance(result, SectionOutput)
        mock_model_gateway.chat.assert_called_once()

    def test_generate_report(self, mock_model_gateway, tmp_path):
        """Test generating a full report."""
        template_content = """
name: test_report
title: Test Report
sections:
  - key: section1
    title: Section 1
    target_words: 100
    required_facets: []
    evidence_policy: allow_synthesis
  - key: section2
    title: Section 2
    target_words: 100
    required_facets: []
    evidence_policy: allow_synthesis
"""
        template_file = tmp_path / "test_report.yaml"
        template_file.write_text(template_content)

        generator = SectionGenerator(mock_model_gateway, templates_dir=tmp_path)
        sections = generator.generate_report("test_report", context={"asset": "600000.SH"})

        assert len(sections) == 2
        assert sections[0].key == "section1"
        assert sections[1].key == "section2"

    def test_template_caching(self, mock_model_gateway, tmp_path):
        """Test that templates are cached after first load."""
        template_content = """
name: test
title: Test
sections:
  - key: test
    title: Test
    target_words: 100
    required_facets: []
    evidence_policy: allow_synthesis
"""
        template_file = tmp_path / "test.yaml"
        template_file.write_text(template_content)

        generator = SectionGenerator(mock_model_gateway, templates_dir=tmp_path)

        # Load twice
        sections1 = generator.load_template("test")
        sections2 = generator.load_template("test")

        # Should be same object from cache
        assert sections1 is sections2
