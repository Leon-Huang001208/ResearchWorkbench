"""Phase 2 单元测试 - Markdown 渲染器."""

import tempfile
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
    TableElement,
    TextRun,
)
from core.contracts.document import Document, Section
from reporting.rendering.markdown_renderer import MarkdownRenderer


@pytest.fixture
def renderer():
    return MarkdownRenderer()


@pytest.fixture
def minimal_doc():
    return Document(
        document_id="test_001",
        title="测试报告",
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
        metadata={"author": "Research Workbench"},
    )


class TestMarkdownRendererBasic:
    def test_render_document_to_file(self, renderer, minimal_doc):
        """渲染到文件."""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = renderer.render_document(minimal_doc, f.name)
            content = Path(path).read_text(encoding="utf-8")
            assert "# 测试报告" in content
            assert "*自动生成*" in content
            assert "这是第一段内容" in content
            assert "*author*: Research Workbench" in content

    def test_render_to_buffer(self, renderer, minimal_doc):
        """渲染到内存缓冲区."""
        buf = renderer.render_to_buffer(minimal_doc)
        content = buf.read().decode("utf-8")
        assert "# 测试报告" in content


class TestMarkdownElements:
    def test_heading_all_levels(self, renderer):
        """所有标题级别."""
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
                                HeadingElement(text="H1", level=1),
                                HeadingElement(text="H2", level=2),
                                HeadingElement(text="H3", level=3),
                                HeadingElement(text="H6", level=6),
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "# H1" in content
        assert "## H2" in content
        assert "### H3" in content
        assert "###### H6" in content

    def test_paragraph_with_rich_text(self, renderer):
        """富文本段落渲染."""
        doc = Document(
            title="富文本测试",
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
                                        TextRun(text="普通文本 "),
                                        TextRun(text="加粗", bold=True),
                                        TextRun(text=" 斜体", italic=True),
                                        TextRun(
                                            text="链接",
                                            hyperlink="https://example.com",
                                        ),
                                    ]
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "**加粗**" in content
        assert "斜体" in content
        assert "[链接](https://example.com)" in content

    def test_bullet_list(self, renderer):
        """无序列表渲染."""
        doc = Document(
            title="列表测试",
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
                                        ListItem.plain("项目三"),
                                    ]
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "- 项目一" in content
        assert "- 项目二" in content
        assert "- 项目三" in content

    def test_ordered_list(self, renderer):
        """有序列表渲染."""
        doc = Document(
            title="列表测试",
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
                                        ListItem.plain("第一步"),
                                        ListItem.plain("第二步"),
                                    ],
                                    start=1,
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "1. 第一步" in content
        assert "2. 第二步" in content

    def test_table(self, renderer):
        """表格渲染."""
        doc = Document(
            title="表格测试",
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
                                        [TextRun(text="名称")],
                                        [TextRun(text="数值")],
                                    ],
                                    rows=[
                                        [
                                            [TextRun(text="营收")],
                                            [TextRun(text="100亿")],
                                        ],
                                        [
                                            [TextRun(text="利润")],
                                            [TextRun(text="20亿")],
                                        ],
                                    ],
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "| 名称 | 数值 |" in content
        assert "| 营收 | 100亿 |" in content
        assert "| 利润 | 20亿 |" in content

    def test_quote(self, renderer):
        """引用块渲染."""
        doc = Document(
            title="引用测试",
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
                                    attribution="—— Jesse Livermore",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "> 市场永远是对的。" in content
        assert "> —— Jesse Livermore" in content

    def test_callout(self, renderer):
        """提示框渲染."""
        doc = Document(
            title="提示框测试",
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
                                    text="估值处于历史高位。",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "🔑" in content
        assert "核心发现" in content
        assert "估值处于历史高位" in content

    def test_key_value(self, renderer):
        """键值对渲染."""
        doc = Document(
            title="KV测试",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                KeyValueElement(
                                    pairs=[
                                        ("上证指数", "3,250"),
                                        ("深证成指", "11,200"),
                                    ]
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "**上证指数**" in content
        assert "3,250" in content

    def test_divider(self, renderer):
        """分隔线渲染."""
        doc = Document(
            title="分隔线测试",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                ParagraphElement.plain("上文"),
                                DividerElement(),
                                ParagraphElement.plain("下文"),
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "上文" in content
        assert "---" in content
        assert "下文" in content

    def test_multi_section_document(self, renderer):
        """多章节文档."""
        doc = Document(
            title="多章节报告",
            sections=[
                Section(
                    section_id="s1",
                    title="第一章",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[ParagraphElement.plain("第一章内容。")],
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
                            elements=[ParagraphElement.plain("第二章内容。")],
                        )
                    ],
                ),
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "# 多章节报告" in content
        assert "第一章内容" in content
        assert "第二章内容" in content

    def test_empty_document(self, renderer):
        """空文档渲染."""
        doc = Document(title="空文档")
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "# 空文档" in content

    def test_hidden_element_skipped(self, renderer):
        """不可见元素被跳过."""
        doc = Document(
            title="隐藏测试",
            sections=[
                Section(
                    section_id="s1",
                    title="章节",
                    blocks=[
                        ContentBlock(
                            block_id="b1",
                            elements=[
                                ParagraphElement.plain("可见段落"),
                                ParagraphElement(
                                    runs=[TextRun(text="隐藏段落")],
                                    visible=False,
                                ),
                            ],
                        )
                    ],
                )
            ],
        )
        buf = renderer.render_to_buffer(doc)
        content = buf.read().decode("utf-8")
        assert "可见段落" in content
        assert "隐藏段落" not in content
