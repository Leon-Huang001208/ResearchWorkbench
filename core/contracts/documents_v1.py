"""
AlphaFoundry v1 统一文档契约.

本模块定义了 Issue #42 要求的统一文档 schema，支持多种来源类型（电报、新闻、研报、公众号、会议纪要等）
映射到同一个主模型，并提供完整的元数据、分类、质量评分和时效性字段。
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# =============================================================================
# Enums for standardized classification
# =============================================================================


class DocType(str, Enum):
    """文档类型枚举"""

    TELEGRAM = "telegram"  # 电报/快讯
    NEWS = "news"  # 新闻
    COMMENTARY = "commentary"  # 评论文章
    REPORT = "report"  # 券商研报
    WECHAT = "wechat"  # 公众号
    TRANSCRIPT = "transcript"  # 会议纪要
    FILING = "filing"  # 公告/备案
    POLICY = "policy"  # 政策文件
    INTERNAL_NOTE = "internal_note"  # 内部笔记


class SourceType(str, Enum):
    """来源类型枚举"""

    CLS = "cls"  # 财联社
    CNSTOCK = "cnstock"  # 中国证券网
    CNSTOCK_FLASH = "cnstock_flash"  # 中国证券网-快讯
    ZHIQIU_REPORTS = "zhiqiu_reports"  # 知丘研报
    ZHIQIU_WECHAT = "zhiqiu_wechat"  # 知丘公众号
    ZHIQIU_TRANSCRIPT = "zhiqiu_transcript"  # 知丘会议纪要
    EAST_MONEY = "east_money"  # 东方财富
    SINA_FINANCE = "sina_finance"  # 新浪财经
    WIND = "wind"  # Wind
    AKSHARE = "akshare"  # AKShare
    BAOSTOCK = "baostock"  # BaoStock
    CJPY = "cjpy"  # 财经朋友圈
    CNINFO = "cninfo"  # 巨潮资讯网
    CSINDEX = "csindex"  # 中证指数
    SZSE = "szse"  # 深圳证券交易所
    YAHOO = "yahoo"  # Yahoo Finance
    BLOOMBERG = "bloomberg"  # Bloomberg
    REUTERS = "reuters"  # Reuters
    COMPANY_ANNOUNCEMENT = "company_announcement"  # 公司公告
    GOVERNMENT_POLICY = "government_policy"  # 政府政策
    INTERNAL = "internal"  # 内部来源
    OTHER = "other"  # 其他


class SourceReliabilityLevel(str, Enum):
    """来源可信度层级 - 按 Issue #42 要求定义"""

    OFFICIAL = "official"  # 官方来源（最高可信度）
    ESTABLISHED_MEDIA = "established_media"  # 权威媒体
    RESEARCH_INSTITUTE = "research_institute"  # 研究机构
    SPECIALIZED_MEDIA = "specialized_media"  # 专业媒体
    OPINION_LEADER = "opinion_leader"  # 意见领袖
    SOCIAL_MEDIA = "social_media"  # 社交媒体（最低可信度）
    UNKNOWN = "unknown"  # 未知可信度


class SubjectivityLevel(str, Enum):
    """主观性层级"""

    FACT_ONLY = "fact_only"  # 纯事实
    FACT_HEAVY = "fact_heavy"  # 事实为主
    MIXED = "mixed"  # 事实观点混合
    OPINION_HEAVY = "opinion_heavy"  # 观点为主
    OPINION_ONLY = "opinion_only"  # 纯观点


class DocumentProcessingStatus(str, Enum):
    """处理状态"""

    RAW = "raw"  # 原始状态
    PARSED = "parsed"  # 已解析
    CHUNKED = "chunked"  # 已分块
    CLASSIFIED = "classified"  # 已分类
    ENRICHED = "enriched"  # 已富集
    COMPLETE = "complete"  # 完成


