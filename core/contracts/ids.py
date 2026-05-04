from typing import Literal

from pydantic import BaseModel, Field


class CanonicalId(BaseModel):
    """规范标识符 - 用于唯一标识各类资产"""

    canonical_id: str
    asset_type: Literal["equity", "etf", "future", "spot_commodity", "fx", "index", "bond", "fund"]
    market: str
    venue: str
    symbol: str
    vendor_ids: dict[str, str] = Field(default_factory=dict)
    name_zh: str | None = None
    name_en: str | None = None
