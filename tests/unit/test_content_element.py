"""Phase 1 单元测试 - ContentElement 类型层级序列化/反序列化."""

import pytest
from pydantic import ValidationError

from core.contracts.content_element import (
    BulletListElement,
    CalloutElement,
    CalloutType,
    ChartElement,
    ChartElementType,
    ContentBlock,
    ContentElementType,
    DividerElement,
    HeadingElement,
    HorizontalAlignment,
    ImageElement,
    KeyValueElement,
    ListItem,
    OrderedListElement,
    ParagraphElement,
    QuoteElement,
    SpeakerNotesElement,
    TableElement,
    TextRun,
)
from core.contracts.document import (
    DesignTokens,
    Document,
    Section,
    TemplateSlot,
    brief_tokens,
    presentation_tokens,
    report_tokens,
)

# ============================================================================
# TextRun 测试
# ============================================================================


class TestTextRun:
    def test_plain_creation(self):
        """纯文本 TextRun 创建."""
        run = TextRun.plain("Hello World")
        assert run.text == "Hello World"
        assert run.bold is False
        assert run.italic is False

    def test_styled_creation(self):
        """带样式的 TextRun 创建."""
        run = TextRun(
            text="重要",
            bold=True,
            italic=True,
            color="#E53E3E",
            size=14,
            font="SimHei",
            hyperlink="https://example.com",
        )
        assert run.bold is True
        assert run.italic is True
        assert run.color == "#E53E3E"
        assert run.size == 14
        assert run.font == "SimHei"
        assert run.hyperlink == "https://example.com"

    def test_serialization(self):
        """TextRun 序列化为 JSON."""
        run = TextRun(text="测试", bold=True)
        data = run.model_dump()
        assert data["text"] == "测试"
        assert data["bold"] is True


# ============================================================================
# 段落/标题元素测试
# ============================================================================


class TestParagraphElement:
    def test_plain_paragraph(self):
        """纯文本段落."""
        p = ParagraphElement.plain("这是一段测试文本。")
        assert p.element_type == ContentElementType.PARAGRAPH
        assert len(p.runs) == 1
        assert p.runs[0].text == "这是一段测试文本。"

    def test_rich_paragraph(self):
        """富文本段落."""
        p = ParagraphElement(
            element_id="para_1",
            runs=[
                TextRun(text="正常文本 "),
                TextRun(text="加粗文本", bold=True),
                TextRun(text=" 斜体文本", italic=True),
            ],
            alignment=HorizontalAlignment.CENTER,
            line_spacing=2.0,
        )
        assert len(p.runs) == 3
        assert p.alignment == HorizontalAlignment.CENTER
        assert p.line_spacing == 2.0

    def test_serialization_roundtrip(self):
        """序列化后反序列化."""
        p = ParagraphElement.plain("Roundtrip test")
        json_str = p.model_dump_json()
        restored = ParagraphElement.model_validate_json(json_str)
        assert restored.runs[0].text == "Roundtrip test"


class TestHeadingElement:
    def test_heading_creation(self):
        """标题元素创建."""
        h = HeadingElement(text="第二章 市场分析", level=2)
        assert h.element_type == ContentElementType.HEADING
        assert h.text == "第二章 市场分析"
        assert h.level == 2

    def test_heading_level_validation(self):
        """标题级别验证."""
        with pytest.raises(ValidationError):
            HeadingElement(text="Invalid", level=7)

    def test_level_default(self):
        """默认标题级别."""
        h = HeadingElement(text="Default Level")
        assert h.level == 2


# ============================================================================
# 列表元素测试
# ============================================================================


class TestBulletListElement:
    def test_simple_list(self):
        """简单无序列表."""
        lst = BulletListElement(
            items=[
                ListItem.plain("项目一"),
                ListItem.plain("项目二"),
                ListItem.plain("项目三"),
            ]
        )
        assert lst.element_type == ContentElementType.BULLET_LIST
        assert len(lst.items) == 3
        assert lst.items[0].runs[0].text == "项目一"

    def test_nested_list(self):
        """嵌套列表."""
        lst = BulletListElement(
            items=[
                ListItem(
                    runs=[TextRun(text="父级")],
                    sub_items=[ListItem.plain("子级")],
                )
            ]
        )
        assert len(lst.items[0].sub_items) == 1
        assert lst.items[0].sub_items[0].runs[0].text == "子级"

    def test_rich_text_list(self):
        """富文本列表项."""
        lst = BulletListElement(
            items=[
                ListItem(
                    runs=[
                        TextRun(text="重要：", bold=True),
                        TextRun(text="这是加粗前缀"),
                    ]
                )
            ]
        )
        assert lst.items[0].runs[0].bold is True