class DocumentReviewStatus(str, Enum):
    """审核状态"""

    PENDING = "pending"  # 待审核
    APPROVED = "approved"  # 已通过
    REJECTED = "rejected"  # 已拒绝
    FLAGGED = "flagged"  # 已标记需关注


# =============================================================================
# Core Document Schema (Issue #42: 统一 JSON 主 schema)
# =============================================================================


class DocumentClassification(BaseModel):
    """文档分类信息"""

    doc_type: Optional[DocType] = Field(default=None, description="文档类型")
    source_type: Optional[SourceType] = Field(default=None, description="来源类型")
    primary_industry: Optional[str] = Field(default=None, description="主要行业")
    secondary_industries: List[str] = Field(default_factory=list, description="次要行业")
    topics: List[str] = Field(default_factory=list, description="主题标签")
    event_types: List[str] = Field(default_factory=list, description="事件类型")
    region: Optional[str] = Field(default=None, description="地域")


class DocumentQuality(BaseModel):
    """文档质量评分"""

    source_reliability_level: SourceReliabilityLevel = Field(
        default=SourceReliabilityLevel.UNKNOWN, description="来源可信度层级"
    )
    subjectivity_level: SubjectivityLevel = Field(
        default=SubjectivityLevel.MIXED, description="主观性层级"
    )
    fact_opinion_ratio: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="事实观点比例（1.0=纯事实，0.0=纯观点）"
    )
    research_usability_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="研究可用性评分（1.0=最有用）"
    )
    content_quality_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="内容质量评分"
    )
    is_fact_source: bool = Field(default=True, description="是否为事实来源")


class DocumentTimeliness(BaseModel):
    """文档时效性信息 - Issue #42 要求的关键时间字段"""

    publish_time: Optional[datetime] = Field(default=None, description="发布时间")
    publish_time_precision: Optional[str] = Field(
        default=None, description="发布时间精度（day/hour/minute/second）"
    )
    crawl_time: Optional[datetime] = Field(default=None, description="抓取时间")
    available_time: Optional[datetime] = Field(default=None, description="系统可用时间")
    event_time: Optional[datetime] = Field(default=None, description="事件发生时间")
    is_historical: bool = Field(default=False, description="是否为历史文档")
    is_live: bool = Field(default=False, description="是否为实时内容")


class DocumentEvidenceProfile(BaseModel):
    """文档证据概况 - 用于支持 RAG 检索"""

    has_explicit_facts: bool = Field(default=False, description="是否有明确事实")
    has_explicit_opinions: bool = Field(default=False, description="是否有明确观点")
    has_data_points: bool = Field(default=False, description="是否有数据点")
    has_quotes: bool = Field(default=False, description="是否有引述")
    has_analysis: bool = Field(default=False, description="是否有分析")
    has_recommendations: bool = Field(default=False, description="是否有建议")
    evidence_quality_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class DocumentProcessingMeta(BaseModel):
    """处理元数据"""

    status: DocumentProcessingStatus = Field(
        default=DocumentProcessingStatus.RAW, description="处理状态"
    )
    parser_version: Optional[str] = Field(default=None, description="解析器版本")
    chunker_version: Optional[str] = Field(default=None, description="分块器版本")
    classifier_version: Optional[str] = Field(default=None, description="分类器版本")
    enricher_version: Optional[str] = Field(default=None, description="富集器版本")
    processing_started_at: Optional[datetime] = Field(default=None, description="处理开始时间")
    processing_completed_at: Optional[datetime] = Field(default=None, description="处理完成时间")
    processing_errors: List[str] = Field(default_factory=list, description="处理错误")
    retry_count: int = Field(default=0, description="重试次数")


class DocumentReview(BaseModel):
    """审核信息"""

    status: DocumentReviewStatus = Field(default=DocumentReviewStatus.PENDING, description="审核状态")
    reviewer: Optional[str] = Field(default=None, description="审核人")
    reviewed_at: Optional[datetime] = Field(default=None, description="审核时间")
    review_notes: Optional[str] = Field(default=None, description="审核备注")
    needs_human_review: bool = Field(default=False, description="是否需要人工审核")
    flags: List[str] = Field(default_factory=list, description="标记项")


