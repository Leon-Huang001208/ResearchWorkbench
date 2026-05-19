"""
BaoStock 基础适配器模块

定义统一的数据结构和适配器基类。
遵循项目现有架构，与 AkShare 适配器保持一致。
"""
from abc import ABC
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from core.observability import get_logger

logger = get_logger("baostock")


@dataclass
class BaoStockConfig:
    """BaoStock 适配器配置"""

    # 通用配置
    enable_cache: bool = True
    cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    cache_dir: Optional[str] = None

    # 请求配置
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 2.0

    # 行情配置
    default_frequency: str = "d"  # d=日k线, w=周, m=月
    default_adjustflag: str = "3"  # 1=后复权, 2=前复权, 3=不复权

    # 调试配置
    verbose: bool = False


# 默认配置实例
DEFAULT_CONFIG = BaoStockConfig()


class BaoStockError(Exception):
    """BaoStock 操作错误"""

    pass


class BaseBaoStockFetcher(ABC):
    """BaoStock 数据获取器基类"""

    def __init__(self, config: Optional[BaoStockConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self._bs = None
        self._initialized = False

    def _initialize(self) -> None:
        """延迟初始化 BaoStock"""
        if self._initialized:
            return

        try:
            import baostock as bs

            self._bs = bs
            self._initialized = True
            if self.config.verbose:
                logger.debug("BaoStock initialized successfully")
        except ImportError:
            logger.error("BaoStock not installed, please install it first")
            raise

    @property
    def bs(self):
        """获取 BaoStock 模块实例"""
        if not self._initialized:
            self._initialize()
        return self._bs

    @contextmanager
    def login_session(self):
        """
        BaoStock 登录会话上下文管理器

        确保正确登录和登出，防止资源泄漏。
        """
        self._initialize()
        lg = self.bs.login()

        if lg.error_code != "0":
            logger.error(f"BaoStock login failed: {lg.error_msg}")
            raise BaoStockError(f"Login failed: {lg.error_msg}")

        try:
            yield
        finally:
            logout_result = self.bs.logout()
            if logout_result.error_code != "0":
                logger.warning(f"BaoStock logout had error: {logout_result.error_msg}")


class BaoStockAdapter:
    """
    BaoStock 统一适配器

    整合行情、财务、新闻、宏观数据的统一接口。
    """

    def __init__(self, config: Optional[BaoStockConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.logger = get_logger("baostock_adapter")

        # 延迟初始化各个 fetcher
        self._market: Optional[Any] = None

    @property
    def market(self):
        """行情数据获取器"""
        if self._market is None:
            from data_layer.crawlers.baostock.market import BaoStockMarketFetcher

            self._market = BaoStockMarketFetcher(self.config)
        return self._market

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 测试获取一只股票的少量数据
            with self.market.login_session():
                test_data = self.market.get_historical_data(
                    symbol="600519.SH",
                    start_date=date.today() - timedelta(days=5),
                    end_date=date.today(),
                    limit=3,
                )

            return {
                "status": "healthy",
                "source": "baostock",
                "data_count": len(test_data),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"BaoStock health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
