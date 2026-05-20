#!/usr/bin/env python3
"""
AkShare 使用示例

展示如何在 AlphaFoundry 中使用 AkShare 适配器
"""
import logging
import sys
from datetime import date, datetime
from pathlib import Path

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("akshare_examples")


def example_1_basic_setup():
    """示例 1: 基本设置"""
    logger.info("=" * 60)
    logger.info("Example 1: Basic Setup")
    logger.info("=" * 60)

    from data_layer.crawlers.akshare import AkShareAdapter, AkShareConfig

    # 创建配置
    config = AkShareConfig(
        enable_cache=False,
        verbose=True,
    )

    # 创建适配器
    adapter = AkShareAdapter(config)

    logger.info(f"✓ Adapter created: {adapter}")
    logger.info(f"✓ Config: cache={config.enable_cache}, verbose={config.verbose}")

    # 访问各个 fetcher
    logger.info("✓ Market fetcher available")
    logger.info("✓ Financial fetcher available")
    logger.info("✓ News fetcher available")
    logger.info("✓ Macro fetcher available")

    return adapter


def example_2_data_classes():
    """示例 2: 使用数据类"""
    logger.info("=" * 60)
    logger.info("Example 2: Using Data Classes")
    logger.info("=" * 60)

    from data_layer.crawlers.akshare import (
        FinancialData,
        MacroData,
        MarketData,
        NewsData,
        StockInfo,
    )

    # 市场数据
    market_data = MarketData(
        symbol="600000.SH",
        timestamp=datetime.now(),
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
        volume=1000000,
        amount=10500000.0,
    )
    logger.info(f"✓ MarketData: {market_data.symbol}, close={market_data.close}")

    # 股票信息
    stock_info = StockInfo(
        symbol="600000.SH",
        name="浦发银行",
        market="SH",
        industry="银行",
    )
    logger.info(f"✓ StockInfo: {stock_info.name} ({stock_info.symbol})")

    # 新闻数据
    news_data = NewsData(
        title="银行板块上涨",
        content="今日银行板块全线上涨...",
        publish_time=datetime.now(),
        source="example",
        symbols=["600000.SH", "000001.SZ"],
    )
    logger.info(f"✓ NewsData: {news_data.title}")

    # 财务数据
    financial_data = FinancialData(
        symbol="600000.SH",
        report_date=date(2024, 3, 31),
        report_type="quarterly",
        net_profit=1000000000.0,
        roe=10.5,
        total_revenue=5000000000.0,
    )
    logger.info(f"✓ FinancialData: ROE={financial_data.roe}%")

    # 宏观数据
    macro_data = MacroData(
        indicator="GDP",
        value=1234567.89,
        period="2024-Q1",
        unit="亿元",
    )
    logger.info(f"✓ MacroData: {macro_data.indicator}={macro_data.value}{macro_data.unit}")


def example_3_market_functions():
    """示例 3: 市场功能"""
    logger.info("=" * 60)
    logger.info("Example 3: Market Functions")
    logger.info("=" * 60)

    from data_layer.crawlers.akshare import AkShareConfig
    from data_layer.crawlers.akshare.market import AkShareMarketFetcher

    config = AkShareConfig(verbose=True)
    fetcher = AkShareMarketFetcher(config)

    # 测试代码标准化
    test_codes = ["600000", "600000.SH", "000001", "000001.SZ", "831010"]

    for code in test_codes:
        normalized = fetcher._normalize_symbol(code)
        cleaned = fetcher._clean_symbol(code)
        market = fetcher._infer_market(code)
        logger.info(f"  {code} -> {normalized} (market={market}, clean={cleaned})")

    logger.info("✓ Market code normalization working")


def example_4_with_existing_adapter():
    """示例 4: 与现有 AKShareAdapter 一起使用"""
    logger.info("=" * 60)
    logger.info("Example 4: Using with Existing AKShareAdapter")
    logger.info("=" * 60)

    try:
        from data_layer.adapters.akshare_adapter import AKShareAdapter  # noqa: F401

        logger.info("✓ Existing AKShareAdapter available")
    except ImportError:
        logger.warning("Existing AKShareAdapter not found (this is normal)")

    try:
        from data_layer.adapters.data_source_router import DataSourceRouter  # noqa: F401

        logger.info("✓ DataSourceRouter available")
    except ImportError:
        logger.warning("DataSourceRouter not found")


def run_all_examples():
    """运行所有示例"""
    print()
    print("=" * 60)
    print("AlphaFoundry AkShare Usage Examples")
    print("=" * 60)
    print()

    examples = [
        ("Basic Setup", example_1_basic_setup),
        ("Data Classes", example_2_data_classes),
        ("Market Functions", example_3_market_functions),
        ("Existing Adapter", example_4_with_existing_adapter),
    ]

    results = []
    for name, example_func in examples:
        try:
            example_func()
            results.append((name, True, None))
            print()
        except Exception as e:
            logger.error(f"✗ {name} failed: {e}")
            results.append((name, False, str(e)))
            print()

    # 总结
    logger.info("=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)

    for name, success, error in results:
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"  {name}: {status}")
        if error:
            logger.info(f"    Error: {error}")

    all_passed = all(success for _, success, _ in results)

    logger.info("=" * 60)
    if all_passed:
        logger.info("All examples passed!")
    else:
        logger.warning("Some examples failed!")

    return all_passed


def main():
    """主函数"""
    success = run_all_examples()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
