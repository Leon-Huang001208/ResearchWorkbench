"""Wind 龙虎榜特征组 —— 从 Wind Excel 插件获取龙虎榜数据作为异常交易/聪明钱因子"""

from typing import Any

import pandas as pd

from signal_lab.features.base import Feature, FeatureGroup


class LHBNetBuyFeature(Feature):
    """龙虎榜净买入额特征 —— 聪明钱净方向"""

    def __init__(self):
        super().__init__(
            name="lhb_net_buy",
            description="龙虎榜净买入额（元）— 聪明钱方向",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get("lhb_net_buy_col", "lhb_net_buy")
        if col in data.columns:
            return data[col]
        return pd.Series([pd.NA] * len(data), index=data.index)


class LHBBuySellRatioFeature(Feature):
    """龙虎榜买卖比 = 买入金额 / 卖出金额 — >1 表示净买入"""

    def __init__(self):
        super().__init__(
            name="lhb_buy_sell_ratio",
            description="龙虎榜买卖金额比 — 聪明钱强度",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        buy_col = kwargs.get("lhb_buy_amt_col", "lhb_buy_amt")
        sell_col = kwargs.get("lhb_sell_amt_col", "lhb_sell_amt")
        if buy_col in data.columns and sell_col in data.columns:
            sell = data[sell_col].replace(0, pd.NA)
            return data[buy_col] / sell
        return pd.Series([pd.NA] * len(data), index=data.index)


class LHBIntensityFeature(Feature):
    """龙虎榜强度 = 净买入额 / 成交额 — 聪明钱参与度"""

    def __init__(self):
        super().__init__(
            name="lhb_intensity",
            description="龙虎榜净额/成交额 — 聪明钱参与度",
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        net_col = kwargs.get("lhb_net_buy_col", "lhb_net_buy")
        amount_col = kwargs.get("amount_col", "amount")
        if net_col in data.columns and amount_col in data.columns:
            amount = data[amount_col].replace(0, pd.NA)
            return data[net_col] / amount
        # Fallback: use buy/sell
        buy_col = kwargs.get("lhb_buy_amt_col", "lhb_buy_amt")
        sell_col = kwargs.get("lhb_sell_amt_col", "lhb_sell_amt")
        if buy_col in data.columns and sell_col in data.columns:
            if amount_col in data.columns:
                amount = data[amount_col].replace(0, pd.NA)
                return (data[buy_col] - data[sell_col]) / amount
        return pd.Series([pd.NA] * len(data), index=data.index)


class WindBlockFeatures(FeatureGroup):
    """Wind 龙虎榜特征组

    从 Wind 龙虎榜数据中提取异常交易/聪明钱因子：
    - 龙虎榜净买入额（聪明钱方向）
    - 龙虎榜买卖比（聪明钱强度）
    - 龙虎榜强度（聪明钱参与度）
    """

    def __init__(self):
        features = [
            LHBNetBuyFeature(),
            LHBBuySellRatioFeature(),
            LHBIntensityFeature(),
        ]
        super().__init__("wind_block", features)
