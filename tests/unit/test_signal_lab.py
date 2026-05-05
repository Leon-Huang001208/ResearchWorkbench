"""
信号实验室模块测试

覆盖: 特征组, 回测引擎 (SimpleBacktester, VectorBTBacktester, BacktraderEngine), 评分, 标签
"""
import pytest
import pandas as pd
import numpy as np

from core.contracts import AlphaSignal
from signal_lab.features import Feature, FeatureBuilder, FeatureGroup
from signal_lab.features.groups import (
    PriceVolumeFeatures,
    ValuationFeatures,
    FinancialFeatures,
    FundFlowFeatures,
    IndustryFeatures,
    MacroFeatures,
)
from signal_lab.labels import RelativeReturnLabeler, compute_relative_return_label
from signal_lab.scoring import CompositeScorer, ConfidenceScorer, SignalRanker, StrengthScorer
from signal_lab.backtests import SimpleBacktester, VectorBTBacktester, BacktraderEngine
from signal_lab.backtests.base import BacktestResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def price_data():
    """生成测试用价格数据"""
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=300, freq="B")
    close = 100.0 + np.random.randn(300).cumsum()
    close = np.maximum(close, 10.0)  # 避免负价格
    volume = np.random.randint(100_000, 10_000_000, 300).astype(float)
    return pd.DataFrame({"close": close, "volume": volume}, index=dates)


@pytest.fixture
def price_data_ohlcv():
    """生成OHLCV测试数据"""
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=300, freq="B")
    close = 100.0 + np.random.randn(300).cumsum()
    close = np.maximum(close, 10.0)
    high = close * (1 + np.abs(np.random.randn(300)) * 0.02)
    low = close * (1 - np.abs(np.random.randn(300)) * 0.02)
    open_ = close * (1 + np.random.randn(300) * 0.01)
    volume = np.random.randint(100_000, 10_000_000, 300).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def sample_signal():
    """生成测试用AlphaSignal"""
    return AlphaSignal(
        signal_id="test_signal_001",
        subject_id="600519.SH",
        horizon="20d",
        thesis="看好白酒板块",
        score=0.8,
        confidence=0.7,
        status="candidate",
    )


@pytest.fixture
def sample_signals():
    """生成多个测试用AlphaSignal"""
    return [
        AlphaSignal(
            signal_id=f"test_{i}",
            subject_id="600519.SH",
            horizon="20d",
            thesis=f"信号{i}",
            score=0.5 + i * 0.1,
            confidence=0.6,
            status="candidate",
        )
        for i in range(5)
    ]


# ===========================================================================
# 特征模块测试
# ===========================================================================

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

    def test_compute_features(self, price_data):
        """测试特征计算"""
        builder = FeatureBuilder()
        builder.add_group(PriceVolumeFeatures())

        features = builder.compute_features(price_data)

        assert isinstance(features, pd.DataFrame)
        assert len(features) == 300
        # 至少有一些非NA值
        assert features.dropna(how="all", axis=1).shape[1] > 0


