"""
Core contracts for asset-related data structures.

This module defines Pydantic models that standardize asset data representations
across the AlphaFoundry system, ensuring consistent data exchange between
services, data layers, and APIs.
"""

from datetime import date as date_type
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from signal_lab.features.indicators.models import TechnicalIndicators
else:
    TechnicalIndicators = Any


class Shareholder(BaseModel):
    """股东信息"""

    name: str = Field(description="股东名称")
    share_ratio: float = Field(description="持股比例")
    change_ratio: Optional[float] = Field(None, description="持股变动比例")
    is_state_owned: bool = Field(False, description="是否为国资/国企")
    shareholder_type: Optional[str] = Field(None, description="股东类型")


class FinancialSummary(BaseModel):
    """财务摘要"""

    revenue: Optional[float] = Field(None, description="营收")
    net_profit: Optional[float] = Field(None, description="净利润")
    roe: Optional[float] = Field(None, description="净资产收益率")
    roa: Optional[float] = Field(None, description="总资产收益率")
    gross_margin: Optional[float] = Field(None, description="毛利率")
    debt_ratio: Optional[float] = Field(None, description="资产负债率")
    pe_ttm: Optional[float] = Field(None, description="市盈率TTM")
    pb_mrq: Optional[float] = Field(None, description="市净率MRQ")
    ev_ebitda: Optional[float] = Field(None, description="企业价值倍数")
    dividend_yield: Optional[float] = Field(None, description="股息率")
    report_date: Optional[date_type] = Field(None, description="报告日期")


class CapitalFlowItem(BaseModel):
    """资金流向单项数据"""

    inflow: float = Field(description="流入金额")
    outflow: float = Field(description="流出金额")
    net_flow: float = Field(description="净流金额")
    percentage: Optional[float] = Field(None, description="占比")


class CapitalFlow(BaseModel):
    """资金流向数据"""

    main_inflow: float = Field(0.0, description="主力流入")
    main_outflow: float = Field(0.0, description="主力流出")
    main_net: float = Field(0.0, description="主力净流")
    super_inflow: Optional[float] = Field(None, description="超大单流入")
    super_outflow: Optional[float] = Field(None, description="超大单流出")
    super_net: Optional[float] = Field(None, description="超大单净流")
    large_inflow: Optional[float] = Field(None, description="大单流入")
    large_outflow: Optional[float] = Field(None, description="大单流出")
    large_net: Optional[float] = Field(None, description="大单净流")
    medium_inflow: Optional[float] = Field(None, description="中单流入")
    medium_outflow: Optional[float] = Field(None, description="中单流出")
    medium_net: Optional[float] = Field(None, description="中单净流")
    small_inflow: Optional[float] = Field(None, description="小单流入")
    small_outflow: Optional[float] = Field(None, description="小单流出")
    small_net: Optional[float] = Field(None, description="小单净流")
    northbound_flow: Optional[float] = Field(None, description="北向资金流向")
    as_of: Optional[datetime] = Field(None, description="数据时间")


class IndustryData(BaseModel):
    """行业数据"""

    sw_level_1: Optional[str] = Field(None, description="申万一级行业")
    sw_level_2: Optional[str] = Field(None, description="申万二级行业")
    sw_level_3: Optional[str] = Field(None, description="申万三级行业")
    industry_pe: Optional[float] = Field(None, description="行业PE")
    industry_pb: Optional[float] = Field(None, description="行业PB")
    sector_rank: Optional[int] = Field(None, description="板块涨幅排名")
    total_stocks: Optional[int] = Field(None, description="板块股票总数")
    stock_rank_in_sector: Optional[int] = Field(None, description="股票在板块中的涨跌排名")
    industry_heat: Optional[float] = Field(None, description="行业热度")
    related_concepts: list[str] = Field(default_factory=list, description="相关概念")


class ChipDistributionPoint(BaseModel):
    """筹码分布数据点 - 单个价格区间上的筹码集中度"""

    price: float = Field(description="价格区间中值")
    volume: float = Field(description="该价格区间的成交量/筹码量")
    concentration_pct: float = Field(description="筹码集中度百分比(该区间筹码占总筹码比例)")


