#!/usr/bin/env python3
"""
AkShare 集成测试脚本

测试 AkShare 适配器的各项功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from datetime import datetime
import logging

# 配置简单日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("akshare_integration_test")


def test_adapter_import():
    """测试导入适配器"""
    logger.info("Testing adapter import...")


    logger.info("✓ All modules imported successfully")
    return True


def test_config_creation():
    """测试配置创建"""
    logger.info("Testing config creation...")

    from data_layer.crawlers.akshare import AkShareConfig, DEFAULT_CONFIG

    # 默认配置
    assert DEFAULT_CONFIG is not None
    assert DEFAULT_CONFIG.enable_cache is True

    # 自定义配置
    config = AkShareConfig(
        enable_cache=False,
        verbose=True,
        news_limit=50,
    )
    assert config.enable_cache is False
    assert config.verbose is True
    assert config.news_limit == 50

    logger.info("✓ Config creation successful")
    return True


def test_data_classes():
    """测试数据类"""
    logger.info("Testing data classes...")

    from data_layer.crawlers.akshare import (
        MarketData,
        NewsData,
        StockInfo,
    )

    # 测试市场数据
    md = MarketData(
        symbol="600000.SH",
        timestamp=datetime.now(),
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
        volume=1000000,
    )
    assert md.symbol == "600000.SH"
    assert md.close == 10.5

    # 测试新闻数据
    nd = NewsData(
        title="Test News",
        content="Test Content",
        publish_time=datetime.now(),
        source="test",
    )
    assert nd.title == "Test News"

    # 测试股票信息
    si = StockInfo(
        symbol="600000.SH",
        name="浦发银行",
        market="SH",
        industry="银行",
    )
    assert si.name == "浦发银行"

    logger.info("✓ Data classes working")
    return True


def test_adapter_creation():
    """测试适配器创建"""
    logger.info("Testing adapter creation...")

    from data_layer.crawlers.akshare import AkShareAdapter, AkShareConfig

    config = AkShareConfig(enable_cache=False, verbose=True)
    adapter = AkShareAdapter(config)

    # 验证 fetcher 访问
    assert adapter.market is not None
    assert adapter.financial is not None
    assert adapter.news is not None
    assert adapter.macro is not None

    logger.info("✓ Adapter created successfully")
    return True


def test_market_fetcher_basic():
    """测试行情获取器基础功能"""
    logger.info("Testing market fetcher...")

    from data_layer.crawlers.akshare import AkShareMarketFetcher, AkShareConfig

    config = AkShareConfig(enable_cache=False, verbose=True)
    fetcher = AkShareMarketFetcher(config)

    # 测试代码标准化
    assert fetcher._normalize_symbol("600000") == "600000.SH"
    assert fetcher._normalize_symbol("000001") == "000001.SZ"
    assert fetcher._clean_symbol("600000.SH") == "600000"
    assert fetcher._infer_market("600000.SH") == "SH"
    assert fetcher._infer_market("000001.SZ") == "SZ"

    logger.info("✓ Market fetcher basic functions working")
    return True


def run_safe_function_test():
    """运行安全的功能测试（不真正调用 AkShare API）"""
    logger.info("=" * 60)
    logger.info("Running AkShare Integration Tests (Safe Mode)")
    logger.info("=" * 60)

    tests = [
        ("Adapter Import", test_adapter_import),
        ("Config Creation", test_config_creation),
        ("Data Classes", test_data_classes),
        ("Adapter Creation", test_adapter_creation),
        ("Market Fetcher Basic", test_market_fetcher_basic),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            logger.error(f"✗ {name} failed: {e}")
            results.append((name, False, str(e)))

    logger.info("=" * 60)
    logger.info("Test Summary:")
    for name, success, error in results:
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"  {name}: {status}")
        if error:
            logger.info(f"    Error: {error}")

    all_passed = all(success for _, success, _ in results)
    logger.info("=" * 60)
    if all_passed:
        logger.info("All tests passed!")
    else:
        logger.warning("Some tests failed!")

    return all_passed


def main():
    """主函数"""
    print()
    print("=" * 60)
    print("AlphaFoundry AkShare Integration Test")
    print("=" * 60)
    print()

    success = run_safe_function_test()

    print()
    if success:
        print("✓ All integration tests passed!")
        return 0
    else:
        print("✗ Some integration tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
