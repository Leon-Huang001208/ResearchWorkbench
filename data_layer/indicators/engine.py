
import logging
import pandas as pd
from .models import TechnicalIndicators

logger = logging.getLogger(__name__)

class TechnicalIndicatorEngine:
    """技术指标引擎 - 三层降级"""
    
    def __init__(self):
        self._provider = None
        self._provider_name = "unknown"
        self._init_provider()
    
    def _init_provider(self):
        """按优先级初始化 provider"""
        # 1. 尝试 TA-Lib
        try:
            from .talib_provider import TALibProvider
            self._provider = TALibProvider()
            self._provider_name = "talib"
            logger.info("技术指标引擎: 使用 TA-Lib provider")
            return
        except ImportError:
            logger.warning("TA-Lib 不可用，降级到 pandas-ta")
        
        # 2. 尝试 pandas-ta
        try:
            from .pandas_ta_provider import PandasTAProvider
            self._provider = PandasTAProvider()
            self._provider_name = "pandas_ta"
            logger.info("技术指标引擎: 使用 pandas-ta provider")
            return
        except ImportError:
            logger.warning("pandas-ta 不可用，降级到 builtin")
        
        # 3. builtin 兜底
        from .builtin_provider import BuiltinProvider
        self._provider = BuiltinProvider()
        self._provider_name = "builtin"
        logger.info("技术指标引擎: 使用 builtin provider")
    
    def calculate(self, df: pd.DataFrame, symbol: str) -> TechnicalIndicators:
        """
        计算技术指标
        
        Args:
            df: K线数据，必须包含 open/high/low/close/volume 列
            symbol: 证券代码
        
        Returns:
            TechnicalIndicators 对象
        """
        if len(df) < 60:
            logger.warning(f"{symbol} 数据不足60天，部分指标可能不准确")
        
        result = self._provider.calculate(df, symbol)
        result.provider = self._provider_name
        return result
    
    @property
    def provider_name(self) -> str:
        return self._provider_name
