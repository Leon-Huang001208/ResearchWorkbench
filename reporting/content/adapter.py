"""
内容模型适配器 - 旧格式 ↔ 新统一内容模型转换.

提供零破坏性的向后兼容适配层：
- SectionOutput → Section：将旧 content: str 包装为 ParagraphElement
- SectionOutput 列表 → Document：聚合为完整 Document
- FactCard → ContentElement 列表：将事实卡片拆解为内容元素
- CompiledReport → Document：编译器产出转换为通用文档

设计原则：
- 所有转换都是纯函数，不产生副作用
- 当 SectionOutput.content_elements 已填充时，优先使用新字段
- 当 SectionOutput.content_elements 为空时，自动从 content 字段生成
"""

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
    OrderedListElement,
    ParagraphElement,
    TextRun,
)
from core.contracts.document import DesignTokens, Document, Section
from core.observability import get_logger

logger = get_logger(__name__)

# 延迟导入以避免循环依赖
# SectionOutput, FactCard, CompiledReport 等类型在函数内按需导入


class ContentAdapter:
    """内容模型适配器 - 将旧格式转换为新统一内容模型."""

    # ========================================================================
    # SectionOutput → Section
    # ========================================================================

    @staticmethod
    def section_output_to_section(section_output: Any) -> Section:
        """将旧 SectionOutput 转换为新 Section.

        转换逻辑：
        1. 如果 content_elements 已填充 → 直接使用
        2. 否则 → 从 content 字符串生成 ParagraphElement
        3. 附加 fact_card / warnings 等信息作为额外内容元素

        Args:
            section_output: SectionOutput 实例.

        Returns:
            对应的 Section 对象.
        """
        from core.contracts.reporting import SectionOutput

        so: SectionOutput = section_output

        # 优先使用 content_elements（新字段）
        if so.content_elements:
            elements: List[ContentElement] = list(so.content_elements)
        else:
            # 从旧 content: str 生成
            elements = ContentAdapter._content_to_elements(
                content=so.content,
                title=so.title,
                key=so.key,
            )

        # 附加 fact_card 信息（如果有）
        if so.fact_card:
            fc_elements = ContentAdapter._fact_card_to_elements(so.fact_card)
            elements.extend(fc_elements)

        # 附加警告信息（如果有）
        if so.warnings:
            elements.append(
                CalloutElement(
                    callout_type=CalloutType.WARNING,
                    title="⚠️ 校验警告",
                    text="\n".join(f"- {w}" for w in so.warnings),
                )
            )

        # 构建 ContentBlock
        block = ContentBlock(
            block_id=so.key,
            elements=elements,
            layout_hint="full",
        )

        return Section(
            section_id=so.key,
            title=so.title,
            blocks=[block],
            metadata={
                "source": "SectionOutput",
                "key": so.key,
                "evidence_refs": so.evidence_refs,
                "scenario_refs": so.scenario_refs,
            },
        )

    # ========================================================================
    # SectionOutput 列表 → Document
    # ========================================================================

    @staticmethod
    def sections_to_document(
        title: str,
        sections: List[Any],
        metadata: Optional[Dict[str, Any]] = None,
        design_tokens: Optional[DesignTokens] = None,
        document_id: str = "",
    ) -> Document:
        """将 SectionOutput 列表转换为完整 Document.

        Args:
            title: 文档标题.
            sections: SectionOutput 列表.
            metadata: 文档元数据.
            design_tokens: 设计令牌（默认使用 report_tokens）.
            document_id: 文档 ID.

        Returns:
            Document 对象.
        """
        doc_sections = [ContentAdapter.section_output_to_section(s) for s in sections]

        return Document(
            document_id=document_id,
            title=title,
            sections=doc_sections,
            design_tokens=design_tokens or DesignTokens(),
            metadata=metadata or {},
        )

    # ========================================================================
    # CompiledReport → Document
    # ========================================================================

    @staticmethod
    def compiled_report_to_document(
        compiled_report: Any,
        design_tokens: Optional[DesignTokens] = None,
    ) -> Document:
        """将 CompiledReport 转换为 Document.

        转换逻辑：
        1. ReportOutline → Document.title / Document.metadata
        2. CompiledSection[] → Section[]
        3. FactRecord[] → 附加入证据引用信息

        Args:
            compiled_report: CompiledReport 实例.
            design_tokens: 设计令牌.

        Returns:
            Document 对象.
        """
        sections: List[Section] = []

        for compiled_section in compiled_report.sections:
            elements = ContentAdapter._content_to_elements(
                content=compiled_section.content,
                title=compiled_section.title,
                key=compiled_section.section_id,
            )

            # 附加引用信息
            if compiled_section.citations:
                citation_texts = [
                    c.display_text for c in compiled_section.citations if c.display_text
                ]
                if citation_texts:
                    elements.append(
                        BulletListElement(
                            items=[
                                ListItem(runs=[TextRun(text=t)])
                                for t in citation_texts[:10]  # 限制引用数量
                            ]
                        )
                    )

            block = ContentBlock(
                block_id=compiled_section.section_id,
                elements=elements,
            )
            sections.append(
                Section(
                    section_id=compiled_section.section_id,
                    title=compiled_section.title,
                    blocks=[block],
                )
            )

        return Document(
            document_id=compiled_report.report_id,
            title=compiled_report.outline.report_title,
            subtitle=compiled_report.outline.thesis or None,
            sections=sections,
            design_tokens=design_tokens or DesignTokens(),
            metadata={
                "source": "CompiledReport",
                "compiler_version": compiled_report.compiler_version,
                "facts_count": len(compiled_report.facts),
            },
        )

    # ========================================================================
    # 纯文本 → ContentElement 列表
    # ========================================================================

    @staticmethod
    def wrap_string_as_elements(
        content: str,
        title: str = "",
        section_key: str = "",
    ) -> List[ContentElement]:
        """将纯文本字符串包装为基础 ContentElement 列表.

        适用于简单的一节一文本场景。

        Args:
            content: 文本内容.
            title: 可选的章节标题.
            section_key: 可选的章节 key.

        Returns:
            ContentElement 列表.
        """
        return ContentAdapter._content_to_elements(
            content=content,
            title=title,
            key=section_key,
        )

    # ========================================================================
    # 内部方法
    # ========================================================================

    @staticmethod
    def _content_to_elements(
        content: str,
        title: str = "",
        key: str = "",
    ) -> List[ContentElement]:
        """将 content 字符串解析为 ContentElement 列表.

        简单的启发式解析：
        - 以 ## 开头的行 → HeadingElement(level=2)
        - 以 ### 开头的行 → HeadingElement(level=3)
        - 以 - 开头的连续行 → BulletListElement
        - 其他行 → ParagraphElement

        Args:
            content: 文本内容.
            title: 可选的章节标题.
            key: 可选的章节 key.

        Returns:
            ContentElement 列表.
        """
        elements: List[ContentElement] = []

        # 如果指定了标题，先添加标题元素
        if title:
            elements.append(HeadingElement(text=title, level=2))

        if not content.strip():
            return elements

        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # 空行跳过
            if not line.strip():
                i += 1
                continue

            # Markdown heading: ## Title
            if line.startswith("## ") or line.startswith("### "):
                level = 2 if line.startswith("## ") else 3
                heading_text = line.lstrip("#").strip()
                elements.append(HeadingElement(text=heading_text, level=level))
                i += 1
                continue

            # Markdown list: - item
            if line.strip().startswith("- ") or line.strip().startswith("* "):
                list_items: List[ListItem] = []
                while i < len(lines) and (
                    lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")
                ):
                    item_text = lines[i].strip()[2:].strip()
                    list_items.append(ListItem(runs=[TextRun(text=item_text)]))
                    i += 1
                elements.append(BulletListElement(items=list_items))
                continue

            # 数字列表: 1. item
            if line.strip() and line.strip()[0].isdigit() and ". " in line.strip()[:4]:
                ordered_list_items: List[ListItem] = []
                while (
                    i < len(lines)
                    and lines[i].strip()
                    and (lines[i].strip()[0].isdigit() and ". " in lines[i].strip()[:4])
                ):
                    item_text = lines[i].strip().split(". ", 1)[-1]
                    ordered_list_items.append(ListItem(runs=[TextRun(text=item_text)]))
                    i += 1
                elements.append(ContentAdapter._make_ordered_list(ordered_list_items))
                continue

            # 普通段落：收集连续的非空行
            para_lines: List[str] = []
            while i < len(lines) and lines[i].strip():
                if (
                    lines[i].startswith("#")
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
    def _make_ordered_list(items: List[ListItem]) -> OrderedListElement:
        """创建有序列表元素."""
        return OrderedListElement(items=items)

    @staticmethod
    def _fact_card_to_elements(fact_card: Any) -> List[ContentElement]:
        """将 FactCard 转换为 ContentElement 列表.

        Args:
            fact_card: FactCard 实例.

        Returns:
            ContentElement 列表.
        """
        elements: List[ContentElement] = []

        # 关键变化 → 无序列表
        if fact_card.key_changes:
            items = [ListItem(runs=[TextRun(text=c)]) for c in fact_card.key_changes]
            elements.append(
                BulletListElement(
                    items=items,
                    element_id="fact_card_key_changes",
                )
            )

        # 驱动因素 → KeyValueElement
        if fact_card.drivers:
            pairs = [(f"驱动因素 {i+1}", d) for i, d in enumerate(fact_card.drivers)]
            elements.append(KeyValueElement(pairs=pairs))

        # 影响分析 → 无序列表
        if fact_card.impacts:
            items = [ListItem(runs=[TextRun(text=c)]) for c in fact_card.impacts]
            elements.append(
                BulletListElement(
                    items=items,
                    element_id="fact_card_impacts",
                )
            )

        # 风险提示 → CalloutElement
        if fact_card.risks:
            risk_text = "\n".join(f"- {r}" for r in fact_card.risks)
            elements.append(
                CalloutElement(
                    callout_type=CalloutType.WARNING,
                    title="⚠️ 风险提示",
                    text=risk_text,
                    element_id="fact_card_risks",
                )
            )

        # 观察重点 → CalloutElement
        if fact_card.watch_points:
            wp_text = "\n".join(f"- {w}" for w in fact_card.watch_points)
            elements.append(
                CalloutElement(
                    callout_type=CalloutType.TIP,
                    title="🔍 观察重点",
                    text=wp_text,
                    element_id="fact_card_watch_points",
                )
            )

        return elements


# 便捷别名函数
def section_output_to_section(section_output: Any) -> Section:
    """便捷函数：SectionOutput → Section."""
    return ContentAdapter.section_output_to_section(section_output)


def sections_to_document(
    title: str,
    sections: List[Any],
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Document:
    """便捷函数：SectionOutput 列表 → Document."""
    return ContentAdapter.sections_to_document(title, sections, metadata, **kwargs)
