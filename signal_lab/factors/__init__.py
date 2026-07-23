"""Dynamic multi-factor research layer."""

from core.contracts.factors import (
    DynamicFactorWeights,
    FactorCategory,
    FactorDefinition,
    FactorDirection,
    FactorEvaluation,
    FactorValue,
)
from signal_lab.factors.evaluation import FactorEvaluator
from signal_lab.factors.fusion import EventFactorFusion, FusionWeights
from signal_lab.factors.matrix import FactorMatrixBuilder
from signal_lab.factors.models import FactorScoreResult, RollingICWeightedModel

__all__ = [
    "DynamicFactorWeights",
    "EventFactorFusion",
    "FactorCategory",
    "FactorDefinition",
    "FactorDirection",
    "FactorEvaluation",
    "FactorEvaluator",
    "FactorMatrixBuilder",
    "FactorScoreResult",
    "FactorValue",
    "FusionWeights",
    "RollingICWeightedModel",
]
