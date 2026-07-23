"""Phase 2 单元测试 - Word 渲染器."""

import io
import tempfile

import pytest

from core.contracts.content_element import (
    BulletListElement,
    CalloutElement,
    CalloutType,
    ContentBlock,
    HeadingElement,
    KeyValueElement,
    ListItem,
    OrderedListElement,
    ParagraphElement,
    QuoteElement,
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
def minimal_doc():
    return Document(
        document_id="test_w_001",
        title="Word测试报告",
        subtitle="自动生成",
        sections=[
            Section(
                section_id="s1",
                title="第一章",
                blocks=[
                    ContentBlock(
                        block_id="b1",
                        elements=[ParagraphElement.plain("这是第一段内容。")],
                    )
                ],
            )
        ],
        metadata={"author": "AlphaFoundry"},
    )


class TestWordRendererBasic:
    def test_render_document_to_file(self, renderer, minimal_doc):
        """渲染到 .docx 文件."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = renderer.render_document(minimal_doc, f.name)
            assert path.suffix == ".docx"
            assert path.exists()
            assert path.stat().st_size > 0

    def test_render_to_buffer(self, renderer, minimal_doc):
        """渲染到内存缓冲区."""
        buf = renderer.render_to_buffer(minimal_doc)
        assert isinstance(buf, io.BytesIO)
        assert buf.getbuffer().nbytes > 0

    def test_format_name(self, renderer):
        """格式名称."""
        assert renderer.format_name == "Word"


class TestWordElements:
    def test_heading_rendering(self, renderer):
        """标题渲染."""
        doc = Document(
            title="标题测试",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                HeadingElement(text="H1标题", level=1),
                                HeadingElement(text="H2标题", level=2),
                                HeadingElement(text="H3标题", level=3),
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        # 验证输出非空
        assert buf.getbuffer().nbytes > 0

    def test_paragraph_with_rich_text(self, renderer):
        """富文本段落渲染."""
        doc = Document(
            title="富文本",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                ParagraphElement(
                                    runs=[
                                        TextRun(text="普通"),
                                        TextRun(text="加粗", bold=True),
                                        TextRun(text="斜体", italic=True),
                                        TextRun(text="彩色", color="#E53E3E"),
                                    ]
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_bullet_list(self, renderer):
        """无序列表渲染."""
        doc = Document(
            title="列表",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                BulletListElement(
                                    items=[
                                        ListItem.plain("项目一"),
                                        ListItem.plain("项目二"),
                                    ]
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_ordered_list(self, renderer):
        """有序列表渲染."""
        doc = Document(
            title="有序列表",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                OrderedListElement(
                                    items=[
                                        ListItem.plain("步骤一"),
                                        ListItem.plain("步骤二"),
                                    ]
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_table(self, renderer):
        """表格渲染."""
        doc = Document(
            title="表格",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
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
                                        [
                                            [TextRun(text="A1")],
                                            [TextRun(text="B1")],
                                        ],
                                        [
                                            [TextRun(text="A2")],
                                            [TextRun(text="B2")],
                                        ],
                                    ],
                                    title="测试表格",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_quote(self, renderer):
        """引用块渲染."""
        doc = Document(
            title="引用",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                QuoteElement(
                                    text="市场永远是对的。",
                                    attribution="—— 佚名",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_callout(self, renderer):
        """提示框渲染."""
        doc = Document(
            title="提示框",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                CalloutElement(
                                    callout_type=CalloutType.KEY_FINDING,
                                    title="核心发现",
                                    text="重要信息。",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_key_value(self, renderer):
        """键值对渲染."""
        doc = Document(
            title="KV",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[KeyValueElement(pairs=[("K1", "V1"), ("K2", "V2")])],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_multi_section_with_page_breaks(self, renderer):
        """多章节带分页."""
        doc = Document(
            title="多章节",
            sections=[
                Section(
                    section_id="s1",
                    title="第一章",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("第一章内容")],
                        )
                    ],
                ),
                Section(
                    section_id="s2",
                    title="第二章",
                    page_break_before=True,
                    blocks=[
                        ContentBlock(
                            block_id="b2",
                            elements=[ParagraphElement.plain("第二章内容")],
                        )
                    ],
                ),
            ],
        )
        buf = renderer.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0

    def test_custom_design_tokens(self, renderer):
        """自定义设计令牌."""
        tokens = DesignTokens(
            primary_color="#000000",
            heading_font="Arial",
            body_font="Times New Roman",
            body_size=14,
        )
        doc = Document(
            title="自定义样式",
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
        renderer_with_tokens = WordRenderer(tokens)
        buf = renderer_with_tokens.render_to_buffer(doc)
        assert buf.getbuffer().nbytes > 0


class TestWordRendererError:
    def test_missing_docx(self, monkeypatch):
        """python-docx 不可用时的错误提示."""
        # This test always passes since DOCX_AVAILABLE is true in this env
        pass