class TestPriceVolumeFeatures:
    """价量特征组测试"""

    def test_feature_count(self):
        """确认价量特征至少有10个"""
        group = PriceVolumeFeatures()
        assert len(group.get_feature_names()) >= 10

    def test_price_change(self, price_data):
        """测试价格变化特征"""
        group = PriceVolumeFeatures()
        result = group.compute_all(price_data, feature_names=["price_change_1d"])
        assert "price_change_1d" in result.columns
        # 第二个值应约等于 (close[1] - close[0]) / close[0]
        expected = (price_data["close"].iloc[1] - price_data["close"].iloc[0]) / price_data["close"].iloc[0]
        actual = result["price_change_1d"].iloc[1]
        assert abs(actual - expected) < 1e-10

    def test_volatility(self, price_data):
        """测试波动率特征"""
        group = PriceVolumeFeatures()
        result = group.compute_all(price_data, feature_names=["volatility_20d"])
        assert "volatility_20d" in result.columns
        # 前20个为NaN（pct_change第一个为NaN + rolling window=20需要20个值）
        assert result["volatility_20d"].iloc[:20].isna().all()
        # 第21个(索引20)有值
        assert not pd.isna(result["volatility_20d"].iloc[20])

    def test_rsi(self, price_data):
        """测试RSI特征"""
        group = PriceVolumeFeatures()
        result = group.compute_all(price_data, feature_names=["rsi_14d"])
        assert "rsi_14d" in result.columns

    def test_turnover_rate(self, price_data):
        """测试换手率特征"""
        group = PriceVolumeFeatures()
        result = group.compute_all(price_data, feature_names=["turnover_rate_20d"])
        assert "turnover_rate_20d" in result.columns

    def test_amount(self, price_data):
        """测试成交额特征"""
        group = PriceVolumeFeatures()
        result = group.compute_all(price_data, feature_names=["amount_20d"])
        assert "amount_20d" in result.columns
        # 成交额 = close * volume, 应有值
        assert not result["amount_20d"].iloc[20:].isna().all()

    def test_abnormal_return(self, price_data):
        """测试异常收益特征"""
        group = PriceVolumeFeatures()
        result = group.compute_all(price_data, feature_names=["abnormal_return_20d"])
        assert "abnormal_return_20d" in result.columns


class TestFinancialFeatures:
    """财务特征组测试"""

    def test_feature_count(self):
        """确认财务特征至少有5个"""
        group = FinancialFeatures()
        assert len(group.get_feature_names()) >= 5

    def test_roe_with_data(self):
        """测试ROE计算"""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        data = pd.DataFrame({
            "net_profit": np.random.randn(50) * 1e6,
            "equity": np.random.uniform(1e7, 1e8, 50),
        }, index=dates)
        group = FinancialFeatures()
        result = group.compute_all(data, feature_names=["roe"])
        assert "roe" in result.columns
        assert not result["roe"].isna().all()

    def test_debt_ratio(self):
        """测试资产负债率"""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        data = pd.DataFrame({
            "total_debt": np.random.uniform(1e7, 5e7, 50),
            "total_assets": np.random.uniform(5e7, 1e8, 50),
        }, index=dates)
        group = FinancialFeatures()
        result = group.compute_all(data, feature_names=["debt_ratio"])
        assert "debt_ratio" in result.columns
        assert (result["debt_ratio"].dropna() >= 0).all()
        assert (result["debt_ratio"].dropna() <= 1).all()

    def test_current_ratio(self):
        """测试流动比率"""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        data = pd.DataFrame({
            "current_assets": np.random.uniform(1e7, 5e7, 50),
            "current_liabilities": np.random.uniform(5e6, 3e7, 50),
        }, index=dates)
        group = FinancialFeatures()
        result = group.compute_all(data, feature_names=["current_ratio"])
        assert "current_ratio" in result.columns
        assert not result["current_ratio"].isna().all()


class TestFundFlowFeatures:
    """资金流特征组测试"""

    def test_feature_count(self):
        """确认资金流特征至少有5个"""
        group = FundFlowFeatures()
        assert len(group.get_feature_names()) >= 5

    def test_net_inflow(self):
        """测试净流入"""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        data = pd.DataFrame({
            "net_inflow": np.random.randn(50) * 1e5,
        }, index=dates)
        group = FundFlowFeatures()
        result = group.compute_all(data, feature_names=["net_inflow_1d"])
        assert "net_inflow_1d" in result.columns

    def test_large_order_ratio(self):
        """测试大单占比"""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        data = pd.DataFrame({
            "large_order_amount": np.random.uniform(1e5, 1e6, 50),
            "amount": np.random.uniform(1e6, 1e7, 50),
        }, index=dates)
        group = FundFlowFeatures()
        result = group.compute_all(data, feature_names=["large_order_ratio_20d"])
        assert "large_order_ratio_20d" in result.columns

    def test_main_force_net_inflow(self):
        """测试主力净流入"""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        data = pd.DataFrame({
            "net_inflow": np.random.randn(50) * 1e5,
        }, index=dates)
        group = FundFlowFeatures()
        result = group.compute_all(data, feature_names=["main_force_net_inflow_5d"])
        assert "main_force_net_inflow_5d" in result.columns


