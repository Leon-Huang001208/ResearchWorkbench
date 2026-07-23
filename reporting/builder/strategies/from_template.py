"""
模板驱动策略 — 从 YAML 模板 + 运行时上下文构建 Document.

TemplateStrategy 封装了 TemplateConfig → Document 的转换逻辑，
支持模板变量插值、条件渲染和设计令牌提取。

这是 UnifiedPipeline 中 strategy="template" 的实际执行者。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from core.contracts.content_element import (
    BulletListElement,
    ContentBlock,
    ContentElement,
    HeadingElement,
    KeyValueElement,
    ListItem,
    OrderedListElement,
    ParagraphElement,
    TableElement,
    TextRun,
)
from core.contracts.document import DesignTokens, Document, Section
from core.observability import get_logger

if TYPE_CHECKING:
    from core.contracts.reporting import TemplateConfig

logger = get_logger(__name__)


class TemplateStrategy:
    """模板驱动策略 — 从 YAML 模板 + 上下文构建 Document.

    支持功能：
    - 基础模板：每个 SectionSpec → Section（Heading + Paragraph）
    - v2 增强模板：支持 blocks/elements 定义、变量插值
    - 条件渲染：模板中的 visible 字段控制章节可见性
    - 设计令牌：从模板 metadata.design_tokens 中提取

    Usage:
        strategy = TemplateStrategy()
        doc = strategy.build(template_config, context={"asset": "600519.SH"})
    """

    def build(
        self,
        template: "TemplateConfig",
        context: Optional[Dict[str, Any]] = None,
        design_tokens: Optional[DesignTokens] = None,
    ) -> Document:
        """从模板配置构建 Document.

        Args:
            template: 模板配置.
            context: 运行时上下文（变量值，用于插值）.
            design_tokens: 设计令牌（覆盖模板内的设置）.

        Returns:
            Document 对象.
        """
        ctx = context or {}
        tokens = design_tokens or self._extract_tokens(template)

        sections: List[Section] = []
        for section_spec in template.sections:
            # 条件可见性：检查 metadata 中的 visible 字段
            if not self._is_section_visible(section_spec, ctx):
                logger.debug(
                    "Section hidden by condition",
                    extra={"section": section_spec.key},
                )
                continue

            section = self._build_section(section_spec, ctx)
            sections.append(section)

        return Document(
            document_id=template.name,
            title=self._interpolate(template.name.replace("_", " ").title(), ctx),
            subtitle=self._interpolate(template.description or "", ctx) or None,
            sections=sections,
            design_tokens=tokens,
            metadata={
                "source": "TemplateStrategy",
                "template_name": template.name,
                "template_version": template.version,
                "context_keys": list(ctx.keys()),
            },
        )

    # ========================================================================
    # Section 构建
    # ========================================================================

    def _build_section(self, section_spec: Any, ctx: Dict[str, Any]) -> Section:
        """从 SectionSpec 构建 Section.

        优先检查 section_spec 是否有 blocks 定义（v2 模板格式），
        否则使用默认的一头一段结构（v1 兼容）。
        """
        # 尝试 v2 格式：section 自带 blocks 定义
        if hasattr(section_spec, "blocks") and section_spec.blocks:
            blocks = self._build_blocks(section_spec, ctx)
        else:
            # v1 格式：创建默认 block（Heading + Paragraph）
            blocks = self._build_default_block(section_spec, ctx)

        # 检查 page_break_before
        page_break = getattr(section_spec, "page_break_before", False)

        # 检查 slide_layout
        slide_layout = getattr(section_spec, "slide_layout", None)

        # 检查 speaker_notes
        speaker_notes_raw = getattr(section_spec, "speaker_notes", None)
        speaker_notes = self._interpolate(speaker_notes_raw, ctx) if speaker_notes_raw else None

        return Section(
            section_id=section_spec.key,
            title=self._interpolate(section_spec.title, ctx),
            blocks=blocks,
            page_break_before=page_break,
            slide_layout=slide_layout,
            speaker_notes=speaker_notes,
            metadata={
                "target_words": getattr(section_spec, "target_words", 0),
                "evidence_policy": getattr(section_spec, "evidence_policy", "strict"),
            },
        )

    def _build_default_block(
        self,
        section_spec: Any,
        ctx: Dict[str, Any],
    ) -> List[ContentBlock]:
        """为 v1 模板格式构建默认 ContentBlock.

        默认结构：HeadingElement(level=2) + ParagraphElement（内容从 context 注入）.
        """
        title = self._interpolate(section_spec.title, ctx)
        content = str(ctx.get(section_spec.key, ""))

        elements: List[ContentElement] = [
            HeadingElement(
                text=title,
                level=2,
                element_id=f"heading_{section_spec.key}",
            ),
            ParagraphElement.plain(
                text=content,
                element_id=f"content_{section_spec.key}",
            ),
        ]

        return [
            ContentBlock(
                block_id=section_spec.key,
                elements=elements,
            )
        ]

    def _build_blocks(
        self,
        section_spec: Any,
        ctx: Dict[str, Any],
    ) -> List[ContentBlock]:
        """从 v2 模板的 blocks 定义构建 ContentBlock 列表.

        v2 模板格式:
            blocks:
              - block_id: summary
                layout: full
                elements:
                  - type: paragraph
                    generation:
                      strategy: llm
                      prompt_template: "..."
                  - type: table
                    generation:
                      strategy: extract
                      source: context.top_industries
        """
        blocks: List[ContentBlock] = []

        for blk_spec in section_spec.blocks:
            elements = self._build_elements_from_spec(blk_spec, ctx)
            blocks.append(
                ContentBlock(
                    block_id=blk_spec.get("block_id", section_spec.key),
                    elements=elements,
                    layout_hint=blk_spec.get("layout", "full"),
                )
            )

        return blocks

    # ========================================================================
    # 元素构建（v2 模板）
    # ========================================================================

    def _build_elements_from_spec(
        self,
        blk_spec: Dict[str, Any],
        ctx: Dict[str, Any],
    ) -> List[ContentElement]:
        """从 v2 模板的 elements 定义构建 ContentElement 列表.

        每个 element spec 包含:
        - type: 元素类型
        - generation: 生成配置（strategy, source, prompt_template 等）
        - 其他元素特定字段

        当前支持的生成策略：
        - inline:  直接从 spec 中取值
        - extract: 从 context 中按 key 提取
        - llm:     由 LLM 生成（标记为 LLM_REQUIRED，由调用方注入）
        """
        elements: List[ContentElement] = []

        for el_spec in blk_spec.get("elements", []):
            gen = el_spec.get("generation", {})
            gen_strategy = gen.get("strategy", "inline")

            if gen_strategy == "llm":
                # LLM 生成策略：创建占位符元素，标记需要 LLM 注入
                el = self._create_placeholder_element(el_spec, ctx)
            elif gen_strategy == "extract":
                # 从 context 中提取
                source_key = gen.get("source", "").replace("context.", "")
                source_data = self._resolve_context_path(ctx, source_key)
                el = self._create_element_from_data(el_spec, source_data, ctx)
            else:
                # inline：直接从 spec 取值
                el = self._create_element_inline(el_spec, ctx)

            if el:
                elements.append(el)

        return elements

    def _create_element_inline(
        self,
        spec: Dict[str, Any],
        ctx: Dict[str, Any],
    ) -> Optional[ContentElement]:
        """从内联 spec 创建 ContentElement."""
        el_type = spec.get("type", "paragraph")

        if el_type == "heading":
            return HeadingElement(
                text=self._interpolate(spec.get("text", ""), ctx),
                level=spec.get("level", 2),
            )
        elif el_type == "paragraph":
            return ParagraphElement.plain(
                text=self._interpolate(spec.get("text", ""), ctx),
            )
        elif el_type == "bullet_list":
            items = [ListItem.plain(self._interpolate(item, ctx)) for item in spec.get("items", [])]
            return BulletListElement(items=items)
        elif el_type == "ordered_list":
            items = [ListItem.plain(self._interpolate(item, ctx)) for item in spec.get("items", [])]
            return OrderedListElement(items=items)
        elif el_type == "key_value":
            pairs = []
            for pair_spec in spec.get("pairs", []):
                key = self._interpolate(pair_spec.get("label", ""), ctx)
                val = self._interpolate(str(ctx.get(pair_spec.get("key", ""), "")), ctx)
                pairs.append((key, val))
            return KeyValueElement(pairs=pairs)
        elif el_type == "divider":
            from core.contracts.content_element import DividerElement

            return DividerElement()
        else:
            logger.warning(
                "Unknown inline element type",
                extra={"type": el_type},
            )
            return None

    def _create_element_from_data(
        self,
        spec: Dict[str, Any],
        data: Any,
        ctx: Dict[str, Any],
    ) -> Optional[ContentElement]:
        """从提取的数据创建 ContentElement."""
        el_type = spec.get("type", "paragraph")

        if el_type == "paragraph":
            text = str(data) if not isinstance(data, str) else data
            return ParagraphElement.plain(text=self._interpolate(text, ctx))
        elif el_type == "bullet_list":
            items_data = data if isinstance(data, list) else [str(data)]
            items = [ListItem.plain(str(item)) for item in items_data]
            return BulletListElement(items=items)
        elif el_type == "key_value":
            pairs_data = data if isinstance(data, dict) else {}
            pairs = [(str(k), str(v)) for k, v in pairs_data.items()]
            return KeyValueElement(pairs=pairs)
        elif el_type == "table":
            headers_data = spec.get("headers", [])
            rows_data = data if isinstance(data, list) else []
            return TableElement(
                headers=[[TextRun(text=str(h))] for h in headers_data],
                rows=[[TextRun(text=str(cell)) for cell in row] for row in rows_data],
            )
        else:
            logger.warning(
                "Unknown extract element type",
                extra={"type": el_type},
            )
            return None

    def _create_placeholder_element(
        self,
        spec: Dict[str, Any],
        ctx: Dict[str, Any],
    ) -> Optional[ContentElement]:
        """创建 LLM 占位符元素 — 标记需要 LLM 生成的内容."""
        el_type = spec.get("type", "paragraph")
        prompt_template = spec.get("generation", {}).get("prompt_template", "")
        target_words = spec.get("generation", {}).get("target_words", 300)

        placeholder_text = f"[LLM_REQUIRED: {prompt_template} | target_words={target_words}]"
        placeholder_prompt = self._interpolate(prompt_template, ctx)

        if el_type == "paragraph":
            return ParagraphElement(
                runs=[TextRun(text=placeholder_text, italic=True)],
                metadata={
                    "llm_required": True,
                    "prompt_template": placeholder_prompt,
                    "target_words": target_words,
                },
            )
        else:
            logger.warning(
                "LLM generation not supported for element type",
                extra={"type": el_type},
            )
            return None

    # ========================================================================
    # 辅助方法
    # ========================================================================

    @staticmethod
    def _interpolate(text: str, ctx: Dict[str, Any]) -> str:
        """简单的变量插值：将 {{var_name}} 替换为上下文中的值.

        Args:
            text: 包含 {{var}} 占位符的文本.
            ctx: 变量上下文.

        Returns:
            插值后的文本.
        """
        import re

        def replacer(match: re.Match) -> str:
            var_name = match.group(1).strip()
            return str(ctx.get(var_name, match.group(0)))

        return re.sub(r"\{\{(\w+)\}\}", replacer, text)

    @staticmethod
    def _resolve_context_path(ctx: Dict[str, Any], path: str) -> Any:
        """解析上下文中的点号路径.

        Args:
            ctx: 上下文字典.
            path: 点号分隔的路径（如 "market_data.indices"）.

        Returns:
            路径对应的值，不存在时返回 None.
        """
        if not path:
            return None

        parts = path.split(".")
        current: Any = ctx
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return None
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    @staticmethod
    def _is_section_visible(section_spec: Any, ctx: Dict[str, Any]) -> bool:
        """判断章节是否应该可见.

        检查 section_spec 的 visible 属性或 metadata 中的条件。
        """
        visible = getattr(section_spec, "visible", None)
        if visible is not None:
            if isinstance(visible, bool):
                return visible
            if isinstance(visible, str):
                # 将可见性表达式解释为上下文键存在性
                return bool(ctx.get(visible, False))

        # 检查 metadata 中的条件
        meta = getattr(section_spec, "metadata", {}) or {}
        condition = meta.get("visible_if") if isinstance(meta, dict) else None
        if condition and isinstance(condition, str):
            return bool(ctx.get(condition, False))

        return True

    @staticmethod
    def _extract_tokens(template: "TemplateConfig") -> DesignTokens:
        """从模板 metadata 中提取设计令牌."""
        dt_dict = template.metadata.get("design_tokens", {})
        if dt_dict:
            try:
                return DesignTokens(**dt_dict)
            except Exception:
                logger.warning(
                    "Failed to parse design_tokens from template metadata",
                    extra={"template": template.name},
                )
        return DesignTokens()
