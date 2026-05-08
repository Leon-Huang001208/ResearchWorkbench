"""分析师循环决策控制台契约。

定义决策工作区、决策动作、审计记录和复盘记录的数据结构。
"""
from datetime import datetime
from typing import Literal, Optional, List, Dict

from pydantic import BaseModel, Field


class DecisionAction(BaseModel):
    """分析师可执行的决策动作"""

    action_type: Literal["approve", "watch", "reject", "defer", "revise_thesis", "add_to_paper_portfolio"]
    action_by: str  # 分析师ID/名称
    action_at: datetime = Field(default_factory=datetime.utcnow)
    rationale: str  # 决策理由
    changes: Optional[Dict[str, str]] = None  # 修改的内容，key为修改字段，value为修改描述


class AnalystDecision(BaseModel):
    """分析师对单个候选的决策"""

    decision_id: str
    workspace_id: str
    candidate_id: str  # 可以是PortfolioCandidate或AlphaSignal的ID
    candidate_type: Literal["signal", "portfolio_candidate", "proposal"]
    previous_status: str
    final_action: DecisionAction
    revision_history: List[DecisionAction] = Field(default_factory=list)
    is_closed: bool = False


class DecisionWorkspace(BaseModel):
    """每日决策工作区"""

    workspace_id: str
    workspace_date: datetime
    status: Literal["open", "in_review", "closed"] = "open"
    candidate_ids: List[str] = Field(default_factory=list)
    team_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str
    closed_at: Optional[datetime] = None
    notes: Optional[str] = None


class DecisionAudit(BaseModel):
    """决策审计记录"""

    audit_id: str
    decision_id: str
    action: str
    actor: str
    timestamp: datetime
    before_state: Dict
    after_state: Dict
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class PostMortemRecord(BaseModel):
    """决策复盘记录"""

    post_mortem_id: str
    decision_id: str
    original_decision: str
    realized_outcome: Literal["win", "loss", "draw", "pending"]
    outcome_metrics: Dict[str, float] = Field(default_factory=dict)
    learning_points: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    linked_signal_accuracy: Optional[float] = None
