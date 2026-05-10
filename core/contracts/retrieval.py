"""
RAG 检索层契约 - Issue #45.

定义检索配置、过滤条件、证据包等数据结构，支持多种检索 profiles、
时间衰减、结构化过滤，以及报告与回测视角分离。
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from core.contracts.documents_v1 import (
    DocType,
    SourceReliabilityLevel,
    SourceType,
    SubjectivityLevel,
)


class RetrievalProfileType(str, Enum):
    """检索 Profile 类型 - Issue #45 要求"""

    DAILY_REPORT = "daily_report"
    WEEKLY_REPORT = "weekly_report"
    MONTHLY_REPORT = "monthly_report"
    DEEP_DIVE = "deep_dive"
    BACKTEST_REPLAY = "backtest_replay"


class EvidenceType(str, Enum):
    """证据类型"""

    FACT = "fact"
    OPINION = "opinion"
    MIXED = "mixed"
    DATA = "data"
    QUOTE = "quote"
    ANALYSIS = "analysis"


# =============================================================================
# Retrieval Profile Configuration
# =============================================================================


class RecencyDecayConfig(BaseModel):
    """时间衰减配置"""

    half_life_days: float = Field(7.0, description="半衰期（天）")
    decay_factor: float = Field(0.95, description="衰减因子")
    min_score_weight: float = Field(0.1, description="最小分数权重")


class SourceWeightConfig(BaseModel):
    """来源权重配置"""

    weights: Dict[SourceType, float] = Field(default_factory=dict, description="来源权重")
    default_weight: float = Field(1.0, description="默认权重")


class DocTypeLookbackConfig(BaseModel):
    """文档类型回看时间配置"""

    lookback_days: Dict[DocType, int] = Field(
        default_factory=lambda: {
            DocType.TELEGRAM: 3,
            DocType.NEWS: 7,
            DocType.COMMENTARY: 14,
            DocType.REPORT: 30,
            DocType.TRANSCRIPT: 30,
            DocType.WECHAT: 14,
        }
    )
    default_lookback_days: int = Field(14, description="默认回看天数")


class RetrievalProfile(BaseModel):
    """
    检索 Profile - 定义不同场景的检索配置.

    Issue #45 要求的核心概念，支持 daily_report、weekly_report、
    monthly_report、deep_dive、backtest_replay 五种 profiles。
    """

    profile_type: RetrievalProfileType = Field(description="Profile 类型")
    name: str = Field(description="Profile 名称")
    description: str = Field(description="Profile 描述")

    # 时间配置
    lookback_config: DocTypeLookbackConfig = Field(
        default_factory=DocTypeLookbackConfig, description="文档类型回看配置"
    )
    recency_decay: RecencyDecayConfig = Field(
        default_factory=RecencyDecayConfig, description="时间衰减配置"
    )

    # 来源配置
    source_weights: SourceWeightConfig = Field(
        default_factory=SourceWeightConfig, description="来源权重配置"
    )

    # 质量过滤
    min_research_usability: float = Field(0.0, ge=0.0, le=1.0, description="最小研究可用性")
    min_source_reliability: Optional[SourceReliabilityLevel] = Field(None, description="最小来源可信度")
    allow_opinion_sources: bool = Field(True, description="是否允许观点来源")

    # 检索参数
    max_documents: int = Field(50, description="最大文档数")
    max_chunks: int = Field(100, description="最大分块数")
    vector_weight: float = Field(0.7, ge=0.0, le=1.0, description="向量搜索权重")
    keyword_weight: float = Field(0.3, ge=0.0, le=1.0, description="关键词搜索权重")

    # 回测特定配置
    use_available_time: bool = Field(False, description="是否使用 available_time（回测用）")
    available_time_cutoff: Optional[datetime] = Field(None, description="可用时间截止点（回测用）")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "profile_type": "daily_report",
                    "name": "Daily Report Profile",
                    "description": "用于生成日常报告的检索配置，侧重最新信息",
                    "max_documents": 30,
                    "max_chunks": 60,
                }
            ]
        }
    }


# =============================================================================
# Filtering and Query
# =============================================================================