class PriceBar(BaseModel):
    """K线数据"""

    date: date_type = Field(description="日期")
    open: float = Field(description="开盘价")
    high: float = Field(description="最高价")
    low: float = Field(description="最低价")
    close: float = Field(description="收盘价")
    volume: Optional[float] = Field(None, description="成交量")
    amount: Optional[float] = Field(None, description="成交额")
    turnover: Optional[float] = Field(None, description="换手率")
    ma5: Optional[float] = Field(None, description="5日均线")
    ma10: Optional[float] = Field(None, description="10日均线")
    ma20: Optional[float] = Field(None, description="20日均线")
    ma60: Optional[float] = Field(None, description="60日均线")
    boll_upper: Optional[float] = Field(None, description="布林带上轨")
    boll_middle: Optional[float] = Field(None, description="布林带中轨")
    boll_lower: Optional[float] = Field(None, description="布林带下轨")
    macd_dif: Optional[float] = Field(None, description="MACD DIF")
    macd_dea: Optional[float] = Field(None, description="MACD DEA")
    macd_hist: Optional[float] = Field(None, description="MACD 柱")
    vwap: Optional[float] = Field(None, description="均价(VWAP)")
    kdj_k: Optional[float] = Field(None, description="KDJ K值")
    kdj_d: Optional[float] = Field(None, description="KDJ D值")
    kdj_j: Optional[float] = Field(None, description="KDJ J值")
    rsi: Optional[float] = Field(None, description="RSI(14)")
    pe_ttm: Optional[float] = Field(None, description="市盈率TTM(日频)")
    pb: Optional[float] = Field(None, description="市净率(日频)")
    pct_change: Optional[float] = Field(None, description="涨跌幅")
    amplitude: Optional[float] = Field(None, description="振幅")


class EventImpact(BaseModel):
    """事件影响"""

    event_id: str = Field(description="事件ID")
    title: str = Field(description="事件标题")
    content: Optional[str] = Field(None, description="事件内容")
    impact_score: Optional[float] = Field(None, description="影响评分")
    impact_direction: Optional[str] = Field(None, description="影响方向: positive/negative/neutral")
    publish_date: Optional[datetime] = Field(None, description="发布日期")
    price_reaction: Optional[float] = Field(None, description="价格反应")
    event_type: Optional[str] = Field(None, description="事件类型")
    source: Optional[str] = Field(None, description="来源")
    url: Optional[str] = Field(None, description="原文链接")


class MacroSensitivity(BaseModel):
    """宏观敏感性分析"""

    interest_rate_sensitivity: Optional[float] = Field(None, description="利率敏感度")
    inflation_sensitivity: Optional[float] = Field(None, description="通胀敏感度")
    exchange_rate_sensitivity: Optional[float] = Field(None, description="汇率敏感度")
    commodity_sensitivity: Optional[float] = Field(None, description="大宗商品敏感度")
    liquidity_sensitivity: Optional[float] = Field(None, description="流动性敏感度")
    key_macro_factors: list[str] = Field(default_factory=list, description="关键宏观因子")


class AssetBasicInfo(BaseModel):
    """资产基本信息"""

    symbol: str = Field(description="代码")
    name: str = Field(description="名称")
    short_name: Optional[str] = Field(None, description="简称")
    listing_date: Optional[date_type] = Field(None, description="上市日期")
    total_shares: Optional[float] = Field(None, description="总股本")
    float_shares: Optional[float] = Field(None, description="流通股本")
    market_cap: Optional[float] = Field(None, description="总市值")
    float_market_cap: Optional[float] = Field(None, description="流通市值")
    area: Optional[str] = Field(None, description="地域")
    business_scope: Optional[str] = Field(None, description="经营范围")
    main_business: Optional[str] = Field(None, description="主营业务")