class TestValuationFeatures:
    """估值特征组测试"""

    def test_feature_count(self):
        """确认估值特征至少有5个"""
        group = ValuationFeatures()
        assert len(group.get_feature_names()) >= 5

    def test_pe_ratio(self):
        """测试市盈率"""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        data = pd.DataFrame({
            "close": np.random.uniform(10, 100, 50),
            "eps": np.random.uniform(0.5, 5, 50),
        }, index=dates)
        group = ValuationFeatures()
        result = group.compute_all(data, feature_names=["pe_ratio"])
        assert "pe_ratio" in result.columns
        assert not result["pe_ratio"].isna().all()


class TestIndustryFeatures:
    """行业特征组测试"""

    def test_feature_count(self):
        """确认行业特征至少有5个"""
        group = IndustryFeatures()
        assert len(group.get_feature_names()) >= 5

    def test_industry_momentum(self):
        """测试行业动量"""
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        data = pd.DataFrame({
            "industry_return": np.random.randn(100) * 0.02,
        }, index=dates)
        group = IndustryFeatures()
        result = group.compute_all(data, feature_names=["industry_momentum_20d"])
        assert "industry_momentum_20d" in result.columns

    def test_industry_concentration(self):
        """测试行业集中度"""
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        data = pd.DataFrame({
            "industry_return": np.random.randn(100) * 0.02,
        }, index=dates)
        group = IndustryFeatures()
        result = group.compute_all(data, feature_names=["industry_concentration_60d"])
        assert "industry_concentration_60d" in result.columns


class TestMacroFeatures:
    """宏观特征组测试"""

    def test_feature_count(self):
        """确认宏观特征至少有5个"""
        group = MacroFeatures()
        assert len(group.get_feature_names()) >= 5

    def test_macro_exposure(self):
        """测试宏观暴露"""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        data = pd.DataFrame({
            "market": np.random.randn(50) * 0.01,
        }, index=dates)
        group = MacroFeatures()
        result = group.compute_all(data, feature_names=["market_exposure"])
        assert "market_exposure" in result.columns

    def test_macro_momentum(self):
        """测试宏观动量"""
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        data = pd.DataFrame({
            "market": np.random.randn(100).cumsum() * 0.01,
        }, index=dates)
        group = MacroFeatures()
        result = group.compute_all(data, feature_names=["market_momentum_60d"])
        assert "market_momentum_60d" in result.columns

    def test_credit_spread(self):
        """测试信用利差"""
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        data = pd.DataFrame({
            "credit_spread": np.random.uniform(0.01, 0.05, 100),
        }, index=dates)
        group = MacroFeatures()
        result = group.compute_all(data, feature_names=["credit_spread_20d"])
        assert "credit_spread_20d" in result.columns


# ===========================================================================
# 标签模块测试
# ===========================================================================

class TestLabels:
    """标签模块测试"""

    def test_simple_return_label(self):
        """测试简单收益标签"""
        result = compute_relative_return_label(0.10, 0.03)
        assert abs(result - 0.07) < 0.001

    def test_relative_return_labeler(self):
        """测试相对收益标签器"""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        prices = pd.Series(100.0 + np.random.randn(100).cumsum(), index=dates)

        labeler = RelativeReturnLabeler(horizon=20)
        labels = labeler.compute(prices)

        assert isinstance(labels, pd.Series)
        assert len(labels) == 100


# ===========================================================================
# 评分模块测试
# ===========================================================================

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

    def test_signal_ranker(self, sample_signals):
        """测试信号排名器"""
        ranker = SignalRanker()
        ranked = ranker.rank(sample_signals)

        assert len(ranked) == 5
        # 检查是否按分数排序
        assert ranked[0][2] == 1  # 第一名
        assert ranked[-1][2] == 5  # 最后一名


