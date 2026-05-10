"""
Core contracts for scenarios (hypotheses and scenario sets).

This module defines Pydantic models for scenario hypotheses and scenario sets in AlphaFoundry.
"""
from typing import Literal

from pydantic import BaseModel, Field


class ScenarioHypothesis(BaseModel):
    """情景假设 - 单个可能的未来情景.

    Represents a single possible future scenario, including scenario ID, title,
    horizon, probability, assumptions, key triggers, invalidation signals,
    impact map, evidence assertion IDs, and confidence.

    Attributes:
        scenario_id: Unique identifier for the scenario.
        title: Title of the scenario.
        horizon: Time horizon ("short", "mid", "long").
        probability: Probability of the scenario (0.0 to 1.0).
        assumptions: List of assumptions for the scenario.
        key_triggers: List of key triggers for the scenario.
        invalidation_signals: List of signals that would invalidate the scenario.
        impact_map: Dictionary mapping assets/entities to impacts.
        evidence_assertion_ids: List of evidence assertion IDs supporting the scenario.
        confidence: Confidence in the scenario (0.0 to 1.0).
    """

    scenario_id: str = Field(description="Unique identifier for the scenario")
    title: str = Field(description="Title of the scenario")
    horizon: Literal["short", "mid", "long"] = Field(description="Time horizon (short, mid, long)")
    probability: float = Field(description="Probability of the scenario (0.0 to 1.0)")
    assumptions: list[str] = Field(
        default_factory=list, description="List of assumptions for the scenario"
    )
    key_triggers: list[str] = Field(
        default_factory=list, description="List of key triggers for the scenario"
    )
    invalidation_signals: list[str] = Field(
        default_factory=list, description="List of signals that would invalidate the scenario"
    )
    impact_map: dict = Field(
        default_factory=dict, description="Dictionary mapping assets/entities to impacts"
    )
    evidence_assertion_ids: list[str] = Field(
        default_factory=list, description="List of evidence assertion IDs supporting the scenario"
    )
    confidence: float = Field(description="Confidence in the scenario (0.0 to 1.0)")


class ScenarioSet(BaseModel):
    """情景集合 - 对某个问题的多个互斥情景.

    Represents a set of mutually exclusive scenarios for a question, including
    set ID, question, hypotheses, normalization check, and residual uncertainty.

    Attributes:
        set_id: Unique identifier for the scenario set.
        question: Question that the scenario set addresses.
        hypotheses: List of scenario hypotheses in the set.
        normalization_check: Whether probabilities are normalized (default False).
        residual_uncertainty: List of residual uncertainty points.
    """

    set_id: str = Field(description="Unique identifier for the scenario set")
    question: str = Field(description="Question that the scenario set addresses")
    hypotheses: list[ScenarioHypothesis] = Field(
        default_factory=list, description="List of scenario hypotheses in the set"
    )
    normalization_check: bool = Field(
        default=False, description="Whether probabilities are normalized"
    )
    residual_uncertainty: list[str] = Field(
        default_factory=list, description="List of residual uncertainty points"
    )
