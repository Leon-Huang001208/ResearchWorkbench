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
    source: str = Field("auto", description="数据源: auto（自动降级）/ mock / local / ifind / akshare")
    use_mock: Optional[bool] = Field(None, description="是否使用模拟数据")


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