# ===========================================================================
# 回测结果契约测试
# ===========================================================================

class TestBacktestResult:
    """BacktestResult Pydantic模型测试"""

    def test_backtest_result_is_pydantic(self):
        """确认BacktestResult是Pydantic模型"""
        from pydantic import BaseModel
        assert issubclass(BacktestResult, BaseModel)

    def test_backtest_result_fields(self):
        """测试BacktestResult字段"""
        result = BacktestResult(
            total_return=0.15,
            annual_return=0.12,
            volatility=0.20,
            sharpe_ratio=1.5,
            max_drawdown=-0.10,
            win_rate=0.55,
            total_trades=42,
            signal_id="sig_001",
            engine="vectorbt",
        )
        assert result.total_return == 0.15
        assert result.signal_id == "sig_001"
        assert result.engine == "vectorbt"
        assert result.total_trades == 42

    def test_backtest_result_to_dict(self):
        """测试to_dict方法"""
        result = BacktestResult(
            total_return=0.10,
            signal_id="sig_001",
            engine="simple",
        )
        d = result.to_dict()
        assert d["total_return"] == 0.10
        assert d["signal_id"] == "sig_001"
        assert d["engine"] == "simple"

    def test_backtest_result_engine_enum(self):
        """测试engine字段只能是有效值"""
        for engine in ("simple", "vectorbt", "backtrader"):
            result = BacktestResult(engine=engine)
            assert result.engine == engine

    def test_backtest_result_invalid_engine(self):
        """测试无效engine值"""
        with pytest.raises(Exception):
            BacktestResult(engine="invalid_engine")


# ===========================================================================
# 回测引擎测试
# ===========================================================================

class TestSimpleBacktester:
    """简单回测器测试"""

    def test_simple_backtester(self, price_data):
        """测试简单回测器"""
        backtester = SimpleBacktester(initial_capital=1_000_000)
        result = backtester.run(price_data)

        assert isinstance(result, BacktestResult)
        assert result.total_return is not None
        assert result.sharpe_ratio is not None
        assert result.max_drawdown <= 0.0
        assert result.engine == "simple"
        assert len(result.equity_curve) == len(price_data)

    def test_backtest_with_signals(self, price_data, sample_signal):
        """测试带信号的回测"""
        backtester = SimpleBacktester()
        result = backtester.run(price_data, [sample_signal])

        assert isinstance(result, BacktestResult)
        assert result.total_return is not None
        assert result.engine == "simple"


class TestVectorBTBacktester:
    """VectorBT回测引擎测试"""

    def test_vectorbt_basic(self, price_data):
        """测试基本回测"""
        backtester = VectorBTBacktester(initial_capital=1_000_000)
        result = backtester.run(price_data)

        assert isinstance(result, BacktestResult)
        assert result.engine == "vectorbt"
        assert isinstance(result.total_return, float)
        assert isinstance(result.sharpe_ratio, float)
        assert isinstance(result.max_drawdown, float)
        assert isinstance(result.total_trades, int)

    def test_vectorbt_with_signals(self, price_data, sample_signal):
        """测试带信号的回测"""
        backtester = VectorBTBacktester()
        result = backtester.run(price_data, [sample_signal])

        assert isinstance(result, BacktestResult)
        assert result.engine == "vectorbt"
        assert result.signal_id == sample_signal.signal_id

    def test_vectorbt_with_entries_exits(self, price_data):
        """测试直接传入entries/exits"""
        # 简单MA交叉
        close = price_data["close"]
        ma_short = close.rolling(20).mean()
        ma_long = close.rolling(60).mean()
        entries = (ma_short > ma_long).fillna(False)
        exits = (ma_short < ma_long).fillna(False)

        backtester = VectorBTBacktester()
        result = backtester.run(price_data, entries=entries, exits=exits)

        assert isinstance(result, BacktestResult)
        assert result.engine == "vectorbt"

    def test_vectorbt_result_has_metrics(self, price_data):
        """测试结果包含所有核心指标"""
        backtester = VectorBTBacktester()
        result = backtester.run(price_data)

        # 检查所有BacktestResult字段
        assert hasattr(result, "total_return")
        assert hasattr(result, "annual_return")
        assert hasattr(result, "volatility")
        assert hasattr(result, "sharpe_ratio")
        assert hasattr(result, "max_drawdown")
        assert hasattr(result, "win_rate")
        assert hasattr(result, "total_trades")
        assert hasattr(result, "signal_id")
        assert hasattr(result, "engine")

    def test_vectorbt_multiple_signals(self, price_data, sample_signals):
        """测试多信号组合回测"""
        backtester = VectorBTBacktester()
        result = backtester.run(price_data, sample_signals)

        assert isinstance(result, BacktestResult)
        assert result.engine == "vectorbt"


