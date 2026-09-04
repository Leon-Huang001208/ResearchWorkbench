"""
ContentBuilder — 将各种输入转换为统一的 Document 模型.

支持四种输入方式：
1. from_template()   — TemplateConfig + context → Document
2. from_sections()   — List[SectionOutput] → Document (委托 ContentAdapter)
3. from_compiled()   — CompiledReport → Document (委托 ContentAdapter)
4. from_dict()       — JSON/dict spec → Document (编程式构建)

ContentBuilder 是统一流水线的"构建"阶段的入口。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from core.contracts.document import DesignTokens, Document
from core.observability import get_logger

if TYPE_CHECKING:
    from core.contracts.reporting import TemplateConfig

logger = get_logger(__name__)


class ContentBuilder:
    """内容构建器 — 将任意输入组装为 Document.

    策略模式：每种输入类型有对应的构建方法，最终产出统一的 Document.

    Usage:
        builder = ContentBuilder()
        doc = builder.from_template(template_config, context={"asset": "600519.SH"})
    """

    # ========================================================================
    # 模板驱动
    # ========================================================================

    def from_template(
        self,
        template: "TemplateConfig",
        context: Optional[Dict[str, Any]] = None,
        design_tokens: Optional[DesignTokens] = None,
    ) -> Document:
        """从 TemplateConfig + 上下文构建 Document.

        将模板的 sections 列表转换为 Document 的 Section 列表。
        每个 section 转换为一个 ContentBlock，其中包含
        HeadingElement + ParagraphElement（内容由调用方注入）。

        Args:
            template: 模板配置.
            context: 生成上下文（资产代码、日期、主题等）.
            design_tokens: 设计令牌（默认从模板 metadata 中读取，fallback 到 report_tokens）.

        Returns:
            Document 对象.
        """
        from core.contracts.content_element import (
            ContentBlock,
            HeadingElement,
            ParagraphElement,
        )
        from core.contracts.document import Section

        ctx = context or {}
        tokens = design_tokens or self._extract_tokens(template)

        sections: List[Section] = []
        for spec in template.sections:
            # 每个 section spec → 一个 Section + 一个 ContentBlock
            elements = [
                HeadingElement(
                    text=spec.title,
                    level=2,
                    element_id=f"heading_{spec.key}",
                ),
                ParagraphElement.plain(
                    text=ctx.get(spec.key, ""),
                    element_id=f"para_{spec.key}",
                ),
            ]

            sections.append(
                Section(
                    section_id=spec.key,
                    title=spec.title,
                    blocks=[
                        ContentBlock(
                            block_id=spec.key,
                            elements=elements,
                        )
                    ],
                    metadata={
                        "target_words": spec.target_words,
                        "evidence_policy": spec.evidence_policy,
                    },
                )
            )

        return Document(
            document_id=template.name,
            title=template.name.replace("_", " ").title(),
            subtitle=template.description or None,
            sections=sections,
            design_tokens=tokens,
            metadata={
                "source": "TemplateConfig",
                "template_name": template.name,
                "template_version": template.version,
                "context_keys": list(ctx.keys()),
            },
        )

    # ========================================================================
    # SectionOutput 列表 → Document（委托 ContentAdapter）
    # ========================================================================

    def from_sections(
        self,
        title: str,
        sections: List[Any],
        metadata: Optional[Dict[str, Any]] = None,
        design_tokens: Optional[DesignTokens] = None,
    ) -> Document:
        """从 SectionOutput 列表转换为 Document.

        委托给 ContentAdapter.sections_to_document()。

        Args:
            title: 文档标题.
            sections: SectionOutput 列表.
            metadata: 文档元数据.
            design_tokens: 设计令牌.

        Returns:
            Document 对象.
        """
        from reporting.content.adapter import ContentAdapter

        return ContentAdapter.sections_to_document(
            title=title,
            sections=sections,
            metadata=metadata,
            design_tokens=design_tokens,
        )

    # ========================================================================
    # CompiledReport → Document（委托 ContentAdapter）
    # ========================================================================

    def from_compiled(
        self,
        compiled_report: Any,
        design_tokens: Optional[DesignTokens] = None,
    ) -> Document:
        """从 CompiledReport 转换为 Document.

        委托给 ContentAdapter.compiled_report_to_document()。

        Args:
            compiled_report: CompiledReport 实例.
            design_tokens: 设计令牌.

        Returns:
            Document 对象.
        """
        from reporting.content.adapter import ContentAdapter

        return ContentAdapter.compiled_report_to_document(
            compiled_report=compiled_report,
            design_tokens=design_tokens,
        )

    # ========================================================================
    # 字典/JSON → Document（编程式构建）
    # ========================================================================

    def from_dict(
        self,
        spec: Dict[str, Any],
        design_tokens: Optional[DesignTokens] = None,
    ) -> Document:
        """从纯字典/JSON 构建 Document（程序化生成）.

        字典格式:
        {
            "title": "报告标题",
            "subtitle": "副标题",
            "sections": [
                {
                    "section_id": "sec_1",
                    "title": "章节标题",
                    "blocks": [
                        {
                            "block_id": "b1",
                            "elements": [
                                {"type": "paragraph", "text": "内容"},
                                {"type": "heading", "text": "子标题", "level": 2},
                                {"type": "bullet_list", "items": ["A", "B"]},
                            ]
                        }
                    ]
                }
            ],
            "metadata": {"author": "Research Workbench"},
        }

        Args:
            spec: 文档规范字典.
            design_tokens: 设计令牌.

        Returns:
            Document 对象.
        """
        from core.contracts.content_element import (
            BulletListElement,
            ContentBlock,
            HeadingElement,
            ListItem,
            ParagraphElement,
        )
        from core.contracts.document import Section

        sections: List[Section] = []

        for sec_spec in spec.get("sections", []):
            blocks: List[ContentBlock] = []

            for blk_spec in sec_spec.get("blocks", []):
                elements = []

                for el_spec in blk_spec.get("elements", []):
                    el_type = el_spec.get("type", "paragraph")

                    if el_type == "heading":
                        elements.append(
                            HeadingElement(
                                text=el_spec.get("text", ""),
                                level=el_spec.get("level", 2),
                            )
                        )
                    elif el_type == "bullet_list":
                        items = [ListItem.plain(item) for item in el_spec.get("items", [])]
                        elements.append(BulletListElement(items=items))
                    elif el_type == "paragraph":
                        elements.append(ParagraphElement.plain(el_spec.get("text", "")))
                    else:
                        logger.warning(
                            "Unknown element type in dict spec",
                            extra={"type": el_type},
                        )

                blocks.append(
                    ContentBlock(
                        block_id=blk_spec.get("block_id", ""),
                        elements=elements,
                        layout_hint=blk_spec.get("layout", "full"),
                    )
                )

            sections.append(
                Section(
                    section_id=sec_spec.get("section_id", ""),
                    title=sec_spec.get("title", ""),
                    blocks=blocks,
                )
            )

        return Document(
            document_id=spec.get("document_id", ""),
            title=spec.get("title", "Untitled"),
            subtitle=spec.get("subtitle"),
            sections=sections,
            design_tokens=design_tokens or DesignTokens(),
            metadata=spec.get("metadata", {}),
        )

    # ========================================================================
    # 辅助方法
    # ========================================================================

    @staticmethod
    def _extract_tokens(template: "TemplateConfig") -> DesignTokens:
        """从 TemplateConfig.metadata 中提取设计令牌.

        支持 v2 模板在 metadata 中嵌入 design_tokens 字典。
        """
        dt_dict = template.metadata.get("design_tokens", {})
        if dt_dict:
            try:
                return DesignTokens(**dt_dict)
            except Exception:
                logger.warning(
                    "Failed to parse design_tokens from template metadata, using defaults",
                    extra={"template": template.name},
                )
        return DesignTokens()