class RetrievalFilters(BaseModel):
    """
    检索过滤条件 - Issue #45 要求的完整过滤维度.

    支持时间范围、来源、行业、主题、实体、事件类型、
    可信度、主观性等多维度过滤。
    """

    # 时间过滤
    publish_time_after: Optional[datetime] = Field(None, description="发布时间之后")
    publish_time_before: Optional[datetime] = Field(None, description="发布时间之前")
    available_time_before: Optional[datetime] = Field(None, description="可用时间之前（回测用）")

    # 来源过滤
    doc_types: Optional[List[DocType]] = Field(None, description="文档类型列表")
    source_types: Optional[List[SourceType]] = Field(None, description="来源类型列表")
    source_names: Optional[List[str]] = Field(None, description="来源名称列表")

    # 分类过滤
    primary_industries: Optional[List[str]] = Field(None, description="主要行业列表")
    secondary_industries: Optional[List[str]] = Field(None, description="次要行业列表")
    topics: Optional[List[str]] = Field(None, description="主题列表")
    event_types: Optional[List[str]] = Field(None, description="事件类型列表")

    # 实体过滤
    entity_ids: Optional[List[str]] = Field(None, description="实体ID列表")
    entity_names: Optional[List[str]] = Field(None, description="实体名称列表")
    entity_types: Optional[List[str]] = Field(None, description="实体类型列表")

    # 质量过滤
    min_research_usability: Optional[float] = Field(None, ge=0.0, le=1.0, description="最小研究可用性")
    min_source_reliability: Optional[SourceReliabilityLevel] = Field(None, description="最小来源可信度")
    min_evidence_quality: Optional[float] = Field(None, ge=0.0, le=1.0, description="最小证据质量")

    # 主观性过滤
    allowed_subjectivity: Optional[List[SubjectivityLevel]] = Field(None, description="允许的主观性层级")
    only_fact_sources: bool = Field(False, description="仅事实来源")

    # 证据特征过滤
    has_explicit_facts: Optional[bool] = Field(None, description="有明确事实")
    has_data_points: Optional[bool] = Field(None, description="有数据点")
    has_quotes: Optional[bool] = Field(None, description="有引述")
    has_analysis: Optional[bool] = Field(None, description="有分析")


class RetrievalQuery(BaseModel):
    """检索查询"""

    query_text: str = Field(description="查询文本")
    filters: Optional[RetrievalFilters] = Field(None, description="过滤条件")
    profile_type: Optional[RetrievalProfileType] = Field(None, description="使用的 Profile 类型")
    max_results: int = Field(20, description="最大结果数")
    include_chunks: bool = Field(True, description="是否包含分块")
    include_entities: bool = Field(False, description="是否包含实体")


# =============================================================================
# Evidence Package (Output)
# =============================================================================


class EvidenceChunk(BaseModel):
    """证据分块 - 单个分块的证据信息"""

    chunk_id: str = Field(description="分块ID")
    doc_id: str = Field(description="文档ID")
    content: str = Field(description="分块内容")
    title: Optional[str] = Field(None, description="分块标题")
    chunk_index: int = Field(0, description="分块索引")

    # 评分
    relevance_score: float = Field(0.0, ge=0.0, le=1.0, description="相关性分数")
    recency_score: float = Field(0.0, ge=0.0, le=1.0, description="时效性分数")
    quality_score: float = Field(0.0, ge=0.0, le=1.0, description="质量分数")
    combined_score: float = Field(0.0, ge=0.0, le=1.0, description="综合分数")

    # 证据类型
    evidence_type: EvidenceType = Field(EvidenceType.MIXED, description="证据类型")

    # 元数据
    topics: List[str] = Field(default_factory=list, description="主题")
    entities: List[str] = Field(default_factory=list, description="实体")


class EvidenceDocument(BaseModel):
    """证据文档 - 单个文档的证据信息"""

    doc_id: str = Field(description="文档ID")
    title: str = Field(description="标题")
    summary: Optional[str] = Field(None, description="摘要")

    # 来源信息
    source_type: SourceType = Field(description="来源类型")
    source_name: Optional[str] = Field(None, description="来源名称")
    source_url: Optional[str] = Field(None, description="来源URL")

    # 时间信息
    publish_time: Optional[datetime] = Field(None, description="发布时间")
    available_time: Optional[datetime] = Field(None, description="可用时间")

    # 分类信息
    primary_industry: Optional[str] = Field(None, description="主要行业")
    topics: List[str] = Field(default_factory=list, description="主题")
    event_types: List[str] = Field(default_factory=list, description="事件类型")

    # 质量信息
    source_reliability: SourceReliabilityLevel = Field(
        default=SourceReliabilityLevel.UNKNOWN, description="来源可信度"
    )
    subjectivity: SubjectivityLevel = Field(default=SubjectivityLevel.MIXED, description="主观性层级")
    evidence_quality: float = Field(0.0, ge=0.0, le=1.0, description="证据质量")

    # 分块（如果包含）
    chunks: List[EvidenceChunk] = Field(default_factory=list, description="证据分块")

    # 引用锚点（用于报告生成）
    citation_anchor: str = Field(description="引用锚点")