class TestOrderedListElement:
    def test_ordered_list(self):
        """有序列表."""
        lst = OrderedListElement(
            items=[ListItem.plain("第一步"), ListItem.plain("第二步")],
            start=1,
        )
        assert lst.element_type == ContentElementType.ORDERED_LIST
        assert lst.start == 1
        assert len(lst.items) == 2


# ============================================================================
# 表格/图表/图片元素测试
# ============================================================================


class TestTableElement:
    def test_table_creation(self):
        """表格元素创建."""
        t = TableElement(
            element_id="table_1",
            headers=[[TextRun(text="名称")], [TextRun(text="数值")]],
            rows=[
                [[TextRun(text="营收")], [TextRun(text="100亿")]],
                [[TextRun(text="利润")], [TextRun(text="20亿")]],
            ],
            col_widths=[2.0, 1.0],
            title="财务数据",
            style="striped",
        )
        assert t.element_type == ContentElementType.TABLE
        assert len(t.headers) == 2
        assert len(t.rows) == 2
        assert t.col_widths == [2.0, 1.0]

    def test_table_defaults(self):
        """表格默认值."""
        t = TableElement()
        assert t.style == "bordered"
        assert t.headers == []
        assert t.rows == []


class TestChartElement:
    def test_chart_creation(self):
        """图表元素创建."""
        c = ChartElement(
            chart_id="chart_1",
            chart_type=ChartElementType.LINE,
            title="指数走势",
            data_labels=["Jan", "Feb", "Mar"],
            data_series=[[100.0, 105.0, 110.0]],
            source_note="数据来源：Wind",
        )
        assert c.element_type == ContentElementType.CHART
        assert c.chart_type == ChartElementType.LINE
        assert len(c.data_series) == 1

    def test_chart_image_bytes_excluded(self):
        """image_bytes 在序列化时排除."""
        c = ChartElement(
            chart_id="c1",
            title="Test",
            image_bytes=b"fake_png_data",
        )
        data = c.model_dump()
        assert "image_bytes" not in data


class TestImageElement:
    def test_image_creation(self):
        """图片元素创建."""
        img = ImageElement(
            image_id="img_1",
            image_data=b"binary_data",
            alt_text="K线图",
            caption="图1：日K线走势",
        )
        assert img.element_type == ContentElementType.IMAGE
        assert img.image_data == b"binary_data"

    def test_image_data_excluded(self):
        """image_data 在序列化时排除."""
        img = ImageElement(image_id="i1", image_data=b"data")
        data = img.model_dump()
        assert "image_data" not in data


# ============================================================================
# 装饰元素测试
# ============================================================================


class TestQuoteElement:
    def test_quote_creation(self):
        """引用块创建."""
        q = QuoteElement(
            text="市场总是对的。",
            attribution="—— Jesse Livermore",
        )
        assert q.element_type == ContentElementType.QUOTE
        assert "Jesse Livermore" in q.attribution


class TestCalloutElement:
    def test_callout_creation(self):
        """提示框创建."""
        c = CalloutElement(
            callout_type=CalloutType.KEY_FINDING,
            title="核心发现",
            text="AI 产业链中游估值已处于历史80%分位。",
        )
        assert c.element_type == ContentElementType.CALLOUT
        assert c.callout_type == CalloutType.KEY_FINDING

    def test_callout_type_default(self):
        """默认提示框类型."""
        c = CalloutElement(text="Info")
        assert c.callout_type == CalloutType.INFO


class TestKeyValueElement:
    def test_kv_creation(self):
        """键值对元素创建."""
        kv = KeyValueElement(
            pairs=[("上证指数", "3,250.50"), ("深证成指", "11,200.30")],
            columns=2,
        )
        assert kv.element_type == ContentElementType.KEY_VALUE
        assert len(kv.pairs) == 2
        assert kv.columns == 2


class TestDividerElement:
    def test_divider(self):
        """分隔线元素创建."""
        d = DividerElement()
        assert d.element_type == ContentElementType.DIVIDER


class TestSpeakerNotesElement:
    def test_speaker_notes(self):
        """演讲者备注."""
        sn = SpeakerNotesElement(text="这一页强调 AI 基础设施投资机会。")
        assert sn.element_type == ContentElementType.SPEAKER_NOTES


# ============================================================================
# ContentBlock 测试
# ============================================================================


