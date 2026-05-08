"""Model/Prompt/Strategy Governance & Experiment Tracking 契约。

版本化 prompts、extraction strategies、mapping heuristics、timing weights、scoring logic，
追踪每个 signal / replay / simulation 的策略来源，支持实验对比和回滚。
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── 策略组件类型 ──────────────────────────────────────

class StrategyComponentType(str, Enum):
    """策略组件类型"""
    PROMPT = "prompt"
    EXTRACTION_STRATEGY = "extraction_strategy"
    MAPPING_HEURISTIC = "mapping_heuristic"
    TIMING_WEIGHT = "timing_weight"
    SCORING_LOGIC = "scoring_logic"


# ─── 策略版本 ──────────────────────────────────────────

class StrategyVersion(BaseModel):
    """策略版本 — 记录一个策略组件的具体版本。

    每个 StrategyVersion 代表某个组件（prompt/extraction/mapping/timing/scoring）
    在某个时间点的快照，包含版本号、内容摘要和完整配置。
    """
    version_id: str
    component_type: StrategyComponentType
    component_name: str
    version_number: int = 1
    description: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""
    parent_version_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    created_by: str = "system"
    tags: List[str] = Field(default_factory=list)


class StrategyVersionCreateRequest(BaseModel):
    """创建策略版本请求"""
    component_type: StrategyComponentType
    component_name: str
    description: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)
    parent_version_id: Optional[str] = None
    created_by: str = "system"
    tags: List[str] = Field(default_factory=list)


# ─── 实验记录 ──────────────────────────────────────────

class ExperimentRecord(BaseModel):
    """实验记录 — 关联一次实验运行中使用的策略版本集合和产生的结果。

    每次信号生成、回放或模拟运行都可以记录为一个实验，
    包含使用的策略版本集合和输出的指标。
    """
    experiment_id: str
    name: str
    description: str = ""
    strategy_version_ids: List[str] = Field(default_factory=list)
    experiment_type: str = "signal"  # signal / replay / simulation
    entity_id: Optional[str] = None  # 关联的 signal_id / job_id / result_id
    metrics: Dict[str, float] = Field(default_factory=dict)
    status: str = "running"  # running / completed / failed
    started_at: datetime
    completed_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExperimentCreateRequest(BaseModel):
    """创建实验记录请求"""
    name: str
    description: str = ""
    strategy_version_ids: List[str] = Field(default_factory=list)
    experiment_type: str = "signal"
    entity_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── 实验对比 ──────────────────────────────────────────

class ExperimentMetricDiff(BaseModel):
    """实验指标差异"""
    metric_name: str
    experiment_a_value: Optional[float] = None
    experiment_b_value: Optional[float] = None
    diff: Optional[float] = None
    pct_change: Optional[float] = None


class ExperimentComparison(BaseModel):
    """实验对比 — 两个实验的 side-by-side 对比。"""
    experiment_a_id: str
    experiment_b_id: str
    experiment_a_name: str = ""
    experiment_b_name: str = ""
    common_metrics: List[ExperimentMetricDiff] = Field(default_factory=list)
    strategy_diffs: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class ExperimentCompareRequest(BaseModel):
    """实验对比请求"""
    experiment_a_id: str
    experiment_b_id: str


# ─── 治理报告 ──────────────────────────────────────────

class StrategyVersionSummary(BaseModel):
    """策略版本摘要"""
    component_type: StrategyComponentType
    component_name: str
    active_version_id: Optional[str] = None
    active_version_number: Optional[int] = None
    total_versions: int = 0


class GovernanceReport(BaseModel):
    """治理报告 — 当前所有策略组件的版本状态和实验摘要。"""
    generated_at: datetime
    strategy_summaries: List[StrategyVersionSummary] = Field(default_factory=list)
    total_experiments: int = 0
    recent_experiment_ids: List[str] = Field(default_factory=list)
    active_strategy_count: int = 0
    rollback_candidates: List[Dict[str, Any]] = Field(default_factory=list)


# ─── 回滚 ──────────────────────────────────────────────

class RollbackRequest(BaseModel):
    """回滚请求 — 将某个策略组件回滚到指定版本。"""
    component_type: StrategyComponentType
    component_name: str
    target_version_id: str


class RollbackResult(BaseModel):
    """回滚结果"""
    component_type: StrategyComponentType
    component_name: str
    previous_active_version_id: Optional[str] = None
    new_active_version_id: str
    success: bool
    message: str = ""


# ─── Governance Metadata（关联现有实体）──────────────────

class GovernanceMetadata(BaseModel):
    """治理元数据 — 可嵌入 signal / replay / simulation 记录中。"""
    strategy_version_id: Optional[str] = None
    experiment_id: Optional[str] = None
    component_versions: Dict[str, str] = Field(default_factory=dict)  # component_name -> version_id
