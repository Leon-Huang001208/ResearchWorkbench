"""配置驱动的模板渲染器 — v2 报告生成引擎的核心.

打开精排 .docx 模板，根据 ReportTemplateConfig 执行每个 EnhancedPlaceholder
的生成策略，将生成内容（富文本/图表网格/图片）注入模板，输出最终 .docx。

这是 Phase 2 的主入口，协调 RichTextInjector 和 ChartGridInjector。

与旧路径 (WordProjection.save_from_template) 的关系：
    - 旧路径：{{key}} → str 扁平替换，段落格式完全依赖模板
    - 新路径：{{key}} → EnhancedPlaceholder，支持富文本/图表网格/条件显示
    - 两路径共存，通过 config 版本检测自动选择
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

from core.contracts.reporting import (
    EnhancedPlaceholder,
    GenerationMode,
    PlaceholderType,
    ReportTemplateConfig,
)
from core.observability import get_logger

logger = get_logger(__name__)

# XML 1.0 / OOXML 非法字符（C0+C1 控制字符 + 代理对 + 非字符）
_XML_INVALID_CONTROL = re.compile(
    r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\uD800-\uDFFF￾￿]"
)

try:
    from docx import Document as DocxDocument

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class ConfigDrivenTemplateRenderer:
    """配置驱动的模板渲染器.

    打开 .docx 模板，根据 ReportTemplateConfig 执行每个 EnhancedPlaceholder
    的生成策略，将生成内容注入模板，输出最终 .docx。

    Usage:
        config = ReportTemplateConfig.from_yaml("config/report_config.yaml")
        renderer = ConfigDrivenTemplateRenderer(
            config=config,
            generation_service=generation_service,
            chart_service=chart_service,
            project_dir=Path("report_projects/华安ETF周报"),
        )
        renderer.render(Path("output.docx"))
    """

    def __init__(
        self,
        config: ReportTemplateConfig,
        *,
        generation_service: Any = None,
        chart_service: Any = None,
        project_dir: Optional[Path] = None,
    ) -> None:
        """初始化渲染器.

        Args:
            config: v2 报告模板配置.
            generation_service: ReportProjectGenerationService 实例.
            chart_service: ReportProjectChartService 实例.
            project_dir: 项目根目录（用于解析相对路径）.
        """
        if not DOCX_AVAILABLE:
            raise ImportError(
                "python-docx is required for ConfigDrivenTemplateRenderer. "
                "Install with: pip install python-docx"
            )

        self._config = config
        self._generation_service = generation_service
        self._chart_service = chart_service
        self._project_dir = project_dir or Path.cwd()

        # 延迟导入避免循环依赖
        from reporting.rendering.chart_grid_injector import ChartGridInjector
        from reporting.rendering.rich_text_injector import RichTextInjector

        self._rich_text_injector = RichTextInjector()
        self._chart_grid_injector = ChartGridInjector(chart_service=chart_service)

        # 运行时上下文（用于条件评估）
        self._context: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def render(
        self,
        output_path: Path,
        *,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """执行完整渲染流程.

        Args:
            output_path: 输出文件路径.
            extra_context: 额外的运行时上下文（如 evidence_count）.

        Returns:
            输出文件路径.
        """
        logger.info(
            "ConfigDrivenTemplateRenderer: 开始渲染",
            extra={
                "template": self._config.template.word_template,
                "placeholder_count": len(self._config.placeholders),
            },
        )

        # 1. 打开模板
        template_path = self._resolve_template_path()
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")

        doc = DocxDocument(str(template_path))
        logger.info("模板已加载", extra={"path": str(template_path)})

        # 2. 初始化上下文
        self._context = extra_context or {}
        self._context["placeholder_count"] = len(self._config.placeholders)

        # 3. 按顺序处理每个占位符
        generated_count = 0
        error_count = 0
        for key, placeholder in self._config.placeholders.items():
            try:
                if self._process_placeholder(doc, key, placeholder):
                    generated_count += 1
                else:
                    logger.info("跳过占位符", extra={"key": key, "reason": "不可见"})
            except Exception:
                logger.exception("处理占位符失败", extra={"key": key})
                error_count += 1

        # 4. 后处理
        self._post_process(doc)

        # 5. 保存
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))

        logger.info(
            "ConfigDrivenTemplateRenderer: 渲染完成",
            extra={
                "output": str(output_path),
                "generated": generated_count,
                "errors": error_count,
                "total": len(self._config.placeholders),
            },
        )
        return output_path

    # ------------------------------------------------------------------
    # 占位符处理
    # ------------------------------------------------------------------

    def _process_placeholder(
        self,
        doc: Any,
        key: str,
        placeholder: EnhancedPlaceholder,
    ) -> bool:
        """处理单个增强占位符.

        Args:
            doc: Word Document 对象.
            key: 占位符 key.
            placeholder: 增强占位符定义.

        Returns:
            True 表示已处理（生成了内容），False 表示跳过.
        """
        # 条件可见性检查
        if not self._evaluate_visibility(placeholder):
            self._handle_hidden_placeholder(doc, key, placeholder)
            return False

        # 获取完整的生成/格式配置（合并 defaults）
        gen_mode = placeholder.generation_mode
        gen_config = placeholder.generation_config

        # 根据占位符类型分发处理
        if placeholder.type in (PlaceholderType.TEXT, PlaceholderType.RICH_TEXT):
            return self._process_text_placeholder(doc, key, placeholder, gen_mode, gen_config)
        elif placeholder.type == PlaceholderType.CHART_GRID:
            return self._process_chart_grid_placeholder(doc, key, placeholder)
        elif placeholder.type == PlaceholderType.IMAGE:
            return self._process_image_placeholder(doc, key, placeholder)
        elif placeholder.type == PlaceholderType.CHART:
            return self._process_chart_placeholder(doc, key, placeholder)
        elif placeholder.type == PlaceholderType.TABLE_DATA:
            return self._process_table_placeholder(doc, key, placeholder)
        else:
            logger.warning("未知占位符类型", extra={"key": key, "type": placeholder.type})
            return False

    def _process_text_placeholder(
        self,
        doc: Any,
        key: str,
        placeholder: EnhancedPlaceholder,
        gen_mode: GenerationMode,
        gen_config: Any,
    ) -> bool:
        """处理 TEXT / RICH_TEXT 类型占位符.

        1. 根据 generation_mode 获取内容
        2. 使用 RichTextInjector 注入到模板段落
        """
        # 生成内容
        generated_text = self._generate_content(key, placeholder, gen_mode, gen_config)

        # 校验内容
        if placeholder.validation and generated_text:
            generated_text = self._validate_content(generated_text, placeholder.validation, key)

        # 找到模板中的占位符段落并注入
        para = self._find_placeholder_in_doc(doc, key)
        if para is None:
            logger.warning("未找到占位符段落", extra={"key": key})
            return False

        if placeholder.rich_text_spec:
            # RICH_TEXT 模式：多 Run 注入
            self._rich_text_injector.inject(
                paragraph=para,
                placeholder_key=key,
                spec=placeholder.rich_text_spec,
                generated_text=generated_text,
                preserve_paragraph_style=placeholder.use_template_paragraph_style,
            )
        else:
            # TEXT 模式：简单文本替换（兼容旧行为）
            self._simple_text_replace(para, key, generated_text)

        self._context[key] = generated_text
        self._context[f"{key}_char_count"] = len(generated_text) if generated_text else 0
        return True

    def _process_chart_grid_placeholder(
        self,
        doc: Any,
        key: str,
        placeholder: EnhancedPlaceholder,
    ) -> bool:
        """处理 CHART_GRID 类型占位符."""
        if not placeholder.chart_grid_spec:
            logger.warning("CHART_GRID 缺少 chart_grid_spec", extra={"key": key})
            return False

        self._chart_grid_injector.inject_at_placeholder(
            doc=doc,
            placeholder_key=key,
            spec=placeholder.chart_grid_spec,
            project_dir=self._project_dir,
        )
        return True

    def _process_image_placeholder(
        self,
        doc: Any,
        key: str,
        placeholder: EnhancedPlaceholder,
    ) -> bool:
        """处理 IMAGE 类型占位符.

        将图片嵌入到占位符段落位置。
        """
        para = self._find_placeholder_in_doc(doc, key)
        if para is None:
            logger.warning("未找到图片占位符段落", extra={"key": key})
            return False

        if not placeholder.data_source or not placeholder.data_source.file_path:
            logger.warning("IMAGE 缺少 file_path", extra={"key": key})
            return False

        try:
            from docx.shared import Inches

            run = para.add_run()
            image_path = self._project_dir / placeholder.data_source.file_path
            run.add_picture(str(image_path), width=Inches(6.0))
            # 清除占位符文本
            for r in para.runs:
                if f"{{{{{key}}}}}" in (r.text or ""):
                    r.text = ""
            self._rich_text_injector._remove_empty_runs(para)
        except Exception:
            logger.exception("图片嵌入失败", extra={"key": key})
            return False

        return True

    def _process_chart_placeholder(
        self,
        doc: Any,
        key: str,
        placeholder: EnhancedPlaceholder,
    ) -> bool:
        """处理 CHART 类型占位符（单个图表）."""
        # 单个图表包装为 1×1 的 ChartGridSpec
        from core.contracts.reporting import ChartCellSpec, ChartGridSpec

        if not placeholder.data_source:
            logger.warning("CHART 缺少 data_source", extra={"key": key})
            return False

        cell_spec = ChartCellSpec(
            title=placeholder.title or key,
            chart_id=key,
            chart_type="line",
            data_source=placeholder.data_source,
            rendering_mode="matplotlib_image",
        )

        grid_spec = ChartGridSpec(rows=1, cols=1, cells=[cell_spec])
        self._chart_grid_injector.inject_at_placeholder(
            doc=doc,
            placeholder_key=key,
            spec=grid_spec,
            project_dir=self._project_dir,
        )
        return True

    def _process_table_placeholder(
        self,
        doc: Any,
        key: str,
        placeholder: EnhancedPlaceholder,
    ) -> bool:
        """处理 TABLE_DATA 类型占位符.

        当前为占位实现，后续 Phase 整合 TableDataBlock 渲染。
        """
        logger.info("TABLE_DATA 占位符处理（占位实现）", extra={"key": key})
        return True

    # ------------------------------------------------------------------
    # 内容生成
    # ------------------------------------------------------------------

    def _generate_content(
        self,
        key: str,
        placeholder: EnhancedPlaceholder,
        gen_mode: GenerationMode,
        gen_config: Any,
    ) -> str:
        """根据生成模式获取内容.

        Args:
            key: 占位符 key.
            placeholder: 占位符定义.
            gen_mode: 生成模式.
            gen_config: 生成配置.

        Returns:
            生成的内容文本.
        """
        if gen_mode == GenerationMode.STATIC:
            # 静态文本：从 rich_text_spec 的静态 Run 中提取
            if placeholder.rich_text_spec:
                parts = [
                    r.text or ""
                    for r in placeholder.rich_text_spec.runs
                    if not r.is_dynamic and r.text
                ]
                return "".join(parts)
            return ""

        elif gen_mode == GenerationMode.EVIDENCE_GROUNDED:
            return self._generate_via_llm(key, placeholder, gen_config)

        elif gen_mode == GenerationMode.LLM_DIRECT:
            return self._generate_via_llm(key, placeholder, gen_config)

        elif gen_mode == GenerationMode.DATA_DRIVEN:
            return self._generate_from_data(key, placeholder)

        else:
            logger.warning("未知生成模式", extra={"key": key, "mode": gen_mode})
            return ""

    def _generate_via_llm(
        self,
        key: str,
        placeholder: EnhancedPlaceholder,
        gen_config: Any,
    ) -> str:
        """通过 LLM（可能含证据检索）生成内容.

        优先使用 context 中的预生成文本（来自 _execute_word_v2 的批量生成），
        避免二次调用 LLM。

        Args:
            key: 占位符 key.
            placeholder: 占位符定义.
            gen_config: GenerationConfig 或 None.

        Returns:
            LLM 生成的文本.
        """
        # 优先使用预生成文本
        pre_generated = self._context.get("generated_texts", {}).get(key, "")
        if pre_generated:
            logger.info("使用预生成文本", extra={"key": key, "chars": len(pre_generated)})
            return pre_generated

        if self._generation_service is None:
            logger.warning("无 generation_service，跳过 LLM 生成", extra={"key": key})
            return f"[{placeholder.title or key} — 待生成]"

        try:
            # 委托给现有的 ReportProjectGenerationService
            result = self._generation_service.generate_placeholder_content(
                key=key,
                title=placeholder.title,
                gen_config=gen_config,
                defaults=self._config.defaults,
                context=self._context,
            )
            if result:
                logger.info("LLM 生成成功", extra={"key": key, "chars": len(result)})
                return result
            else:
                logger.warning("LLM 生成返回空", extra={"key": key})
                return ""
        except Exception:
            logger.exception("LLM 生成失败", extra={"key": key})
            return f"[{placeholder.title or key} — 生成失败]"

    def _generate_from_data(
        self,
        key: str,
        placeholder: EnhancedPlaceholder,
    ) -> str:
        """从数据源生成内容（Excel/DB 模板化文本）.

        当前为占位实现。
        """
        logger.info("DATA_DRIVEN 生成（占位实现）", extra={"key": key})
        return ""

    # ------------------------------------------------------------------
    # 内容校验
    # ------------------------------------------------------------------

    def _validate_content(
        self,
        text: str,
        validation: Any,
        key: str,
    ) -> str:
        """校验生成内容并执行清理.

        Args:
            text: 原始文本.
            validation: ValidationSpec.
            key: 占位符 key.

        Returns:
            校验并清理后的文本.
        """

        # 禁用词过滤
        if validation.forbidden_terms:
            for term in validation.forbidden_terms:
                if term in text:
                    logger.warning("内容包含禁用词", extra={"key": key, "term": term})
                    text = text.replace(term, "***")

        # LLM 指令泄露检查
        if validation.forbid_instruction_leaks:
            leak_patterns = ["严格依据", "根据检索结果", "请根据", "以下是"]
            for pattern in leak_patterns:
                if text.strip().startswith(pattern):
                    # 尝试去掉第一行
                    lines = text.split("\n", 1)
                    if len(lines) > 1:
                        text = lines[1].strip()
                        logger.info("移除疑似指令泄露首行", extra={"key": key})

        # 长度检查
        if validation.min_chars and len(text) < validation.min_chars:
            logger.warning("内容过短", extra={"key": key, "chars": len(text)})

        return text

    # ------------------------------------------------------------------
    # 可见性控制
    # ------------------------------------------------------------------

    def _evaluate_visibility(self, placeholder: EnhancedPlaceholder) -> bool:
        """评估占位符的可见性条件.

        支持 visible 和 visible_if (Jinja2 表达式) 两种方式。

        Args:
            placeholder: 占位符定义.

        Returns:
            True 表示可见，False 表示隐藏.
        """
        if not placeholder.visible:
            return False

        if placeholder.visible_if:
            try:
                import jinja2

                env = jinja2.Environment()
                template = env.compile_expression(placeholder.visible_if)
                result = template(**self._context)
                return bool(result)
            except Exception:
                logger.exception(
                    "visible_if 表达式评估失败",
                    extra={"key": placeholder.key, "expr": placeholder.visible_if},
                )
                return placeholder.visible  # 评估失败时 fallback 到 visible

        return True

    def _handle_hidden_placeholder(
        self,
        doc: Any,
        key: str,
        placeholder: EnhancedPlaceholder,
    ) -> None:
        """处理不可见的占位符.

        根据 hide_strategy 决定处理方式：
        - remove_placeholder: 清空占位符文本
        - remove_paragraph: 删除占位符所在段落
        - remove_section: 删除占位符所在节（暂不实现）
        """
        strategy = placeholder.hide_strategy

        if strategy == "remove_paragraph":
            para = self._find_placeholder_in_doc(doc, key)
            if para is not None:
                para._element.getparent().remove(para._element)
                logger.info("隐藏占位符段落已删除", extra={"key": key})
        elif strategy == "remove_placeholder":
            para = self._find_placeholder_in_doc(doc, key)
            if para is not None:
                for run in para.runs:
                    if f"{{{{{key}}}}}" in (run.text or ""):
                        run.text = ""
                self._rich_text_injector._remove_empty_runs(para)
                logger.info("隐藏占位符文本已清空", extra={"key": key})

    # ------------------------------------------------------------------
    # 模板操作工具
    # ------------------------------------------------------------------

    def _resolve_template_path(self) -> Path:
        """解析模板文件路径.

        优先从 project_dir 查找，其次从 config 中的路径。

        Returns:
            模板文件绝对路径.
        """
        template_name = self._config.template.word_template

        # 1. 尝试 project_dir/templates/{name}
        candidate = self._project_dir / "templates" / template_name
        if candidate.exists():
            return candidate

        # 2. 尝试 project_dir/{name}
        candidate = self._project_dir / template_name
        if candidate.exists():
            return candidate

        # 3. 以绝对路径尝试
        candidate = Path(template_name)
        return candidate

    def _find_placeholder_in_doc(self, doc: Any, key: str) -> Any:
        """在文档中查找占位符段落.

        与 ChartGridInjector._find_placeholder_paragraph 逻辑相同，
        保留在渲染器中作为独立工具方法。

        Args:
            doc: Word Document.
            key: 占位符 key.

        Returns:
            Paragraph 对象或 None.
        """
        patterns = [f"{{{{{key}}}}}", f"{{{key}}}"]

        for para in doc.paragraphs:
            for pattern in patterns:
                if pattern in (para.text or ""):
                    return para

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        for pattern in patterns:
                            if pattern in (para.text or ""):
                                return para

        return None

    @staticmethod
    def _simple_text_replace(paragraph: Any, key: str, replacement: str) -> None:
        """简单的文本占位符替换（兼容旧行为）.

        Args:
            paragraph: 段落对象.
            key: 占位符 key.
            replacement: 替换文本.
        """
        patterns = [f"{{{{{key}}}}}", f"{{{key}}}"]
        full_text = paragraph.text

        for pattern in patterns:
            if pattern in full_text:
                if full_text.strip() == pattern.strip():
                    # 整段替换
                    for run in paragraph.runs:
                        run.clear()
                    if paragraph.runs:
                        paragraph.runs[0].text = _XML_INVALID_CONTROL.sub("", replacement)
                    else:
                        paragraph.add_run(_XML_INVALID_CONTROL.sub("", replacement))
                else:
                    # 部分替换
                    new_text = _XML_INVALID_CONTROL.sub("", full_text.replace(pattern, replacement))
                    for run in paragraph.runs[1:]:
                        run._element.getparent().remove(run._element)
                    if paragraph.runs:
                        paragraph.runs[0].text = new_text
                    else:
                        paragraph.add_run(new_text)
                break

        # 清理空 Run
        runs_to_remove = []
        for run in paragraph.runs:
            if not run.text or not run.text.strip():
                runs_to_remove.append(run)
        for run in runs_to_remove:
            run._element.getparent().remove(run._element)

    def _post_process(self, doc: Any) -> None:
        """文档后处理.

        - 清理所有空 Run（WPS 兼容）
        - 更新时间戳字段
        """
        # 清理正文中的空 Run
        for para in doc.paragraphs:
            self._rich_text_injector._remove_empty_runs(para)

        # 清理表格中的空 Run
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        self._rich_text_injector._remove_empty_runs(para)

        logger.info("后处理完成")