class TestContentBlock:
    def test_block_with_mixed_elements(self):
        """混合元素内容块."""
        block = ContentBlock(
            block_id="block_1",
            elements=[
                HeadingElement(text="摘要", level=2),
                ParagraphElement.plain("这是摘要内容。"),
                BulletListElement(items=[ListItem.plain("要点一")]),
            ],
            layout_hint="full",
        )
        assert len(block.elements) == 3
        assert block.elements[0].element_type == ContentElementType.HEADING
        assert block.elements[1].element_type == ContentElementType.PARAGRAPH
        assert block.elements[2].element_type == ContentElementType.BULLET_LIST

    def test_page_break_before(self):
        """分页标志."""
        block = ContentBlock(block_id="pb", page_break_before=True)
        assert block.page_break_before is True


# ============================================================================
# DesignTokens 测试
# ============================================================================


class TestDesignTokens:
    def test_default_tokens(self):
        """默认设计令牌."""
        tokens = DesignTokens()
        assert tokens.primary_color == "#1A365D"
        assert tokens.body_font == "Microsoft YaHei"
        assert tokens.heading_sizes[1] == 28
        assert tokens.body_size == 11
        assert len(tokens.chart_palette) == 8

    def test_custom_tokens(self):
        """自定义设计令牌."""
        tokens = DesignTokens(
            primary_color="#FF0000",
            body_font="SimSun",
            heading_sizes={1: 36, 2: 24, 3: 18, 4: 14, 5: 12, 6: 10},
        )
        assert tokens.primary_color == "#FF0000"
        assert tokens.body_font == "SimSun"

    def test_preset_report_tokens(self):
        """研报预设令牌."""
        tokens = report_tokens()
        assert tokens.body_font == "SimSun"
        assert tokens.heading_font == "SimHei"

    def test_preset_presentation_tokens(self):
        """PPT 预设令牌."""
        tokens = presentation_tokens()
        assert tokens.heading_sizes[1] == 36
        assert tokens.body_size == 14

    def test_preset_brief_tokens(self):
        """简报预设令牌."""
        tokens = brief_tokens()
        assert tokens.body_size == 10


# ============================================================================
# Section / Document 测试
# ============================================================================


class TestSection:
    def test_section_creation(self):
        """章节创建."""
        section = Section(
            section_id="sec_1",
            title="市场概览",
            blocks=[
                ContentBlock(
                    block_id="b1",
                    elements=[ParagraphElement.plain("市场概述内容。")],
                )
            ],
        )
        assert section.section_id == "sec_1"
        assert len(section.blocks) == 1

    def test_section_slide_layout(self):
        """PPT 幻灯片布局提示."""
        section = Section(
            section_id="sec_2",
            title="图表分析",
            slide_layout="TITLE_AND_CONTENT",
        )
        assert section.slide_layout == "TITLE_AND_CONTENT"

    def test_section_speaker_notes(self):
        """演讲者备注."""
        section = Section(
            section_id="sec_3",
            title="风险提示",
            speaker_notes="强调尾部风险，控制语速。",
        )
        assert "尾部风险" in section.speaker_notes


class TestDocument:
    def test_document_creation(self):
        """文档创建."""
        doc = Document(
            document_id="doc_001",
            title="2026年Q2市场回顾",
            subtitle="AlphaFoundry 自动生成",
            sections=[
                Section(
                    section_id="s1",
                    title="摘要",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("摘要文本")],
                        )
                    ],
                )
            ],
            metadata={"author": "AlphaFoundry", "version": "2.0"},
        )
        assert doc.title == "2026年Q2市场回顾"
        assert doc.subtitle == "AlphaFoundry 自动生成"
        assert len(doc.sections) == 1
        assert doc.version == "1.0"

    def test_document_with_custom_tokens(self):
        """使用自定义设计令牌的文档."""
        doc = Document(
            title="测试文档",
            design_tokens=DesignTokens(primary_color="#000000"),
        )
        assert doc.design_tokens.primary_color == "#000000"

    def test_document_serialization(self):
        """文档序列化."""
        doc = Document(
            document_id="d1",
            title="Test",
            sections=[
                Section(
                    section_id="s1",
                    title="Test Section",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("Hello")],
                        )
                    ],
                )
            ],
        )
        data = doc.model_dump()
        assert data["title"] == "Test"
        assert len(data["sections"]) == 1


# ============================================================================
# TemplateSlot 测试
# ============================================================================


class TestTemplateSlot:
    def test_slot_creation(self):
        """模板槽位创建."""
        slot = TemplateSlot(
            slot_id="slot_market_summary",
            slot_type="text",
            placeholder_pattern="{{text_market_summary}}",
            constraints={"max_chars": 500},
        )
        assert slot.slot_id == "slot_market_summary"
        assert slot.slot_type == "text"
        assert slot.constraints["max_chars"] == 500
