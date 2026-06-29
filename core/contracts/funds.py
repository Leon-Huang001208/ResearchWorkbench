"""Fund intelligence domain contracts."""

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class FundMaster(BaseModel):
    """基金主数据。"""

    symbol: str = Field(description="Fund symbol, such as 000001.OF")
    name: str = Field(description="Fund name")
    fund_type: Optional[str] = Field(default=None, description="Fund category")
    management_company: Optional[str] = Field(default=None, description="Management company")
    inception_date: Optional[date] = Field(default=None, description="Fund inception date")
    benchmark: Optional[str] = Field(default=None, description="Performance benchmark")
    latest_size: Optional[float] = Field(default=None, description="Latest fund size")

    @field_validator("symbol", "name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()


class FundNavPoint(BaseModel):
    """基金日净值数据点。"""

    symbol: str = Field(description="Fund symbol")
    trading_day: date = Field(description="Trading day")
    unit_nav: float = Field(description="Unit NAV")
    accumulated_nav: Optional[float] = Field(default=None, description="Accumulated NAV")
    daily_return: Optional[float] = Field(default=None, description="Daily return")


class FundHolding(BaseModel):
    """基金股票持仓。"""

    symbol: str = Field(description="Fund symbol")
    report_date: date = Field(description="Disclosure report date")
    stock_symbol: str = Field(description="Held stock symbol")
    stock_name: Optional[str] = Field(default=None, description="Held stock name")
    industry: Optional[str] = Field(default=None, description="Industry label")
    theme: Optional[str] = Field(default=None, description="Theme label")
    weight: float = Field(description="Holding weight in fund NAV")
    market_value: Optional[float] = Field(default=None, description="Holding market value")


class FundManagerProfile(BaseModel):
    """基金经理画像。"""

    manager_id: str = Field(description="Manager identifier")
    manager_name: str = Field(description="Manager name")
    institution_name: Optional[str] = Field(default=None, description="Institution name")
    tenure_start: Optional[date] = Field(default=None, description="Tenure start date")
    tenure_end: Optional[date] = Field(default=None, description="Tenure end date")


class FundPerformanceMetrics(BaseModel):
    """基金收益风险指标。"""

    total_return: Optional[float] = Field(default=None, description="Total return")
    annualized_return: Optional[float] = Field(default=None, description="Annualized return")
    max_drawdown: Optional[float] = Field(default=None, description="Maximum drawdown")
    volatility: Optional[float] = Field(default=None, description="Annualized volatility")
    win_rate: Optional[float] = Field(default=None, description="Positive-return day ratio")
    ulcer_index: Optional[float] = Field(default=None, description="Ulcer index")


class FundExposureBreakdown(BaseModel):
    """基金或组合穿透后的暴露项。"""

    label: str = Field(description="Exposure label")
    weight: float = Field(description="Exposure weight")


class FundDetail(BaseModel):
    """基金详情聚合对象。"""

    master: FundMaster = Field(description="Fund master data")
    managers: List[FundManagerProfile] = Field(
        default_factory=list, description="Current or historical managers"
    )
    latest_nav: Optional[FundNavPoint] = Field(default=None, description="Latest NAV point")
    performance: FundPerformanceMetrics = Field(
        default_factory=FundPerformanceMetrics, description="Performance metrics"
    )
    latest_holdings: List[FundHolding] = Field(
        default_factory=list, description="Latest disclosed holdings"
    )


class PortfolioFundExposure(BaseModel):
    """基金组合穿透结果。"""

    positions: Dict[str, float] = Field(description="Fund symbol to portfolio weight")
    industry_exposure: List[FundExposureBreakdown] = Field(default_factory=list)
    stock_exposure: List[FundExposureBreakdown] = Field(default_factory=list)
    theme_exposure: List[FundExposureBreakdown] = Field(default_factory=list)
