"""
特征构建器

提供特征工程的构建和管理功能。
"""
from typing import Any, Dict, List, Optional

import pandas as pd

from core.observability import get_logger
from signal_lab.features.base import FeatureGroup

logger = get_logger(__name__)


class FeatureBuilder:
    """特征构建器 - 管理多个特征组"""

    def __init__(self):
        self.groups: Dict[str, FeatureGroup] = {}

    def add_group(self, group: FeatureGroup) -> None:
        """
        添加特征组

        Args:
            group: 特征组对象
        """
        self.groups[group.name] = group
        logger.debug(f"Added feature group: {group.name}")

    def compute_features(
        self,
        data: pd.DataFrame,
        group_names: Optional[List[str]] = None,
        feature_names: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        计算特征

        Args:
            data: 输入数据
            group_names: 指定要计算的特征组名称列表，None表示全部
            feature_names: 指定要计算的特征名称列表，None表示全部
            **kwargs: 其他参数

        Returns:
            特征DataFrame
        """
        result = pd.DataFrame(index=data.index)

        groups_to_compute = group_names if group_names else list(self.groups.keys())

        for group_name in groups_to_compute:
            if group_name in self.groups:
                group_result = self.groups[group_name].compute_all(
                    data, feature_names, **kwargs
                )
                for col in group_result.columns:
                    result[f"{group_name}.{col}"] = group_result[col]

        logger.info(f"Computed {len(result.columns)} features from {len(groups_to_compute)} groups")
        return result

    def get_all_feature_names(self) -> List[str]:
        """获取所有特征名称"""
        all_features = []
        for group_name, group in self.groups.items():
            for feature_name in group.get_feature_names():
                all_features.append(f"{group_name}.{feature_name}")
        return all_features

    def get_group_names(self) -> List[str]:
        """获取所有特征组名称"""
        return list(self.groups.keys())
