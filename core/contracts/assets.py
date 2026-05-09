"""
Core contracts for asset-related data structures.

This module defines Pydantic models that standardize asset data representations
across the AlphaFoundry system, ensuring consistent data exchange between
services, data layers, and APIs.
"""

from datetime import datetime
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from data_layer.indicators.models import TechnicalIndicators
else:
    TechnicalIndicators = Any


class AssetAnalysisSnapshot(BaseModel):
    """资产分析快照 - 标准化的资产分析数据结构.

    Captures a comprehensive snapshot of asset analysis data at a specific point in time,
    including financial metrics, fund flows, price/volume, valuation, shareholder info,
    industry context, event impacts, macro exposures, technical indicators, and sentiment.

    Attributes:
        canonical_id: Unique canonical identifier for the asset.
        as_of: Timestamp representing when this snapshot was generated.
        financial: Dictionary containing financial metrics (e.g., revenue, profit, margins).
        fund_flow: Dictionary containing fund flow data (e.g., institutional flows, retail flows).
        price_volume: Dictionary containing price and volume data (e.g., OHLCV, VWAP).
        valuation: Dictionary containing valuation metrics (e.g., P/E, P/B, EV/EBITDA).
        shareholder: Dictionary containing shareholder information (e.g., major holders, ownership changes).
        industry: Dictionary containing industry-level context and metrics.
        event_impact: List of event identifiers that impact this asset.
        macro_exposure: Dictionary containing macroeconomic exposure metrics (e.g., interest rate sensitivity).
        evidence_refs: List of reference identifiers for supporting evidence (e.g., news, reports).
        technical: Technical indicators data structure or dictionary (or None).
        sentiment: Dictionary containing sentiment metrics (e.g., news sentiment, social sentiment).
    """

    canonical_id: str = Field(description="Unique canonical identifier for the asset")
    as_of: datetime = Field(description="Timestamp when this snapshot was generated")
    financial: dict[str, Any] = Field(default_factory=dict, description="Financial metrics (revenue, profit, margins, etc.)")
    fund_flow: dict[str, Any] = Field(default_factory=dict, description="Fund flow data (institutional, retail, etc.)")
    price_volume: dict[str, Any] = Field(default_factory=dict, description="Price and volume data (OHLCV, VWAP, etc.)")
    valuation: dict[str, Any] = Field(default_factory=dict, description="Valuation metrics (P/E, P/B, EV/EBITDA, etc.)")
    shareholder: dict[str, Any] = Field(default_factory=dict, description="Shareholder information (major holders, ownership changes, etc.)")
    industry: dict[str, Any] = Field(default_factory=dict, description="Industry-level context and metrics")
    event_impact: list[str] = Field(default_factory=list, description="List of event identifiers impacting this asset")
    macro_exposure: dict[str, Any] = Field(default_factory=dict, description="Macroeconomic exposure metrics (interest rate sensitivity, etc.)")
    evidence_refs: list[str] = Field(default_factory=list, description="Reference identifiers for supporting evidence (news, reports, etc.)")
    technical: TechnicalIndicators | dict[str, Any] | None = Field(default_factory=dict, description="Technical indicators data")
    sentiment: dict[str, Any] | None = Field(default_factory=dict, description="Sentiment metrics (news sentiment, social sentiment, etc.)")
