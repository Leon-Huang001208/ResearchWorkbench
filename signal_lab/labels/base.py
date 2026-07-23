"""
标签基类

定义标签生成的基础接口。
"""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from core.observability import get_logger

logger = get_logger(__name__)


class Labeler(ABC):
    """标签生成器基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    def compute(
        self,
        prices: pd.DataFrame,
        **kwargs: Any,
    ) -> pd.Series:
        """
        计算标签

        Args:
            prices: 价格数据
            **kwargs: 其他参数

        Returns:
            标签序列
        """
        pass

    def __call__(self, prices: pd.DataFrame, **kwargs: Any) -> pd.Series:
        """调用compute方法"""
        return self.compute(prices, **kwargs)
