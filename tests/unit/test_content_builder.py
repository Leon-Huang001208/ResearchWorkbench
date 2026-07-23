"""
ContentBuilder 测试套件.

测试四种输入方式：from_template, from_sections, from_compiled, from_dict.
"""

from unittest.mock import MagicMock

import pytest

from core.contracts.content_element import (
    BulletListElement,
    HeadingElement,
    ParagraphElement,
)
from core.contracts.document import DesignTokens, Document
from core.contracts.reporting import (
    SectionOutput,
    SectionSpec,
    TemplateConfig,
)
from reporting.builder.content_builder import ContentBuilder

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def builder():
    return ContentBuilder()


@pytest.fixture
def sample_template():
    return TemplateConfig(
        name="test_report",
        description="A test report template",
        version="1.0",
        sections=[
            SectionSpec(
                key="summary",
                title="Summary",
                target_words=200,
                evidence_policy="strict",
            ),
            SectionSpec(
                key="analysis",
                title="Analysis",
                target_words=300,
                evidence_policy="allow_synthesis",
            ),
        ],
    )


@pytest.fixture
def sample_context():
    return {
        "summary": "This is the summary content.",
        "analysis": "This is the analysis content with more detail.",
    }


@pytest.fixture
def sample_section_outputs():
    return [
        SectionOutput(
            key="sec1",
            title="Section One",
            content="Content for section one.",
        ),
        SectionOutput(
            key="sec2",
            title="Section Two",
            content="## Sub Heading\n\n- Item A\n- Item B\n\nMore text here.",
        ),
    ]


# ============================================================================
# from_template 测试
# ============================================================================


class TestFromTemplate:
    def test_basic_template_to_document(self, builder, sample_template, sample_context):
        doc = builder.from_template(sample_template, context=sample_context)
        assert isinstance(doc, Document)
        assert doc.title == "Test Report"
        assert doc.document_id == "test_report"
        assert len(doc.sections) == 2

    def test_template_section_structure(self, builder, sample_template, sample_context):
        doc = builder.from_template(sample_template, context=sample_context)
        s1 = doc.sections[0]
        assert s1.section_id == "summary"
        assert s1.title == "Summary"
        assert len(s1.blocks) == 1
        assert len(s1.blocks[0].elements) >= 1

    def test_template_context_injection(self, builder, sample_template, sample_context):
        doc = builder.from_template(sample_template, context=sample_context)
        # 第一个 section 的内容应该从 context 注入
        paragraph_el = doc.sections[0].blocks[0].elements[-1]
        assert isinstance(paragraph_el, ParagraphElement)
        # 内容来自 context
        text = "".join(r.text for r in paragraph_el.runs)
        assert "summary content" in text

    def test_template_missing_context_keys(self, builder, sample_template):
        doc = builder.from_template(sample_template, context={})
        assert len(doc.sections) == 2
        # 没有 context 时内容为空字符串
        paragraph_el = doc.sections[0].blocks[0].elements[-1]
        text = "".join(r.text for r in paragraph_el.runs)
        assert text == ""

    def test_template_with_design_tokens(self, builder, sample_template, sample_context):
        tokens = DesignTokens(primary_color="#FF0000")
        doc = builder.from_template(sample_template, context=sample_context, design_tokens=tokens)
        assert doc.design_tokens.primary_color == "#FF0000"

    def test_template_metadata(self, builder, sample_template, sample_context):
        doc = builder.from_template(sample_template, context=sample_context)
        assert doc.metadata["source"] == "TemplateConfig"
        assert doc.metadata["template_name"] == "test_report"
        assert doc.metadata["template_version"] == "1.0"
        assert "summary" in doc.metadata["context_keys"]

    def test_template_extracts_tokens_from_metadata(self, builder):
        tpl = TemplateConfig(
            name="styled_report",
            description="",
            version="2.0",
            sections=[
                SectionSpec(key="s1", title="S1", target_words=100),
            ],
            metadata={
                "design_tokens": {
                    "primary_color": "#00FF00",
                    "heading_font": "Arial",
                }
            },
        )
        doc = builder.from_template(tpl)
        assert doc.design_tokens.primary_color == "#00FF00"
        assert doc.design_tokens.heading_font == "Arial"

    def test_template_empty_context(self, builder, sample_template):
        doc = builder.from_template(sample_template)
        assert len(doc.sections) == 2


# ============================================================================
# from_sections 测试
# ============================================================================


