"""Phase 2 单元测试 - RenderContext + DocumentRenderer 抽象基类."""

from pathlib import Path

import pytest

from core.contracts.content_element import (
    BulletListElement,
    CalloutElement,
    CalloutType,
    ContentBlock,
    DividerElement,
    HeadingElement,
    KeyValueElement,
    ListItem,
    OrderedListElement,
    ParagraphElement,
    QuoteElement,
    SpeakerNotesElement,
    TableElement,
    TextRun,
)
from core.contracts.document import DesignTokens, Document, Section
from reporting.rendering.base import DocumentRenderer, RenderContext, render_document

# ============================================================================
# RenderContext 测试
# ============================================================================


class TestRenderContext:
    def test_default_creation(self):
        """默认 RenderContext 创建."""
        ctx = RenderContext()
        assert ctx.document_title == ""
        assert ctx.current_section_index == 0
        assert ctx.total_sections == 0
        assert ctx.slide_number == 0
        assert ctx.metadata == {}

    def test_custom_values(self):
        """自定义 RenderContext."""
        ctx = RenderContext(
            document_title="测试",
            current_section_index=2,
            total_sections=5,
            slide_number=3,
            metadata={"key": "value"},
        )
        assert ctx.document_title == "测试"
        assert ctx.current_section_index == 2
        assert ctx.total_sections == 5
        assert ctx.slide_number == 3
        assert ctx.metadata["key"] == "value"


# ============================================================================
# 最小具体渲染器（用于测试基类分发逻辑）
# ============================================================================


class _FakeRenderer(DocumentRenderer):
    """用于测试基类分发逻辑的假渲染器（非 pytest 测试类）."""

    __test__ = False

    @property
    def format_name(self) -> str:
        return "Test"

    def __init__(self, tokens=None):
        super().__init__(tokens)
        self.rendered_elements: list[str] = []
        self.document_started = False
        self.document_ended = False

    def _begin_document(self, document):
        self.document_started = True

    def _end_document(self, document):
        self.document_ended = True

    def _finalize(self, output_path: Path) -> None:
        pass

    def _render_heading(self, element):
        self.rendered_elements.append(f"heading:{element.text}")

    def _render_paragraph(self, element):
        texts = [r.text for r in element.runs] if element.runs else [""]
        self.rendered_elements.append(f"paragraph:{''.join(texts)}")

    def _render_bullet_list(self, element):
        self.rendered_elements.append(f"bullet_list:{len(element.items)}")

    def _render_ordered_list(self, element):
        self.rendered_elements.append(f"ordered_list:{len(element.items)}")

    def _render_table(self, element):
        self.rendered_elements.append(f"table:{len(element.rows)}x{len(element.headers)}")

    def _render_chart(self, element):
        self.rendered_elements.append(f"chart:{element.chart_id}")

    def _render_image(self, element):
        self.rendered_elements.append(f"image:{element.image_id}")

    def _render_quote(self, element):
        self.rendered_elements.append(f"quote:{element.text[:20]}")

    def _render_callout(self, element):
        self.rendered_elements.append(f"callout:{element.callout_type}")

    def _render_key_value(self, element):
        self.rendered_elements.append(f"key_value:{len(element.pairs)}")

    def _render_divider(self, element):
        self.rendered_elements.append("divider")

    def _render_speaker_notes(self, element):
        self.rendered_elements.append(f"speaker_notes:{element.text[:20]}")


@pytest.fixture
def test_renderer():
    return _FakeRenderer()


# ============================================================================
# 元素分发测试
# ============================================================================


