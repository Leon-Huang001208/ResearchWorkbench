"""
UnifiedPipeline — 统一报告生成流水线.

将报告生成拆分为三个独立阶段：
    Build → Validate → Render

- Build:  通过 ContentBuilder 将输入转换为统一 Document 模型
- Validate: 对 Document 进行结构和内容验证
- Render:  通过 DocumentRenderer 将 Document 渲染为目标格式

策略模式：Build 阶段通过 BuildStrategy 接口支持多种构建策略：
- from_research: 10 步深度研究编译器驱动
- from_sections: SectionOutput 列表驱动（向后兼容）
- from_dict: 纯字典驱动（编程式生成）
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from core.contracts.document import DesignTokens, Document
from core.observability import get_logger

if TYPE_CHECKING:
    from reporting.builder.content_builder import ContentBuilder
    from reporting.rendering.base import DocumentRenderer

logger = get_logger(__name__)


# ============================================================================
# 流水线结果
# ============================================================================


@dataclass
class PipelineResult:
    """统一流水线执行结果.

    Attributes:
        document: 构建好的 Document（可用于进一步操作）.
        outputs: 格式名 → 输出文件路径的映射.
        buffers: 格式名 → BytesIO 缓冲区的映射（流式输出）.
        warnings: 验证阶段产生的警告列表.
        success: 整体是否成功.
        error: 失败时的错误消息.
    """

    document: Optional[Document] = None
    outputs: Dict[str, Path] = field(default_factory=dict)
    buffers: Dict[str, io.BytesIO] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


# ============================================================================
# 验证结果
# ============================================================================


@dataclass
class ValidationResult:
    """Document 验证结果.

    Attributes:
        is_valid: 是否通过验证.
        errors: 错误列表（必须修复）.
        warnings: 警告列表（可以继续但需注意）.
        stats: 文档统计信息.
    """

    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# UnifiedPipeline
# ============================================================================


class UnifiedPipeline:
    """统一报告流水线 — 串联 Build → Validate → Render 三个阶段.

    设计意图：
    1. 将旧三套流水线（ReportPipeline, ReportCompiler, ProjectRunService）
       统一到单个入口点
    2. Build 阶段通过策略模式支持不同的输入来源
    3. Validate 阶段提供统一的文档验证（结构/内容/引用）
    4. Render 阶段通过 DocumentRenderer 多态输出

    Usage:
        pipeline = UnifiedPipeline()
        pipeline.register_renderer("word", WordRenderer())
        pipeline.register_renderer("markdown", MarkdownRenderer())

        task = ReportTask(
            task_id="rpt_001",
            template_name="weekly_report",
            context={"asset": "600519.SH", "date": "2026-07-20"},
        )
        result = pipeline.execute(task, ["word", "markdown"])
    """

    def __init__(
        self,
        content_builder: Optional["ContentBuilder"] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        """初始化流水线.

        Args:
            content_builder: ContentBuilder 实例（None 时自动创建）.
            output_dir: 默认输出目录（None 时使用当前目录）.
        """
        from reporting.builder.content_builder import ContentBuilder

        self.content_builder = content_builder or ContentBuilder()
        self.output_dir = output_dir or Path("output")
        self._renderers: Dict[str, "DocumentRenderer"] = {}
        logger.info("UnifiedPipeline initialized", extra={"output_dir": str(self.output_dir)})

    # ========================================================================
    # 渲染器注册
    # ========================================================================

    def register_renderer(self, format_name: str, renderer: "DocumentRenderer") -> None:
        """注册一个格式渲染器.

        Args:
            format_name: 格式名称（"word", "ppt", "markdown" 等）.
            renderer: DocumentRenderer 实例.
        """
        self._renderers[format_name.lower()] = renderer
        logger.info(
            "Renderer registered",
            extra={"format": format_name, "renderer": renderer.format_name},
        )

    # ========================================================================
    # 主执行入口
    # ========================================================================

    def execute(
        self,
        task: Any,
        output_formats: List[str],
        output_dir: Optional[Path] = None,
        strategy: str = "sections",
        design_tokens: Optional[DesignTokens] = None,
    ) -> PipelineResult:
        """执行完整流水线：Build → Validate → Render.

        Args:
            task: 报告任务（ReportTask 或兼容对象）.
            output_formats: 输出格式列表（如 ["word", "ppt", "markdown"]）.
            output_dir: 输出目录（覆盖构造函数中的默认值）.
            strategy: 构建策略（"research", "sections", "compiled", "dict", "document"）.
            design_tokens: 设计令牌（覆盖模板中的设置）.

        Returns:
            PipelineResult 包含输出路径和状态信息.
        """
        result = PipelineResult()

        try:
            # ── 阶段 1: Build ──
            logger.info(
                "Pipeline: Build phase starting",
                extra={"task_id": getattr(task, "task_id", "?"), "strategy": strategy},
            )
            document = self._build(task, strategy, design_tokens)
            result.document = document
            logger.info(
                "Pipeline: Build phase complete",
                extra={
                    "title": document.title,
                    "sections": len(document.sections),
                    "blocks": sum(len(s.blocks) for s in document.sections),
                },
            )

            # ── 阶段 2: Validate ──
            logger.info("Pipeline: Validate phase starting")
            validation = self._validate(document)
            result.warnings = validation.warnings

            if validation.errors:
                result.success = False
                result.error = f"Validation failed: {'; '.join(validation.errors)}"
                logger.error(
                    "Pipeline: Validate phase failed",
                    extra={"errors": validation.errors},
                )
                return result

            if validation.warnings:
                logger.warning(
                    "Pipeline: Validate phase warnings",
                    extra={"warnings": validation.warnings},
                )
            else:
                logger.info("Pipeline: Validate phase passed")

            # ── 阶段 3: Render ──
            logger.info(
                "Pipeline: Render phase starting",
                extra={"formats": output_formats},
            )
            out_dir = output_dir or self.output_dir
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            for fmt in output_formats:
                fmt_lower = fmt.lower()
                renderer = self._resolve_renderer(fmt_lower)
                ext = self._format_extension(fmt_lower)

                output_path = out_dir / f"{document.document_id}.{ext}"
                rendered_path = renderer.render_document(document, output_path)
                result.outputs[fmt_lower] = rendered_path
                logger.info(
                    "Pipeline: Rendered format",
                    extra={"format": fmt_lower, "output": str(rendered_path)},
                )

            logger.info(
                "Pipeline: Complete",
                extra={"outputs": {k: str(v) for k, v in result.outputs.items()}},
            )

        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.error("Pipeline: Execution failed", extra={"error": str(e)}, exc_info=True)

        return result

    def execute_to_buffer(
        self,
        task: Any,
        output_formats: List[str],
        strategy: str = "sections",
        design_tokens: Optional[DesignTokens] = None,
    ) -> PipelineResult:
        """执行流水线并输出到内存缓冲区（而非文件）.

        适用于 API 响应或程序内消费。

        Args:
            task: 报告任务.
            output_formats: 输出格式列表.
            strategy: 构建策略.
            design_tokens: 设计令牌.

        Returns:
            PipelineResult 包含内存缓冲区和状态信息.
        """
        result = PipelineResult()

        try:
            # Build + Validate（与 execute 相同）
            document = self._build(task, strategy, design_tokens)
            result.document = document
            validation = self._validate(document)
            result.warnings = validation.warnings

            if validation.errors:
                result.success = False
                result.error = f"Validation failed: {'; '.join(validation.errors)}"
                return result

            # Render to buffer
            for fmt in output_formats:
                fmt_lower = fmt.lower()
                renderer = self._resolve_renderer(fmt_lower)
                buffer = renderer.render_to_buffer(document)
                result.buffers[fmt_lower] = buffer

        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.error(
                "Pipeline: Buffer execution failed",
                extra={"error": str(e)},
                exc_info=True,
            )

        return result

    # ========================================================================
    # 构建阶段（策略分发）
    # ========================================================================

    def _build(
        self,
        task: Any,
        strategy: str,
        design_tokens: Optional[DesignTokens] = None,
    ) -> Document:
        """根据策略构建 Document.

        支持策略：
        - "research":  从深度研究编译器构建
        - "sections":  从 SectionOutput 列表构建
        - "compiled":  从 CompiledReport 构建
        - "dict":      从字典/JSON spec 构建
        - "document":  任务本身就是 Document（直通模式）
        """
        if strategy in ("sections", "section_outputs"):
            return self._build_from_sections(task, design_tokens)
        elif strategy in ("compiled", "research"):
            return self._build_from_compiled(task, design_tokens)
        elif strategy == "dict":
            return self.content_builder.from_dict(
                spec=getattr(task, "context", {}),
                design_tokens=design_tokens,
            )
        elif strategy == "document":
            # 直通模式：任务本身就是 Document
            from core.contracts.document import Document as Doc

            if isinstance(task, Doc):
                return task
            raise ValueError("strategy='document' requires task to be a Document instance")
        else:
            raise ValueError(
                f"Unsupported build strategy: {strategy!r}. "
                "Supported: research, sections, compiled, dict, document"
            )

    def _build_from_sections(
        self,
        task: Any,
        design_tokens: Optional[DesignTokens] = None,
    ) -> Document:
        """SectionOutput 策略：SectionOutput 列表 → Document."""
        sections = getattr(task, "sections", [])
        title = getattr(task, "title", getattr(task, "template_name", "Untitled"))
        metadata = getattr(task, "metadata", None)
        return self.content_builder.from_sections(
            title=title,
            sections=sections,
            metadata=metadata,
            design_tokens=design_tokens,
        )

    def _build_from_compiled(
        self,
        task: Any,
        design_tokens: Optional[DesignTokens] = None,
    ) -> Document:
        """深度研究策略：CompiledReport → Document."""
        compiled_report = getattr(task, "compiled_report", task)
        return self.content_builder.from_compiled(
            compiled_report=compiled_report,
            design_tokens=design_tokens,
        )

    # ========================================================================
    # 验证阶段
    # ========================================================================

    def _validate(self, document: Document) -> ValidationResult:
        """验证 Document 结构和内容.

        检查项：
        1. 基本结构：必须有标题和至少一个章节
        2. 章节完整性：每个章节必须有 section_id 和 title
        3. 内容块完整性：每个章节至少有一个内容块
        4. 元素完整性：每个内容块至少有一个元素
        5. 统计信息：章节数、块数、元素数

        Args:
            document: 待验证的 Document.

        Returns:
            ValidationResult 包含错误和警告.
        """
        result = ValidationResult()

        # 统计
        total_blocks = sum(len(s.blocks) for s in document.sections)
        total_elements = sum(len(b.elements) for s in document.sections for b in s.blocks)
        result.stats = {
            "sections": len(document.sections),
            "blocks": total_blocks,
            "elements": total_elements,
            "has_design_tokens": document.design_tokens is not None,
        }

        # 1. 基本结构
        if not document.title:
            result.errors.append("Document must have a title")
        if not document.document_id:
            result.warnings.append("Document has no document_id (auto-generated)")
        if not document.sections:
            result.errors.append("Document must have at least one section")

        # 2. 章节完整性
        seen_ids: set = set()
        for i, section in enumerate(document.sections):
            if not section.section_id:
                result.errors.append(f"Section {i + 1} ({section.title}): missing section_id")
            elif section.section_id in seen_ids:
                result.errors.append(f"Duplicate section_id: {section.section_id}")
            else:
                seen_ids.add(section.section_id)

            if not section.title:
                result.warnings.append(f"Section {section.section_id}: missing title")

            # 3. 内容块完整性
            if not section.blocks:
                result.warnings.append(
                    f"Section '{section.title or section.section_id}': no content blocks"
                )
                continue

            # 4. 元素完整性
            for j, block in enumerate(section.blocks):
                if not block.elements:
                    result.warnings.append(
                        f"Block '{block.block_id}' in section "
                        f"'{section.title or section.section_id}': no elements"
                    )
                if not block.block_id:
                    result.warnings.append(
                        f"Block #{j + 1} in section "
                        f"'{section.title or section.section_id}': missing block_id"
                    )

                # 检查不可见元素的占比
                invisible = sum(1 for e in block.elements if not e.visible)
                if invisible > 0:
                    result.stats.setdefault("invisible_elements", 0)
                    result.stats["invisible_elements"] += invisible

        # 5. 设计令牌检查
        if document.design_tokens is None:
            result.warnings.append("Document has no design_tokens (will use defaults)")

        result.is_valid = len(result.errors) == 0
        if result.is_valid:
            logger.info(
                "Document validation passed",
                extra=result.stats,
            )
        else:
            logger.warning(
                "Document validation failed",
                extra={"errors": result.errors, **result.stats},
            )

        return result

    # ========================================================================
    # 渲染阶段辅助
    # ========================================================================

    def _resolve_renderer(self, format_name: str) -> "DocumentRenderer":
        """解析格式名为渲染器实例.

        优先级：
        1. 已注册的渲染器（register_renderer）
        2. 内置渲染器（Word/PPT/Markdown）

        Args:
            format_name: 格式名称（"word", "docx", "ppt", "pptx", "markdown", "md"）.

        Returns:
            DocumentRenderer 实例.

        Raises:
            ValueError: 不支持的格式.
        """
        # 规范化名称
        normalized = format_name.lower()
        if normalized in ("word", "docx"):
            normalized = "word"
        elif normalized in ("ppt", "pptx", "powerpoint"):
            normalized = "ppt"
        elif normalized in ("md", "markdown"):
            normalized = "markdown"

        # 已注册的渲染器优先
        if normalized in self._renderers:
            return self._renderers[normalized]

        # 内置渲染器作为后备
        if normalized == "word":
            from reporting.rendering.word_renderer import WordRenderer

            return WordRenderer()
        elif normalized == "ppt":
            from reporting.rendering.ppt_renderer import PPTRenderer

            return PPTRenderer()
        elif normalized == "markdown":
            from reporting.rendering.markdown_renderer import MarkdownRenderer

            return MarkdownRenderer()
        else:
            raise ValueError(f"Unsupported format: {format_name!r}")

    @staticmethod
    def _format_extension(format_name: str) -> str:
        """将格式名映射为文件扩展名."""
        mapping = {
            "word": "docx",
            "docx": "docx",
            "ppt": "pptx",
            "pptx": "pptx",
            "powerpoint": "pptx",
            "markdown": "md",
            "md": "md",
        }
        return mapping.get(format_name.lower(), format_name.lower())


# ============================================================================
# 便捷函数
# ============================================================================


def quick_render(
    document: Document,
    *formats: str,
    output_dir: Optional[Path] = None,
) -> PipelineResult:
    """快速渲染：直接从 Document 渲染为指定格式（跳过 Build 和 Validate）.

    Args:
        document: 源 Document.
        *formats: 输出格式（"word", "ppt", "markdown"）.
        output_dir: 输出目录.

    Returns:
        PipelineResult 包含输出路径.
    """
    pipeline = UnifiedPipeline(output_dir=output_dir)
    return pipeline.execute(
        task=document,
        output_formats=list(formats),
        strategy="dict",  # 不会被用到因为 task 本身就是 Document
    )
