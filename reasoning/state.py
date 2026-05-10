"""
推理引擎 - 状态定义
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RequestType(str, Enum):
    """请求类型"""

    ASSET_ANALYSIS = "asset_analysis"  # 资产分析
    THESIS_RESEARCH = "thesis_research"  # 专题研究
    MARKET_REPORT = "market_report"  # 市场报告
    SIGNAL_VALIDATION = "signal_validation"  # 信号验证


class ScenarioHypothesis(BaseModel):
    """情景假设"""

    scenario_id: str
    title: str
    horizon: str = "mid"  # short/mid/long
    probability: float = Field(ge=0.0, le=1.0)
    assumptions: List[str] = Field(default_factory=list)
    key_triggers: List[str] = Field(default_factory=list)
    invalidation_signals: List[str] = Field(default_factory=list)
    impact_map: Dict = Field(default_factory=dict)
    evidence_assertion_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.7


class ReasoningState(BaseModel):
    """推理状态"""

    # 输入
    request_type: RequestType
    question: str
    subject_ids: List[str] = Field(default_factory=list)

    # 中间结果
    retrieved_doc_ids: List[str] = Field(default_factory=list)
    retrieved_assertion_ids: List[str] = Field(default_factory=list)
    retrieved_events: List[Dict] = Field(default_factory=list)

    # 假设
    hypotheses: List[ScenarioHypothesis] = Field(default_factory=list)
    residual_uncertainty: List[str] = Field(default_factory=list)

    # 反证审查结果
    skeptic_notes: List[str] = Field(default_factory=list)

    # 输出
    final_answer: Optional[str] = None
    report_sections: List[Dict] = Field(default_factory=list)

    # 追踪信息
    trace_id: Optional[str] = None
    provider: str = "unknown"
    model_name: str = "unknown"
    prompt_version: str = "v1"
    total_latency_ms: int = 0
    total_tokens: int = 0

    # 元数据
    metadata: Dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


def create_initial_state(
    request_type: RequestType,
    question: str,
    subject_ids: Optional[List[str]] = None,
) -> ReasoningState:
    """创建初始状态"""
    return ReasoningState(
        request_type=request_type,
        question=question,
        subject_ids=subject_ids or [],
    )
