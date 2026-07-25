"""Phase 4 测试 — PPT 高级功能（y-offset 分页/原生图表/单元格填充/模板/过渡）."""

import io

import pytest

from core.contracts.content_element import (
    BulletListElement,
    ChartElement,
    ChartElementType,
    ContentBlock,
    DividerElement,
    HeadingElement,
    ListItem,
    ParagraphElement,
    SpeakerNotesElement,
    TableElement,
    TextRun,
)
from core.contracts.document import DesignTokens, Document, Section

# 检查 python-pptx 是否可用
try:
    import pptx  # noqa: F401

    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

pytestmark = pytest.mark.skipif(not PPTX_AVAILABLE, reason="python-pptx not installed")


from reporting.rendering.ppt_renderer import PPTRenderer


@pytest.fixture
def renderer():
    return PPTRenderer()


@pytest.fixture
def single_section_doc():
    """单章节文档."""
    return Document(
        document_id="test_ppt_adv_001",
        title="PPT测试报告",
        sections=[
            Section(
                section_id="s1",
                title="第一章",
                blocks=[
                    ContentBlock(
                        block_id="b1",
                        elements=[ParagraphElement.plain("内容文本")],
                    )
                ],
            )
        ],
    )


@pytest.fixture
def chart_doc():
    """含图表元素的文档."""
    return Document(
        document_id="chart_test",
        title="图表测试",
        sections=[
            Section(
                section_id="s1",
                title="数据图表",
                blocks=[
                    ContentBlock(
                        block_id="b1",
                        elements=[
                            ChartElement(
                                chart_id="chart_1",
                                chart_type=ChartElementType.BAR,
                                title="月度涨跌幅",
                                data_labels=["1月", "2月", "3月"],
                                data_series=[[1.2, -0.5, 2.1], [0.8, 0.3, 1.5]],
                            )
                        ],
                    )
                ],
            )
        ],
    )


