"""
AkShare 基础适配器模块

定义统一的数据结构和适配器基类。
"""
from abc import ABC
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from core.observability import get_logger

from .config import DEFAULT_CONFIG, AkShareConfig

logger = get_logger("akshare")


@dataclass
class MarketData:
    """统一市场数据结构 (K线/行情)"""

    symbol: str
    timestamp: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    amount: Optional[float] = None
    turnover: Optional[float] = None  # 换手率
    pe: Optional[float] = None  # 市盈率
    pb: Optional[float] = None  # 市净率

    # 额外元数据
    source: str = "akshare"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StockInfo:
    """股票基本信息"""

    symbol: str
    name: str
    market: str  # sh/sz/bj
    industry: Optional[str] = None
    list_date: Optional[date] = None
    total_shares: Optional[float] = None  # 总股本
    float_shares: Optional[float] = None  # 流通股本

    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FinancialData:
    """财务数据"""

    symbol: str
    report_date: date  # 报告期
    report_type: str  # quarterly/annual

    # 主要财务指标
    total_revenue: Optional[float] = None  # 营业收入
    net_profit: Optional[float] = None  # 净利润
    total_assets: Optional[float] = None  # 总资产
    total_liabilities: Optional[float] = None  # 总负债
    equity: Optional[float] = None  # 净资产

    # 财务比率
    roe: Optional[float] = None  # 净资产收益率
    roa: Optional[float] = None  # 总资产收益率
    gross_margin: Optional[float] = None  # 毛利率
    net_margin: Optional[float] = None  # 净利率
    debt_ratio: Optional[float] = None  # 资产负债率

    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NewsData:
    """统一新闻数据结构"""

    title: str
    content: str
    publish_time: datetime
    source: str

    url: Optional[str] = None
    article_id: Optional[str] = None
    summary: Optional[str] = None

    # 关联标的
    symbols: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)

    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MacroData:
    """宏观经济数据"""

    indicator: str  # 指标名称
    value: float
    period: str  # 期别 (YYYY, YYYY-MM, YYYY-Q1 等)
    unit: Optional[str] = None
    source: str = "akshare"
    publish_date: Optional[date] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseAkShareFetcher(ABC):
    """AkShare 数据获取器基类"""

    def __init__(self, config: Optional[AkShareConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self._ak = None
        self._initialized = False

    def _initialize(self) -> None:
        """延迟初始化 AkShare"""
        if self._initialized:
            return

        try:
            import akshare as ak

            self._ak = ak
            self._initialized = True
            if self.config.verbose:
                logger.debug("AkShare initialized successfully")
        except ImportError:
            logger.error("AkShare not installed, please install it first")
            raise

    @property
    def ak(self):
        """获取 AkShare 模块实例"""
        if not self._initialized:
            self._initialize()
        return self._ak


class AkShareAdapter:
    """
    AkShare 统一适配器

    整合行情、财务、新闻、宏观数据的统一接口。
    """

    def __init__(self, config: Optional[AkShareConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.logger = get_logger("akshare_adapter")

        # 延迟初始化各 fetcher
        self._market: Optional[Any] = None
        self._financial: Optional[Any] = None
        self._news: Optional[Any] = None
        self._macro: Optional[Any] = None

    @property
    def market(self):
        """行情数据获取器"""
        if self._market is None:
            from .market import AkShareMarketFetcher

            self._market = AkShareMarketFetcher(self.config)
        return self._market

    @property
    def financial(self):
        """财务数据获取器"""
        if self._financial is None:
            from .financial import AkShareFinancialFetcher

            self._financial = AkShareFinancialFetcher(self.config)
        return self._financial

    @property
    def news(self):
        """新闻数据获取器"""
        if self._news is None:
            from .news import AkShareNewsFetcher

            self._news = AkShareNewsFetcher(self.config)
        return self._news

    @property
    def macro(self):
        """宏观数据获取器"""
        if self._macro is None:
            from .macro import AkShareMacroFetcher

            self._macro = AkShareMacroFetcher(self.config)
        return self._macro

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 测试获取 A 股列表
            self._initialize()
            _ = self.market.get_stock_list(limit=5)
            return {
                "status": "healthy",
                "source": "akshare",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"AkShare health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _initialize(self):
        """确保初始化"""
        from .market import AkShareMarketFetcher

        # 触发初始化
        if self._market is None:
            self._market = AkShareMarketFetcher(self.config)
        self._market._initialize()
