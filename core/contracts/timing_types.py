"""Timing and outcome shared types.

These types are used across timing_engine, memory_learning, and core/contracts.
Centralizing them here eliminates duplicate definitions.
"""

from typing import Literal

TimingAction = Literal["enter", "wait", "reduce", "exit", "block"]
OutcomeHorizon = Literal["1d", "5d", "20d", "30d", "60d"]
FailureType = Literal[
    "wrong_thesis",
    "timing_error",
    "crowding_error",
    "regime_misread",
    "data_quality",
    "execution_error",
    "risk_error",
    "unknown",
]
