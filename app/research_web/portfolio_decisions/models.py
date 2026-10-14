"""Explicit, bounded ETF research inputs. Uploaded data never grants admission."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=20, decimal_places=8)]
Positive = Annotated[Decimal, Field(gt=0, max_digits=20, decimal_places=8)]
Weight = Annotated[Decimal, Field(ge=0, le=1, max_digits=12, decimal_places=8)]
Symbol = Annotated[str, Field(pattern=r"^[0-9]{6}\.(SH|SZ)$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class StrategySpec(Contract):
    strategy_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    version: str = Field(min_length=1, max_length=64)
    effective_from: date
    asset_pool: list[Symbol] = Field(min_length=1, max_length=30)
    benchmark: str = Field(min_length=1, max_length=64)
    initial_cash: Positive
    risk_budget: Weight
    security_cap: Weight
    industry_caps: dict[str, Weight] = Field(min_length=1, max_length=30)
    min_cash_weight: Weight
    fee_rate: Weight
    minimum_fee: Money
    slippage_bps: Annotated[Decimal, Field(ge=0, le=1000)]
    max_price_deviation: Weight
    participation_rate: Annotated[Decimal, Field(gt=0, le=1)]
    order_lifetime_sessions: int = Field(ge=1, le=5, strict=True)
    lookback_sessions: Literal[63] = 63
    max_names: Literal[3] = 3
    execution_mode: Literal["paper"] = "paper"
    rule: Literal["weekly_positive_total_return_equal_weight_v1"] = (
        "weekly_positive_total_return_equal_weight_v1"
    )
    missing_data_action: Literal["block_new_risk_preserve_holdings"] = (
        "block_new_risk_preserve_holdings"
    )
    exit_rule: Literal["not_selected_at_rebalance"] = "not_selected_at_rebalance"
    reentry_same_event: Literal[False] = False

    @model_validator(mode="after")
    def distinct_assets(self):
        if len(set(self.asset_pool)) != len(self.asset_pool):
            raise ValueError("duplicate_asset")
        return self


class AssetRule(Contract):
    symbol: Symbol
    asset_class: Literal["mainland_equity_etf"] = "mainland_equity_etf"
    industry: str = Field(min_length=1, max_length=64)
    eligible_from: date
    eligible_until: date
    known_at: datetime
    rule_version: str = Field(min_length=1, max_length=64)
    lot_size: int = Field(ge=1, le=10000, strict=True)
    price_tick: Positive
    turnaround: Literal["T+1", "T+0"]


class Bar(Contract):
    symbol: Symbol
    day: date
    known_at: datetime
    execution_known_at: datetime
    open: Positive | None
    close: Positive | None
    total_return_index: Positive | None
    volume_shares: int | None = Field(ge=0, le=10**12, strict=True)
    suspended: bool = Field(strict=True)
    upper_limit: Positive | None
    lower_limit: Positive | None
    cash_distribution: Money
    split_ratio: Positive


class BenchmarkBar(Contract):
    day: date
    known_at: datetime
    total_return_index: Positive


class ResearchSnapshot(Contract):
    source: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1, max_length=256)
    data_version: str = Field(min_length=1, max_length=64)
    currency: Literal["CNY"]
    price_unit: Literal["CNY/share"]
    volume_unit: Literal["share"]
    price_basis: Literal["exchange_unadjusted"]
    return_basis: Literal["total_return_index"]
    volume_basis: Literal["daily_post_session_participation"]
    calendar: list[date] = Field(min_length=2, max_length=1500)
    calendar_known_at: datetime
    assets: list[AssetRule] = Field(min_length=1, max_length=30)
    bars: list[Bar] = Field(max_length=45000)
    benchmark: list[BenchmarkBar] = Field(max_length=1500)
    missing: list[str] = Field(max_length=30)
    provenance: Literal["engineering_only"]

    @model_validator(mode="after")
    def coherent_snapshot(self):
        if self.calendar != sorted(set(self.calendar)):
            raise ValueError("calendar_not_strictly_ordered")
        symbols = [asset.symbol for asset in self.assets]
        if len(symbols) != len(set(symbols)):
            raise ValueError("duplicate_asset_rule")
        keys = [(bar.symbol, bar.day) for bar in self.bars]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate_bar")
        if len({bar.day for bar in self.benchmark}) != len(self.benchmark):
            raise ValueError("duplicate_benchmark_bar")
        times = (
            [self.calendar_known_at]
            + [a.known_at for a in self.assets]
            + [b.known_at for b in self.bars]
            + [b.execution_known_at for b in self.bars]
            + [b.known_at for b in self.benchmark]
        )
        if any(t.tzinfo is None or t.utcoffset() is None for t in times):
            raise ValueError("timezone_required")
        for asset in self.assets:
            if asset.eligible_from > asset.eligible_until:
                raise ValueError("invalid_eligibility_range")
        for bar in self.bars:
            if bar.symbol not in symbols or bar.day not in self.calendar:
                raise ValueError("bar_outside_declared_scope")
            if (
                bar.upper_limit is not None
                and bar.lower_limit is not None
                and bar.lower_limit >= bar.upper_limit
            ):
                raise ValueError("invalid_price_limits")
        return self


class ManualDecision(Contract):
    day: date
    action: Literal["adopt", "veto", "defer"]
    reason: str = Field(min_length=1, max_length=1000)
    evidence_ref: str = Field(min_length=1, max_length=256)
    decided_at: datetime


class ReplayRequest(Contract):
    strategy: StrategySpec
    snapshot: ResearchSnapshot
    start_date: date
    end_date: date
    manual_decisions: list[ManualDecision] = Field(max_length=300)

    @model_validator(mode="after")
    def complete_configuration(self):
        if not set(self.strategy.asset_pool).issubset({a.symbol for a in self.snapshot.assets}):
            raise ValueError("asset_rule_missing")
        if any(a.industry not in self.strategy.industry_caps for a in self.snapshot.assets):
            raise ValueError("industry_cap_missing")
        if (
            self.start_date > self.end_date
            or self.start_date not in self.snapshot.calendar
            or self.end_date not in self.snapshot.calendar
        ):
            raise ValueError("invalid_replay_range")
        if len({d.day for d in self.manual_decisions}) != len(self.manual_decisions):
            raise ValueError("duplicate_manual_decision")
        for decision in self.manual_decisions:
            if decision.decided_at.tzinfo is None:
                raise ValueError("timezone_required")
            index = (
                self.snapshot.calendar.index(decision.day)
                if decision.day in self.snapshot.calendar
                else -1
            )
            if (
                index < 0
                or index + 1 >= len(self.snapshot.calendar)
                or not self.start_date <= decision.day <= self.end_date
                or decision.day.isocalendar()[:2]
                == self.snapshot.calendar[index + 1].isocalendar()[:2]
            ):
                raise ValueError("manual_decision_requires_rebalance_event")
        return self
