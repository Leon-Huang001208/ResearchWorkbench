"""
特征组模块

包含各类金融特征组的实现。
"""

from .financial import FinancialFeatures
from .fund_flow import FundFlowFeatures
from .industry import IndustryFeatures
from .macro import MacroFeatures
from .price_volume import PriceVolumeFeatures
from .valuation import ValuationFeatures
from .wind_block import WindBlockFeatures
from .wind_consensus import WindConsensusFeatures
from .wind_margin import WindMarginFeatures

__all__ = [
    "PriceVolumeFeatures",
    "ValuationFeatures",
    "FinancialFeatures",
    "FundFlowFeatures",
    "IndustryFeatures",
    "MacroFeatures",
    "WindBlockFeatures",
    "WindConsensusFeatures",
    "WindMarginFeatures",
]