class TestElementDispatch:
    def test_dispatch_heading(self, test_renderer):
        """HeadingElement 分发到 _render_heading."""
        doc = Document(
            title="T",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[HeadingElement(text="标题", level=1)],
                        )
                    ],
                )
            ],
        )
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert "heading:标题" in test_renderer.rendered_elements

    def test_dispatch_paragraph(self, test_renderer):
        """ParagraphElement 分发到 _render_paragraph."""
        doc = Document(
            title="T",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("测试段落")],
                        )
                    ],
                )
            ],
        )
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert "paragraph:测试段落" in test_renderer.rendered_elements

    def test_dispatch_bullet_list(self, test_renderer):
        """BulletListElement 分发到 _render_bullet_list."""
        doc = Document(
            title="T",
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
                                        ListItem.plain("A"),
                                        ListItem.plain("B"),
                                    ]
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert "bullet_list:2" in test_renderer.rendered_elements

    def test_dispatch_ordered_list(self, test_renderer):
        """OrderedListElement 分发到 _render_ordered_list."""
        doc = Document(
            title="T",
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
                                        ListItem.plain("1"),
                                        ListItem.plain("2"),
                                        ListItem.plain("3"),
                                    ]
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert "ordered_list:3" in test_renderer.rendered_elements

    def test_dispatch_table(self, test_renderer):
        """TableElement 分发到 _render_table."""
        doc = Document(
            title="T",
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
                                        [TextRun(text="H1")],
                                        [TextRun(text="H2")],
                                    ],
                                    rows=[
                                        [
                                            [TextRun(text="V1")],
                                            [TextRun(text="V2")],
                                        ]
                                    ],
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert any("table:" in e for e in test_renderer.rendered_elements)

    def test_dispatch_quote(self, test_renderer):
        """QuoteElement 分发到 _render_quote."""
        doc = Document(
            title="T",
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
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert "quote:市场永远是对的。" in test_renderer.rendered_elements

    def test_dispatch_callout(self, test_renderer):
        """CalloutElement 分发到 _render_callout."""
        doc = Document(
            title="T",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                CalloutElement(
                                    callout_type=CalloutType.WARNING,
                                    text="警告内容",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert any("callout:" in e for e in test_renderer.rendered_elements)

    def test_dispatch_key_value(self, test_renderer):
        """KeyValueElement 分发到 _render_key_value."""
        doc = Document(
            title="T",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                KeyValueElement(pairs=[("K1", "V1"), ("K2", "V2"), ("K3", "V3")])
                            ],
                        )
                    ],
                )
            ],
        )
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert "key_value:3" in test_renderer.rendered_elements

    def test_dispatch_divider(self, test_renderer):
        """DividerElement 分发到 _render_divider."""
        doc = Document(
            title="T",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[DividerElement()],
                        )
                    ],
                )
            ],
        )
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert "divider" in test_renderer.rendered_elements

    def test_dispatch_speaker_notes(self, test_renderer):
        """SpeakerNotesElement 分发到 _render_speaker_notes."""
        doc = Document(
            title="T",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[SpeakerNotesElement(text="演讲备注内容")],
                        )
                    ],
                )
            ],
        )
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert any("speaker_notes:" in e for e in test_renderer.rendered_elements)

    def test_hidden_element_skipped(self, test_renderer):
        """visible=False 的元素被跳过."""
        doc = Document(
            title="T",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                ParagraphElement.plain("可见"),
                                ParagraphElement(
                                    runs=[TextRun(text="不可见")],
                                    visible=False,
                                ),
                            ],
                        )
                    ],
                )
            ],
        )
        test_renderer.render_document(doc, Path("_test_dispatch.md"))
        assert "paragraph:可见" in test_renderer.rendered_elements
        assert "不可见" not in str(test_renderer.rendered_elements)


# ============================================================================
# 结构遍历测试
# ============================================================================


class TestDocumentTraversal:
    def test_document_lifecycle(self, test_renderer):
        """文档生命周期: begin → sections → end."""
        doc = Document(
            title="生命周期测试",
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
        test_renderer.render_document(doc, Path("_test_lifecycle.md"))
        assert test_renderer.document_started
        assert test_renderer.document_ended
        assert "paragraph:内容" in test_renderer.rendered_elements

    def test_context_updates(self, test_renderer):
        """渲染上下文在遍历过程中更新."""
        doc = Document(
            title="上下文测试",
            sections=[
                Section(
                    section_id="s1",
                    title="第一章",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("内容1")],
                        )
                    ],
                ),
                Section(
                    section_id="s2",
                    title="第二章",
                    blocks=[
                        ContentBlock(
                            block_id="b2",
                            elements=[ParagraphElement.plain("内容2")],
                        )
                    ],
                ),
            ],
        )
        test_renderer.render_document(doc, Path("_test_context.md"))
        assert test_renderer._ctx.document_title == "上下文测试"
        assert test_renderer._ctx.total_sections == 2

    def test_document_uses_own_tokens(self, test_renderer):
        """Document 自带的设计令牌覆盖渲染器默认值."""
        custom_tokens = DesignTokens(primary_color="#FF0000")
        doc = Document(
            title="自定义令牌",
            design_tokens=custom_tokens,
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
        test_renderer.render_document(doc, Path("_test_tokens.md"))
        assert test_renderer.tokens.primary_color == "#FF0000"
        assert len(test_renderer.tokens.chart_palette) == 8  # 其他字段来自默认


# ============================================================================
# render_document 便捷函数测试
# ============================================================================


class TestRenderDocumentFunction:
    def test_render_word_format(self):
        """渲染为 Word 格式."""
        doc = Document(
            title="测试",
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
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = render_document(doc, f.name, format="word")
            assert path.suffix == ".docx"
            assert path.exists()

    def test_render_markdown_format(self):
        """渲染为 Markdown 格式."""
        doc = Document(
            title="测试",
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
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = render_document(doc, f.name, format="markdown")
            content = Path(path).read_text(encoding="utf-8")
            assert "# 测试" in content

    def test_render_unknown_format(self):
        """不支持的格式抛出 ValueError."""
        doc = Document(title="测试")
        with pytest.raises(ValueError, match="Unsupported format"):
            render_document(doc, "_test.xyz", format="pdf")
