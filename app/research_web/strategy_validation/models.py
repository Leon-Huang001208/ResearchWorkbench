"""Closed browser configuration for offline research strategy validation."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Rule = Literal["volume_stall", "sma5_close", "sma10_close", "sma20_close"]
RULES = ("volume_stall", "sma5_close", "sma10_close", "sma20_close")
Identity = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class ValidationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    dataset_id: Identity
    rules: list[Rule] = Field(min_length=1, max_length=4)
    horizon: Literal[1, 5, 10] = 5
    volume_ratio: float = Field(default=1.30, ge=1, le=5)
    high_window: Literal[20, 60] = 20
    near_high_pct: float = Field(default=2.0, ge=0.1, le=20)
    ma_previous_gap_pct: float = Field(default=3.0, ge=0.1, le=20)
    ma_close_gap_pct: float = Field(default=2.5, ge=0.1, le=20)
    sell_cost_bps: int = Field(default=10, ge=0, le=100)

    @field_validator("horizon", "high_window", mode="before")
    @classmethod
    def strict_integer_choices(cls, value: int) -> int:
        if type(value) is not int:
            raise ValueError("strategy_choice_requires_integer")
        return value

    @field_validator("rules")
    @classmethod
    def unique_rules(cls, value: list[Rule]) -> list[Rule]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate_strategy_rule")
        return value
