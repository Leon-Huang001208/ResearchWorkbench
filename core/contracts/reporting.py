"""
Core contracts for reporting (section specs and outputs).

This module defines Pydantic models for report section specifications and
section outputs in Research Workbench.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

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



# Update forward references.
# compiler types (FactRecord / Provenance / Citation / CompiledSection) are
# referenced as string annotations to avoid a circular import: compiler.py
# imports reporting.py at runtime, so reporting.py must load first and must NOT
# import compiler at module top level. The compiler-typed fields on
# SectionOutput / FactCard are rebuilt AFTER compiler.py finishes loading —
# see the unified rebuild at the bottom of core/contracts/__init__.py.
# Here we only rebuild self-referential models (none currently), so there is
# nothing to do at import time.
