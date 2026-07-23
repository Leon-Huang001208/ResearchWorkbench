"""Phase 1 单元测试 - 向后兼容适配器."""

from core.contracts.content_element import (
    ContentElementType,
)
from core.contracts.document import DesignTokens
from core.contracts.reporting import (
    FactCard,
    SectionOutput,
)
from reporting.content.adapter import (
    ContentAdapter,
    section_output_to_section,
    sections_to_document,
)

# ============================================================================
# SectionOutput → Section 转换测试
# ============================================================================


class TestSectionOutputToSection:
    def test_basic_conversion(self):
        """基本转换：SectionOutput(content) → Section."""
        so = SectionOutput(
            key="market_summary",
            title="市场概览",
            content="本周上证指数上涨2.3%，深证成指下跌0.5%。",
        )

        section = ContentAdapter.section_output_to_section(so)

        assert section.section_id == "market_summary"
        assert section.title == "市场概览"
        assert len(section.blocks) == 1
        assert len(section.blocks[0].elements) >= 1

        # 第一个元素应该是 HeadingElement
        heading = section.blocks[0].elements[0]
        assert heading.element_type == ContentElementType.HEADING
        assert heading.text == "市场概览"

    def test_content_parsed_as_paragraph(self):
        """content 字符串被解析为段落."""
        so = SectionOutput(
            key="test",
            title="测试",
            content="这是一段普通的文本内容。",
        )

        section = ContentAdapter.section_output_to_section(so)

        # 应该有 heading + paragraph
        elements = section.blocks[0].elements
        assert len(elements) >= 2
        assert elements[1].element_type == ContentElementType.PARAGRAPH

    def test_content_with_markdown_headings(self):
        """content 中的 Markdown 标题被解析为 HeadingElement."""
        content = """## 子标题一
这是第一段内容。

## 子标题二
这是第二段内容。"""

        so = SectionOutput(key="structured", title="结构化内容", content=content)

        section = ContentAdapter.section_output_to_section(so)
        elements = section.blocks[0].elements

        # 应该有 1 个章节标题 + 2 个子标题 + 2 个段落
        headings = [e for e in elements if e.element_type == ContentElementType.HEADING]
        assert len(headings) >= 2  # 至少包含原 title heading + 1 个子标题

    def test_content_with_bullet_list(self):
        """content 中的 Markdown 列表被解析为 BulletListElement."""
        content = """要点如下：
- 第一个要点
- 第二个要点
- 第三个要点"""

        so = SectionOutput(key="bullets", title="要点", content=content)

        section = ContentAdapter.section_output_to_section(so)
        elements = section.blocks[0].elements

        # 应该包含 BulletListElement
        lists = [e for e in elements if e.element_type == ContentElementType.BULLET_LIST]
        assert len(lists) >= 1
        assert len(lists[0].items) >= 3

    def test_with_fact_card(self):
        """FactCard 中的关键变化被转换为列表."""
        fc = FactCard(
            key_changes=["营收增长20%", "净利润翻倍"],
            drivers=["AI需求爆发", "产能扩张"],
            risks=["原材料涨价风险"],
            watch_points=["Q3订单增速"],
        )

        so = SectionOutput(
            key="with_facts",
            title="带事实卡",
            content="分析内容。",
            fact_card=fc,
        )

        section = ContentAdapter.section_output_to_section(so)
        elements = section.blocks[0].elements

        # 应该包含从 fact_card 生成的 CalloutElement（风险）和列表
        callouts = [e for e in elements if e.element_type == ContentElementType.CALLOUT]
        assert len(callouts) >= 1  # 至少风险提示

        lists = [e for e in elements if e.element_type == ContentElementType.BULLET_LIST]
        assert len(lists) >= 1  # 至少关键变化

    def test_with_warnings(self):
        """warnings 被转换为 CalloutElement."""
        so = SectionOutput(
            key="warned",
            title="带警告",
            content="内容。",
            warnings=["字数不足", "缺少引用"],
        )

        section = ContentAdapter.section_output_to_section(so)
        elements = section.blocks[0].elements

        callouts = [e for e in elements if e.element_type == ContentElementType.CALLOUT]
        assert len(callouts) >= 1
        warning_callout = callouts[0]
        assert "字数不足" in warning_callout.text

    def test_content_elements_field_priority(self):
        """content_elements 字段优先于 content 字符串."""
        from core.contracts.content_element import ParagraphElement as PE
        from core.contracts.content_element import TextRun

        custom_elements = [
            PE(
                element_id="custom",
                runs=[TextRun(text="这是来自 content_elements 的文本")],
            )
        ]

        so = SectionOutput(
            key="priority_test",
            title="优先测试",
            content="这段文本应该被忽略。",
            content_elements=custom_elements,
        )

        section = ContentAdapter.section_output_to_section(so)
        elements = section.blocks[0].elements

        # 第一个非 heading 元素应该来自 content_elements
        paragraphs = [e for e in elements if e.element_type == ContentElementType.PARAGRAPH]
        assert any("content_elements" in p.runs[0].text for p in paragraphs if p.runs)

    def test_empty_content(self):
        """空 content 的处理."""
        so = SectionOutput(key="empty", title="空章节", content="")

        section = ContentAdapter.section_output_to_section(so)

        # 至少应有标题
        assert len(section.blocks[0].elements) >= 1


