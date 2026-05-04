"""
特征基类

定义特征计算的基础接口和通用功能。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd

from core.observability import get_logger

logger = get_logger(__name__)


class Feature(ABC):
    """特征基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        """
        计算特征值

        Args:
            data: 输入数据
            **kwargs: 其他参数

        Returns:
            特征值序列
        """
        pass

    def __call__(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        """调用compute方法"""
        return self.compute(data, **kwargs)


class FeatureGroup(ABC):
    """特征组基类 - 管理一组相关特征"""

    def __init__(self, name: str, features: Optional[List[Feature]] = None):
        self.name = name
        self.features: Dict[str, Feature] = {}
        if features:
            for feature in features:
                self.add_feature(feature)

    def add_feature(self, feature: Feature) -> None:
        """
        添加特征

        Args:
            feature: 特征对象
        """
        self.features[feature.name] = feature
        logger.debug(f"Added feature: {feature.name} to group: {self.name}")

    def compute_all(
        self,
        data: pd.DataFrame,
        feature_names: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        计算所有特征

        Args:
            data: 输入数据
            feature_names: 指定要计算的特征名称列表，None表示全部
            **kwargs: 其他参数

        Returns:
            特征DataFrame
        """
        result = pd.DataFrame(index=data.index)

        features_to_compute = (
            feature_names if feature_names else list(self.features.keys())
        )

        for name in features_to_compute:
            if name in self.features:
                try:
                    result[name] = self.features[name].compute(data, **kwargs)
                except Exception as e:
                    logger.error(f"Failed to compute feature {name}: {e}", exc_info=True)
                    result[name] = pd.NA

        return result

    def get_feature_names(self) -> List[str]:
        """获取所有特征名称"""
        return list(self.features.keys())