class EvidencePackage(BaseModel):
    """
    证据包 - Issue #45 要求的核心输出结构.

    包含检索到的文档和分块，标注为事实/观点/混合类型，
    带有引用锚点，可直接用于报告生成或回测分析。
    """

    query: RetrievalQuery = Field(description="原始查询")
    profile_used: Optional[RetrievalProfile] = Field(None, description="使用的 Profile")

    # 统计信息
    total_documents_found: int = Field(0, description="找到的文档总数")
    total_chunks_found: int = Field(0, description="找到的分块总数")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow, description="检索时间")

    # 证据文档列表
    documents: List[EvidenceDocument] = Field(default_factory=list, description="证据文档列表")

    # 过滤条件摘要
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="应用的过滤条件摘要")

    # 来源分布
    source_distribution: Dict[str, int] = Field(default_factory=dict, description="来源分布")
    industry_distribution: Dict[str, int] = Field(default_factory=dict, description="行业分布")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": {"query_text": "茅台业绩分析"},
                    "total_documents_found": 5,
                    "total_chunks_found": 15,
                }
            ]
        }
    }


# =============================================================================
# Predefined Profiles (Convenience)
# =============================================================================


def create_daily_report_profile() -> RetrievalProfile:
    """创建日报 Profile"""
    return RetrievalProfile(
        profile_type=RetrievalProfileType.DAILY_REPORT,
        name="Daily Report",
        description="用于日常报告生成，侧重最新、可信度高的信息",
        lookback_config=DocTypeLookbackConfig(
            lookback_days={
                DocType.TELEGRAM: 1,
                DocType.NEWS: 2,
                DocType.COMMENTARY: 3,
                DocType.REPORT: 7,
                DocType.TRANSCRIPT: 7,
                DocType.WECHAT: 3,
            },
            default_lookback_days=3,
        ),
        recency_decay=RecencyDecayConfig(
            half_life_days=2.0, decay_factor=0.9, min_score_weight=0.3
        ),
        source_weights=SourceWeightConfig(
            weights={
                SourceType.CAILIAN_SHE: 1.2,
                SourceType.CHINA_SECURITY_JOURNAL: 1.1,
                SourceType.ZHIQIU_REPORTS: 1.0,
            },
            default_weight=1.0,
        ),
        min_research_usability=0.3,
        allow_opinion_sources=True,
        max_documents=30,
        max_chunks=60,
        vector_weight=0.7,
        keyword_weight=0.3,
        use_available_time=False,
    )


def create_weekly_report_profile() -> RetrievalProfile:
    """创建周报 Profile"""
    return RetrievalProfile(
        profile_type=RetrievalProfileType.WEEKLY_REPORT,
        name="Weekly Report",
        description="用于周报生成，平衡时效性和深度",
        lookback_config=DocTypeLookbackConfig(
            lookback_days={
                DocType.TELEGRAM: 5,
                DocType.NEWS: 7,
                DocType.COMMENTARY: 14,
                DocType.REPORT: 21,
                DocType.TRANSCRIPT: 21,
                DocType.WECHAT: 10,
            },
            default_lookback_days=14,
        ),
        recency_decay=RecencyDecayConfig(
            half_life_days=5.0, decay_factor=0.95, min_score_weight=0.2
        ),
        source_weights=SourceWeightConfig(
            weights={
                SourceType.ZHIQIU_REPORTS: 1.3,
                SourceType.CHINA_SECURITY_JOURNAL: 1.1,
                SourceType.CAILIAN_SHE: 1.0,
            },
            default_weight=1.0,
        ),
        min_research_usability=0.4,
        allow_opinion_sources=True,
        max_documents=50,
        max_chunks=100,
        vector_weight=0.75,
        keyword_weight=0.25,
        use_available_time=False,
    )