class AssetAnalysisCard(BaseModel):
    """资产分析卡片 - 完善的资产分析界面数据结构.

    包含了用户需要的所有模块：基本信息、财务、股东、行业、事件、宏观等.
    """

    canonical_id: str = Field(description="Unique canonical identifier for the asset")
    as_of: datetime = Field(description="Timestamp when this snapshot was generated")

    # 基本信息
    basic_info: Optional[AssetBasicInfo] = Field(None, description="基本信息")

    # 市场数据
    current_price: Optional[float] = Field(None, description="当前价格")
    price_change: Optional[float] = Field(None, description="涨跌额")
    price_change_pct: Optional[float] = Field(None, description="涨跌幅")
    volume: Optional[float] = Field(None, description="成交量")
    amount: Optional[float] = Field(None, description="成交额")
    turnover: Optional[float] = Field(None, description="换手率")
    high_52w: Optional[float] = Field(None, description="52周最高")
    low_52w: Optional[float] = Field(None, description="52周最低")
    price_bars: list[PriceBar] = Field(default_factory=list, description="K线数据")

    # 财务与估值
    financial: Optional[FinancialSummary] = Field(None, description="财务摘要")
    valuation: dict[str, Any] = Field(default_factory=dict, description="估值指标")

    # 资金流向
    capital_flow: Optional[CapitalFlow] = Field(None, description="资金流向")

    # 股东信息
    top_10_shareholders: list[Shareholder] = Field(default_factory=list, description="前十大股东")
    top_10_float_shareholders: list[Shareholder] = Field(
        default_factory=list, description="前十大流通股东"
    )

    # 行业信息
    industry: Optional[IndustryData] = Field(None, description="行业数据")

    # 事件影响
    recent_events: list[EventImpact] = Field(default_factory=list, description="近期事件")

    # 宏观敏感性
    macro_sensitivity: Optional[MacroSensitivity] = Field(None, description="宏观敏感性")

    # 其他兼容字段
    financial_dict: dict[str, Any] = Field(default_factory=dict, description="财务数据（兼容旧格式）")
    fund_flow: dict[str, Any] = Field(default_factory=dict, description="资金流向（兼容旧格式）")
    price_volume: dict[str, Any] = Field(default_factory=dict, description="量价数据（兼容旧格式）")
    shareholder: dict[str, Any] = Field(default_factory=dict, description="股东信息（兼容旧格式）")
    industry_dict: dict[str, Any] = Field(default_factory=dict, description="行业信息（兼容旧格式）")
    event_impact: list[str] = Field(default_factory=list, description="事件影响ID列表（兼容旧格式）")
    macro_exposure: dict[str, Any] = Field(default_factory=dict, description="宏观暴露（兼容旧格式）")
    evidence_refs: list[str] = Field(default_factory=list, description="证据引用")
    technical: TechnicalIndicators | dict[str, Any] = Field(
        default_factory=lambda: {}, description="技术指标"
    )
    sentiment: dict[str, Any] = Field(default_factory=dict, description="情绪指标")
    chip_distribution: list[ChipDistributionPoint] = Field(
        default_factory=list, description="筹码分布数据"
    )
    avg_cost: Optional[float] = Field(None, description="平均持仓成本")
    chip_peak_price: Optional[float] = Field(None, description="筹码峰价格(最大筹码集中价位)")
    chip_peak_upper: Optional[float] = Field(None, description="筹码峰上边界(半峰高价位)")
    chip_peak_lower: Optional[float] = Field(None, description="筹码峰下边界(半峰低价位)")


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
    financial: dict[str, Any] = Field(
        default_factory=dict, description="Financial metrics (revenue, profit, margins, etc.)"
    )
    fund_flow: dict[str, Any] = Field(
        default_factory=dict, description="Fund flow data (institutional, retail, etc.)"
    )
    price_volume: dict[str, Any] = Field(
        default_factory=dict, description="Price and volume data (OHLCV, VWAP, etc.)"
    )
    valuation: dict[str, Any] = Field(
        default_factory=dict, description="Valuation metrics (P/E, P/B, EV/EBITDA, etc.)"
    )
    shareholder: dict[str, Any] = Field(
        default_factory=dict,
        description="Shareholder information (major holders, ownership changes, etc.)",
    )
    industry: dict[str, Any] = Field(
        default_factory=dict, description="Industry-level context and metrics"
    )
    event_impact: list[str] = Field(
        default_factory=list, description="List of event identifiers impacting this asset"
    )
    macro_exposure: dict[str, Any] = Field(
        default_factory=dict,
        description="Macroeconomic exposure metrics (interest rate sensitivity, etc.)",
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Reference identifiers for supporting evidence (news, reports, etc.)",
    )
    technical: TechnicalIndicators | dict[str, Any] = Field(
        default_factory=lambda: {}, description="Technical indicators data"
    )
    sentiment: dict[str, Any] = Field(
        default_factory=dict,
        description="Sentiment metrics (news sentiment, social sentiment, etc.)",
    )
