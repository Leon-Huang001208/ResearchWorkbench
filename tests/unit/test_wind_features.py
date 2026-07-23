"""Wind 特征组单元测试"""

import pandas as pd

from signal_lab.features.groups.wind_block import WindBlockFeatures
from signal_lab.features.groups.wind_consensus import WindConsensusFeatures
from signal_lab.features.groups.wind_margin import WindMarginFeatures


class TestWindConsensusFeatures:
    """一致预期特征组测试"""

    def test_feature_group_registration(self):
        group = WindConsensusFeatures()
        assert group.name == "wind_consensus"
        assert len(group.features) >= 6
        assert "cons_net_profit_fy1" in group.features
        assert "cons_eps_fy1" in group.features
        assert "cons_target_price_upside" in group.features
        assert "cons_rating_score" in group.features

    def test_compute_with_full_data(self):
        data = pd.DataFrame(
            {
                "cons_net_profit": [1e10, 2e10],
                "cons_eps": [5.0, 6.0],
                "target_price": [2000, 2500],
                "close": [1800, 2000],
                "rating": [2.0, 1.5],
                "rating_num": [30, 25],
            }
        )
        group = WindConsensusFeatures()
        result = group.compute_all(data)
        assert len(result.columns) >= 6
        assert not result.empty

    def test_compute_with_empty_data(self):
        data = pd.DataFrame()
        group = WindConsensusFeatures()
        result = group.compute_all(data)
        assert result.empty

    def test_compute_with_missing_columns(self):
        """缺少列时返回 NA 但不崩溃"""
        data = pd.DataFrame({"unrelated": [1, 2, 3]})
        group = WindConsensusFeatures()
        result = group.compute_all(data)
        assert len(result.columns) >= 6

    def test_target_price_upside_calculation(self):
        data = pd.DataFrame(
            {
                "target_price": [2200, 2400],
                "close": [2000, 2000],
            }
        )
        group = WindConsensusFeatures()
        result = group.compute_all(data)
        assert "cons_target_price_upside" in result.columns
        # upside = (2200/2000 - 1) * 100 = 10%, (2400/2000 - 1) * 100 = 20%
        assert abs(result["cons_target_price_upside"].iloc[0] - 10.0) < 0.01
        assert abs(result["cons_target_price_upside"].iloc[1] - 20.0) < 0.01

    def test_rating_score_inversion(self):
        """评级: 1=买入最好, 5=卖出最差; 反转后 5-1=4 是最高分"""
        data = pd.DataFrame({"rating": [1.0, 3.0, 5.0]})
        group = WindConsensusFeatures()
        result = group.compute_all(data)
        assert "cons_rating_score" in result.columns
        assert result["cons_rating_score"].iloc[0] == 4.0  # 5 - 1
        assert result["cons_rating_score"].iloc[1] == 2.0  # 5 - 3
        assert result["cons_rating_score"].iloc[2] == 0.0  # 5 - 5


class TestWindMarginFeatures:
    """融资融券特征组测试"""

    def test_feature_group_registration(self):
        group = WindMarginFeatures()
        assert group.name == "wind_margin"
        assert len(group.features) >= 4
        assert "margin_balance" in group.features
        assert "short_balance" in group.features
        assert "net_margin_flow" in group.features

    def test_compute_with_full_data(self):
        data = pd.DataFrame(
            {
                "margin_balance": [5e9, 6e9],
                "short_balance": [1e6, 2e6],
                "margin_buy": [5e8, 3e8],
                "margin_repay": [3e8, 4e8],
            }
        )
        group = WindMarginFeatures()
        result = group.compute_all(data)
        assert not result.empty
        assert "net_margin_flow" in result.columns
        # net = buy - repay: 5e8-3e8=2e8, 3e8-4e8=-1e8
        assert result["net_margin_flow"].iloc[0] == 2e8
        assert result["net_margin_flow"].iloc[1] == -1e8

    def test_short_ratio_calculation(self):
        data = pd.DataFrame(
            {
                "short_balance": [1e6, 2e6],
                "margin_balance": [5e9, 4e9],
            }
        )
        group = WindMarginFeatures()
        result = group.compute_all(data)
        assert "short_ratio" in result.columns
        assert abs(result["short_ratio"].iloc[0] - 0.0002) < 1e-10
        assert abs(result["short_ratio"].iloc[1] - 0.0005) < 1e-10

    def test_compute_with_empty_data(self):
        data = pd.DataFrame()
        group = WindMarginFeatures()
        result = group.compute_all(data)
        assert result.empty


class TestWindBlockFeatures:
    """龙虎榜特征组测试"""

    def test_feature_group_registration(self):
        group = WindBlockFeatures()
        assert group.name == "wind_block"
        assert len(group.features) >= 2
        assert "lhb_net_buy" in group.features
        assert "lhb_buy_sell_ratio" in group.features

    def test_compute_with_full_data(self):
        data = pd.DataFrame(
            {
                "lhb_net_buy": [1e8, -5e7],
                "lhb_buy_amt": [3e8, 1e8],
                "lhb_sell_amt": [2e8, 1.5e8],
            }
        )
        group = WindBlockFeatures()
        result = group.compute_all(data)
        assert not result.empty
        assert "lhb_buy_sell_ratio" in result.columns
        # 3e8/2e8=1.5, 1e8/1.5e8=0.667
        assert abs(result["lhb_buy_sell_ratio"].iloc[0] - 1.5) < 0.01
        assert abs(result["lhb_buy_sell_ratio"].iloc[1] - 0.667) < 0.01

    def test_buy_sell_ratio_handles_zero_sell(self):
        """卖出为0时不崩溃"""
        data = pd.DataFrame(
            {
                "lhb_buy_amt": [1e8, 1e8],
                "lhb_sell_amt": [0, 0],
            }
        )
        group = WindBlockFeatures()
        result = group.compute_all(data)
        assert "lhb_buy_sell_ratio" in result.columns

    def test_intensity_with_amount(self):
        data = pd.DataFrame(
            {
                "lhb_net_buy": [1e8, -5e7],
                "amount": [1e9, 1e9],
            }
        )
        group = WindBlockFeatures()
        result = group.compute_all(data)
        assert "lhb_intensity" in result.columns
        assert abs(result["lhb_intensity"].iloc[0] - 0.1) < 0.01  # 1e8/1e9
        assert abs(result["lhb_intensity"].iloc[1] - (-0.05)) < 0.01  # -5e7/1e9


class TestWindFeatureGroupsIntegration:
    """跨特征组集成测试"""

    def test_all_groups_instantiable(self):
        groups = [
            WindConsensusFeatures(),
            WindMarginFeatures(),
            WindBlockFeatures(),
        ]
        for g in groups:
            assert g.name
            assert len(g.features) > 0

    def test_all_groups_compute_on_shared_data(self):
        """所有组可以在同一份数据上计算"""
        data = pd.DataFrame(
            {
                "cons_net_profit": [1e10],
                "cons_eps": [5.0],
                "target_price": [2000],
                "close": [1800],
                "rating": [2.0],
                "rating_num": [30],
                "margin_balance": [5e9],
                "short_balance": [1e6],
                "margin_buy": [5e8],
                "margin_repay": [3e8],
                "lhb_net_buy": [1e8],
                "lhb_buy_amt": [3e8],
                "lhb_sell_amt": [2e8],
                "amount": [1e9],
            },
            index=[0],
        )

        for GroupCls in [WindConsensusFeatures, WindMarginFeatures, WindBlockFeatures]:
            group = GroupCls()
            result = group.compute_all(data)
            assert not result.empty
            assert len(result) == 1