def create_monthly_report_profile() -> RetrievalProfile:
    """创建月报 Profile"""
    return RetrievalProfile(
        profile_type=RetrievalProfileType.MONTHLY_REPORT,
        name="Monthly Report",
        description="用于月报生成，侧重深度分析和研究报告",
        lookback_config=DocTypeLookbackConfig(
            lookback_days={
                DocType.TELEGRAM: 10,
                DocType.NEWS: 30,
                DocType.COMMENTARY: 45,
                DocType.REPORT: 60,
                DocType.TRANSCRIPT: 60,
                DocType.WECHAT: 30,
            },
            default_lookback_days=30,
        ),
        recency_decay=RecencyDecayConfig(
            half_life_days=15.0, decay_factor=0.98, min_score_weight=0.1
        ),
        source_weights=SourceWeightConfig(
            weights={
                SourceType.ZHIQIU_REPORTS: 1.5,
                SourceType.ZHIQIU_TRANSCRIPT: 1.3,
                SourceType.BLOOMBERG: 1.2,
                SourceType.REUTERS: 1.2,
            },
            default_weight=1.0,
        ),
        min_research_usability=0.5,
        allow_opinion_sources=True,
        max_documents=80,
        max_chunks=150,
        vector_weight=0.8,
        keyword_weight=0.2,
        use_available_time=False,
    )


def create_deep_dive_profile() -> RetrievalProfile:
    """创建深度研究 Profile"""
    return RetrievalProfile(
        profile_type=RetrievalProfileType.DEEP_DIVE,
        name="Deep Dive",
        description="用于深度专题研究，全面检索相关信息",
        lookback_config=DocTypeLookbackConfig(
            lookback_days={
                DocType.TELEGRAM: 30,
                DocType.NEWS: 90,
                DocType.COMMENTARY: 120,
                DocType.REPORT: 180,
                DocType.TRANSCRIPT: 180,
                DocType.WECHAT: 90,
            },
            default_lookback_days=90,
        ),
        recency_decay=RecencyDecayConfig(
            half_life_days=30.0, decay_factor=0.99, min_score_weight=0.05
        ),
        source_weights=SourceWeightConfig(
            weights={
                SourceType.ZHIQIU_REPORTS: 1.4,
                SourceType.ZHIQIU_TRANSCRIPT: 1.4,
                SourceType.COMPANY_ANNOUNCEMENT: 1.3,
                SourceType.GOVERNMENT_POLICY: 1.3,
            },
            default_weight=1.0,
        ),
        min_research_usability=0.3,
        allow_opinion_sources=True,
        max_documents=150,
        max_chunks=300,
        vector_weight=0.85,
        keyword_weight=0.15,
        use_available_time=False,
    )


def create_backtest_replay_profile(
    available_time_cutoff: Optional[datetime] = None,
) -> RetrievalProfile:
    """
    创建回看重放 Profile.

    Issue #45 要求：使用 available_time 确保回测时不会使用未来信息。
    """
    return RetrievalProfile(
        profile_type=RetrievalProfileType.BACKTEST_REPLAY,
        name="Backtest Replay",
        description="用于回测研究，严格按 available_time 过滤，避免未来信息泄漏",
        lookback_config=DocTypeLookbackConfig(
            lookback_days={
                DocType.TELEGRAM: 30,
                DocType.NEWS: 90,
                DocType.COMMENTARY: 120,
                DocType.REPORT: 180,
                DocType.TRANSCRIPT: 180,
                DocType.WECHAT: 90,
            },
            default_lookback_days=90,
        ),
        recency_decay=RecencyDecayConfig(
            half_life_days=15.0, decay_factor=0.98, min_score_weight=0.05
        ),
        source_weights=SourceWeightConfig(
            weights={
                SourceType.CAILIAN_SHE: 1.0,
                SourceType.CHINA_SECURITY_JOURNAL: 1.0,
                SourceType.ZHIQIU_REPORTS: 1.0,
            },
            default_weight=1.0,
        ),
        min_research_usability=0.2,
        allow_opinion_sources=True,
        max_documents=100,
        max_chunks=200,
        vector_weight=0.7,
        keyword_weight=0.3,
        use_available_time=True,
        available_time_cutoff=available_time_cutoff,
    )


PROFILE_FACTORY = {
    RetrievalProfileType.DAILY_REPORT: create_daily_report_profile,
    RetrievalProfileType.WEEKLY_REPORT: create_weekly_report_profile,
    RetrievalProfileType.MONTHLY_REPORT: create_monthly_report_profile,
    RetrievalProfileType.DEEP_DIVE: create_deep_dive_profile,
    RetrievalProfileType.BACKTEST_REPLAY: create_backtest_replay_profile,
}


def get_profile(
    profile_type: RetrievalProfileType, available_time_cutoff: Optional[datetime] = None
) -> RetrievalProfile:
    """获取指定类型的 Profile"""
    if profile_type == RetrievalProfileType.BACKTEST_REPLAY:
        return create_backtest_replay_profile(available_time_cutoff)

    factory = PROFILE_FACTORY.get(profile_type)
    if not factory:
        raise ValueError(f"Unknown profile type: {profile_type}")

    return factory()
