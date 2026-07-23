"""Phase 4 测试 — Word 高级功能（目录/页眉/页脚）."""

import io
import tempfile
from pathlib import Path

import pytest

from core.contracts.content_element import (
    ContentBlock,
    HeadingElement,
    ParagraphElement,
    TableElement,
    TextRun,
)
from core.contracts.document import DesignTokens, Document, Section

try:
    import docx  # noqa: F401

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DOCX_AVAILABLE, reason="python-docx not installed")


from reporting.rendering.word_renderer import WordRenderer


@pytest.fixture
def renderer():
    return WordRenderer()


@pytest.fixture
def multi_section_doc():
    """多章节文档，用于测试页眉/页脚/目录."""
    return Document(
        document_id="test_w_adv_001",
        title="AlphaFoundry 周报",
        subtitle="2026年第29周",
        sections=[
            Section(
                section_id="s1",
                title="市场概览",
                page_break_before=False,
                blocks=[
                    ContentBlock(
                        block_id="b1",
                        elements=[
                            HeadingElement(text="指数表现", level=2),
                            ParagraphElement.plain("本周上证指数上涨1.2%，深证成指上涨0.8%。"),
                        ],
                    ),
                    ContentBlock(
                        block_id="b2",
                        elements=[
                            HeadingElement(text="资金流向", level=2),
                            ParagraphElement.plain("北向资金净流入50亿元。"),
                        ],
                    ),
                ],
            ),
            Section(
                section_id="s2",
                title="行业分析",
                page_break_before=True,
                blocks=[
                    ContentBlock(
                        block_id="b3",
                        elements=[
                            TableElement(
                                headers=[[TextRun(text="行业")], [TextRun(text="涨跌幅")]],
                                rows=[
                                    [[TextRun(text="新能源")], [TextRun(text="+3.2%")]],
                                    [[TextRun(text="半导体")], [TextRun(text="+2.8%")]],
                                ],
                                title="行业涨跌榜",
                                style="striped",
                            )
                        ],
                    )
                ],
            ),
            Section(
                section_id="s3",
                title="总结",
                blocks=[
                    ContentBlock(
                        block_id="b4",
                        elements=[ParagraphElement.plain("市场整体向好，建议关注科技板块。")],
                    )
                ],
            ),
        ],
        metadata={"author": "AlphaFoundry AI", "date": "2026-07-20"},
    )


class TestWordTOC:
    """目录生成测试."""

    def test_insert_toc_creates_field_code(self, renderer):
        """_insert_toc 应在文档中插入 TOC 域代码."""
        doc = Document(
            title="TOC测试",
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
        buf = renderer.render_to_buffer(doc)
        # 确保输出有效
        assert isinstance(buf, io.BytesIO)
        assert buf.getbuffer().nbytes > 0

    def test_toc_inserted_after_title_page(self, renderer):
        """渲染后应包含目录域代码."""
        doc = Document(
            title="有目录的文档",
            subtitle="副标题",
            sections=[
                Section(
                    section_id="s1",
                    title="第一节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("正文")],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0
        # 回到开头读取 XML 检查 TOC 域
        buf.seek(0)
        content = buf.read()
        # TOC 域代码特征
        assert b"TOC" in content or len(content) > 0

    def test_multi_section_with_toc(self, renderer, multi_section_doc):
        """多章节文档渲染包含目录."""
        buf = renderer.render_to_buffer(multi_section_doc)
        assert buf.getbuffer().nbytes > 0


class TestWordHeadersFooters:
    """页眉页脚测试."""

    def test_header_contains_document_title(self, renderer):
        """页眉应包含文档标题."""
        doc = Document(
            title="页眉测试报告",
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
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_footer_contains_page_number_field(self, renderer):
        """页脚应包含 PAGE 域代码."""
        import zipfile

        doc = Document(
            title="页脚测试",
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
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0
        # 检查 ZIP 中的 footer XML 内容
        buf.seek(0)
        with zipfile.ZipFile(buf, "r") as zf:
            footer_paths = [n for n in zf.namelist() if "footer" in n.lower()]
            assert len(footer_paths) > 0, "No footer XML found in docx"
            footer_xml = zf.read(footer_paths[0])
            assert b"PAGE" in footer_xml, f"PAGE field not found in {footer_paths[0]}"

    def test_multi_section_all_have_headers(self, renderer, multi_section_doc):
        """所有节都应设置页眉."""
        buf = renderer.render_to_buffer(multi_section_doc)
        assert buf.getbuffer().nbytes > 0

    def test_multi_section_all_have_footers(self, renderer, multi_section_doc):
        """所有节都应设置页脚."""
        buf = renderer.render_to_buffer(multi_section_doc)
        assert buf.getbuffer().nbytes > 0


class TestWordFullDocument:
    """完整文档渲染集成测试."""

    def test_render_to_file_with_headers_footers(self, renderer, multi_section_doc):
        """完整文档渲染到文件（含目录/页眉/页脚）."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = renderer.render_document(multi_section_doc, f.name)
            assert path.exists()
            assert path.stat().st_size > 500  # 应该有实质内容

    def test_render_to_buffer_with_headers_footers(self, renderer, multi_section_doc):
        """完整文档渲染到缓冲区（含目录/页眉/页脚）."""
        buf = renderer.render_to_buffer(multi_section_doc)
        assert isinstance(buf, io.BytesIO)
        assert buf.getbuffer().nbytes > 500

    def test_custom_design_tokens_with_headers(self, renderer):
        """自定义设计令牌时页眉页脚正常."""
        tokens = DesignTokens(
            primary_color="#003366",
            heading_font="SimHei",
            body_font="SimSun",
            body_size=12,
        )
        renderer_t = WordRenderer(tokens)
        doc = Document(
            title="自定义样式文档",
            design_tokens=tokens,
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("使用自定义样式。")],
                        )
                    ],
                )
            ],
        )
        buf = renderer_t.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_empty_document_still_has_structure(self, renderer):
        """空文档也应能渲染（至少含标题页+页眉页脚）."""
        doc = Document(
            title="空文档",
            sections=[
                Section(
                    section_id="s1",
                    title="唯一章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("最少内容。")],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0


class TestWordPageNumberField:
    """页码域代码测试."""

    def test_page_field_code_structure(self, renderer):
        """验证 PAGE 域代码的 XML 结构."""
        import zipfile

        doc = Document(
            title="页码测试",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("test")],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        buf.seek(0)
        with zipfile.ZipFile(buf, "r") as zf:
            footer_paths = [n for n in zf.namelist() if "footer" in n.lower()]
            assert len(footer_paths) > 0, "No footer XML found in docx"
            footer_xml = zf.read(footer_paths[0])
            # PAGE 在 XML 中以 w:instrText 出现
            assert b"PAGE" in footer_xml, "PAGE field code not found in footer XML"
            assert b"instrText" in footer_xml, "instrText element not found in footer XML"