class DocumentV1(BaseModel):
    """
    AlphaFoundry v1 统一文档模型.

    这是 Issue #42 要求的统一 JSON 主 schema，整合了所有来源类型的文档。
    """

    doc_id: str = Field(description="文档唯一标识符")

    # 核心字段
    doc_type: DocType = Field(description="文档类型")
    source_type: SourceType = Field(description="来源类型")
    title: str = Field(description="标题")
    summary: Optional[str] = Field(default=None, description="摘要")
    content: str = Field(description="内容（正文/纯文本）")

    # 元数据
    doc_metadata: Dict[str, Any] = Field(default_factory=dict, description="文档元数据")
    source_metadata: Dict[str, Any] = Field(default_factory=dict, description="来源元数据")

    # 分类
    classification: DocumentClassification = Field(
        default_factory=DocumentClassification, description="分类信息"
    )

    # 质量评分
    quality: DocumentQuality = Field(default_factory=DocumentQuality, description="质量评分")

    # 证据概况
    evidence_profile: DocumentEvidenceProfile = Field(
        default_factory=DocumentEvidenceProfile, description="证据概况"
    )

    # 时效性
    timeliness: DocumentTimeliness = Field(default_factory=DocumentTimeliness, description="时效性信息")

    # 处理状态
    processing: DocumentProcessingMeta = Field(
        default_factory=DocumentProcessingMeta, description="处理元数据"
    )

    # 审核状态
    review: DocumentReview = Field(default_factory=DocumentReview, description="审核信息")

    # 额外字段
    extra: Dict[str, Any] = Field(default_factory=dict, description="额外字段")

    # 来源关联
    source_name: Optional[str] = Field(default=None, description="来源名称")
    source_url: Optional[str] = Field(default=None, description="来源URL")
    language: str = Field(default="zh", description="语言")
    content_hash: Optional[str] = Field(default=None, description="内容哈希（用于去重）")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "doc_id": "doc_001",
                    "doc_type": "telegram",
                    "source_type": "cls",
                    "title": "央行宣布降准0.5个百分点",
                    "summary": "中国人民银行决定下调金融机构存款准备金率",
                    "content": "中国人民银行决定，自2024年5月10日起，下调金融机构存款准备金率0.5个百分点...",
                    "quality": {
                        "source_reliability_level": "official",
                        "subjectivity_level": "fact_only",
                        "is_fact_source": True,
                    },
                    "timeliness": {
                        "publish_time": "2024-05-09T17:00:00Z",
                        "crawl_time": "2024-05-09T17:01:00Z",
                    },
                }
            ]
        }
    }


# =============================================================================
# Source-specific Schemas (Issue #42: 各来源扩展 schema)
# =============================================================================


class TelegramSchema(BaseModel):
    """电报/快讯特定 schema"""

    telegram_id: Optional[str] = Field(default=None, description="电报ID")
    channel: Optional[str] = Field(default=None, description="频道")
    is_breaking: bool = Field(default=False, description="是否为快讯")
    priority: Optional[int] = Field(default=None, description="优先级")
    symbols: List[str] = Field(default_factory=list, description="相关代码")


class NewsSchema(BaseModel):
    """新闻特定 schema"""

    author: Optional[str] = Field(default=None, description="作者")
    section: Optional[str] = Field(default=None, description="版面/栏目")
    word_count: Optional[int] = Field(default=None, description="字数")
    keywords: List[str] = Field(default_factory=list, description="关键词")
    related_companies: List[str] = Field(default_factory=list, description="相关公司")


