"""API 请求/响应模型"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ─── 通用 ───────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """统一错误响应"""

    error: str
    detail: Optional[str] = None


# ─── 资产分析 ───────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    """资产分析请求"""

    canonical_id: str = Field(..., description="资产代码，如 600000.SH")
    as_of: Optional[datetime] = Field(None, description="快照时间，默认当前时间")
    source: str = Field(
        "auto", description="数据源: auto（自动降级）/ mock / local / ifind / akshare"
    )
    use_mock: Optional[bool] = Field(None, description="是否使用模拟数据")
    time_range: Optional[str] = Field(
        None, description="时间范围: 1M/3M/6M/1Y/2Y/3Y/5Y/ALL，默认1Y"
    )


class AnalyzeResponse(BaseModel):
    """资产分析响应"""

    canonical_id: str
    as_of: datetime
    financial: Dict[str, Any] = Field(default_factory=dict)
    fund_flow: Dict[str, Any] = Field(default_factory=dict)
    price_volume: Dict[str, Any] = Field(default_factory=dict)
    valuation: Dict[str, Any] = Field(default_factory=dict)
    shareholder: Dict[str, Any] = Field(default_factory=dict)
    industry: Dict[str, Any] = Field(default_factory=dict)
    event_impact: List[str] = Field(default_factory=list)
    macro_exposure: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[str] = Field(default_factory=list)


# ─── 情景分析 ───────────────────────────────────────────


class ScenarioRequest(BaseModel):
    """情景生成请求"""

    topic: str = Field(..., description="研究主题")
    subject_ids: Optional[List[str]] = Field(None, description="主题 ID 列表")
    use_evidence: bool = Field(True, description="是否使用真实证据")
    min_evidence_count: int = Field(1, description="最低证据数量阈值")
    regime_filter: Optional[str] = Field(None, description="市场环境过滤")


class ScenarioEvidence(BaseModel):
    """场景证据"""

    events: List[Dict[str, Any]] = Field(default_factory=list, description="相关历史事件")
    outcomes: List[Dict[str, Any]] = Field(default_factory=list, description="相关 Outcome 记录")


class ScenarioHypothesisResponse(BaseModel):
    """情景假设响应"""

    scenario_id: str
    title: str
    horizon: str
    probability: float
    assumptions: List[str] = Field(default_factory=list)
    key_triggers: List[str] = Field(default_factory=list)
    invalidation_signals: List[str] = Field(default_factory=list)
    impact_map: Dict[str, Any] = Field(default_factory=dict)
    evidence_assertion_ids: List[str] = Field(default_factory=list)
    confidence: float
    evidence: ScenarioEvidence = Field(
        default_factory=ScenarioEvidence, description="真实事件/Outcome 证据"
    )
    evidence_strength: str = Field(default="none", description="证据强度: high/medium/low/none")


class ScenarioResponse(BaseModel):
    """情景集合响应"""

    set_id: str
    question: str
    hypotheses: List[ScenarioHypothesisResponse] = Field(default_factory=list)
    normalization_check: bool = False
    residual_uncertainty: List[str] = Field(default_factory=list)
    propagation_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="传播模式")
    regime_summaries: List[Dict[str, Any]] = Field(default_factory=list, description="市场环境摘要")


# ─── 审核 ───────────────────────────────────────────────


class ReviewItemResponse(BaseModel):
    """审核项响应"""

    assertion_id: str
    subject_entity_id: Optional[str] = None
    predicate: str
    confidence: float
    source_doc_id: str
    reviewer_status: str
    reviewer: Optional[str] = None


class ReviewStatsResponse(BaseModel):
    """审核统计响应"""

    pending_assertions: int = 0
    approved_assertions: int = 0
    rejected_assertions: int = 0
    pending_events: int = 0


class ReviewActionResponse(BaseModel):
    """审核操作响应"""

    item_id: str
    action: str
    success: bool
    message: Optional[str] = None


# ─── 信号 ───────────────────────────────────────────────


class SignalCreateRequest(BaseModel):
    """信号创建请求"""

    subject_id: str = Field(..., description="主体ID")
    thesis: str = Field(..., description="研究论点")
    horizon: str = Field("20d", description="预测期: 1d / 5d / 20d / 60d")
    score: float = Field(0.5, ge=0.0, le=1.0, description="分数")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="置信度")
    scenario_refs: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    status: str = Field("research_only", description="状态")


class SignalResponse(BaseModel):
    """信号响应"""

    signal_id: str
    subject_id: str
    horizon: str
    thesis: str
    score: float
    confidence: float
    scenario_refs: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    status: str


class SignalValidateResponse(BaseModel):
    """信号验证响应"""

    signal_id: str
    composite_score: float
    features: Dict[str, Any] = Field(default_factory=dict)
    backtest: Dict[str, Any] = Field(default_factory=dict)
    validated_at: str


class SignalPromoteResponse(BaseModel):
    """信号升级响应"""

    signal_id: str
    old_status: Optional[str] = None
    new_status: str
    success: bool
    message: Optional[str] = None


# ─── 摄入 ───────────────────────────────────────────────


class IngestTextRequest(BaseModel):
    """文本摄入请求"""

    text: str = Field(..., description="文本内容")
    source_type: str = Field("report", description="来源类型")
    source_name: str = Field("unknown", description="来源名称")
    title: Optional[str] = Field(None, description="标题")


class IngestResponse(BaseModel):
    """摄入响应"""

    doc_id: str
    title: str
    assertions_extracted: int = 0
    assertions_approved: int = 0
    assertions_pending: int = 0
    events_extracted: int = 0
    events_approved: int = 0
    events_pending: int = 0


# ─── 摄入监控 ───────────────────────────────────────────


class IngestSourceStatus(BaseModel):
    """单个来源的摄入状态"""

    source_type: str
    source_name: Optional[str] = None
    status: str = "unknown"  # running/paused/error/unknown
    last_fetch: Optional[str] = None
    total_fetched: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    dedupe_rate: float = 0.0
    is_paused: bool = False
    pause_reason: Optional[str] = None
    watermark_id: Optional[str] = None
    watermark_timestamp: Optional[str] = None


class PDFStats(BaseModel):
    """PDF 统计"""

    total_pdfs: int = 0
    pending_conversion: int = 0
    converted: int = 0
    failed_conversion: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict)


class IngestOverviewResponse(BaseModel):
    """摄入状态概览"""

    sources: Dict[str, IngestSourceStatus] = Field(default_factory=dict)
    pdf_stats: PDFStats = Field(default_factory=PDFStats)
    overall_health: str = "healthy"
    generated_at: str


class ProcessedItemResponse(BaseModel):
    """已处理项目响应"""

    item_id: str
    source_type: str
    source_name: Optional[str] = None
    item_type: str
    title: Optional[str] = None
    content_preview: Optional[str] = None
    content_hash: Optional[str] = None
    first_seen_at: str
    first_processed_at: Optional[str] = None
    process_count: int = 1


class ProcessedStatsResponse(BaseModel):
    """已处理统计响应"""

    total_items: int = 0
    by_source_type: Dict[str, int] = Field(default_factory=dict)
    daily_stats: List[Dict[str, Any]] = Field(default_factory=list)


class PDFArtifactResponse(BaseModel):
    """PDF 制品响应"""

    pdf_id: str
    doc_id: Optional[str] = None
    source_obj_id: Optional[str] = None
    file_path: str
    file_name: str
    file_size_bytes: int
    file_hash_sha256: str
    source_type: str
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    source_broker: Optional[str] = None
    fetch_timestamp: str
    parse_status: str = "pending"
    parse_error: Optional[str] = None


# ─── 摄入管理 ───────────────────────────────────────────


class IngestTriggerRequest(BaseModel):
    """手动触发摄入请求"""

    mode: str = Field("incremental", description="incremental/full")
    dry_run: bool = Field(False, description="是否只预览不执行")


class IngestTriggerResponse(BaseModel):
    """触发响应"""

    source_type: str
    triggered: bool
    dry_run: bool
    message: Optional[str] = None
    estimated_items: Optional[int] = None


class IngestPauseRequest(BaseModel):
    """暂停摄入请求"""

    reason: str = Field(..., description="暂停原因")


class IngestPauseResponse(BaseModel):
    """暂停响应"""

    source_type: str
    paused: bool
    reason: str


class IngestResumeResponse(BaseModel):
    """恢复响应"""

    source_type: str
    resumed: bool


class IngestResetResponse(BaseModel):
    """重置响应"""

    source_type: str
    reset: bool
    message: Optional[str] = None


class IngestConfigResponse(BaseModel):
    """配置响应"""

    source_type: str
    crawl_config: Dict[str, Any] = Field(default_factory=dict)
    crawl_mode: str = "incremental"
    is_paused: bool = False


class IngestConfigUpdate(BaseModel):
    """配置更新请求"""

    crawl_config: Optional[Dict[str, Any]] = None
    crawl_mode: Optional[str] = None
