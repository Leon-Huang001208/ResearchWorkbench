from typing import Literal

from pydantic import BaseModel, Field


class ScenarioHypothesis(BaseModel):
    """情景假设 - 单个可能的未来情景"""

    scenario_id: str
    title: str
    horizon: Literal["short", "mid", "long"]
    probability: float
    assumptions: list[str] = Field(default_factory=list)
    key_triggers: list[str] = Field(default_factory=list)
    invalidation_signals: list[str] = Field(default_factory=list)
    impact_map: dict = Field(default_factory=dict)
    evidence_assertion_ids: list[str] = Field(default_factory=list)
    confidence: float


class ScenarioSet(BaseModel):
    """情景集合 - 对某个问题的多个互斥情景"""

    set_id: str
    question: str
    hypotheses: list[ScenarioHypothesis] = Field(default_factory=list)
    normalization_check: bool = False
    residual_uncertainty: list[str] = Field(default_factory=list)
