import logging

import pandas as pd

from .models import TechnicalIndicators

logger = logging.getLogger(__name__)


class PandasTAProvider:
    """pandas-ta 指标实现（第二优先级，预留空壳）"""

    def calculate(self, df: pd.DataFrame, symbol: str) -> TechnicalIndicators:
        """计算所有技术指标"""
        logger.warning("pandas-ta provider 尚未实现，返回空结果")
        latest_date = (
            df.index[-1].strftime("%Y-%m-%d")
            if hasattr(df.index, "strftime")
            else str(df.index[-1])
        )
        return TechnicalIndicators(symbol=symbol, date=latest_date)
