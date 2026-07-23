"""
Core contracts for model/prompt/strategy governance and experiment tracking.

This module defines Pydantic models for versioning prompts, extraction strategies,
mapping heuristics, timing weights, and scoring logic; tracking the strategy
sources for signals, replays, and simulations; and supporting experiment
comparison and rollback functionality.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ─── 策略组件类型 ──────────────────────────────────────


class StrategyComponentType(str, Enum):
    """策略组件类型.

    Enumeration of strategy component types, including prompts, extraction strategies,
    mapping heuristics, timing weights, and scoring logic.
    """

    PROMPT = "prompt"
    EXTRACTION_STRATEGY = "extraction_strategy"
    MAPPING_HEURISTIC = "mapping_heuristic"
    TIMING_WEIGHT = "timing_weight"
    SCORING_LOGIC = "scoring_logic"


# ─── 策略版本 ──────────────────────────────────────────


class StrategyVersion(BaseModel):
    """策略版本 — 记录一个策略组件的具体版本.

    Each StrategyVersion represents a snapshot of a component (prompt, extraction,
    mapping, timing, scoring) at a specific point in time, including version number,
    description, configuration, content hash, parent version, active status, creation
    info, and tags.

    Attributes:
        version_id: Unique identifier for the strategy version.
        component_type: Type of the strategy component.
        component_name: Name of the strategy component.
        version_number: Version number (starting from 1).
        description: Description of this version.
        config: Configuration dictionary for this version.
        content_hash: Hash of the component's content (for integrity checks).
        parent_version_id: Optional ID of the parent version (if this is a derivative).
        is_active: Whether this version is currently active (True) or not (False).
        created_at: Timestamp when this version was created.
        created_by: Identifier or name of the user who created this version (default "system").
        tags: List of tags for categorization.
    """

    version_id: str = Field(description="Unique identifier for the strategy version")
    component_type: StrategyComponentType = Field(description="Type of the strategy component")
    component_name: str = Field(description="Name of the strategy component")
    version_number: int = Field(default=1, description="Version number")
    description: str = Field(default="", description="Description of this version")
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuration dictionary")
    content_hash: str = Field(default="", description="Hash of the component's content")
    parent_version_id: Optional[str] = Field(
        default=None, description="Optional ID of the parent version"
    )
    is_active: bool = Field(default=True, description="Whether this version is currently active")
    created_at: datetime = Field(description="Timestamp when this version was created")
    created_by: str = Field(default="system", description="Identifier or name of the creator")
    tags: List[str] = Field(default_factory=list, description="List of tags for categorization")


class StrategyVersionCreateRequest(BaseModel):
    """创建策略版本请求.

    Request schema for creating a new strategy version, including component type,
    component name, description, config, parent version, creator, and tags.

    Attributes:
        component_type: Type of the strategy component.
        component_name: Name of the strategy component.
        description: Description of the new version.
        config: Configuration dictionary for the new version.
        parent_version_id: Optional ID of the parent version (if applicable).
        created_by: Identifier or name of the user creating this version (default "system").
        tags: List of tags for categorization.
    """

    component_type: StrategyComponentType = Field(description="Type of the strategy component")
    component_name: str = Field(description="Name of the strategy component")
    description: str = Field(default="", description="Description of the new version")
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuration dictionary")
    parent_version_id: Optional[str] = Field(
        default=None, description="Optional ID of the parent version"
    )
    created_by: str = Field(default="system", description="Identifier or name of the creator")
    tags: List[str] = Field(default_factory=list, description="List of tags for categorization")


# ─── 实验记录 ──────────────────────────────────────────


class ExperimentRecord(BaseModel):
    """实验记录 — 关联一次实验运行中使用的策略版本集合和产生的结果.

    Each signal generation, replay, or simulation run can be recorded as an experiment,
    containing the set of strategy versions used and the output metrics.

    Attributes:
        experiment_id: Unique identifier for the experiment.
        name: Name of the experiment.
        description: Description of the experiment.
        strategy_version_ids: List of strategy version IDs used in this experiment.
        experiment_type: Type of experiment (signal, replay, simulation) (default "signal").
        entity_id: Optional ID of the associated entity (signal_id, job_id, result_id).
        metrics: Dictionary of metrics generated by the experiment.
        status: Status of the experiment (running, completed, failed) (default "running").
        started_at: Timestamp when the experiment started.
        completed_at: Timestamp when the experiment completed (if applicable).
        tags: List of tags for categorization.
        metadata: Additional metadata as a dictionary.
    """

    experiment_id: str = Field(description="Unique identifier for the experiment")
    name: str = Field(description="Name of the experiment")
    description: str = Field(default="", description="Description of the experiment")
    strategy_version_ids: List[str] = Field(
        default_factory=list, description="List of strategy version IDs used"
    )
    experiment_type: str = Field(
        default="signal", description="Type of experiment (signal, replay, simulation)"
    )
    entity_id: Optional[str] = Field(
        default=None, description="Optional ID of the associated entity"
    )
    metrics: Dict[str, float] = Field(default_factory=dict, description="Dictionary of metrics")
    status: str = Field(
        default="running", description="Status of the experiment (running, completed, failed)"
    )
    started_at: datetime = Field(description="Timestamp when the experiment started")
    completed_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the experiment completed (if applicable)"
    )
    tags: List[str] = Field(default_factory=list, description="List of tags for categorization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ExperimentCreateRequest(BaseModel):
    """创建实验记录请求.

    Request schema for creating a new experiment record, including name, description,
    strategy version IDs, experiment type, entity ID, tags, and metadata.

    Attributes:
        name: Name of the experiment.
        description: Description of the experiment.
        strategy_version_ids: List of strategy version IDs to use.
        experiment_type: Type of experiment (signal, replay, simulation) (default "signal").
        entity_id: Optional ID of the associated entity (if applicable).
        tags: List of tags for categorization.
        metadata: Additional metadata as a dictionary.
    """

    name: str = Field(description="Name of the experiment")
    description: str = Field(default="", description="Description of the experiment")
    strategy_version_ids: List[str] = Field(
        default_factory=list, description="List of strategy version IDs to use"
    )
    experiment_type: str = Field(
        default="signal", description="Type of experiment (signal, replay, simulation)"
    )
    entity_id: Optional[str] = Field(
        default=None, description="Optional ID of the associated entity"
    )
    tags: List[str] = Field(default_factory=list, description="List of tags for categorization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# ─── 实验对比 ──────────────────────────────────────────


class ExperimentMetricDiff(BaseModel):
    """实验指标差异.

    Represents the difference in a metric between two experiments, including metric name,
    values from both experiments, absolute difference, and percentage change.

    Attributes:
        metric_name: Name of the metric.
        experiment_a_value: Value of the metric from experiment A (if available).
        experiment_b_value: Value of the metric from experiment B (if available).
        diff: Absolute difference between the two values (if available).
        pct_change: Percentage change between the two values (if available).
    """

    metric_name: str = Field(description="Name of the metric")
    experiment_a_value: Optional[float] = Field(
        default=None, description="Value from experiment A (if available)"
    )
    experiment_b_value: Optional[float] = Field(
        default=None, description="Value from experiment B (if available)"
    )
    diff: Optional[float] = Field(
        default=None, description="Absolute difference between the two values (if available)"
    )
    pct_change: Optional[float] = Field(
        default=None, description="Percentage change between the two values (if available)"
    )


class ExperimentComparison(BaseModel):
    """实验对比 — 两个实验的 side-by-side 对比.

    Represents a side-by-side comparison between two experiments, including both
    experiment IDs/names, common metrics with differences, strategy differences,
    and a summary.

    Attributes:
        experiment_a_id: Unique identifier for experiment A.
        experiment_b_id: Unique identifier for experiment B.
        experiment_a_name: Name of experiment A (optional).
        experiment_b_name: Name of experiment B (optional).
        common_metrics: List of metric differences between the two experiments.
        strategy_diffs: Dictionary of strategy differences between the two experiments.
        summary: Summary of the comparison.
    """

    experiment_a_id: str = Field(description="Unique identifier for experiment A")
    experiment_b_id: str = Field(description="Unique identifier for experiment B")
    experiment_a_name: str = Field(default="", description="Name of experiment A (optional)")
    experiment_b_name: str = Field(default="", description="Name of experiment B (optional)")
    common_metrics: List[ExperimentMetricDiff] = Field(
        default_factory=list, description="List of metric differences"
    )
    strategy_diffs: Dict[str, Any] = Field(
        default_factory=dict, description="Dictionary of strategy differences"
    )
    summary: str = Field(default="", description="Summary of the comparison")


class ExperimentCompareRequest(BaseModel):
    """实验对比请求.

    Request schema for comparing two experiments, including both experiment IDs.

    Attributes:
        experiment_a_id: Unique identifier for experiment A.
        experiment_b_id: Unique identifier for experiment B.
    """

    experiment_a_id: str = Field(description="Unique identifier for experiment A")
    experiment_b_id: str = Field(description="Unique identifier for experiment B")


# ─── 治理报告 ──────────────────────────────────────────


class StrategyVersionSummary(BaseModel):
    """策略版本摘要.

    Summary of a strategy component's versions, including component type, component name,
    active version ID/number, and total versions.

    Attributes:
        component_type: Type of the strategy component.
        component_name: Name of the strategy component.
        active_version_id: Unique identifier of the active version (if any).
        active_version_number: Version number of the active version (if any).
        total_versions: Total number of versions for this component.
    """

    component_type: StrategyComponentType = Field(description="Type of the strategy component")
    component_name: str = Field(description="Name of the strategy component")
    active_version_id: Optional[str] = Field(
        default=None, description="Unique identifier of the active version (if any)"
    )
    active_version_number: Optional[int] = Field(
        default=None, description="Version number of the active version (if any)"
    )
    total_versions: int = Field(
        default=0, description="Total number of versions for this component"
    )


class GovernanceReport(BaseModel):
    """治理报告 — 当前所有策略组件的版本状态和实验摘要.

    Represents a governance report, including generation timestamp, strategy summaries,
    total experiments, recent experiment IDs, active strategy count, and rollback candidates.

    Attributes:
        generated_at: Timestamp when this report was generated.
        strategy_summaries: List of strategy version summaries.
        total_experiments: Total number of experiments recorded.
        recent_experiment_ids: List of IDs of recent experiments.
        active_strategy_count: Number of currently active strategies.
        rollback_candidates: List of candidate versions for potential rollback.
    """

    generated_at: datetime = Field(description="Timestamp when this report was generated")
    strategy_summaries: List[StrategyVersionSummary] = Field(
        default_factory=list, description="List of strategy version summaries"
    )
    total_experiments: int = Field(default=0, description="Total number of experiments recorded")
    recent_experiment_ids: List[str] = Field(
        default_factory=list, description="List of IDs of recent experiments"
    )
    active_strategy_count: int = Field(
        default=0, description="Number of currently active strategies"
    )
    rollback_candidates: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of rollback candidates"
    )


# ─── 回滚 ──────────────────────────────────────────────


class RollbackRequest(BaseModel):
    """回滚请求 — 将某个策略组件回滚到指定版本.

    Request schema for rolling back a strategy component to a specific version,
    including component type, component name, and target version ID.

    Attributes:
        component_type: Type of the strategy component to roll back.
        component_name: Name of the strategy component to roll back.
        target_version_id: Unique identifier of the version to roll back to.
    """

    component_type: StrategyComponentType = Field(
        description="Type of the strategy component to roll back"
    )
    component_name: str = Field(description="Name of the strategy component to roll back")
    target_version_id: str = Field(description="Unique identifier of the version to roll back to")


class RollbackResult(BaseModel):
    """回滚结果.

    Represents the result of a rollback operation, including component type,
    component name, previous active version ID, new active version ID, success status,
    and message.

    Attributes:
        component_type: Type of the strategy component that was rolled back.
        component_name: Name of the strategy component that was rolled back.
        previous_active_version_id: Unique identifier of the previously active version (if any).
        new_active_version_id: Unique identifier of the new active version.
        success: Whether the rollback was successful (True) or not (False).
        message: Message describing the result of the rollback.
    """

    component_type: StrategyComponentType = Field(
        description="Type of the strategy component that was rolled back"
    )
    component_name: str = Field(description="Name of the strategy component that was rolled back")
    previous_active_version_id: Optional[str] = Field(
        default=None, description="Unique identifier of the previously active version (if any)"
    )
    new_active_version_id: str = Field(description="Unique identifier of the new active version")
    success: bool = Field(description="Whether the rollback was successful")
    message: str = Field(default="", description="Message describing the result")


# ─── Governance Metadata（关联现有实体）──────────────────


class GovernanceMetadata(BaseModel):
    """治理元数据 — 可嵌入 signal / replay / simulation 记录中.

    Metadata that can be embedded in signal, replay, or simulation records, including
    strategy version ID, experiment ID, and component versions.

    Attributes:
        strategy_version_id: Optional unique identifier of the strategy version used.
        experiment_id: Optional unique identifier of the associated experiment.
        component_versions: Dictionary mapping component names to version IDs.
    """

    strategy_version_id: Optional[str] = Field(
        default=None, description="Optional strategy version ID used"
    )
    experiment_id: Optional[str] = Field(
        default=None, description="Optional associated experiment ID"
    )
    component_versions: Dict[str, str] = Field(
        default_factory=dict, description="Dictionary mapping component names to version IDs"
    )