class TestFromSections:
    def test_basic_sections_to_document(self, builder, sample_section_outputs):
        doc = builder.from_sections(
            title="Test Document",
            sections=sample_section_outputs,
        )
        assert isinstance(doc, Document)
        assert doc.title == "Test Document"
        assert len(doc.sections) == 2

    def test_sections_preserve_title(self, builder, sample_section_outputs):
        doc = builder.from_sections(
            title="My Doc",
            sections=sample_section_outputs,
        )
        assert doc.sections[0].title == "Section One"
        assert doc.sections[1].title == "Section Two"

    def test_sections_with_metadata(self, builder, sample_section_outputs):
        doc = builder.from_sections(
            title="Doc with meta",
            sections=sample_section_outputs,
            metadata={"author": "test", "date": "2026-07-20"},
        )
        assert doc.metadata["author"] == "test"
        assert doc.metadata["date"] == "2026-07-20"

    def test_sections_content_parsing(self, builder, sample_section_outputs):
        doc = builder.from_sections(
            title="Parsed",
            sections=sample_section_outputs,
        )
        # 第二个 section 的 content 包含 markdown 标记
        sec2 = doc.sections[1]
        elements = sec2.blocks[0].elements
        # 应该有标题元素和内容元素
        assert any(isinstance(e, HeadingElement) for e in elements)

    def test_sections_content_elements_priority(self, builder):

        so = SectionOutput(
            key="test_pri",
            title="Priority Test",
            content="Old content string",
            content_elements=[
                ParagraphElement.plain("New element content"),
            ],
        )
        doc = builder.from_sections(title="Test", sections=[so])
        elements = doc.sections[0].blocks[0].elements
        assert len(elements) == 1
        assert elements[0].runs[0].text == "New element content"

    def test_sections_empty_list(self, builder):
        doc = builder.from_sections(title="Empty", sections=[])
        assert len(doc.sections) == 0

    def test_sections_with_design_tokens(self, builder, sample_section_outputs):
        tokens = DesignTokens(body_size=20)
        doc = builder.from_sections(
            title="Styled",
            sections=sample_section_outputs,
            design_tokens=tokens,
        )
        assert doc.design_tokens.body_size == 20


# ============================================================================
# from_dict 测试
# ============================================================================


class TestFromDict:
    def test_minimal_dict(self, builder):
        spec = {
            "title": "Minimal Report",
            "sections": [
                {
                    "section_id": "sec1",
                    "title": "Section 1",
                    "blocks": [
                        {
                            "block_id": "b1",
                            "elements": [
                                {"type": "paragraph", "text": "Hello World"},
                            ],
                        }
                    ],
                }
            ],
        }
        doc = builder.from_dict(spec)
        assert isinstance(doc, Document)
        assert doc.title == "Minimal Report"
        assert len(doc.sections) == 1
        assert doc.sections[0].title == "Section 1"

    def test_dict_with_heading(self, builder):
        spec = {
            "title": "Doc",
            "sections": [
                {
                    "section_id": "s1",
                    "title": "S1",
                    "blocks": [
                        {
                            "block_id": "b1",
                            "elements": [
                                {"type": "heading", "text": "My Heading", "level": 1},
                                {"type": "paragraph", "text": "Content after heading."},
                            ],
                        }
                    ],
                }
            ],
        }
        doc = builder.from_dict(spec)
        elements = doc.sections[0].blocks[0].elements
        assert isinstance(elements[0], HeadingElement)
        assert elements[0].text == "My Heading"
        assert elements[0].level == 1

    def test_dict_with_bullet_list(self, builder):
        spec = {
            "title": "List Doc",
            "sections": [
                {
                    "section_id": "s1",
                    "title": "Bullets",
                    "blocks": [
                        {
                            "block_id": "b1",
                            "elements": [
                                {
                                    "type": "bullet_list",
                                    "items": ["Item 1", "Item 2", "Item 3"],
                                },
                            ],
                        }
                    ],
                }
            ],
        }
        doc = builder.from_dict(spec)
        elements = doc.sections[0].blocks[0].elements
        assert isinstance(elements[0], BulletListElement)
        assert len(elements[0].items) == 3

    def test_dict_with_subtitle(self, builder):
        spec = {
            "title": "Report",
            "subtitle": "A deep dive into markets",
            "sections": [],
        }
        doc = builder.from_dict(spec)
        assert doc.subtitle == "A deep dive into markets"

    def test_dict_with_metadata(self, builder):
        spec = {
            "title": "Meta Report",
            "metadata": {"author": "Claude", "version": 1},
            "sections": [],
        }
        doc = builder.from_dict(spec)
        assert doc.metadata["author"] == "Claude"

    def test_dict_unknown_element_type(self, builder):
        spec = {
            "title": "Strange Doc",
            "sections": [
                {
                    "section_id": "s1",
                    "title": "S1",
                    "blocks": [
                        {
                            "block_id": "b1",
                            "elements": [
                                {"type": "nonexistent", "text": "???"},
                                {"type": "paragraph", "text": "Valid content."},
                            ],
                        }
                    ],
                }
            ],
        }
        doc = builder.from_dict(spec)
        # 未知类型应该被跳过，只保留 paragraph
        elements = doc.sections[0].blocks[0].elements
        assert len(elements) == 1
        assert isinstance(elements[0], ParagraphElement)

    def test_dict_multiple_sections(self, builder):
        spec = {
            "title": "Multi Section",
            "sections": [
                {"section_id": "s1", "title": "First", "blocks": []},
                {"section_id": "s2", "title": "Second", "blocks": []},
                {"section_id": "s3", "title": "Third", "blocks": []},
            ],
        }
        doc = builder.from_dict(spec)
        assert len(doc.sections) == 3

    def test_dict_layout_hint(self, builder):
        spec = {
            "title": "Layout Test",
            "sections": [
                {
                    "section_id": "s1",
                    "title": "Layout",
                    "blocks": [
                        {
                            "block_id": "b1",
                            "layout": "two_col",
                            "elements": [
                                {"type": "paragraph", "text": "Two column content."},
                            ],
                        }
                    ],
                }
            ],
        }
        doc = builder.from_dict(spec)
        assert doc.sections[0].blocks[0].layout_hint == "two_col"

    def test_dict_with_design_tokens(self, builder):
        tokens = DesignTokens(primary_color="#ABCDEF")
        spec = {"title": "Styled", "sections": []}
        doc = builder.from_dict(spec, design_tokens=tokens)
        assert doc.design_tokens.primary_color == "#ABCDEF"


