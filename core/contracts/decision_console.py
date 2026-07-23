"""
Core contracts for the analyst decision console.

This module defines Pydantic models for decision workspaces, decision actions,
auditing records, and post-mortem (review) records, standardizing the data
structures used in the AlphaFoundry decision-making workflow.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DecisionAction(BaseModel):
    """分析师可执行的决策动作.

    Represents an action taken by an analyst on a candidate, including action type,
    actor, timestamp, rationale, and any changes made.

    Attributes:
        action_type: Type of action (approve, watch, reject, defer, revise_thesis, add_to_paper_portfolio).
        action_by: Identifier or name of the analyst who took the action.
        action_at: Timestamp when the action was taken (defaults to UTC now).
        rationale: Rationale or justification for the action.
        changes: Optional dictionary of changes made (key: field name, value: description of change).
    """

    action_type: Literal[
        "approve", "watch", "reject", "defer", "revise_thesis", "add_to_paper_portfolio"
    ] = Field(description="Type of decision action")
    action_by: str = Field(description="Identifier or name of the analyst who took the action")
    action_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when the action was taken"
    )
    rationale: str = Field(description="Rationale or justification for the action")
    changes: Optional[Dict[str, str]] = Field(
        default=None, description="Optional dictionary of changes made"
    )


class AnalystDecision(BaseModel):
    """分析师对单个候选的决策.

    Represents an analyst's decision on a single candidate, including decision ID,
    workspace ID, candidate information, previous status, final action, revision history,
    and whether the decision is closed.

    Attributes:
        decision_id: Unique identifier for the decision.
        workspace_id: Unique identifier for the associated decision workspace.
        candidate_id: Unique identifier for the candidate (signal, portfolio candidate, or proposal).
        candidate_type: Type of candidate (signal, portfolio_candidate, proposal).
        previous_status: Previous status of the candidate before this decision.
        final_action: The final decision action taken.
        revision_history: List of previous decision actions (revision history).
        is_closed: Whether the decision is closed (True) or still open (False).
    """

    decision_id: str = Field(description="Unique identifier for the decision")
    workspace_id: str = Field(description="Unique identifier for the associated decision workspace")
    candidate_id: str = Field(
        description="Unique identifier for the candidate (signal, portfolio candidate, or proposal)"
    )
    candidate_type: Literal["signal", "portfolio_candidate", "proposal"] = Field(
        description="Type of candidate"
    )
    previous_status: str = Field(
        description="Previous status of the candidate before this decision"
    )
    final_action: DecisionAction = Field(description="The final decision action taken")
    revision_history: List[DecisionAction] = Field(
        default_factory=list, description="List of previous decision actions"
    )
    is_closed: bool = Field(default=False, description="Whether the decision is closed")


class DecisionWorkspace(BaseModel):
    """每日决策工作区.

    Represents a daily decision workspace, including workspace ID, date, status,
    candidate IDs, team ID, creation info, closure info, and notes.

    Attributes:
        workspace_id: Unique identifier for the workspace.
        workspace_date: Date for which this workspace is intended.
        status: Status of the workspace (open, in_review, closed).
        candidate_ids: List of candidate IDs included in this workspace.
        team_id: Optional team ID for multi-tenant environments.
        created_at: Timestamp when the workspace was created (defaults to UTC now).
        created_by: Identifier or name of the user who created the workspace.
        closed_at: Timestamp when the workspace was closed (if applicable).
        notes: Optional notes about the workspace.
    """

    workspace_id: str = Field(description="Unique identifier for the workspace")
    workspace_date: datetime = Field(description="Date for which this workspace is intended")
    status: Literal["open", "in_review", "closed"] = Field(
        default="open", description="Status of the workspace"
    )
    candidate_ids: List[str] = Field(
        default_factory=list, description="List of candidate IDs in this workspace"
    )
    team_id: Optional[str] = Field(default=None, description="Optional team ID")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when the workspace was created"
    )
    created_by: str = Field(description="Identifier or name of the user who created the workspace")
    closed_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the workspace was closed (if applicable)"
    )
    notes: Optional[str] = Field(default=None, description="Optional notes about the workspace")


class DecisionAudit(BaseModel):
    """决策审计记录.

    Represents an audit record for a decision, including audit ID, decision ID,
    action, actor, timestamp, before/after state, IP address, and user agent.

    Attributes:
        audit_id: Unique identifier for the audit record.
        decision_id: Unique identifier for the associated decision.
        action: Action that was taken (e.g., "approve", "revise_thesis").
        actor: Identifier or name of the user who took the action.
        timestamp: Timestamp when the action was taken.
        before_state: State of the decision before the action.
        after_state: State of the decision after the action.
        ip_address: Optional IP address of the user (if available).
        user_agent: Optional user agent of the user (if available).
    """

    audit_id: str = Field(description="Unique identifier for the audit record")
    decision_id: str = Field(description="Unique identifier for the associated decision")
    action: str = Field(description="Action that was taken")
    actor: str = Field(description="Identifier or name of the user who took the action")
    timestamp: datetime = Field(description="Timestamp when the action was taken")
    before_state: Dict = Field(description="State of the decision before the action")
    after_state: Dict = Field(description="State of the decision after the action")
    ip_address: Optional[str] = Field(default=None, description="Optional IP address of the user")
    user_agent: Optional[str] = Field(default=None, description="Optional user agent of the user")


class PostMortemRecord(BaseModel):
    """决策复盘记录.

    Represents a post-mortem (review) record for a decision, including post-mortem ID,
    decision ID, original decision, realized outcome, outcome metrics, learning points,
    creation/update timestamps, and linked signal accuracy.

    Attributes:
        post_mortem_id: Unique identifier for the post-mortem record.
        decision_id: Unique identifier for the associated decision.
        original_decision: Description of the original decision.
        realized_outcome: Realized outcome (win, loss, draw, pending).
        outcome_metrics: Dictionary of outcome metrics (e.g., return, win rate).
        learning_points: Key learning points from the post-mortem.
        created_at: Timestamp when the post-mortem was created (defaults to UTC now).
        updated_at: Timestamp when the post-mortem was last updated (defaults to UTC now).
        linked_signal_accuracy: Optional accuracy score of the linked signal (if applicable).
    """

    post_mortem_id: str = Field(description="Unique identifier for the post-mortem record")
    decision_id: str = Field(description="Unique identifier for the associated decision")
    original_decision: str = Field(description="Description of the original decision")
    realized_outcome: Literal["win", "loss", "draw", "pending"] = Field(
        description="Realized outcome"
    )
    outcome_metrics: Dict[str, float] = Field(
        default_factory=dict, description="Dictionary of outcome metrics"
    )
    learning_points: str = Field(description="Key learning points from the post-mortem")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when the post-mortem was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the post-mortem was last updated",
    )
    linked_signal_accuracy: Optional[float] = Field(
        default=None, description="Optional accuracy score of the linked signal"
    )