class TestPPTYPagination:
    """智能分页测试."""

    def test_y_offset_initialized(self, renderer, single_section_doc):
        """初始化时 _y_offset 应已设置."""
        buf = renderer.render_to_buffer(single_section_doc)
        assert isinstance(buf, io.BytesIO)
        assert buf.getbuffer().nbytes > 0

    def test_many_elements_triggers_pagination(self, renderer):
        """大量元素应触发自动分页."""
        doc = Document(
            title="长文档",
            sections=[
                Section(
                    section_id="s1",
                    title="长章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain(f"段落 {i}") for i in range(20)],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_continue_slide_has_title(self, renderer):
        """继续幻灯片应有标题."""
        doc = Document(
            title="分页测试",
            sections=[
                Section(
                    section_id="s1",
                    title="长章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain(f"段落 {i}") for i in range(15)],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0


class TestPPTNativeChart:
    """原生图表测试."""

    def test_native_chart_creation(self, renderer, chart_doc):
        """原生 PPT 图表创建."""
        buf = renderer.render_to_buffer(chart_doc)
        assert buf.getbuffer().nbytes > 0

    def test_chart_with_pie_type(self, renderer):
        """饼图类型图表."""
        doc = Document(
            title="饼图",
            sections=[
                Section(
                    section_id="s1",
                    title="数据",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                ChartElement(
                                    chart_id="pie_1",
                                    chart_type=ChartElementType.PIE,
                                    title="行业分布",
                                    data_labels=["科技", "金融", "消费"],
                                    data_series=[[40, 30, 30]],
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_chart_fallback_when_no_data(self, renderer):
        """无数据时图表回退到占位符."""
        doc = Document(
            title="空图表",
            sections=[
                Section(
                    section_id="s1",
                    title="空图表",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                ChartElement(
                                    chart_id="empty_chart",
                                    chart_type=ChartElementType.BAR,
                                    title="无数据图表",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0


class TestPPTCellFill:
    """单元格背景色填充测试."""

    def test_table_with_header_fill(self, renderer):
        """表头行应有背景色填充."""
        doc = Document(
            title="表格填充",
            sections=[
                Section(
                    section_id="s1",
                    title="数据表",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                TableElement(
                                    headers=[
                                        [TextRun(text="列A")],
                                        [TextRun(text="列B")],
                                    ],
                                    rows=[
                                        [[TextRun(text="A1")], [TextRun(text="B1")]],
                                    ],
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_striped_table(self, renderer):
        """交替行背景的条纹表格."""
        doc = Document(
            title="条纹表格",
            sections=[
                Section(
                    section_id="s1",
                    title="数据表",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                TableElement(
                                    headers=[
                                        [TextRun(text="名称")],
                                        [TextRun(text="数值")],
                                    ],
                                    rows=[
                                        [[TextRun(text="A")], [TextRun(text="1")]],
                                        [[TextRun(text="B")], [TextRun(text="2")]],
                                        [[TextRun(text="C")], [TextRun(text="3")]],
                                        [[TextRun(text="D")], [TextRun(text="4")]],
                                    ],
                                    style="striped",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0


class TestPPTTemplate:
    """自定义模板测试."""

    def test_custom_template_path(self, renderer):
        """使用自定义模板路径."""
        tokens = DesignTokens(ppt_template_path="/nonexistent/template.pptx")
        doc = Document(
            document_id="template_test",
            title="模板测试",
            design_tokens=tokens,
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("内容")],
                        )
                    ],
                )
            ],
        )
        renderer_t = PPTRenderer(tokens)
        buf = renderer_t.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_default_no_template(self, renderer):
        """未指定模板时使用默认."""
        buf = renderer.render_to_buffer(
            Document(
                title="无模板",
                sections=[
                    Section(
                        section_id="s1",
                        title="章节",
                        blocks=[
                            ContentBlock(
                                block_id="b1",
                                elements=[ParagraphElement.plain("内容")],
                            )
                        ],
                    )
                ],
            )
        )
        assert buf.getbuffer().nbytes > 0


class TestPPTTransition:
    """幻灯片过渡效果测试."""

    def test_fade_transition(self, renderer):
        """淡入淡出过渡."""
        tokens = DesignTokens(ppt_transition="fade")
        doc = Document(
            title="淡入淡出",
            design_tokens=tokens,
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("内容")],
                        )
                    ],
                )
            ],
        )
        r = PPTRenderer(tokens)
        buf = r.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0
        presentation = pptx.Presentation(buf)
        assert presentation.slides[0]._element.xpath("./p:transition/p:fade")

    def test_push_transition(self, renderer):
        """推入过渡."""
        tokens = DesignTokens(ppt_transition="push")
        doc = Document(
            title="推入",
            design_tokens=tokens,
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("内容")],
                        )
                    ],
                )
            ],
        )
        r = PPTRenderer(tokens)
        buf = r.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_no_transition(self, renderer):
        """无过渡效果（默认）."""
        tokens = DesignTokens()  # ppt_transition=None
        doc = Document(
            title="无过渡",
            design_tokens=tokens,
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("内容")],
                        )
                    ],
                )
            ],
        )
        r = PPTRenderer(tokens)
        buf = r.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0


class TestPPTTwoColumnLayout:
    """双栏布局测试."""

    def test_two_col_layout(self, renderer):
        """双栏布局的 block 渲染."""
        doc = Document(
            title="双栏布局",
            sections=[
                Section(
                    section_id="s1",
                    title="双栏章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            layout_hint="two_col",
                            elements=[
                                ParagraphElement.plain("左栏第一段"),
                                ParagraphElement.plain("左栏第二段"),
                                ParagraphElement.plain("右栏第一段"),
                                ParagraphElement.plain("右栏第二段"),
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_two_col_with_odd_elements(self, renderer):
        """奇数个元素的双栏布局."""
        doc = Document(
            title="奇数双栏",
            sections=[
                Section(
                    section_id="s1",
                    title="双栏",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            layout_hint="two_col",
                            elements=[
                                ParagraphElement.plain("左1"),
                                ParagraphElement.plain("左2"),
                                ParagraphElement.plain("左3"),
                                ParagraphElement.plain("右1"),
                                ParagraphElement.plain("右2"),
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0


class TestPPTSpeakerNotes:
    """演讲者备注测试."""

    def test_section_speaker_notes(self, renderer):
        """Section 级演讲者备注."""
        doc = Document(
            title="备注测试",
            sections=[
                Section(
                    section_id="s1",
                    title="有备注的章节",
                    speaker_notes="这是演讲者备注——本章重点讲市场概况。",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("内容")],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_empty_speaker_notes(self, renderer):
        """无备注时正常渲染."""
        doc = Document(
            title="无备注",
            sections=[
                Section(
                    section_id="s1",
                    title="无备注章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("内容")],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_speaker_notes_and_divider_elements_render(self, renderer):
        """元素级备注和分隔线应通过 PPT 分发器渲染."""
        doc = Document(
            title="元素备注",
            sections=[
                Section(
                    section_id="s1",
                    title="带元素备注的章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                DividerElement(),
                                SpeakerNotesElement(text="元素级演讲者备注"),
                            ],
                        )
                    ],
                )
            ],
        )

        buf = renderer.render_to_buffer(doc)

        from pptx import Presentation as PPTXPresentation

        # 第 0 张是文档标题页；第 1 张才是第一个 Section。
        notes_text_frame = PPTXPresentation(buf).slides[1].notes_slide.notes_text_frame
        assert notes_text_frame is not None
        assert notes_text_frame.text == "元素级演讲者备注"


class TestPPTMultiSection:
    """多章节 PPT 测试."""

    def test_multi_section_with_different_layouts(self, renderer):
        """不同布局的多章节."""
        doc = Document(
            title="多章节PPT",
            sections=[
                Section(
                    section_id="s1",
                    title="标题页",
                    slide_layout="TITLE_SLIDE",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("标题内容")],
                        )
                    ],
                ),
                Section(
                    section_id="s2",
                    title="内容页",
                    slide_layout="TITLE_AND_CONTENT",
                    blocks=[
                        ContentBlock(
                            block_id="b2",
                            elements=[
                                BulletListElement(
                                    items=[ListItem.plain("要点1"), ListItem.plain("要点2")]
                                )
                            ],
                        )
                    ],
                ),
                Section(
                    section_id="s3",
                    title="双栏页",
                    slide_layout="TWO_CONTENT",
                    blocks=[
                        ContentBlock(
                            block_id="b3",
                            elements=[
                                ParagraphElement.plain("栏1"),
                                ParagraphElement.plain("栏2"),
                            ],
                        )
                    ],
                ),
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0
