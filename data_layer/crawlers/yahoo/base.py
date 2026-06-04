"""
Yahoo Finance 基础适配器模块

定义统一的数据结构和适配器基类。
遵循项目现有架构，与 AkShare/BaoStock 适配器保持一致。
"""
import importlib
from abc import ABC
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from core.observability import get_logger
from data_layer.crawlers.utils.anti_crawler_kit import AntiScrapeConfig, AntiScrapeKit

logger = get_logger("yahoo")


@dataclass
class YahooConfig:
    """Yahoo Finance 适配器配置"""

    enable_cache: bool = True
    cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    cache_dir: Optional[str] = None
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 2.0
    base_delay: float = 2.0
    jitter_range: float = 1.0
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1800
    default_interval: str = "1d"
    default_period: str = "1y"
    auto_adjust: bool = True
    verbose: bool = False


DEFAULT_CONFIG = YahooConfig()


class YahooError(Exception):
    """Yahoo Finance 操作错误"""

    pass


@dataclass
class YahooMarketData:
    """Yahoo 市场数据结构（兼容现有 MarketData）"""

    symbol: str
    timestamp: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    adj_close: Optional[float] = None
    source: str = "yahoo"
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "adj_close": self.adj_close,
            "source": self.source,
            "extra": self.extra,
        }


@dataclass
class YahooStockInfo:
    """Yahoo 股票基本信息"""

    symbol: str
    name: str
    currency: str
    exchange: str
    country: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    current_price: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "currency": self.currency,
            "exchange": self.exchange,
            "country": self.country,
            "industry": self.industry,
            "sector": self.sector,
            "market_cap": self.market_cap,
            "pe_ratio": self.pe_ratio,
            "pb_ratio": self.pb_ratio,
            "dividend_yield": self.dividend_yield,
            "beta": self.beta,
            "fifty_two_week_high": self.fifty_two_week_high,
            "fifty_two_week_low": self.fifty_two_week_low,
            "current_price": self.current_price,
            "extra": self.extra,
        }


@dataclass
class YahooFinancialData:
    """Yahoo 财务数据"""

    symbol: str
    report_date: date
    report_type: str
    total_revenue: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    free_cash_flow: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "report_date": self.report_date.isoformat(),
            "report_type": self.report_type,
            "total_revenue": self.total_revenue,
            "net_income": self.net_income,
            "eps": self.eps,
            "total_assets": self.total_assets,
            "total_liabilities": self.total_liabilities,
            "total_equity": self.total_equity,
            "free_cash_flow": self.free_cash_flow,
            "operating_cash_flow": self.operating_cash_flow,
            "gross_margin": self.gross_margin,
            "net_margin": self.net_margin,
            "roe": self.roe,
            "extra": self.extra,
        }


class BaseYahooFetcher(ABC):
    """Yahoo Finance 数据获取器基类"""

    def __init__(self, config: Optional[YahooConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self._yf = None
        self._initialized = False
        self._anti_scrape = AntiScrapeKit(
            AntiScrapeConfig(
                base_delay=self.config.base_delay,
                jitter_range=self.config.jitter_range,
                max_requests_per_minute=self.config.max_requests_per_minute,
                max_requests_per_hour=self.config.max_requests_per_hour,
            )
        )

    def _initialize(self) -> None:
        if self._initialized:
            return

        try:
            self._yf = importlib.import_module("yfinance")
            self._initialized = True
            if self.config.verbose:
                logger.debug("yfinance initialized successfully")
        except ImportError:
            logger.error("yfinance not installed, please install it first")
            raise

    @property
    def yf(self):
        if not self._initialized:
            self._initialize()
        return self._yf

    def _smart_delay(self, is_heavy_request: bool = False):
        self._anti_scrape.before_request(is_heavy_request)

    def _record_success(self):
        self._anti_scrape.after_success()

    def _record_failure(self):
        self._anti_scrape.after_failure()

    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None


class YahooAdapter:
    """Yahoo Finance 统一适配器"""

    def __init__(self, config: Optional[YahooConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.logger = get_logger("yahoo_adapter")
        self._market: Optional[Any] = None
        self._fundamental: Optional[Any] = None
        self._news: Optional[Any] = None
        self._options: Optional[Any] = None

    @property
    def market(self):
        if self._market is None:
            from .market import YahooMarketFetcher

            self._market = YahooMarketFetcher(self.config)
        return self._market

    @property
    def fundamental(self):
        if self._fundamental is None:
            from .fundamental import YahooFundamentalFetcher

            self._fundamental = YahooFundamentalFetcher(self.config)
        return self._fundamental

    @property
    def news(self):
        if self._news is None:
            from .news import YahooNewsFetcher

            self._news = YahooNewsFetcher(self.config)
        return self._news

    @property
    def options(self):
        if self._options is None:
            try:
                options_module = importlib.import_module("data_layer.crawlers.yahoo.options")
                self._options = options_module.YahooOptionsFetcher(self.config)
            except ImportError:
                logger.warning("YahooOptionsFetcher not available")
                self._options = None
        return self._options

    def health_check(self) -> Dict[str, Any]:
        try:
            test_data = self.market.get_historical_data(
                symbol="AAPL",
                period="5d",
                interval="1d",
            )

            return {
                "status": "healthy",
                "source": "yahoo",
                "data_count": len(test_data) if test_data else 0,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            self.logger.error("Yahoo Finance health check failed: %s", e)
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
