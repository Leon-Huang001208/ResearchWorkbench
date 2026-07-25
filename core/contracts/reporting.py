"""
Core contracts for reporting (section specs and outputs).

This module defines Pydantic models for report section specifications and
section outputs in AlphaFoundry.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from core.contracts.content_element import ContentElement
from core.contracts.retrieval import RetrievalProfileType

if TYPE_CHECKING:
    # Avoid circular import at runtime; compiler.py imports from reporting.py.
    from core.contracts.compiler import Citation, CompiledSection, FactRecord, Provenance


class SectionSpec(BaseModel):
    """报告段落规范 - 定义报告各段落的要求.

    Defines the requirements for a report section, including key, title,
    target word count, required facets, scenario requirement, and evidence policy.

    Attributes:
        key: Unique key for the section.
        title: Title of the section.
        target_words: Target word count for the section.
        required_facets: List of required facets for the section.
        scenario_required: Whether a scenario is required (default True).
        evidence_policy: Evidence policy ("strict", "allow_synthesis") (default "strict").
        retrieval_profile: Retrieval profile type for this section.
        prompt_template: Custom prompt template for this section.
        forbidden_terms: List of forbidden terms.
        structure: Structure guidance for the section.
        placeholder: Placeholder name for Word template.
    """

    key: str = Field(description="Unique key for the section")
    title: str = Field(description="Title of the section")
    target_words: int = Field(description="Target word count for the section")
    required_facets: list[str] = Field(
        default_factory=list, description="List of required facets for the section"
    )
    scenario_required: bool = Field(default=True, description="Whether a scenario is required")
    evidence_policy: Literal["strict", "allow_synthesis"] = Field(
        default="strict", description="Evidence policy (strict, allow_synthesis)"
    )
    retrieval_profile: Optional[RetrievalProfileType] = Field(
        default=None, description="Retrieval profile for this section"
    )
    prompt_template: Optional[str] = Field(default=None, description="Custom prompt template")
    forbidden_terms: List[str] = Field(default_factory=list, description="Forbidden terms")
    structure: Optional[str] = Field(default=None, description="Structure guidance")
    placeholder: Optional[str] = Field(
        default=None, description="Placeholder name for Word template"
    )


class SectionOutput(BaseModel):
    """报告段落输出 - 生成的单个段落.

    Represents the output for a single report section, including key, content,
    evidence references, scenario references, and warnings.

    Attributes:
        key: Unique key for the section.
        content: Generated content for the section.
        evidence_refs: List of evidence references used.
        scenario_refs: List of scenario references used.
        warnings: List of warnings generated during section creation.
        fact_card: Fact card used for generation.
        validation_results: Validation results.
    """

    key: str = Field(description="Unique key for the section")
    title: str = Field(description="Title of the section")
    content: str = Field(description="Generated content for the section")
    evidence_refs: list[str] = Field(
        default_factory=list, description="List of evidence references used"
    )
    scenario_refs: list[str] = Field(
        default_factory=list, description="List of scenario references used"
    )
    warnings: list[str] = Field(
        default_factory=list, description="List of warnings generated during section creation"
    )
    fact_card: Optional["FactCard"] = Field(default=None, description="Fact card used")
    validation_results: Optional["ValidationResults"] = Field(
        default=None, description="Validation results"
    )
    # Compiler integration (backward-compatible additions)
    compiled_section: Optional["CompiledSection"] = Field(
        default=None,
        description="Compiled section from the report compiler (outline-first pipeline)",
    )
    citations: list["Citation"] = Field(
        default_factory=list,
        description="Structured citations bound by the compiler citation binder",
    )
    # Phase 1: Universal document framework — content_elements field
    content_elements: list[ContentElement] = Field(
        default_factory=list,
        description="New-format content elements (universal document model). "
        "When populated, takes priority over content: str for rendering.",
    )


class FactCard(BaseModel):
    """事实卡片 - 段落生成的中间层.

    Extracted facts before paragraph generation, providing a structured
    intermediate representation that can be reviewed and validated.

    Attributes:
        key_changes: Key changes identified.
        drivers: Drivers of the changes.
        impacts: Impacts of the changes.
        watch_points: Points to watch.
        risks: Identified risks.
        source_refs: References to sources.
    """

    key_changes: List[str] = Field(default_factory=list, description="Key changes identified")
    drivers: List[str] = Field(default_factory=list, description="Drivers of the changes")
    impacts: List[str] = Field(default_factory=list, description="Impacts of the changes")
    watch_points: List[str] = Field(default_factory=list, description="Points to watch")
    risks: List[str] = Field(default_factory=list, description="Identified risks")
    source_refs: List[str] = Field(default_factory=list, description="References to sources")
    # Compiler integration (backward-compatible additions)
    fact_records: List["FactRecord"] = Field(
        default_factory=list,
        description="Structured fact records from the compiler fact extractor",
    )
    provenance_summary: List["Provenance"] = Field(
        default_factory=list,
        description="Provenance summary for the facts in this card",
    )


class ValidationResult(BaseModel):
    """单个校验结果.

    Attributes:
        check_name: Name of the check.
        passed: Whether the check passed.
        message: Message about the result.
        severity: Severity level.
    """

    check_name: str = Field(description="Name of the check")
    passed: bool = Field(description="Whether the check passed")
    message: str = Field(description="Message about the result")
    severity: Literal["error", "warning", "info"] = Field(
        default="warning", description="Severity level"
    )


class ValidationResults(BaseModel):
    """完整校验结果.

    Attributes:
        overall_passed: Whether overall validation passed.
        results: List of individual validation results.
        word_count: Word count of the content.
    """

    overall_passed: bool = Field(description="Whether overall validation passed")
    results: List[ValidationResult] = Field(
        default_factory=list, description="List of validation results"
    )
    word_count: Optional[int] = Field(default=None, description="Word count of the content")


class TemplateConfig(BaseModel):
    """报告模板配置.

    Complete configuration for a report template, including metadata,
    section specs, and output preferences.

    Attributes:
        name: Name of the template.
        description: Description of the template.
        version: Version of the template.
        target_audience: Target audience.
        sections: List of section specs.
        default_retrieval_profile: Default retrieval profile.
        word_template_path: Path to Word template file.
        excel_template_path: Path to Excel template file.
        placeholders: Mapping of section keys to Word placeholders.
        sort_order: Sort order for displaying templates.
        metadata: Additional metadata.
    """

    name: str = Field(description="Name of the template")
    description: str = Field(description="Description of the template")
    version: str = Field(default="1.0", description="Version of the template")
    target_audience: Optional[str] = Field(default=None, description="Target audience")
    sections: List[SectionSpec] = Field(description="List of section specs")
    default_retrieval_profile: RetrievalProfileType = Field(
        default=RetrievalProfileType.WEEKLY_REPORT, description="Default retrieval profile"
    )
    word_template_path: Optional[str] = Field(default=None, description="Path to Word template")
    excel_template_path: Optional[str] = Field(default=None, description="Path to Excel template")
    placeholders: Dict[str, str] = Field(
        default_factory=dict, description="Section key to placeholder mapping"
    )
    sort_order: int = Field(default=0, description="Sort order for displaying templates")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    # ── v2 便捷属性 ──

    @property
    def is_v2(self) -> bool:
        """是否 v2 模板（version >= 2.0）."""
        try:
            return float(self.version.split(".")[0]) >= 2
        except (ValueError, IndexError):
            return False

    def get_design_tokens(self) -> Optional[Any]:
        """从 metadata 中提取设计令牌.

        Returns:
            DesignTokens 实例或 None.
        """
        dt_dict = self.metadata.get("design_tokens")
        if dt_dict and isinstance(dt_dict, dict):
            from core.contracts.document import DesignTokens

            try:
                return DesignTokens(**dt_dict)
            except Exception:
                pass
        return None


class ReportTask(BaseModel):
    """报告生成任务.

    Represents a complete report generation task, including configuration,
    context, and tracking information.

    Attributes:
        task_id: Unique task ID.
        template_name: Name of the template to use.
        context: Context data for generation.
        created_at: Creation timestamp.
        started_at: Start timestamp.
        completed_at: Completion timestamp.
        status: Current status.
        error_message: Error message if failed.
    """

    task_id: str = Field(description="Unique task ID")
    template_name: str = Field(description="Name of the template")
    context: Dict[str, Any] = Field(default_factory=dict, description="Context data")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    status: Literal["pending", "running", "completed", "failed"] = Field(
        default="pending", description="Current status"
    )
    error_message: Optional[str] = Field(default=None, description="Error message if failed")


class ReportRunLog(BaseModel):
    """报告生成运行日志.

    Complete log of a report generation run for auditing and debugging.

    Attributes:
        task_id: Task ID.
        template_name: Template used.
        sections_log: Log for each section.
        generated_at: Generation timestamp.
        sources_used: List of sources used.
    """

    task_id: str = Field(description="Task ID")
    template_name: str = Field(description="Template used")
    sections_log: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Log for each section"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Generation timestamp"
    )
    sources_used: List[str] = Field(default_factory=list, description="List of sources used")
    # Compiler integration (backward-compatible additions)
    compiler_version: Optional[str] = Field(
        default=None, description="Compiler version that produced this run"
    )
    outline: Optional[Dict[str, Any]] = Field(
        default=None, description="Serialized report outline (if produced by compiler)"
    )


class ChartSpec(BaseModel):
    """图表规范.

    Specification for a chart in Excel output.
    Placeholder naming convention: {{chart_{chart_id}}}

    Attributes:
        chart_id: Unique chart ID.
        chart_type: Type of chart.
        title: Chart title.
        data_range: Data range reference.
        placeholder: Placeholder in Word template (auto-generated if not provided).
    """

    chart_id: str = Field(description="Unique chart ID")
    chart_type: Literal["line", "bar", "pie", "scatter", "area"] = Field(
        description="Type of chart"
    )
    title: str = Field(description="Chart title")
    data_range: str = Field(description="Data range reference")
    placeholder: Optional[str] = Field(
        default=None,
        description="Placeholder in Word template (auto-generated as '{{chart_{chart_id}}}' if not provided)",
    )

    @property
    def normalized_placeholder(self) -> str:
        """获取标准化的占位符名称."""
        return self.placeholder or f"chart_{self.chart_id}"


class TableSpec(BaseModel):
    """表格规范.

    Specification for a table in report output.
    Placeholder naming convention: {{table_{table_id}}}

    Attributes:
        table_id: Unique table ID.
        title: Table title.
        headers: Column headers.
        rows: Table data rows.
        placeholder: Placeholder in Word template (auto-generated if not provided).
    """

    table_id: str = Field(description="Unique table ID")
    title: str = Field(description="Table title")
    headers: List[str] = Field(default_factory=list, description="Column headers")
    rows: List[List[Any]] = Field(default_factory=list, description="Table data rows")
    placeholder: Optional[str] = Field(
        default=None,
        description="Placeholder in Word template (auto-generated as '{{table_{table_id}}}' if not provided)",
    )

    @property
    def normalized_placeholder(self) -> str:
        """获取标准化的占位符名称."""
        return self.placeholder or f"table_{self.table_id}"


class TextPlaceholder(BaseModel):
    """文本占位符规范.

    Placeholder naming convention: {{text_{key}}} or directly use section.key
    """

    key: str = Field(description="Placeholder key")
    content: str = Field(description="Text content")
    placeholder: Optional[str] = Field(
        default=None,
        description="Placeholder in Word template (auto-generated as '{{text_{key}}}' if not provided)",
    )

    @property
    def normalized_placeholder(self) -> str:
        """获取标准化的占位符名称."""
        return self.placeholder or f"text_{self.key}"


# ============================================================================
# Phase 1: Enhanced Placeholder Framework (v2 config-driven reporting)
# ============================================================================


class PlaceholderType(str, Enum):
    """占位符内容类型枚举.

    定义模板占位符可以承载的内容类型。每种类型对应不同的渲染方式：
    - TEXT: 纯文本段落（继承模板段落样式）
    - RICH_TEXT: 富文本段落（多 Run，支持内联格式控制）
    - CHART: 单个图表
    - CHART_GRID: 多图表网格布局（如 2×2 图表矩阵）
    - IMAGE: 图片
    - TABLE_DATA: 数据表格（非图表容器，真正的数据展示表格）
    - COMPOSITE: 复合区域（包含多个子块）
    """

    TEXT = "text"
    RICH_TEXT = "rich_text"
    CHART = "chart"
    CHART_GRID = "chart_grid"
    IMAGE = "image"
    TABLE_DATA = "table_data"
    COMPOSITE = "composite"


class GenerationMode(str, Enum):
    """内容生成模式枚举.

    - STATIC: 静态文本（直接从配置取值）
    - EVIDENCE_GROUNDED: 证据检索 + LLM 生成（核心路径）
    - DATA_DRIVEN: Excel/DB 数据 → 模板化文本
    - LLM_DIRECT: 纯 LLM 生成（给定 prompt，不检索）
    - CHART_EXCEL: 从 Excel 渲染图表（不涉及 LLM）
    """

    STATIC = "static"
    EVIDENCE_GROUNDED = "evidence_grounded"
    DATA_DRIVEN = "data_driven"
    LLM_DIRECT = "llm_direct"
    CHART_EXCEL = "chart_excel"


class InlineRunSpec(BaseModel):
    """内联文本片段规格 — 定义单个 Run 的格式和内容来源.

    映射到 python-docx 的 Run 对象。每个 InlineRunSpec 描述一段文本的
    格式属性（粗体/斜体/字号/颜色/字体）和内容来源（静态文本或动态生成）。

    在 RichTextSpec 中，runs 列表的顺序决定 Word 段落中 Run 的顺序。

    Attributes:
        text: 静态文本内容（generation_mode=STATIC 时使用）.
        placeholder_key: 引用其他占位符的输出（用于组合内容）.
        bold: 是否粗体.
        italic: 是否斜体.
        font_size_pt: 字号（pt），None 表示继承模板.
        color_hex: 文字颜色（hex），如 "#5B9BD5".
        font_name: 字体名称，如 "Times New Roman".
        is_dynamic: 是否为动态 Run（True 表示 text 由 generation 填充）.
    """

    text: Optional[str] = Field(default=None, description="静态文本内容")
    placeholder_key: Optional[str] = Field(default=None, description="引用其他占位符的输出")
    bold: Optional[bool] = Field(default=None, description="是否粗体")
    italic: Optional[bool] = Field(default=None, description="是否斜体")
    font_size_pt: Optional[float] = Field(default=None, description="字号（pt）")
    color_hex: Optional[str] = Field(default=None, description="文字颜色（hex）")
    font_name: Optional[str] = Field(default=None, description="字体名称")
    is_dynamic: bool = Field(default=False, description="是否为动态 Run（由 generation 填充 text）")


class RichTextSpec(BaseModel):
    """富文本规格 — 描述一个段落的 Run 序列.

    用于 RICH_TEXT 类型的占位符。定义了段落中每个 Run 的顺序和格式。
    静态 Run 提供固定标签（如加粗的 "A股方面："），动态 Run 承载 LLM 生成的内容。

    当 runs 列表为空时，表示 LLM 输出纯文本，完全继承模板段落样式。

    Attributes:
        runs: Run 序列（按顺序渲染）.
        default_font: 默认字体（用于动态 Run）.
        default_size_pt: 默认字号（用于动态 Run）.
    """

    runs: List[InlineRunSpec] = Field(default_factory=list, description="Run 序列（按顺序渲染）")
    default_font: str = Field(default="Times New Roman", description="默认字体")
    default_size_pt: float = Field(default=11.0, description="默认字号（pt）")


class DataSourceSpec(BaseModel):
    """统一数据来源定义.

    支持多种数据源类型：Excel 区域/单元格、数据库查询、静态值、文件路径。
    用于图表、表格和 data_driven 文本块的数据绑定。

    Attributes:
        source_type: 数据源类型.
        workbook: Excel 文件路径（相对 project dir）.
        worksheet: Excel 工作表名.
        range_or_cell: Excel 区域或单元格引用，如 "B2:D10" 或 "B2".
        native_chart_part: 原生图表 XML 路径（word/charts/chart1.xml）.
        file_path: 图片文件路径.
        static_value: 静态值.
    """

    source_type: Literal["excel_range", "excel_cell", "db_query", "static", "file"] = Field(
        description="数据源类型"
    )
    workbook: Optional[str] = Field(default=None, description="Excel 文件路径")
    worksheet: Optional[str] = Field(default=None, description="Excel 工作表名")
    range_or_cell: Optional[str] = Field(default=None, description="Excel 区域或单元格引用")
    native_chart_part: Optional[str] = Field(default=None, description="原生图表 XML 路径")
    file_path: Optional[str] = Field(default=None, description="文件路径（图片等）")
    static_value: Optional[Any] = Field(default=None, description="静态值")


class ChartCellSpec(BaseModel):
    """图表网格中的单个单元格.

    对应目标 docx 中 2×2 图表网格的每一个图表位。
    每个单元格包含标题、图表配置和数据来源。

    Attributes:
        title: 图表标题（显示在图表上方）.
        chart_id: 唯一图表标识.
        chart_type: 图表类型.
        data_source: 数据来源.
        rendering_mode: 渲染方式.
        width_inches: 图表宽度（英寸）.
        height_inches: 图表高度（英寸）.
    """

    title: str = Field(description="图表标题")
    chart_id: str = Field(description="唯一图表标识")
    chart_type: Literal[
        "line", "bar", "pie", "scatter", "area", "column_bar", "dual_axis_line"
    ] = Field(description="图表类型")
    data_source: DataSourceSpec = Field(description="数据来源")
    rendering_mode: Literal["native_chart", "matplotlib_image", "embedded_image"] = Field(
        default="matplotlib_image", description="渲染方式"
    )
    width_inches: float = Field(default=3.0, description="图表宽度（英寸）")
    height_inches: float = Field(default=2.0, description="图表高度（英寸）")


class ChartGridSpec(BaseModel):
    """多图表网格布局规格.

    对应目标 docx 中用无边框表格实现的图表矩阵布局。
    例如：2×2 的 A股/海外指数走势 + 涨跌幅对比图网格。

    cells 按 row-major 顺序排列（先填满第一行，再第二行）。

    Attributes:
        rows: 行数.
        cols: 列数.
        cells: 单元格列表（row-major）.
        col_widths: 列宽（英寸），None 为均分.
    """

    rows: int = Field(description="行数")
    cols: int = Field(description="列数")
    cells: List[ChartCellSpec] = Field(description="单元格列表（row-major）")
    col_widths: Optional[List[float]] = Field(default=None, description="列宽（英寸）")


class RetrievalConfig(BaseModel):
    """证据检索配置.

    用于 EVIDENCE_GROUNDED 模式的占位符，定义检索策略和参数。

    Attributes:
        mode: 检索模式（keyword/semantic/hybrid）.
        top_k: 返回结果数.
        candidate_k: 候选池大小.
        keyword_weight: 关键词检索权重（hybrid 模式）.
        semantic_weight: 语义检索权重（hybrid 模式）.
        keywords: 关键词列表.
        keyword_groups: 关键词组（组内 OR，组间 AND）.
        exclude_keywords: 排除关键词.
        rerank_enabled: 是否启用重排序.
        rerank_top_n: 重排序后保留数.
        rerank_min_score: 重排序最低分数阈值.
    """

    mode: Literal["keyword", "semantic", "hybrid"] = Field(default="hybrid", description="检索模式")
    top_k: int = Field(default=10, description="返回结果数")
    candidate_k: int = Field(default=40, description="候选池大小")
    keyword_weight: float = Field(default=0.6, description="关键词检索权重")
    semantic_weight: float = Field(default=0.4, description="语义检索权重")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    keyword_groups: List[List[str]] = Field(default_factory=list, description="关键词组（组内 OR，组间 AND）")
    exclude_keywords: List[str] = Field(default_factory=list, description="排除关键词")
    rerank_enabled: bool = Field(default=True, description="是否启用重排序")
    rerank_top_n: int = Field(default=30, description="重排序后保留数")
    rerank_min_score: float = Field(default=0.35, description="重排序最低分数阈值")


class GenerationConfig(BaseModel):
    """LLM 内容生成配置.

    定义单个占位符的 LLM 生成参数。prompt_template_ref 引用 prompt_templates.md
    中的 ## 标题，prompt_template_inline 则直接内联 prompt。

    Attributes:
        prompt_template_ref: 引用 prompt_templates.md 中的 ## 标题.
        prompt_template_inline: 内联 prompt 模板（不使用外部文件时）.
        retrieval: 证据检索配置.
        target_words: 目标字数.
        max_words: 最大字数.
        writing_structure: 写作要点列表.
        output_mode: 输出模式（单段落/多段落）.
    """

    prompt_template_ref: Optional[str] = Field(
        default=None, description="引用 prompt_templates.md 中的 ## 标题"
    )
    prompt_template_inline: Optional[str] = Field(default=None, description="内联 prompt 模板")
    retrieval: Optional[RetrievalConfig] = Field(default=None, description="证据检索配置")
    target_words: int = Field(default=200, description="目标字数")
    max_words: int = Field(default=300, description="最大字数")
    writing_structure: List[str] = Field(default_factory=list, description="写作要点列表")
    output_mode: Literal["single_paragraph", "multi_paragraph"] = Field(
        default="single_paragraph", description="输出模式"
    )


class ValidationSpec(BaseModel):
    """内容校验规则.

    定义生成后内容的校验规则，包括禁用词、长度限制和数据要求。

    Attributes:
        forbidden_terms: 禁用词列表.
        min_chars: 最小字符数.
        max_chars: 最大字符数.
        require_numbers: 是否必须包含数字.
        forbid_instruction_leaks: 是否禁止 LLM 指令泄露.
    """

    forbidden_terms: List[str] = Field(default_factory=list, description="禁用词列表")
    min_chars: Optional[int] = Field(default=None, description="最小字符数")
    max_chars: Optional[int] = Field(default=None, description="最大字符数")
    require_numbers: bool = Field(default=False, description="是否必须包含数字")
    forbid_instruction_leaks: bool = Field(default=True, description="是否禁止 LLM 指令泄露")


class EnhancedPlaceholder(BaseModel):
    """增强的占位符定义 — v2 配置框架的核心.

    替代扁平的 {{key}} → str 映射。每个占位符是一个有类型的内容区域，
    携带完整的生成策略、格式定义、数据绑定和校验规则。

    不同类型使用不同的配置字段：
    - TEXT/RICH_TEXT → rich_text_spec + generation_config
    - CHART → data_source
    - CHART_GRID → chart_grid_spec
    - IMAGE → data_source
    - TABLE_DATA → data_source

    Attributes:
        key: 对应模板中的 {{key}} 占位符名.
        type: 占位符内容类型.
        title: 人类可读名称（用于日志和 UI）.
        generation_mode: 内容生成模式.
        generation_config: LLM 生成配置（EVIDENCE_GROUNDED/LLM_DIRECT 模式）.
        rich_text_spec: 富文本 Run 结构（RICH_TEXT 类型）.
        use_template_paragraph_style: 是否继承模板段落样式.
        data_source: 数据来源（CHART/IMAGE/TABLE_DATA/DATA_DRIVEN 类型）.
        chart_grid_spec: 图表网格布局（CHART_GRID 类型）.
        validation: 内容校验规则.
        visible: 是否可见.
        visible_if: 条件可见性表达式（Jinja2）.
        hide_strategy: 不可见时的处理策略.
    """

    key: str = Field(default="", description="对应模板中的 {{key}} 占位符名")
    type: PlaceholderType = Field(default=PlaceholderType.TEXT, description="占位符内容类型")
    title: str = Field(default="", description="人类可读名称")

    # 内容生成
    generation_mode: GenerationMode = Field(
        default=GenerationMode.EVIDENCE_GROUNDED, description="内容生成模式"
    )
    generation_config: Optional[GenerationConfig] = Field(default=None, description="LLM 生成配置")

    # 格式控制（TEXT / RICH_TEXT 类型）
    rich_text_spec: Optional[RichTextSpec] = Field(default=None, description="富文本 Run 结构")
    use_template_paragraph_style: bool = Field(default=True, description="是否继承模板段落样式")

    # 数据绑定（CHART / TABLE_DATA / IMAGE 类型）
    data_source: Optional[DataSourceSpec] = Field(default=None, description="数据来源")
    chart_grid_spec: Optional[ChartGridSpec] = Field(
        default=None, description="图表网格布局（CHART_GRID 类型）"
    )

    # 内容校验
    validation: Optional[ValidationSpec] = Field(default=None, description="内容校验规则")

    # 条件显示
    visible: bool = Field(default=True, description="是否可见")
    visible_if: Optional[str] = Field(default=None, description="条件可见性表达式（Jinja2）")
    hide_strategy: Literal["remove_placeholder", "remove_paragraph", "remove_section"] = Field(
        default="remove_placeholder", description="不可见时的处理策略"
    )


class ReportPeriod(BaseModel):
    """报告周期配置.

    Attributes:
        mode: 周期模式（current_week/last_week/custom）.
        lookback_days: 回溯天数.
        start_date: 自定义开始日期（YYYY-MM-DD）.
        end_date: 自定义结束日期（YYYY-MM-DD）.
    """

    mode: Literal["current_week", "last_week", "custom"] = Field(
        default="current_week", description="周期模式"
    )
    lookback_days: int = Field(default=7, description="回溯天数")
    start_date: Optional[str] = Field(default=None, description="自定义开始日期")
    end_date: Optional[str] = Field(default=None, description="自定义结束日期")


class DefaultSettings(BaseModel):
    """报告模板默认设置.

    所有占位符的兜底配置，单个占位符可覆盖。

    Attributes:
        generation_mode: 默认生成模式.
        evidence_policy: 证据策略.
        retrieval: 默认检索配置.
        validators: 默认校验规则.
        report_period: 报告周期.
    """

    generation_mode: GenerationMode = Field(
        default=GenerationMode.EVIDENCE_GROUNDED, description="默认生成模式"
    )
    evidence_policy: Literal["strict", "allow_synthesis"] = Field(
        default="strict", description="证据策略"
    )
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig, description="默认检索配置")
    validators: ValidationSpec = Field(default_factory=ValidationSpec, description="默认校验规则")
    report_period: ReportPeriod = Field(default_factory=ReportPeriod, description="报告周期")


class TemplateReference(BaseModel):
    """模板文件引用.

    Attributes:
        word_template: Word 模板文件名（相对 project dir）.
        excel_workbook: 数据 Excel 文件名.
        chart_workbook: 图表 Excel 文件名.
        prompt_templates: Prompt 模板文件名.
    """

    word_template: str = Field(description="Word 模板文件名")
    excel_workbook: Optional[str] = Field(default=None, description="数据 Excel 文件名")
    chart_workbook: Optional[str] = Field(default=None, description="图表 Excel 文件名")
    prompt_templates: Optional[str] = Field(default=None, description="Prompt 模板文件名")


class ReportTemplateConfig(BaseModel):
    """报告模板配置 — v2 配置框架的顶层模型.

    替代 section_config.yaml 的顶层结构。
    模板定义布局和静态内容，配置定义动态内容的生成策略和格式。

    这是 ConfigDrivenTemplateRenderer 的输入格式。

    Attributes:
        meta: 模板元信息.
        template: 模板文件引用.
        placeholders: 增强占位符映射（key → EnhancedPlaceholder）.
        defaults: 默认设置（所有占位符的兜底值）.
    """

    meta: "ReportTemplateMeta" = Field(description="模板元信息")
    template: TemplateReference = Field(description="模板文件引用")
    placeholders: Dict[str, EnhancedPlaceholder] = Field(
        default_factory=dict, description="增强占位符映射"
    )
    defaults: DefaultSettings = Field(default_factory=DefaultSettings, description="默认设置")

    @model_validator(mode="after")
    def _populate_placeholder_keys(self) -> "ReportTemplateConfig":
        """自动填充占位符 key 为 dict key.

        允许 YAML 中以 dict key 作为占位符标识，
        无需在每个 EnhancedPlaceholder 中重复指定 key。
        """
        for dict_key, placeholder in self.placeholders.items():
            if not placeholder.key:
                placeholder.key = dict_key
        return self


class ReportTemplateMeta(BaseModel):
    """报告模板元信息.

    Attributes:
        name: 模板名称.
        version: 模板版本（v2 配置框架从 "2.0" 开始）.
        description: 模板描述.
        report_type: 报告类型（word/ppt）.
    """

    name: str = Field(description="模板名称")
    version: str = Field(default="2.0", description="模板版本")
    description: str = Field(default="", description="模板描述")
    report_type: Literal["word", "ppt"] = Field(default="word", description="报告类型")


# Update forward references for self-referencing models.
ReportTemplateConfig.model_rebuild()


# Update forward references.
# compiler types (FactRecord / Provenance / Citation / CompiledSection) are
# referenced as string annotations to avoid a circular import: compiler.py
# imports reporting.py at runtime, so reporting.py must load first and must NOT
# import compiler at module top level. The compiler-typed fields on
# SectionOutput / FactCard are rebuilt AFTER compiler.py finishes loading —
# see the unified rebuild at the bottom of core/contracts/__init__.py.
# Here we only rebuild self-referential models (none currently), so there is
# nothing to do at import time.