# ============================================================================
# Sections → Document 转换测试
# ============================================================================


class TestSectionsToDocument:
    def test_basic_document_conversion(self):
        """基本转换：SectionOutput 列表 → Document."""
        sections = [
            SectionOutput(
                key="s1",
                title="第一章",
                content="第一章内容。",
            ),
            SectionOutput(
                key="s2",
                title="第二章",
                content="第二章内容。",
            ),
        ]

        doc = ContentAdapter.sections_to_document(
            title="测试报告",
            sections=sections,
            metadata={"author": "Test"},
        )

        assert doc.title == "测试报告"
        assert len(doc.sections) == 2
        assert doc.sections[0].section_id == "s1"
        assert doc.sections[1].section_id == "s2"

    def test_document_with_custom_tokens(self):
        """使用自定义设计令牌."""
        sections = [SectionOutput(key="s1", title="章节", content="内容。")]

        tokens = DesignTokens(primary_color="#000000")
        doc = ContentAdapter.sections_to_document(
            title="自定义令牌报告",
            sections=sections,
            design_tokens=tokens,
        )

        assert doc.design_tokens.primary_color == "#000000"

    def test_document_metadata(self):
        """文档元数据传递."""
        sections = [SectionOutput(key="s1", title="章节", content="内容。")]

        doc = ContentAdapter.sections_to_document(
            title="元数据测试",
            sections=sections,
            metadata={"source": "test", "tags": ["demo"]},
        )

        assert doc.metadata["source"] == "test"
        assert doc.metadata["tags"] == ["demo"]


# ============================================================================
# wrap_string_as_elements 测试
# ============================================================================


class TestWrapStringAsElements:
    def test_plain_text(self):
        """纯文本包装."""
        elements = ContentAdapter.wrap_string_as_elements("Hello World")
        assert len(elements) == 1
        assert elements[0].element_type == ContentElementType.PARAGRAPH
        assert elements[0].runs[0].text == "Hello World"

    def test_with_title(self):
        """带标题的文本包装."""
        elements = ContentAdapter.wrap_string_as_elements(
            content="正文内容。",
            title="章节标题",
            section_key="test_key",
        )
        # 第一个元素应为标题
        assert elements[0].element_type == ContentElementType.HEADING
        assert elements[0].text == "章节标题"

    def test_mixed_content(self):
        """混合格式文本."""
        content = """## 子标题
这是一段普通文本。

- 项目一
- 项目二

这是另一段文本。"""

        elements = ContentAdapter.wrap_string_as_elements(content)
        assert len(elements) >= 4  # heading + paragraph + list + paragraph

        types = [e.element_type for e in elements]
        assert ContentElementType.HEADING in types
        assert ContentElementType.PARAGRAPH in types
        assert ContentElementType.BULLET_LIST in types


# ============================================================================
# 便捷函数测试
# ============================================================================


class TestConvenienceFunctions:
    def test_section_output_to_section(self):
        """便捷函数与类方法结果一致."""
        so = SectionOutput(key="k", title="t", content="c")

        via_class = ContentAdapter.section_output_to_section(so)
        via_func = section_output_to_section(so)

        assert via_class.section_id == via_func.section_id
        assert via_class.title == via_func.title

    def test_sections_to_document(self):
        """便捷函数与类方法结果一致."""
        sections = [SectionOutput(key="s1", title="章节", content="内容")]

        via_class = ContentAdapter.sections_to_document("报告", sections)
        via_func = sections_to_document("报告", sections)

        assert via_class.title == via_func.title
        assert len(via_class.sections) == len(via_func.sections)


# ============================================================================
# 向后兼容性测试
# ============================================================================


class TestBackwardCompatibility:
    def test_sectionoutput_without_content_elements(self):
        """content_elements 为空时正常 fallback 到 content."""
        so = SectionOutput(
            key="legacy",
            title="旧格式",
            content="这是旧格式的纯文本内容。",
            # content_elements 不传，默认为 []
        )
        section = ContentAdapter.section_output_to_section(so)
        assert len(section.blocks) == 1
        # 应该有 heading + paragraph
        assert len(section.blocks[0].elements) >= 2

    def test_sectionoutput_empty_fields(self):
        """所有可选字段为空时正常处理."""
        so = SectionOutput(key="minimal", title="最小", content="")
        section = ContentAdapter.section_output_to_section(so)
        assert section.section_id == "minimal"

    def test_document_preserves_all_legacy_info(self):
        """转换不丢失任何原有信息."""
        so = SectionOutput(
            key="full",
            title="完整章节",
            content="完整内容。",
            evidence_refs=["[1] 来源A", "[2] 来源B"],
            scenario_refs=["scenario_001"],
            warnings=["测试警告"],
        )

        section = ContentAdapter.section_output_to_section(so)
        # metadata 应包含引用信息
        assert "evidence_refs" in section.metadata
        assert len(section.metadata["evidence_refs"]) == 2