class ReportSchema(BaseModel):
    """研报特定 schema"""

    report_type: Optional[str] = Field(default=None, description="报告类型")
    analyst: Optional[str] = Field(default=None, description="分析师")
    institution: Optional[str] = Field(default=None, description="机构")
    target_price: Optional[float] = Field(default=None, description="目标价")
    rating: Optional[str] = Field(default=None, description="评级")
    tickers: List[str] = Field(default_factory=list, description="相关标的")
    report_date: Optional[datetime] = Field(default=None, description="报告日期")
    is_pdf: bool = Field(default=True, description="是否为PDF")
    page_count: Optional[int] = Field(default=None, description="页数")


class WechatSchema(BaseModel):
    """公众号特定 schema"""

    account: Optional[str] = Field(default=None, description="公众号名称")
    account_id: Optional[str] = Field(default=None, description="公众号ID")
    author: Optional[str] = Field(default=None, description="作者")
    read_count: Optional[int] = Field(default=None, description="阅读数")
    like_count: Optional[int] = Field(default=None, description="点赞数")
    is_original: bool = Field(default=False, description="是否原创")
    tags: List[str] = Field(default_factory=list, description="标签")


class TranscriptSchema(BaseModel):
    """会议纪要特定 schema"""

    transcript_type: Optional[str] = Field(default=None, description="纪要类型")
    company: Optional[str] = Field(default=None, description="公司")
    event_date: Optional[datetime] = Field(default=None, description="会议日期")
    participants: List[str] = Field(default_factory=list, description="参会人")
    speakers: List[str] = Field(default_factory=list, description="发言人")
    qa_count: Optional[int] = Field(default=None, description="问答数量")
    duration_minutes: Optional[int] = Field(default=None, description="时长（分钟）")


# =============================================================================
# Chunk Schema (Issue #42: document_chunks 表)
# =============================================================================


class DocumentChunkV1(BaseModel):
    """文档分块模型"""

    chunk_id: str = Field(description="分块唯一标识符")
    doc_id: str = Field(description="文档ID")
    chunk_index: int = Field(description="分块索引（顺序）")
    chunk_type: str = Field(default="paragraph", description="分块类型")
    title: Optional[str] = Field(default=None, description="分块标题（如果有）")
    content: str = Field(description="分块内容")
    start_offset: Optional[int] = Field(default=None, description="在原文中的起始偏移")
    end_offset: Optional[int] = Field(default=None, description="在原文中的结束偏移")
    token_count: Optional[int] = Field(default=None, description="Token数量")

    # 语义信息
    topics: List[str] = Field(default_factory=list, description="主题")
    entities: List[str] = Field(default_factory=list, description="实体")
    summary: Optional[str] = Field(default=None, description="分块摘要")
    embedding: Optional[str] = Field(default=None, description="向量嵌入")

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# =============================================================================
# Tag Schema (Issue #42: document_tags 表)
# =============================================================================


class DocumentTagV1(BaseModel):
    """文档标签模型"""

    tag_id: str = Field(description="标签唯一标识符")
    doc_id: str = Field(description="文档ID")
    tag: str = Field(description="标签文本")
    tag_type: str = Field(default="topic", description="标签类型")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="置信度")
    source: Optional[str] = Field(default=None, description="标签来源（rule/model/human）")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# =============================================================================
# Document Summary Schema (Issue #42: document_summaries 表)
# =============================================================================


class DocumentSummaryV1(BaseModel):
    """文档摘要模型"""

    summary_id: str = Field(description="摘要唯一标识符")
    doc_id: str = Field(description="文档ID")
    summary_type: str = Field(default="short", description="摘要类型（short/long/bullet）")
    summary: str = Field(description="摘要内容")
    bullet_points: List[str] = Field(default_factory=list, description="要点列表")
    generator_version: Optional[str] = Field(default=None, description="生成器版本")
    quality_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="质量评分")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# =============================================================================
# Entity Mention Schema (Issue #42: document_entity_mentions 表)
# =============================================================================


