#!/usr/bin/env python3
"""
AkShare 完整集成示例

演示如何将 AkShare 数据与 AlphaFoundry 系统集成，包括：
1. 获取行情数据并转为资产分析快照
2. 获取新闻并转为文档封包
3. 获取财务数据并更新资产信息
"""
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# 配置基础日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("akshare_integration")


def example_1_market_data_to_snapshot():
    """
    示例 1: 将行情数据转换为资产分析快照

    演示如何将 AkShare 获取的市场数据与核心系统的资产快照模型集成
    """
    logger.info("=" * 60)
    logger.info("Example 1: Market Data Integration")
    logger.info("=" * 60)

    from data_layer.crawlers.akshare import AkShareAdapter, AkShareConfig

    config = AkShareConfig(enable_cache=False, verbose=True)
    adapter = AkShareAdapter(config)

    logger.info("✓ AkShare adapter initialized")

    # 测试代码标准化功能
    test_symbols = ["600000", "000001.SZ", "300750"]
    logger.info("\nCode normalization test:")
    for symbol in test_symbols:
        normalized = adapter.market._normalize_symbol(symbol)
        clean = adapter.market._clean_symbol(symbol)
        market = adapter.market._infer_market(symbol)
        logger.info(f"  {symbol:<12} -> {normalized:<12} (market: {market}, clean: {clean})")

    logger.info("\n✓ Example 1 completed!")


def example_2_news_data_processing():
    """
    示例 2: 新闻数据处理

    演示如何将 AkShare 新闻数据转换为 DocumentEnvelope
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: News Data Processing")
    logger.info("=" * 60)

    from data_layer.crawlers.akshare import AkShareAdapter, AkShareConfig

    config = AkShareConfig(enable_cache=False, verbose=True, news_limit=10)
    AkShareAdapter(config)

    logger.info("✓ AkShare adapter ready for news fetching")

    # 创建模拟新闻数据（用于演示，不实际调用 API）
    from data_layer.crawlers.akshare.base import NewsData

    sample_news = [
        NewsData(
            title="A股市场开盘上涨，银行板块领涨",
            content="今日早盘，A股三大股指集体高开，银行板块表现活跃...",
            publish_time=datetime.now(),
            source="sina",
            url="https://example.com/news/1",
            symbols=["600000.SH", "000001.SZ"],
        ),
        NewsData(
            title="央行发布最新货币政策报告",
            content="中国人民银行发布最新货币政策执行报告，强调...",
            publish_time=datetime.now() - timedelta(hours=2),
            source="eastmoney",
            url="https://example.com/news/2",
            symbols=["000001.SZ"],
        ),
    ]

    logger.info(f"\nCreated {len(sample_news)} sample news items")

    # 展示如何转换为 DocumentEnvelope
    logger.info("\nConverting to DocumentEnvelope format (demo):")
    from uuid import uuid4

    envelopes = []
    for i, news in enumerate(sample_news):
        # 简化演示，创建基本数据结构
        envelope_data = {
            "doc_id": str(uuid4()),
            "raw_text": news.content,
            "canonical_text": news.content,
            "title": news.title,
            "source_type": "news",
            "source_name": news.source,
            "published_at": news.publish_time,
            "metadata": {
                "url": news.url,
                "symbols": news.symbols,
            },
        }
        envelopes.append(envelope_data)
        logger.info(f"  {i + 1}. [{news.source.upper()}] {news.title[:60]}...")

    logger.info(f"\n✓ Converted {len(envelopes)} news to DocumentEnvelope")
    logger.info("✓ Example 2 completed!")


def example_3_financial_data_usage():
    """
    示例 3: 财务数据分析

    演示如何使用 AkShare 获取的财务数据进行分析
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Financial Data Analysis")
    logger.info("=" * 60)

    from data_layer.crawlers.akshare import AkShareAdapter, AkShareConfig

    config = AkShareConfig(enable_cache=False, verbose=True)
    AkShareAdapter(config)

    logger.info("✓ Financial fetcher ready")

    # 展示财务数据结构
    from data_layer.crawlers.akshare.base import FinancialData

    sample_financials = [
        FinancialData(
            symbol="600000.SH",
            report_date=date(2024, 3, 31),
            report_type="quarterly",
            total_revenue=150000000000.0,
            net_profit=50000000000.0,
            roe=12.5,
            debt_ratio=85.0,
        ),
        FinancialData(
            symbol="600000.SH",
            report_date=date(2023, 12, 31),
            report_type="annual",
            total_revenue=580000000000.0,
            net_profit=180000000000.0,
            roe=14.2,
            debt_ratio=83.5,
        ),
    ]

    logger.info(f"\nSample financial data for {sample_financials[0].symbol}:")
    for fin in sample_financials:
        logger.info(f"  {fin.report_date}: ROE={fin.roe}%, Debt={fin.debt_ratio}%")

    logger.info("\n✓ Example 3 completed!")


