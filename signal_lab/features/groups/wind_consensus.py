"""Wind 一致预期特征组 —— 从 Wind Excel 插件获取分析师一致预期数据作为 Alpha 因子"""

from typing import Any

import pandas as pd

from signal_lab.features.base import Feature, FeatureGroup


class ConsensusNetProfitFeature(Feature):
    """一致预测净利润特征

    使用 Wind 一致预期净利润作为基本面因子。支持 fy1/fy2/fy3/ftm 预测年度变体。
    """

    def __init__(self, fy: str = "fy1"):
        super().__init__(
            name=f"cons_net_profit_{fy}",
            description=f"Wind一致预测净利润 ({fy})",
        )
        self.fy = fy

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get("cons_net_profit_col", f"cons_net_profit_{self.fy}")
        if col in data.columns:
            return data[col]
        if "cons_net_profit" in data.columns:
            return data["cons_net_profit"]
        return pd.Series([pd.NA] * len(data), index=data.index)


class ConsensusEPSFeature(Feature):
    """一致预测 EPS 特征"""

    def __init__(self, fy: str = "fy1"):
        super().__init__(
            name=f"cons_eps_{fy}",
            description=f"Wind一致预测EPS ({fy})",
        )
        self.fy = fy

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get("cons_eps_col", f"cons_eps_{self.fy}")
        if col in data.columns:
            return data[col]
        if "cons_eps" in data.columns:
            return data["cons_eps"]
        return pd.Series([pd.NA] * len(data), index=data.index)


class ConsensusTargetPriceFeature(Feature):
    """一致预测目标价特征

    当前价格相对于一致目标价的上行空间 = (target_price / current_price - 1) * 100%
    """

    def __init__(self):
        super().__init__(
            name="cons_target_price_upside",
            description="一致预测目标价上行空间 (%)",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        target_col = kwargs.get("target_price_col", "target_price")
        close_col = kwargs.get("close_col", "close")

        if target_col in data.columns and close_col in data.columns:
            target = data[target_col]
            close = data[close_col].replace(0, pd.NA)
            return (target / close - 1) * 100

        if target_col in data.columns:
            return data[target_col]
        return pd.Series([pd.NA] * len(data), index=data.index)


class ConsensusRatingFeature(Feature):
    """综合评级特征（数值越低越好：1=买入, 5=卖出）

    转换为 Z-score 风格：rating_num 越高 = 越看好
    """

    def __init__(self):
        super().__init__(
            name="cons_rating_score",
            description="综合评级得分 (5 - rating, 越高越看好)",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get("rating_col", "rating")
        if col in data.columns:
            # Invert: 5 - rating so higher = better
            return 5.0 - data[col]
        return pd.Series([pd.NA] * len(data), index=data.index)


class ConsensusRatingNumFeature(Feature):
    """评级机构数量特征 —— 越多机构覆盖 = 越受关注"""

    def __init__(self):
        super().__init__(
            name="cons_rating_num",
            description="参与评级的机构数量",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get("rating_num_col", "rating_num")
        if col in data.columns:
            return data[col]
        return pd.Series([pd.NA] * len(data), index=data.index)


class WindConsensusFeatures(FeatureGroup):
    """Wind 一致预期特征组

    从 Wind 一致预期数据中提取 Alpha 因子，包括：
    - 净利润预测 (fy1/fy2/ftm)
    - EPS 预测 (fy1/fy2/ftm)
    - 目标价上行空间
    - 评级得分（反转）
    - 评级机构覆盖数量
    """

    def __init__(self):
        features = [
            ConsensusNetProfitFeature("fy1"),
            ConsensusNetProfitFeature("fy2"),
            ConsensusNetProfitFeature("ftm"),
            ConsensusEPSFeature("fy1"),
            ConsensusEPSFeature("fy2"),
            ConsensusEPSFeature("ftm"),
            ConsensusTargetPriceFeature(),
            ConsensusRatingFeature(),
            ConsensusRatingNumFeature(),
        ]
        super().__init__("wind_consensus", features)
