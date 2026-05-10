#!/usr/bin/env python3
"""测试AKShare连接性"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import time

from core.observability import get_logger
from data_layer.adapters.akshare_adapter import AKShareAdapter

logger = get_logger(__name__)


async def test_akshare_direct():
    """直接测试AKShare"""
    import akshare as ak

    print("=" * 60)
    print("测试 AKShare 直接测试")
    print("=" * 60)

    try:
        print("\n1. 测试获取贵州茅台 (sh600519)")
        print("-" * 40)
        start = time.time()

        # 尝试获取贵州茅台数据
        df = ak.stock_zh_a_hist(
            symbol="sh600519", period="daily", start_date="20240501", end_date="20240601"
        )

        elapsed = time.time() - start

        if df is not None and not df.empty:
            print(f"✅ 成功获取 {len(df)} 条数据")
            print(f"   耗时: {elapsed:.2f}秒")
            print(f"   日期范围: {df.iloc[0]['日期']} 至 {df.iloc[-1]['日期']}")
            print(f"   最新收盘: {df.iloc[-1]['收盘']:.2f}")
        else:
            print("❌ 未获取到数据")
        return True

    except Exception as e:
        print(f"❌ AKShare 直接调用失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_adapter():
    """测试AKShareAdapter"""
    print("\n" + "=" * 60)
    print("测试 AKShareAdapter")
    print("=" * 60)

    adapter = AKShareAdapter()

    try:
        print(f"\n1. 适配器可用性: {adapter.is_available()}")

        print("\n2. 测试 fetch_stock_quotes")
        print("-" * 40)

        start = time.time()
        quotes = await adapter.fetch_stock_quotes("600519.SH", "2024-05-01", "2024-06-01")
        elapsed = time.time() - start

        if quotes:
            print(f"✅ 成功获取 {len(quotes)} 条数据")
            print(f"   耗时: {elapsed:.2f}秒")
            print(f"   日期范围: {quotes[0]['date']} 至 {quotes[-1]['date']}")
            print(f"   最新收盘: {quotes[-1]['close']:.2f}")
            return True
        else:
            print("❌ 未获取到数据")
            return False

    except Exception as e:
        print(f"❌ 适配器测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_multiple_stocks():
    """测试多个股票"""
    print("\n" + "=" * 60)
    print("测试多个股票代码")
    print("=" * 60)

    test_codes = [
        "600519.SH",  # 贵州茅台
        "000001.SZ",  # 平安银行
        "002594.SZ",  # 比亚迪
        "601012.SH",  # 隆基绿能
        "000300.SH",  # 沪深300（指数，可能不支持）
    ]

    adapter = AKShareAdapter()

    results = {}
    for code in test_codes:
        print(f"\n测试: {code}")
        try:
            quotes = await adapter.fetch_stock_quotes(code, "2024-05-01", "2024-06-01")
            if quotes:
                print(f"  ✅ 成功: {len(quotes)} 条")
                results[code] = len(quotes)
            else:
                print("  ❌ 失败")
                results[code] = 0
        except Exception as e:
            print(f"  ❌ 异常: {e}")
            results[code] = -1

    print("\n" + "-" * 40)
    print("汇总:")
    for code, count in results.items():
        status = "✅" if count > 0 else "❌"
        print(f"  {status} {code}: {count if count >=0 else 'error'}")

    return any(c > 0 for c in results.values())


async def main():
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "AlphaFoundry AKShare 连接测试" + " " * 26 + "║")
    print("╚" + "═" * 58 + "╝")

    success = 0
    total = 0

    # 测试1: 直接AKShare
    total += 1
    if await test_akshare_direct():
        success += 1

    # 测试2: 适配器
    total += 1
    if await test_adapter():
        success += 1

    # 测试3: 多个股票
    total += 1
    if await test_multiple_stocks():
        success += 1

    print("\n" + "=" * 60)
    print(f"测试完成: {success}/{total} 成功")

    if success == total:
        print("✅ AKShare 工作正常")
        return 0
    else:
        print("⚠️  部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