def example_4_macro_data_analysis():
    """
    示例 4: 宏观数据分析

    演示如何整合宏观经济数据
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Macro Data Analysis")
    logger.info("=" * 60)

    from data_layer.crawlers.akshare import AkShareAdapter, AkShareConfig
    from data_layer.crawlers.akshare.base import MacroData

    config = AkShareConfig(enable_cache=False, verbose=True)
    AkShareAdapter(config)

    logger.info("✓ Macro fetcher ready")

    # 示例宏观数据
    sample_macro = [
        MacroData(indicator="GDP", value=1234567.89, period="2024-Q1", unit="亿元", source="stats"),
        MacroData(indicator="CPI", value=102.5, period="2024-04", unit="指数", source="stats"),
        MacroData(indicator="PMI", value=50.8, period="2024-04", unit="指数", source="stats"),
    ]

    logger.info("\nSample macroeconomic data:")
    for macro in sample_macro:
        logger.info(f"  {macro.indicator}: {macro.value} {macro.unit} ({macro.period})")

    logger.info("\n✓ Example 4 completed!")


def example_5_combined_workflow():
    """
    示例 5: 完整的工作流程

    演示一个完整的研究分析工作流：
    1. 获取股票列表
    2. 选择感兴趣的股票
    3. 获取其历史行情
    4. 获取相关新闻
    5. 获取财务数据
    6. 整合分析
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 5: Combined Research Workflow")
    logger.info("=" * 60)

    from data_layer.crawlers.akshare import AkShareAdapter, AkShareConfig

    config = AkShareConfig(enable_cache=False, verbose=True)
    AkShareAdapter(config)

    logger.info("✓ Starting research workflow...")

    # 步骤 1: 选择研究标的
    target_symbol = "600000.SH"
    logger.info(f"\n1. Selected target: {target_symbol}")

    # 步骤 2: 获取市场数据
    logger.info("2. Market data ready to fetch (requires actual API call)")

    # 步骤 3: 获取相关新闻
    logger.info("3. News data ready to fetch (requires actual API call)")

    # 步骤 4: 获取财务数据
    logger.info("4. Financial data ready to fetch (requires actual API call)")

    # 步骤 5: 获取宏观数据
    logger.info("5. Macro data ready to fetch (requires actual API call)")

    # 模拟整合分析
    logger.info("\nCombining analysis...")
    logger.info("✓ Data sources integrated")
    logger.info("✓ Ready for scenario analysis")

    logger.info("\n✓ Example 5 completed!")


def main():
    """运行所有集成示例"""
    logger.info("\n" + "=" * 60)
    logger.info("AlphaFoundry - AkShare Integration Examples")
    logger.info("=" * 60)

    examples = [
        ("Market Data Integration", example_1_market_data_to_snapshot),
        ("News Data Processing", example_2_news_data_processing),
        ("Financial Data Usage", example_3_financial_data_usage),
        ("Macro Data Analysis", example_4_macro_data_analysis),
        ("Combined Workflow", example_5_combined_workflow),
    ]

    results = []
    for name, example_func in examples:
        try:
            example_func()
            results.append((name, True, None))
        except Exception as e:
            logger.error(f"\n✗ Example '{name}' failed: {e}", exc_info=True)
            results.append((name, False, str(e)))

    # 总结
    logger.info("\n" + "=" * 60)
    logger.info("Integration Examples Summary")
    logger.info("=" * 60)

    all_passed = True
    for name, success, error in results:
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"  {name}: {status}")
        if error:
            logger.info(f"    Error: {error}")
            all_passed = False

    logger.info("=" * 60)
    if all_passed:
        logger.info("All integration examples passed!")
    else:
        logger.warning("Some integration examples failed!")

    logger.info("\n" + "=" * 60)
    logger.info("CLI Usage Quick Reference:")
    logger.info("=" * 60)
    logger.info("  af akshare health                - Check AkShare status")
    logger.info("  af akshare stocks --limit 50     - Fetch stock list")
    logger.info("  af akshare news --limit 20       - Fetch finance news")
    logger.info("  af akshare macro --indicator all - Fetch macro data")
    logger.info("  af akshare quotes -s 600000.SH   - Fetch historical quotes")
    logger.info("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