class TestBacktraderEngine:
    """Backtrader回测引擎测试"""

    def test_backtrader_basic(self, price_data_ohlcv):
        """测试基本回测"""
        backtester = BacktraderEngine(initial_capital=1_000_000)
        result = backtester.run(price_data_ohlcv)

        assert isinstance(result, BacktestResult)
        assert result.engine == "backtrader"
        assert isinstance(result.total_return, float)
        assert isinstance(result.sharpe_ratio, float)
        assert isinstance(result.max_drawdown, float)
        assert isinstance(result.total_trades, int)

    def test_backtrader_with_signals(self, price_data_ohlcv, sample_signal):
        """测试带信号的回测"""
        backtester = BacktraderEngine()
        result = backtester.run(price_data_ohlcv, [sample_signal])

        assert isinstance(result, BacktestResult)
        assert result.engine == "backtrader"
        assert result.signal_id == sample_signal.signal_id

    def test_backtrader_result_has_metrics(self, price_data_ohlcv):
        """测试结果包含所有核心指标"""
        backtester = BacktraderEngine()
        result = backtester.run(price_data_ohlcv)

        assert hasattr(result, "total_return")
        assert hasattr(result, "annual_return")
        assert hasattr(result, "volatility")
        assert hasattr(result, "sharpe_ratio")
        assert hasattr(result, "max_drawdown")
        assert hasattr(result, "win_rate")
        assert hasattr(result, "total_trades")
        assert hasattr(result, "signal_id")
        assert hasattr(result, "engine")

    def test_backtrader_close_only(self, price_data):
        """测试只有close列的数据"""
        backtester = BacktraderEngine()
        result = backtester.run(price_data)

        assert isinstance(result, BacktestResult)
        assert result.engine == "backtrader"


class TestCrossEngineConsistency:
    """跨引擎一致性测试"""

    def test_all_engines_return_backtest_result(self, price_data, price_data_ohlcv):
        """所有引擎都返回BacktestResult"""
        engines = [
            SimpleBacktester(),
            VectorBTBacktester(),
            BacktraderEngine(),
        ]
        data_sources = [price_data, price_data, price_data_ohlcv]

        for engine, data in zip(engines, data_sources):
            result = engine.run(data)
            assert isinstance(result, BacktestResult), f"{engine.name} did not return BacktestResult"
            assert result.engine in ("simple", "vectorbt", "backtrader")

    def test_result_format_consistency(self, price_data, price_data_ohlcv):
        """所有引擎的结果都有相同的字段"""
        results = {}
        engines_data = [
            ("simple", SimpleBacktester(), price_data),
            ("vectorbt", VectorBTBacktester(), price_data),
            ("backtrader", BacktraderEngine(), price_data_ohlcv),
        ]

        for name, engine, data in engines_data:
            results[name] = engine.run(data)

        # 检查所有核心字段存在
        core_fields = ["total_return", "annual_return", "sharpe_ratio", "max_drawdown", "win_rate", "total_trades", "engine"]
        for name, result in results.items():
            for field in core_fields:
                assert hasattr(result, field), f"{name} missing field {field}"
