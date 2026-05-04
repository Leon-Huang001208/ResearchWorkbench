"""
信号实验室完整演示

演示从特征工程到回测的完整信号工作流
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd

from core.contracts import AlphaSignal
from core.services import SignalService
from core.observability import get_logger
from signal_lab.features import FeatureBuilder
from signal_lab.features.groups import (
    FinancialFeatures,
    FundFlowFeatures,
    PriceVolumeFeatures,
    ValuationFeatures,
)
from signal_lab.labels import RelativeReturnLabeler
from signal_lab.scoring import SignalRanker
from signal_lab.backtests import SimpleBacktester

logger = get_logger(__name__)


def generate_sample_prices(
    start_date: str = "2024-01-01",
    periods: int = 252,
    seed: int = 42,
) -> pd.DataFrame:
    """生成示例价格数据"""
    np.random.seed(seed)
    dates = pd.date_range(start=start_date, periods=periods, freq="D")

    # 生成价格序列
    base_price = 100.0
    returns = np.random.normal(0.001, 0.02, periods)
    price_series = base_price * (1 + returns).cumprod()

    # 生成成交量
    volume = np.random.randint(100000, 1000000, periods)

    # 生成一些财务指标
    pe_ratio = 20.0 + np.random.randn(periods).cumsum() * 0.1
    pb_ratio = 2.0 + np.random.randn(periods).cumsum() * 0.05
    roe = 0.15 + np.random.randn(periods) * 0.02

    return pd.DataFrame(
        {
            "close": price_series,
            "volume": volume,
            "pe": pe_ratio,
            "pb": pb_ratio,
            "roe": roe,
        },
        index=dates,
    )


def demo_feature_engineering(prices: pd.DataFrame):
    """演示特征工程"""
    print("\n" + "=" * 60)
    print("  1. 特征工程")
    print("=" * 60)

    builder = FeatureBuilder()
    builder.add_group(PriceVolumeFeatures())
    builder.add_group(ValuationFeatures())
    builder.add_group(FinancialFeatures())
    builder.add_group(FundFlowFeatures())

    print(f"\n特征组: {builder.get_group_names()}")
    print(f"总特征数: {len(builder.get_all_feature_names())}")

    features = builder.compute_features(prices)

    print(f"\n特征数据形状: {features.shape}")
    print(f"\n最新特征值:")
    latest = features.iloc[-1].dropna()
    for name, value in latest.head(10).items():
        print(f"  {name}: {value:.4f}")

    return features


def demo_label_generation(prices: pd.DataFrame):
    """演示标签生成"""
    print("\n" + "=" * 60)
    print("  2. 标签生成")
    print("=" * 60)

    labeler = RelativeReturnLabeler(horizon=20, forward=True)
    labels = labeler.compute(prices)

    print(f"\n标签统计:")
    print(f"  样本数: {len(labels.dropna())}")
    print(f"  均值: {labels.mean():.4%}")
    print(f"  标准差: {labels.std():.4%}")
    print(f"  最小值: {labels.min():.4%}")
    print(f"  最大值: {labels.max():.4%}")

    return labels


def demo_signal_creation():
    """演示信号创建"""
    print("\n" + "=" * 60)
    print("  3. 信号创建")
    print("=" * 60)

    service = SignalService()

    # 创建几个信号
    signal1 = service.create_signal(
        subject_id="600519.SH",
        thesis="白酒行业景气度回升，茅台业绩超预期",
        horizon="20d",
        score=0.8,
        confidence=0.7,
        scenario_refs=["scenario_base", "scenario_optimistic"],
        evidence_refs=["assertion1", "assertion2", "assertion3"],
    )

    signal2 = service.create_signal(
        subject_id="000001.SZ",
        thesis="银行业受益于政策支持，估值修复",
        horizon="60d",
        score=0.6,
        confidence=0.5,
        evidence_refs=["assertion4"],
    )

    signal3 = service.create_signal(
        subject_id="600036.SH",
        thesis="新能源汽车销量超预期，带动产业链",
        horizon="20d",
        score=0.75,
        confidence=0.65,
        scenario_refs=["scenario_optimistic"],
        evidence_refs=["assertion5", "assertion6"],
    )

    print(f"\n已创建 {len(service.signals)} 个信号:")
    for signal_id, signal in service.signals.items():
        print(f"  [{signal.status}] {signal_id[:8]}... - {signal.subject_id}")
        print(f"    {signal.thesis[:40]}...")
        print(f"    Score: {signal.score:.2f}, Confidence: {signal.confidence:.2f}")

    return service


def demo_signal_ranking(service: SignalService):
    """演示信号排名"""
    print("\n" + "=" * 60)
    print("  4. 信号排名")
    print("=" * 60)

    ranker = SignalRanker()
    signals = list(service.signals.values())

    ranked = ranker.rank(signals)

    print(f"\n信号排名:")
    for signal, score, rank in ranked:
        print(f"  {rank}. {signal.subject_id} - 综合评分: {score:.3f}")

    return ranked


def demo_backtesting(prices: pd.DataFrame, service: SignalService):
    """演示回测"""
    print("\n" + "=" * 60)
    print("  5. 信号回测")
    print("=" * 60)

    backtester = SimpleBacktester(
        initial_capital=1000000,
        position_size=0.1,
    )

    signals = list(service.signals.values())
    result = backtester.run(prices, signals)

    print(f"\n回测结果:")
    print(f"  总收益率:    {result.total_return:>10.2%}")
    print(f"  年化收益率:  {result.annual_return:>10.2%}")
    print(f"  波动率:      {result.volatility:>10.2%}")
    print(f"  夏普比率:    {result.sharpe_ratio:>10.2f}")
    print(f"  最大回撤:    {result.max_drawdown:>10.2%}")
    print(f"  胜率:        {result.win_rate:>10.2%}")
    print(f"  交易次数:    {result.num_trades:>10}")

    return result


def demo_trade_candidates(service: SignalService):
    """演示交易候选生成"""
    print("\n" + "=" * 60)
    print("  6. 交易候选生成")
    print("=" * 60)

    signals = list(service.signals.values())

    for signal in signals:
        candidate = service.generate_trade_candidate(signal)
        print(f"\n信号: {signal.subject_id}")
        print(f"  候选ID: {candidate.candidate_id[:8]}...")
        print(f"  动作: {candidate.action}")
        print(f"  仓位建议: {candidate.sizing_hint:.2%}")
        if candidate.risk_notes:
            print(f"  风险提示: {', '.join(candidate.risk_notes)}")


def main():
    """主函数 - 运行完整演示"""
    print("\n" + "=" * 60)
    print("  AlphaFoundry Signal Lab - 完整演示")
    print("=" * 60)

    try:
        # 1. 生成示例数据
        prices = generate_sample_prices()
        print(f"\n示例数据:")
        print(f"  期间: {prices.index[0]} 至 {prices.index[-1]}")
        print(f"  交易日: {len(prices)}")
        print(f"  起始价格: {prices['close'].iloc[0]:.2f}")
        print(f"  结束价格: {prices['close'].iloc[-1]:.2f}")

        # 2. 特征工程
        demo_feature_engineering(prices)

        # 3. 标签生成
        demo_label_generation(prices)

        # 4. 信号创建
        service = demo_signal_creation()

        # 5. 信号排名
        demo_signal_ranking(service)

        # 6. 回测
        demo_backtesting(prices, service)

        # 7. 交易候选
        demo_trade_candidates(service)

        print("\n" + "=" * 60)
        print("  演示完成！")
        print("=" * 60)

        print("\n下一步:")
        print("  - 运行 CLI: af signal --help")
        print("  - 运行 CLI: af backtest --help")
        print("  - 查看文档: docs/")

    except Exception as e:
        print(f"\n✗ 演示过程中出错: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