class EntityMentionV1(BaseModel):
    """实体提及模型"""

    mention_id: str = Field(description="提及唯一标识符")
    doc_id: str = Field(description="文档ID")
    chunk_id: Optional[str] = Field(default=None, description="分块ID（如果有）")
    entity_id: Optional[str] = Field(default=None, description="实体ID（链接到entity表）")
    entity_name: str = Field(description="实体名称")
    entity_type: str = Field(description="实体类型")
    start_offset: Optional[int] = Field(default=None, description="起始偏移")
    end_offset: Optional[int] = Field(default=None, description="结束偏移")
    context: Optional[str] = Field(default=None, description="上下文")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="置信度")
    is_primary: bool = Field(default=False, description="是否为主要实体")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# =============================================================================
# Event Schema (Issue #42: events 表 - 与现有 canonical_event 集成)
# =============================================================================


class DocumentEventV1(BaseModel):
    """文档事件模型"""

    event_id: str = Field(description="事件唯一标识符")
    doc_id: str = Field(description="文档ID")
    canonical_event_id: Optional[str] = Field(
        default=None, description="规范事件ID（链接到canonical_event表）"
    )
    event_type: str = Field(description="事件类型")
    event_time: Optional[datetime] = Field(default=None, description="事件时间")
    subject_entity: Optional[str] = Field(default=None, description="主体实体")
    object_entity: Optional[str] = Field(default=None, description="对象实体")
    event_summary: str = Field(description="事件摘要")
    impact_direction: Optional[str] = Field(default=None, description="影响方向")
    evidence_text: Optional[str] = Field(default=None, description="证据文本")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="置信度")
    extra: Dict[str, Any] = Field(default_factory=dict, description="额外字段")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


# =============================================================================
# Crawl State Schemas (Issue #42: crawl_runs, source_cursors 表)
# =============================================================================


class CrawlRunV1(BaseModel):
    """抓取运行记录"""

    run_id: str = Field(description="运行唯一标识符")
    source_type: SourceType = Field(description="来源类型")
    status: str = Field(default="pending", description="状态")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    success_count: int = Field(default=0, description="成功数量")
    failure_count: int = Field(default=0, description="失败数量")
    skipped_count: int = Field(default=0, description="跳过数量")
    error_log: Optional[str] = Field(default=None, description="错误日志")
    config: Dict[str, Any] = Field(default_factory=dict, description="配置")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


class SourceCursorV1(BaseModel):
    """来源游标 - 用于增量抓取"""

    cursor_id: str = Field(description="游标唯一标识符")
    source_type: SourceType = Field(description="来源类型")
    source_name: Optional[str] = Field(default=None, description="来源名称")
    last_successful_crawl_time: Optional[datetime] = Field(default=None, description="上次成功抓取时间")
    last_source_doc_id: Optional[str] = Field(default=None, description="上次抓取的文档ID")
    lookback_window_minutes: int = Field(default=60, description="回看窗口（分钟）")
    consecutive_failures: int = Field(default=0, description="连续失败次数")
    is_paused: bool = Field(default=False, description="是否暂停")
    config: Dict[str, Any] = Field(default_factory=dict, description="配置")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")


# =============================================================================
# Report Run Schema (Issue #42: report_runs 表)
# =============================================================================


class ReportRunV1(BaseModel):
    """报告运行记录"""

    run_id: str = Field(description="运行唯一标识符")
    report_type: str = Field(description="报告类型")
    report_template: Optional[str] = Field(default=None, description="报告模板")
    status: str = Field(default="pending", description="状态")
    config: Dict[str, Any] = Field(default_factory=dict, description="配置")
    document_ids: List[str] = Field(default_factory=list, description="使用的文档ID列表")
    signal_ids: List[str] = Field(default_factory=list, description="使用的信号ID列表")
    output_path: Optional[str] = Field(default=None, description="输出路径")
    error_log: Optional[str] = Field(default=None, description="错误日志")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
