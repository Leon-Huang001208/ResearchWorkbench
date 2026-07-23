"""Wind 融资融券特征组 —— 从 Wind Excel 插件获取两融数据作为市场情绪/资金面因子"""

from typing import Any

import pandas as pd

from signal_lab.features.base import Feature, FeatureGroup


class MarginBalanceFeature(Feature):
    """融资余额特征 —— 绝对规模反映做多杠杆"""

    def __init__(self):
        super().__init__(
            name="margin_balance",
            description="融资余额（元）— 做多杠杆规模",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get("margin_balance_col", "margin_balance")
        if col in data.columns:
            return data[col]
        return pd.Series([pd.NA] * len(data), index=data.index)


class ShortBalanceFeature(Feature):
    """融券余量特征 —— 绝对规模反映做空压力"""

    def __init__(self):
        super().__init__(
            name="short_balance",
            description="融券余量（股）— 做空压力",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get("short_balance_col", "short_balance")
        if col in data.columns:
            return data[col]
        return pd.Series([pd.NA] * len(data), index=data.index)


class MarginBuyFeature(Feature):
    """融资买入额特征 —— 当日做多意愿"""

    def __init__(self):
        super().__init__(
            name="margin_buy",
            description="融资买入额（元）— 做多意愿",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get("margin_buy_col", "margin_buy")
        if col in data.columns:
            return data[col]
        return pd.Series([pd.NA] * len(data), index=data.index)


class NetMarginFlowFeature(Feature):
    """融资净流入特征 = 融资买入 - 融资偿还"""

    def __init__(self):
        super().__init__(
            name="net_margin_flow",
            description="融资净流入 = 买入额 - 偿还额",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        buy_col = kwargs.get("margin_buy_col", "margin_buy")
        repay_col = kwargs.get("margin_repay_col", "margin_repay")
        if buy_col in data.columns and repay_col in data.columns:
            return data[buy_col] - data[repay_col]
        return pd.Series([pd.NA] * len(data), index=data.index)


class ShortRatioFeature(Feature):
    """融券/融资比率 = 融券余量 / 融资余额 — 做空相对做多强度"""

    def __init__(self):
        super().__init__(
            name="short_ratio",
            description="融券/融资比率 — 做空相对强度",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        short_col = kwargs.get("short_balance_col", "short_balance")
        margin_col = kwargs.get("margin_balance_col", "margin_balance")
        if short_col in data.columns and margin_col in data.columns:
            margin = data[margin_col].replace(0, pd.NA)
            return data[short_col] / margin
        return pd.Series([pd.NA] * len(data), index=data.index)


class WindMarginFeatures(FeatureGroup):
    """Wind 融资融券特征组

    从 Wind 两融数据中提取市场情绪和资金面因子：
    - 融资余额（做多杠杆规模）
    - 融券余量（做空压力）
    - 融资买入额（做多意愿）
    - 融资净流入（多空净力量）
    - 融券/融资比率（做空相对强度）
    """

    def __init__(self):
        features = [
            MarginBalanceFeature(),
            ShortBalanceFeature(),
            MarginBuyFeature(),
            NetMarginFlowFeature(),
            ShortRatioFeature(),
        ]
        super().__init__("wind_margin", features)