# ============================================================================
# from_compiled 测试
# ============================================================================


class TestFromCompiled:
    def test_delegates_to_adapter(self, builder):
        mock_compiled = MagicMock()
        mock_compiled.report_id = "rpt_001"
        mock_compiled.compiler_version = "2.0"
        mock_compiled.facts = []

        mock_section = MagicMock()
        mock_section.section_id = "sec1"
        mock_section.title = "Test Section"
        mock_section.content = "Hello compiled world."
        mock_section.citations = []
        mock_compiled.sections = [mock_section]

        outline = MagicMock()
        outline.report_title = "Compiled Report Title"
        outline.thesis = "A bold thesis"
        mock_compiled.outline = outline

        doc = builder.from_compiled(mock_compiled)
        assert isinstance(doc, Document)
        assert doc.title == "Compiled Report Title"
        assert doc.subtitle == "A bold thesis"
        assert doc.metadata["source"] == "CompiledReport"

    def test_compiled_with_citations(self, builder):
        mock_compiled = MagicMock()
        mock_compiled.report_id = "rpt_002"
        mock_compiled.compiler_version = "2.0"
        mock_compiled.facts = []

        citation = MagicMock()
        citation.display_text = "Source: Bloomberg, 2026-07-20"
        mock_section = MagicMock()
        mock_section.section_id = "sec2"
        mock_section.title = "Section with citations"
        mock_section.content = "Content with evidence."
        mock_section.citations = [citation]
        mock_compiled.sections = [mock_section]

        outline = MagicMock()
        outline.report_title = "Report"
        outline.thesis = None
        mock_compiled.outline = outline

        doc = builder.from_compiled(mock_compiled)
        elements = doc.sections[0].blocks[0].elements
        assert any(isinstance(e, BulletListElement) for e in elements)


# ============================================================================
# _extract_tokens 测试
# ============================================================================


class TestExtractTokens:
    def test_extracts_tokens_from_metadata(self):
        tpl = TemplateConfig(
            name="t",
            description="",
            sections=[SectionSpec(key="s1", title="S1", target_words=100)],
            metadata={
                "design_tokens": {
                    "primary_color": "#123456",
                    "body_size": 14,
                }
            },
        )
        tokens = ContentBuilder._extract_tokens(tpl)
        assert tokens.primary_color == "#123456"
        assert tokens.body_size == 14

    def test_default_tokens_when_empty_metadata(self):
        tpl = TemplateConfig(
            name="t",
            description="",
            sections=[SectionSpec(key="s1", title="S1", target_words=100)],
        )
        tokens = ContentBuilder._extract_tokens(tpl)
        assert isinstance(tokens, DesignTokens)
        # 默认值
        assert tokens.primary_color == "#1A365D"

    def test_fallback_on_invalid_tokens(self):
        tpl = TemplateConfig(
            name="t",
            description="",
            sections=[SectionSpec(key="s1", title="S1", target_words=100)],
            metadata={"design_tokens": {"invalid_field_xyz": 999}},
        )
        tokens = ContentBuilder._extract_tokens(tpl)
        assert isinstance(tokens, DesignTokens)
