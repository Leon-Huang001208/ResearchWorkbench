"""
信号实验室模块测试
"""
import pytest
import pandas as pd
import numpy as np

from core.contracts import AlphaSignal
from signal_lab.features import Feature, FeatureBuilder, FeatureGroup
from signal_lab.features.groups import PriceVolumeFeatures, ValuationFeatures
from signal_lab.labels import RelativeReturnLabeler, compute_relative_return_label
from signal_lab.scoring import CompositeScorer, ConfidenceScorer, SignalRanker, StrengthScorer
from signal_lab.backtests import SimpleBacktester


class TestSimpleFeature(Feature):
    """测试用特征"""

    def __init__(self):
        super().__init__(name="test_feature", description="测试特征")

    def compute(self, data: pd.DataFrame, **kwargs) -> pd.Series:
        return data["close"].pct_change()


class TestFeatures:
    """特征模块测试"""

    def test_feature_group(self):
        """测试特征组"""
        feature = TestSimpleFeature()
        group = FeatureGroup("test", [feature])

        assert group.name == "test"
        assert "test_feature" in group.features

    def test_feature_builder(self):
        """测试特征构建器"""
        builder = FeatureBuilder()

        price_group = PriceVolumeFeatures()
        val_group = ValuationFeatures()

        builder.add_group(price_group)
        builder.add_group(val_group)

        assert "price_volume" in builder.groups
        assert "valuation" in builder.groups

    def test_compute_features(self):
        """测试特征计算"""
        # 创建测试数据
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        prices = pd.DataFrame(
            {"close": 100.0 + np.random.randn(100).cumsum(), "volume": np.random.randint(100000, 1000000, 100)},
            index=dates,
        )

        builder = FeatureBuilder()
        builder.add_group(PriceVolumeFeatures())

        features = builder.compute_features(prices)

        assert isinstance(features, pd.DataFrame)
        assert len(features) == 100


class TestLabels:
    """标签模块测试"""

    def test_simple_return_label(self):
        """测试简单收益标签"""
        result = compute_relative_return_label(0.10, 0.03)
        assert abs(result - 0.07) < 0.001

    def test_relative_return_labeler(self):
        """测试相对收益标签器"""
        # 创建测试数据
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        prices = pd.Series(100.0 + np.random.randn(100).cumsum(), index=dates)

        labeler = RelativeReturnLabeler(horizon=20)
        labels = labeler.compute(prices)

        assert isinstance(labels, pd.Series)
        assert len(labels) == 100


class TestScoring:
    """评分模块测试"""

    def test_confidence_scorer(self):
        """测试置信度评分器"""
        signal = AlphaSignal(
            signal_id="test1",
            subject_id="600519.SH",
            horizon="20d",
            thesis="看好白酒股",
            score=0.8,
            confidence=0.7,
        )

        scorer = ConfidenceScorer()
        score = scorer.score(signal)

        assert score == 0.7

    def test_composite_scorer(self):
        """测试组合评分器"""
        signal = AlphaSignal(
            signal_id="test1",
            subject_id="600519.SH",
            horizon="20d",
            thesis="看好白酒股",
            score=0.8,
            confidence=0.7,
            evidence_refs=["assert1", "assert2"],
            scenario_refs=["scenario1"],
        )

        scorer = CompositeScorer(
            scorers=[
                ConfidenceScorer(),
                StrengthScorer(),
            ],
            weights=[0.5, 0.5],
        )

        score = scorer.score(signal)
        assert 0.0 <= score <= 1.0

    def test_signal_ranker(self):
        """测试信号排名器"""
        signals = [
            AlphaSignal(
                signal_id=f"test{i}",
                subject_id="600519.SH",
                horizon="20d",
                thesis=f"信号{i}",
                score=0.5 + i * 0.1,
                confidence=0.6,
            )
            for i in range(5)
        ]

        ranker = SignalRanker()
        ranked = ranker.rank(signals)

        assert len(ranked) == 5
        # 检查是否按分数排序
        assert ranked[0][2] == 1  # 第一名
        assert ranked[-1][2] == 5  # 最后一名


class TestBacktesting:
    """回测模块测试"""

    def test_simple_backtester(self):
        """测试简单回测器"""
        # 创建测试数据
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        np.random.seed(42)
        prices = pd.DataFrame(
            {"close": 100.0 + np.random.randn(252).cumsum()},
            index=dates,
        )

        backtester = SimpleBacktester(initial_capital=1000000)
        result = backtester.run(prices)

        assert result.total_return is not None
        assert result.sharpe_ratio is not None
        assert result.max_drawdown <= 0.0
        assert len(result.equity_curve) == 252

    def test_backtest_with_signals(self):
        """测试带信号的回测"""
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        prices = pd.DataFrame(
            {"close": 100.0 + np.random.randn(252).cumsum()},
            index=dates,
        )

        signals = [
            AlphaSignal(
                signal_id="test1",
                subject_id="600519.SH",
                horizon="20d",
                thesis="测试信号",
                score=0.8,
                confidence=0.7,
                status="candidate",
            )
        ]

        backtester = SimpleBacktester()
        result = backtester.run(prices, signals)

        assert result.total_return is not None
