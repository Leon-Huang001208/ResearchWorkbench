"""
报告编译器核心契约.

定义 AlphaFoundry "outline-first + evidence-first" 报告编译器的核心数据结构。
该编译器把报告生成从"单次长文生成"重构为"任务分解→来源规划→检索→事实抽取
→大纲→分节写作→引用绑定→批判→渲染"的多阶段流水线。

本模块与 reporting.py 解耦，不修改既有报告契约，避免破坏在用代码。
reporting.py 中的 FactCard / SectionOutput 通过向后兼容字段引用本模块类型。

设计依据：deep-research-report.md（STORM/RAPID/FoRAG/CRAG/LongCite 思路）。
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from core.contracts.documents_v1 import SourceReliabilityLevel, SourceType
from core.contracts.retrieval import EvidenceType, RetrievalProfileType

if TYPE_CHECKING:
    # Avoid circular import at runtime; reporting.py must load first.
    from core.contracts.reporting import ReportRunLog, ValidationResult


class SourceTier(str, Enum):
    """来源分级 - 对应 deep-research-report.md 的来源分层。

    比 SourceReliabilityLevel 更粗粒度，直接服务于报告编译器的
    "证据优先级"决策（一级官方源 > 准一级源 > 二级可信源 > 商业/社媒）。
    """

    TIER_A = "tier_a"  # 一级官方源：交易所公告、监管申报、公司财报、标准组织、专利官方库
    TIER_B = "tier_b"  # 准一级源：业绩会纪要、技术白皮书、官方博客、会议论文
    TIER_C = "tier_c"  # 二级可信源：权威媒体、券商公开摘要、行业协会材料
    TIER_D = "tier_d"  # 商业/社媒源：商业数据库摘要、社媒、意见领袖


def reliability_to_tier(reliability: SourceReliabilityLevel) -> SourceTier:
    """SourceReliabilityLevel → SourceTier 映射.

    将既有 7 级可信度枚举压缩到报告编译器使用的 4 级分层，便于来源优先级决策。
    """
    mapping = {
        SourceReliabilityLevel.OFFICIAL: SourceTier.TIER_A,
        SourceReliabilityLevel.ESTABLISHED_MEDIA: SourceTier.TIER_B,
        SourceReliabilityLevel.RESEARCH_INSTITUTE: SourceTier.TIER_B,
        SourceReliabilityLevel.SPECIALIZED_MEDIA: SourceTier.TIER_C,
        SourceReliabilityLevel.OPINION_LEADER: SourceTier.TIER_C,
        SourceReliabilityLevel.SOCIAL_MEDIA: SourceTier.TIER_D,
        SourceReliabilityLevel.UNKNOWN: SourceTier.TIER_D,
    }
    return mapping.get(reliability, SourceTier.TIER_D)


class ClaimType(str, Enum):
    """事实声明类型 - 对应 deep-research-report.md 证据抽取器 schema."""

    METRIC = "metric"  # 数值型指标（收入、毛利率、产能等）
    EVENT = "event"  # 事件型（订单、投产、人事变动）
    SPEC = "spec"  # 规格/技术参数（速率、form factor、功耗）
    GUIDANCE = "guidance"  # 指引/前瞻（公司 guidance、行业预期）
    RISK = "risk"  # 风险提示


class CitationAnchor(BaseModel):
    """引用锚点 - 定位到证据源的最小粒度.

    支持段落/行/span/页码定位，便于句级引用验证（LongCite 思路）。
    """

    locator_type: str = Field(
        default="span",
        description="定位类型：paragraph|line|span|page",
    )
    locator_value: str = Field(default="", description="定位值，如页码或段落序号")
    chunk_index: Optional[int] = Field(default=None, description="文档内 chunk 序号")


class Provenance(BaseModel):
    """来源溯源 - 一个事实声明的完整来源链.

    每个 FactRecord 必须携带 Provenance，使报告中的每个结论可回溯到
    具体文档、chunk、来源类型与分级。
    """

    doc_id: str = Field(description="源文档 ID")
    chunk_id: Optional[str] = Field(default=None, description="文档内 chunk ID")
    source_type: Optional[SourceType] = Field(default=None, description="来源类型")
    source_name: str = Field(default="", description="来源名称，如'巨潮资讯网'")
    source_url: Optional[str] = Field(default=None, description="来源 URL")
    published_at: Optional[datetime] = Field(default=None, description="来源发布时间")
    source_reliability: Optional[SourceReliabilityLevel] = Field(
        default=None, description="来源可信度层级"
    )
    source_tier: SourceTier = Field(default=SourceTier.TIER_D, description="来源分级")
    citation_anchor: Optional[CitationAnchor] = Field(default=None, description="引用锚点")


class FactRecord(BaseModel):
    """事实记录 - 报告编译器的最小证据单元.

    区别于既有 FactCard（仅 List[str] 无 provenance），FactRecord 是结构化的、
    带来源溯源与置信度的事实声明。所有进入正文/表格/图表的数字与结论，
    必须先落到 FactRecord，再由渲染器消费。
    """

    fact_id: str = Field(description="事实唯一 ID")
    claim_text: str = Field(description="事实声明文本")
    claim_type: ClaimType = Field(default=ClaimType.METRIC, description="声明类型")
    entities: List[str] = Field(
        default_factory=list, description="关联实体（公司名/股票代码/品牌）"
    )
    period: Optional[str] = Field(default=None, description="期间，如 2024Q3 / 2024 年报")
    value: Optional[float] = Field(default=None, description="数值，对 metric 类型有效")
    unit: Optional[str] = Field(default=None, description="单位，如 亿元 / Gbps / %")
    evidence_span: str = Field(default="", description="原文证据片段，用于引用展示与校验")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="抽取置信度 0.0-1.0")
    provenance: Provenance = Field(description="来源溯源")


class Citation(BaseModel):
    """引用 - 正文中的引用标记与对应事实的绑定.

    引用绑定器（citation_binder）解析正文中的 [fact_id] 标记，替换为
    格式化的 [N] 引用，并生成 Citation 对象，实现句级引用可验证。
    """

    citation_id: str = Field(description="引用唯一 ID")
    fact_ids: List[str] = Field(default_factory=list, description="该引用对应的事实 ID 列表")
    display_text: str = Field(default="", description="展示文本，如 '[1] 巨潮资讯网 2024-05-09'")
    anchor: Optional[CitationAnchor] = Field(default=None, description="引用锚点")


class OutlineSection(BaseModel):
    """大纲节点 - 报告结构树的节点.

    大纲规划器（outline_planner）基于 facts 摘要生成标题树，每节明确
    要回答的问题、需要的证据类型、风险与反证。outline 优先于 prose。
    """

    section_id: str = Field(description="节点唯一 ID")
    title: str = Field(description="节点标题")
    goal: str = Field(default="", description="本节要回答的核心问题与目标")
    must_answer: List[str] = Field(default_factory=list, description="本节必须回答的子问题")
    required_evidence_types: List[EvidenceType] = Field(
        default_factory=list, description="本节需要的证据类型"
    )
    required_claim_types: List[ClaimType] = Field(
        default_factory=list, description="本节需要的事实声明类型"
    )
    counterpoints: List[str] = Field(
        default_factory=list, description="风险与反证，必须覆盖而非只写利多"
    )
    subsections: List["OutlineSection"] = Field(default_factory=list, description="子节点")
    target_words: int = Field(default=500, description="目标字数")
    retrieval_profile: Optional[RetrievalProfileType] = Field(
        default=None, description="本节检索 profile"
    )


class ReportOutline(BaseModel):
    """报告大纲 - 编译器的结构骨架.

    由大纲规划器生成，先于正文写作。每个 section 携带证据覆盖要求，
    指导分节写作器只使用匹配的 facts。
    """

    report_title: str = Field(description="报告标题")
    thesis: str = Field(default="", description="核心论点（一句话讲清赛道结论）")
    sections: List[OutlineSection] = Field(default_factory=list, description="章节列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")


class CompiledSection(BaseModel):
    """编译后的章节 - 分节写作器与引用绑定器的产出.

    含正文、引用列表、引用的事实 ID 列表与校验结果。
    """

    section_id: str = Field(description="章节 ID，对应 OutlineSection.section_id")
    title: str = Field(description="章节标题")
    content: str = Field(default="", description="章节正文（含格式化引用 [N]）")
    citations: List[Citation] = Field(default_factory=list, description="本章引用列表")
    fact_ids: List[str] = Field(default_factory=list, description="本章引用的事实 ID 列表")
    validation_result: Optional["ValidationResult"] = Field(
        default=None, description="本章校验结果"
    )


class CompiledReport(BaseModel):
    """编译后的报告 - 报告编译器的最终产出.

    聚合大纲、章节、事实表与运行日志，由 renderer 适配到既有渲染层
    （WordProjection / MarkdownProjection 等）。
    """

    report_id: str = Field(description="报告唯一 ID")
    outline: ReportOutline = Field(description="报告大纲")
    sections: List[CompiledSection] = Field(default_factory=list, description="编译后的章节列表")
    facts: List[FactRecord] = Field(default_factory=list, description="本次报告的事实表")
    run_log: Optional["ReportRunLog"] = Field(default=None, description="运行日志")
    compiler_version: str = Field(default="1.0", description="编译器版本")


class CritiqueSeverity(str, Enum):
    """批判器整体严重度 - 控制 revision 循环是否继续."""

    PASS = "pass"  # 无问题，可直接渲染
    MINOR = "minor"  # 轻微问题，可自动修复或接受
    MAJOR = "major"  # 显著问题，需 revision_pass 修复
    CRITICAL = "critical"  # 致命问题，需人工审核


class CritiqueCategory(str, Enum):
    """批判器问题类别."""

    CLAIM_SUPPORT = "claim_support"  # 声明无事实支撑
    CONFLICT = "conflict"  # 数字/文本与事实矛盾
    COUNTERPOINT = "counterpoint"  # 反证未覆盖
    STRUCTURE = "structure"  # 结构连贯性
    EVIDENCE_SUFFICIENCY = "evidence_sufficiency"  # 证据不足
    FORBIDDEN_TERM = "forbidden_term"  # 禁用词
    # Phase 3.2: citation verifier + numeric checker categories
    CITATION_PRECISION = "citation_precision"  # 引用精度不足：fact 不支撑引用的句子
    ORPHAN_CITATION = "orphan_citation"  # 孤立引用：fact_ids 指向不存在的 fact
    SOURCE_DIVERSITY = "source_diversity"  # 来源多样性不足
    FABRICATED_NUMBER = "fabricated_number"  # 虚构数字：正文数字无匹配 fact
    UNIT_MISMATCH = "unit_mismatch"  # 单位不一致
    PERIOD_MISMATCH = "period_mismatch"  # 期间不一致


class CritiqueIssue(BaseModel):
    """单个批判问题.

    比 ValidationResult 更细粒度：包含位置、冲突事实 ID、修复建议，
    供 revision_pass 精确修复。
    """

    issue_id: str = Field(description="问题唯一 ID")
    category: CritiqueCategory = Field(description="问题类别")
    severity: Literal["error", "warning", "info"] = Field(default="warning", description="严重程度")
    section_id: str = Field(description="所属章节 ID")
    description: str = Field(description="问题描述")
    location: str = Field(
        default="", description="文本位置（段落序号或 span 片段），供 revision_pass 定位"
    )
    conflicting_fact_id: Optional[str] = Field(
        default=None, description="冲突关联的事实 ID（CONFLICT 类别时有效）"
    )
    suggested_fix: str = Field(default="", description="修复建议，供 revision_pass 执行")


class CritiqueReport(BaseModel):
    """批判器完整输出.

    聚合所有检查结果、整体严重度与修复建议，驱动 revision_pass 循环。
    """

    report_id: str = Field(description="关联的报告 ID")
    overall_severity: CritiqueSeverity = Field(
        default=CritiqueSeverity.PASS, description="整体严重度"
    )
    issues: List[CritiqueIssue] = Field(default_factory=list, description="问题列表")
    revision_suggestions: List[str] = Field(
        default_factory=list, description="高层修复建议（自然语言，供 revision_pass 参考）"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="汇总指标：claim_support_rate / conflict_count / counterpoint_coverage / structure_score / evidence_density",
    )


class ResearchPlan(BaseModel):
    """研究计划 - 任务分解器的产出.

    把用户报告需求拆解为 research questions、证据需求表与检索预算，
    指导来源规划器与检索器。
    """

    research_questions: List[str] = Field(default_factory=list, description="研究子问题列表")
    required_claim_types: List[ClaimType] = Field(
        default_factory=list, description="需要的事实声明类型"
    )
    required_evidence_types: List[EvidenceType] = Field(
        default_factory=list, description="需要的证据类型"
    )
    retrieval_budget: Dict[str, int] = Field(
        default_factory=lambda: {"max_documents": 50, "max_chunks": 200},
        description="检索预算",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")


# ═══════════════════════════════════════════════════════════════════════
# Phase 3.3: Evaluation System — 评测体系
# ═══════════════════════════════════════════════════════════════════════


class VerificationStatus(str, Enum):
    """声明验证状态 — 声明与其支撑 fact 的匹配结果."""

    VERIFIED = "verified"  # 声明与 fact 数值/文本匹配
    CONTRADICTED = "contradicted"  # 声明与 fact 冲突
    UNVERIFIABLE = "unverifiable"  # 无匹配 fact 可验证
    IRRELEVANT = "irrelevant"  # 声明为描述性内容，无需验证


class AtomicClaim(BaseModel):
    """原子声明 — 从报告正文拆解的最小可验证声明单元.

    每个 CompiledSection 可拆解为多条 AtomicClaim，每条声明可独立验证
    （与 FactRecord 交叉比对），是评测体系的基础粒度。
    """

    claim_id: str = Field(description="声明唯一 ID")
    claim_text: str = Field(description="声明文本")
    section_id: str = Field(description="来源章节 ID（CompiledSection.section_id）")
    claim_type: ClaimType | None = Field(default=None, description="声明类型")
    fact_ids: list[str] = Field(default_factory=list, description="支撑此声明的 fact ID 列表")
    verification: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIABLE, description="验证状态"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="抽取置信度 0.0-1.0")


class ReportMetrics(BaseModel):
    """报告质量指标 — 五维度量化评测.

    替代 CritiqueReport 中的 ad-hoc Dict[str, Any] metrics，
    所有维度均为显式 Pydantic 字段，支持 A/B 对比与 benchmark 回归。
    """

    # ── 检索质量 ──
    source_tier_a_b_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="Tier A+B 占比")
    total_evidence_chunks: int = Field(default=0, description="证据 chunk 总数")
    evidence_diversity: float = Field(
        default=0.0, ge=0.0, le=1.0, description="去重来源数 / 总来源数"
    )

    # ── 事实质量 ──
    total_facts: int = Field(default=0, description="事实总数")
    claim_support_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="声明支撑率（来自 critic）"
    )
    fabricated_number_count: int = Field(default=0, description="虚构数字数（来自 NumericChecker）")

    # ── 引用品质 ──
    citation_coverage: float = Field(
        default=0.0, ge=0.0, le=1.0, description="引用覆盖率（来自 CitationVerifier）"
    )
    orphan_citation_count: int = Field(default=0, description="孤立引用数")
    source_diversity_pct: float = Field(
        default=0.0, ge=0.0, le=1.0, description="最大单一来源占比（来自 CitationVerifier）"
    )

    # ── 报告质量 ──
    total_words: int = Field(default=0, description="报告总字数")
    total_sections: int = Field(default=0, description="章节总数")
    structure_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="结构评分（来自 critic）"
    )
    counterpoint_coverage: float = Field(
        default=1.0, ge=0.0, le=1.0, description="反证覆盖率（来自 critic）"
    )

    # ── 生产效率 ──
    compilation_time_ms: float = Field(default=0.0, description="编译耗时（毫秒）")
    tokens_used: int = Field(default=0, description="消耗 token 数")
    cost_estimate: float = Field(default=0.0, description="预估成本（USD）")
    revision_rounds: int = Field(default=0, description="修订轮数")

    # ── 综合 ──
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0, description="加权综合评分（0-100）")
    grade: str = Field(default="N/A", description="等级：A(≥85)/B(≥70)/C(≥55)/D(≥40)/F(<40)")


class EvaluationReport(BaseModel):
    """评测报告 — AutoGrader 的完整产出.

    聚合 ReportMetrics、AtomicClaim 列表、所有 CritiqueIssue，
    是 benchmark 回归与 A/B 对比的输入。
    """

    report_id: str = Field(description="关联的 CompiledReport ID")
    metrics: ReportMetrics = Field(default_factory=ReportMetrics, description="质量指标")
    claims: list[AtomicClaim] = Field(default_factory=list, description="拆解的原子声明")
    critique_issues: list[CritiqueIssue] = Field(
        default_factory=list, description="合并的批判问题（critic + verifier）"
    )
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0, description="综合评分")
    grade: str = Field(default="N/A", description="等级")
    evaluated_at: datetime | None = Field(default=None, description="评测时间")


class BenchmarkTask(BaseModel):
    """基准测试任务 — 定义一次报告生成与评测的输入与期望.

    用于 BenchmarkSuite 中的单个任务。不包含 golden facts 的完整集合
    （那是数据策展工作），仅定义任务 prompt、模板与最低期望。
    """

    task_id: str = Field(description="任务唯一 ID")
    prompt: str = Field(description="报告生成 prompt")
    template_name: str = Field(default="standard", description="报告模板名")
    expected_sections: list[str] = Field(default_factory=list, description="期望出现的节标题")
    golden_facts_count: int = Field(default=0, description="最低期望事实数")
    category: str = Field(default="general", description="任务类别（公司研究/行业分析/竞品对比）")
    difficulty: Literal["easy", "medium", "hard"] = Field(default="medium", description="难度等级")


class ABDimensionDiff(BaseModel):
    """A/B 单维度对比结果."""

    dimension: str = Field(description="维度名称")
    value_a: float = Field(default=0.0, description="A 侧值")
    value_b: float = Field(default=0.0, description="B 侧值")
    diff: float = Field(default=0.0, description="差值（B - A）")
    pct_change: float = Field(default=0.0, description="百分比变化")
    winner: Literal["A", "B", "tie"] = Field(default="tie", description="该维度胜者")


class ABComparison(BaseModel):
    """A/B 对比报告 — 两份 EvaluationReport 的逐维度对比."""

    report_id_a: str = Field(description="A 侧报告 ID")
    report_id_b: str = Field(description="B 侧报告 ID")
    label_a: str = Field(default="A", description="A 侧展示标签")
    label_b: str = Field(default="B", description="B 侧展示标签")
    blind_mode: bool = Field(default=False, description="是否盲评")
    dimensions: list[ABDimensionDiff] = Field(default_factory=list, description="各维度对比")
    overall_winner: Literal["A", "B", "tie"] = Field(default="tie", description="综合胜者")
    win_count: dict[str, int] = Field(
        default_factory=lambda: {"A": 0, "B": 0, "tie": 0}, description="各维度胜场统计"
    )
    summary: str = Field(default="", description="对比摘要")


# ── Phase 3.3: 结构化输出的私有 schema（复用 FactExtractor 模式）──


class _ClaimItem(BaseModel):
    """LLM 声明抽取的单条输出 schema（私有，不导出）."""

    claim_text: str = Field(description="声明文本")
    claim_type: str = Field(default="metric", description="声明类型")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度")


class _ClaimExtractionResult(BaseModel):
    """LLM 声明抽取的整体输出 schema（私有，不导出）."""

    claims: list[_ClaimItem] = Field(default_factory=list, description="抽取的声明列表")


# Rebuild forward references.
# Load order: __init__.py imports compiler (line 17) before reporting (line 180).
# compiler.py does NOT import reporting at module top level (TYPE_CHECKING only),
# so reporting.py is NOT yet loaded when compiler.py first runs. We must therefore
# import reporting here at the bottom, which loads it fully, then rebuild every
# model that carries string forward-refs — both compiler's own (ValidationResult,
# ReportRunLog) and reporting's (FactRecord, Provenance, Citation, CompiledSection
# on SectionOutput / FactCard).
_reporting_ns: Dict[str, Any] = {}
try:  # pragma: no cover - import path depends on package initialization order
    from core.contracts import reporting as _reporting_mod  # noqa: F401

    _reporting_ns = {
        "ReportRunLog": _reporting_mod.ReportRunLog,
        "ValidationResult": _reporting_mod.ValidationResult,
    }
except Exception:  # pragma: no cover
    _reporting_mod = None  # type: ignore[assignment]

# compiler's own models reference reporting types
if hasattr(OutlineSection, "model_rebuild"):
    OutlineSection.model_rebuild(_types_namespace=_reporting_ns)
    CompiledSection.model_rebuild(_types_namespace=_reporting_ns)
    CompiledReport.model_rebuild(_types_namespace=_reporting_ns)
else:  # pragma: no cover - Pydantic v1 fallback
    OutlineSection.update_forward_refs(**_reporting_ns)
    CompiledSection.update_forward_refs(**_reporting_ns)
    CompiledReport.update_forward_refs(**_reporting_ns)

# reporting models reference compiler types — rebuild now that compiler is loaded
if _reporting_mod is not None:
    _compiler_ns_for_reporting: Dict[str, Any] = {
        "FactRecord": FactRecord,
        "Provenance": Provenance,
        "Citation": Citation,
        "CompiledSection": CompiledSection,
    }
    if hasattr(_reporting_mod.SectionOutput, "model_rebuild"):
        _reporting_mod.SectionOutput.model_rebuild(_types_namespace=_compiler_ns_for_reporting)
        _reporting_mod.FactCard.model_rebuild(_types_namespace=_compiler_ns_for_reporting)
    else:  # pragma: no cover
        _reporting_mod.SectionOutput.update_forward_refs(**_compiler_ns_for_reporting)
        _reporting_mod.FactCard.update_forward_refs(**_compiler_ns_for_reporting)
