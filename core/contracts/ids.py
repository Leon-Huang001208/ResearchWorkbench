"""
Core contracts for identifier-related data structures.

This module defines Pydantic models that standardize canonical identifiers
for various asset types across the AlphaFoundry system, ensuring consistent
asset referencing.
"""
from typing import Literal

from pydantic import BaseModel, Field


class CanonicalId(BaseModel):
    """规范标识符 - 用于唯一标识各类资产.

    Represents a canonical identifier for an asset, including canonical ID,
    asset type, market, venue, symbol, vendor-specific IDs, and names in
    Chinese and English.

    Attributes:
        canonical_id: Unique canonical identifier for the asset.
        asset_type: Type of asset (equity, etf, future, spot_commodity, fx, index, bond, fund).
        market: Market where the asset is traded (e.g., "CN", "US").
        venue: Trading venue (e.g., "SHSE", "NYSE").
        symbol: Ticker symbol of the asset.
        vendor_ids: Dictionary mapping vendor names to their specific IDs for the asset.
        name_zh: Chinese name of the asset (if available).
        name_en: English name of the asset (if available).
    """

    canonical_id: str = Field(description="Unique canonical identifier for the asset")
    asset_type: Literal[
        "equity", "etf", "future", "spot_commodity", "fx", "index", "bond", "fund"
    ] = Field(description="Type of asset")
    market: str = Field(description="Market where the asset is traded (e.g., CN, US)")
    venue: str = Field(description="Trading venue (e.g., SHSE, NYSE)")
    symbol: str = Field(description="Ticker symbol of the asset")
    vendor_ids: dict[str, str] = Field(
        default_factory=dict, description="Dictionary mapping vendor names to their specific IDs"
    )
    name_zh: str | None = Field(
        default=None, description="Chinese name of the asset (if available)"
    )
    name_en: str | None = Field(
        default=None, description="English name of the asset (if available)"
    )
