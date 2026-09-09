#!/usr/bin/env python3
"""
设置价格数据缓存
- 创建数据库表
- 预填充核心股票的历史数据
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import get_logger
from data_layer.adapters.hybrid_price_adapter import HybridPriceAdapter
from data_layer.repositories.base import ensure_schema

logger = get_logger(__name__)


def main():
    print("\n" + "=" * 80)
    print("  Research Workbench - 设置价格数据缓存")
    print("=" * 80 + "\n")

    # 1. 创建表结构
    print("[1/3] 初始化数据库表结构...")
    ensure_schema()
    print("  ✓ 表结构已准备\n")

    # 2. 预填充核心股票数据
    print("[2/3] 预填充历史数据...")

    adapter = HybridPriceAdapter()

    stocks = [
        ("600519.SH", 1680.0),  # 贵州茅台
        ("000001.SZ", 11.25),  # 平安银行
        ("002594.SZ", 235.50),  # 比亚迪
        ("601012.SH", 28.60),  # 隆基绿能
        ("000300.SH", 3450.0),  # 沪深300
        ("000977.SH", 35.0),  # 浪潮信息
    ]

    for code, base_price in stocks:
        print(f"  - {code}...")
        adapter.prefill_cache_with_historical(code, base_price)

    print("  ✓ 历史数据预填充完成\n")

    # 3. 验证数据
    print("[3/3] 验证数据...")
    for code, _ in stocks:
        data = adapter._get_from_cache(code, "2024-05-01", "2024-08-01")
        print(f"  - {code}: {len(data)} 条记录")

    print("\n" + "=" * 80)
    print("  ✓ 价格数据缓存设置完成！")
    print("=" * 80)
    print("\n使用说明：")
    print("  - ClosedLoopService会自动尝试AKShare在线获取")
    print("  - 在线失败时自动使用本地缓存")
    print("  - 在线成功时自动缓存到本地\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
