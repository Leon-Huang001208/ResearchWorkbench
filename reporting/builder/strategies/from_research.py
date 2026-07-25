"""
深度研究策略 — 从深度研究编译器产出构建 Document.

ResearchStrategy 封装了 CompiledReport → Document 的转换逻辑。
这是 UnifiedPipeline 中 strategy="research" 的实际执行者。

与模板策略不同，深度研究策略的 Document 结构由编译器产出的
ReportOutline 决定，而非预定义模板。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.contracts.content_element import (
    BulletListElement,
    CalloutElement,
    CalloutType,
    ContentBlock,
    ContentElement,
    HeadingElement,
    KeyValueElement,
    ListItem,
    ParagraphElement,
    QuoteElement,
    TextRun,
)
from core.contracts.document import DesignTokens, Document, Section
from core.observability import get_logger

logger = get_logger(__name__)


class ResearchStrategy:
    """深度研究策略 — 从编译器产出构建 Document.

    处理 CompiledReport 的完整结构：
    - ReportOutline → Document 元数据和标题
    - CompiledSection[] → Section[]（保留编译器的结构决策）
    - FactRecord[] → 事实引用和证据映射
    - 批判意见 → CalloutElement（分歧标注）
    - 修订历史 → 可选的附录 Section

    Usage:
        strategy = ResearchStrategy()
        doc = strategy.build(compiled_report)
    """

    def build(
        self,
        compiled_report: Any,
        design_tokens: Optional[DesignTokens] = None,
        include_appendix: bool = True,
    ) -> Document:
        """从 CompiledReport 构建 Document.

        Args:
            compiled_report: CompiledReport 实例.
            design_tokens: 设计令牌.
            include_appendix: 是否包含附录（引用、事实、修订历史等）.

        Returns:
            Document 对象.
        """
        tokens = design_tokens or DesignTokens()

        # 1. 转换章节
        sections: List[Section] = []
        for compiled_section in compiled_report.sections:
            section = self._build_section(compiled_section)
            sections.append(section)

        # 2. 可选附录
        if include_appendix:
            appendix_sections = self._build_appendix(compiled_report)
            sections.extend(appendix_sections)

        # 3. 元数据
        metadata: Dict[str, Any] = {
            "source": "ResearchStrategy",
            "compiler_version": getattr(compiled_report, "compiler_version", "unknown"),
            "facts_count": getattr(getattr(compiled_report, "facts", None), "__len__", lambda: 0)(),
        }

        # 提取 outline 信息
        outline = getattr(compiled_report, "outline", None)
        if outline:
            metadata.update(
                {
                    "report_title": getattr(outline, "report_title", ""),
                    "thesis": getattr(outline, "thesis", ""),
                    "audience": getattr(outline, "target_audience", ""),
                    "tone": getattr(outline, "tone", ""),
                }
            )

        return Document(
            document_id=getattr(compiled_report, "report_id", ""),
            title=(
                outline.report_title
                if outline and hasattr(outline, "report_title")
                else getattr(compiled_report, "report_id", "Research Report")
            ),
            subtitle=(outline.thesis if outline and hasattr(outline, "thesis") else None),
            sections=sections,
            design_tokens=tokens,
            metadata=metadata,
        )

    # ========================================================================
    # Section 构建
    # ========================================================================

    def _build_section(self, compiled_section: Any) -> Section:
        """从 CompiledSection 构建 Section.

        包含：
        - 内容元素（从 content 文本解析）
        - 引用注释（从 citations 提取）
        - 批判意见（如果有 critic_notes）
        - 证据记录（如果有 evidence 或 fact_records）
        """
        elements: List[ContentElement] = []

        # 内容解析（使用启发式 Markdown 解析）
        content_elements = self._parse_content(
            content=getattr(compiled_section, "content", ""),
            title=getattr(compiled_section, "title", ""),
            key=getattr(compiled_section, "section_id", ""),
        )
        elements.extend(content_elements)

        # 引用注释
        citations = getattr(compiled_section, "citations", []) or []
        if citations:
            elements.extend(self._build_citation_elements(citations))

        # 批判意见（如有）
        critic_notes = getattr(compiled_section, "critic_notes", None)
        if critic_notes:
            elements.append(self._build_critic_callout(critic_notes))

        # 证据记录
        evidence = getattr(compiled_section, "evidence", None)
        if evidence:
            elements.append(self._build_evidence_element(evidence))

        block = ContentBlock(
            block_id=getattr(compiled_section, "section_id", ""),
            elements=elements,
        )

        # writer_notes → speaker_notes
        speaker_notes = getattr(compiled_section, "writer_notes", None)

        return Section(
            section_id=getattr(compiled_section, "section_id", ""),
            title=getattr(compiled_section, "title", ""),
            blocks=[block],
            speaker_notes=speaker_notes,
            metadata={
                "source": "CompiledSection",
                "revision_count": getattr(compiled_section, "revision_count", 0),
                "word_count": getattr(compiled_section, "word_count", 0),
            },
        )

    # ========================================================================
    # 附录构建
    # ========================================================================

    def _build_appendix(self, compiled_report: Any) -> List[Section]:
        """构建附录章节列表.

        包含以下可选部分：
        - 引用列表（Citations）
        - 事实记录（Facts）
        - 源计划（Source Plan）
        - 任务分解（Task Decomposition）
        """
        appendix: List[Section] = []

        # 引用附录
        citations = getattr(compiled_report, "citations", None) or []
        if citations:
            appendix.append(self._build_citations_appendix(citations))

        # 事实记录附录
        facts = getattr(compiled_report, "facts", None) or []
        if facts:
            appendix.append(self._build_facts_appendix(facts))

        # 源计划
        source_plan = getattr(compiled_report, "source_plan", None)
        if source_plan:
            appendix.append(
                Section(
                    section_id="appendix_source_plan",
                    title="附录: 信息源计划",
                    blocks=[
                        ContentBlock(
                            block_id="source_plan",
                            elements=[
                                ParagraphElement.plain(
                                    text=str(source_plan),
                                )
                            ],
                        )
                    ],
                    page_break_before=True,
                )
            )

        # 临界意见
        critic = getattr(compiled_report, "critic", None)
        if critic:
            critic_text = getattr(critic, "summary", str(critic))
            appendix.append(
                Section(
                    section_id="appendix_critic",
                    title="附录: 批判性评估",
                    blocks=[
                        ContentBlock(
                            block_id="critic_summary",
                            elements=[
                                CalloutElement(
                                    callout_type=CalloutType.WARNING,
                                    title="🔍 Critical Assessment",
                                    text=str(critic_text),
                                )
                            ],
                        )
                    ],
                    page_break_before=True,
                )
            )

        return appendix

    def _build_citations_appendix(self, citations: List[Any]) -> Section:
        """构建引用列表附录."""
        items: List[ListItem] = []
        for i, citation in enumerate(citations, 1):
            display = getattr(citation, "display_text", str(citation))
            source = getattr(citation, "source", "")
            items.append(
                ListItem(
                    runs=[TextRun(text=f"[{i}] {display}")]
                    + (
                        [TextRun(text=f" — {source}", italic=True, color="#718096")]
                        if source
                        else []
                    )
                )
            )

        return Section(
            section_id="appendix_citations",
            title="附录: 引用文献",
            blocks=[
                ContentBlock(
                    block_id="citations_list",
                    elements=[BulletListElement(items=items)],
                )
            ],
            page_break_before=True,
        )

    def _build_facts_appendix(self, facts: List[Any]) -> Section:
        """构建事实记录附录."""
        elements: List[ContentElement] = []
        for fact in facts:
            elements.append(
                KeyValueElement(
                    pairs=[
                        ("事实", getattr(fact, "content", str(fact))),
                        ("来源", getattr(fact, "source", "未知")),
                        ("置信度", str(getattr(fact, "confidence", "N/A"))),
                    ]
                )
            )

        return Section(
            section_id="appendix_facts",
            title="附录: 事实记录",
            blocks=[
                ContentBlock(
                    block_id="facts_list",
                    elements=elements,
                )
            ],
            page_break_before=True,
        )

    # ========================================================================
    # 元素构建
    # ========================================================================

    @staticmethod
    def _parse_content(
        content: str,
        title: str = "",
        key: str = "",
    ) -> List[ContentElement]:
        """启发式 Markdown 解析 → ContentElement 列表.

        Args:
            content: 文本内容.
            title: 章节标题.
            key: 章节 key.

        Returns:
            ContentElement 列表.
        """
        elements: List[ContentElement] = []

        if title:
            elements.append(HeadingElement(text=title, level=2))

        if not content.strip():
            return elements

        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            if not line.strip():
                i += 1
                continue

            # 标题
            if line.startswith("## ") or line.startswith("### "):
                level = 2 if line.startswith("## ") else 3
                heading_text = line.lstrip("#").strip()
                elements.append(HeadingElement(text=heading_text, level=level))
                i += 1
                continue

            # 引用块
            if line.strip().startswith("> "):
                quote_lines: List[str] = []
                while i < len(lines) and lines[i].strip().startswith("> "):
                    quote_lines.append(lines[i].strip()[2:])
                    i += 1
                elements.append(
                    QuoteElement(
                        text="\n".join(quote_lines),
                        attribution=None,
                    )
                )
                continue

            # 无序列表
            if line.strip().startswith("- ") or line.strip().startswith("* "):
                items: List[ListItem] = []
                while i < len(lines) and (
                    lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")
                ):
                    item_text = lines[i].strip()[2:].strip()
                    items.append(ListItem.plain(item_text))
                    i += 1
                elements.append(BulletListElement(items=items))
                continue

            # 数字列表
            if line.strip() and line.strip()[0].isdigit() and ". " in line.strip()[:4]:
                ordered_items: List[ListItem] = []
                while (
                    i < len(lines)
                    and lines[i].strip()
                    and (lines[i].strip()[0].isdigit() and ". " in lines[i].strip()[:4])
                ):
                    item_text = lines[i].strip().split(". ", 1)[-1]
                    ordered_items.append(ListItem.plain(item_text))
                    i += 1
                # 使用 OrderedListElement 需要导入
                from core.contracts.content_element import OrderedListElement

                elements.append(OrderedListElement(items=ordered_items))
                continue

            # 普通段落
            para_lines: List[str] = []
            while i < len(lines) and lines[i].strip():
                if (
                    lines[i].startswith("#")
                    or lines[i].strip().startswith("> ")
                    or lines[i].strip().startswith("- ")
                    or lines[i].strip().startswith("* ")
                    or (
                        lines[i].strip()
                        and lines[i].strip()[0].isdigit()
                        and ". " in lines[i].strip()[:4]
                    )
                ):
                    break
                para_lines.append(lines[i])
                i += 1

            if para_lines:
                para_text = "\n".join(para_lines)
                elements.append(ParagraphElement.plain(para_text, element_id=key))

        return elements

    @staticmethod
    def _build_citation_elements(citations: List[Any]) -> List[ContentElement]:
        """从引用列表构建内容元素."""
        if not citations:
            return []

        items = []
        for citation in citations:
            display_text = getattr(citation, "display_text", str(citation))
            items.append(
                ListItem(
                    runs=[
                        TextRun(text=display_text),
                    ]
                )
            )
        return [BulletListElement(items=items, element_id="citations")]

    @staticmethod
    def _build_critic_callout(critic_notes: Any) -> CalloutElement:
        """构建批判意见提示框."""
        text = str(critic_notes)
        return CalloutElement(
            callout_type=CalloutType.WARNING,
            title="🔍 批判性审查意见",
            text=text,
            element_id="critic_notes",
        )

    @staticmethod
    def _build_evidence_element(evidence: Any) -> ContentElement:
        """构建证据记录元素."""
        if isinstance(evidence, list):
            items = [ListItem.plain(str(e)) for e in evidence]
            return BulletListElement(items=items, element_id="evidence_list")
        else:
            return ParagraphElement.plain(str(evidence), element_id="evidence")
