#!/usr/bin/env python3
"""
Research Workbench 双源数据系统使用示例

演示如何使用：
1. MultiSourceCoordinator - 主入口
2. 时间窗口策略 - 自动判断是否双源校验
3. 告警和审计 - 记录所有操作
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def example_basic_usage():
    """基本使用示例"""
    print("\n" + "=" * 60)
    print("Example 1: Basic Coordinator Usage")
    print("=" * 60)

    from data_layer.coordinator import get_coordinator

    coordinator = get_coordinator()

    # 1. 查看当前时间窗口决策
    print("\n1. Current time window decision:")
    decision = coordinator.time_window_strategy.get_decision()
    print(f"   Mode: {decision.current_mode.value}")
    print(f"   Active sources: {decision.active_sources}")
    print(f"   Should validate: {decision.should_validate}")

    # 2. 查看健康检查状态
    print("\n2. Health check (skipping real network calls):")
    print("   Coordinator is ready and components are initialized")


def example_time_window():
    """时间窗口策略示例"""
    print("\n" + "=" * 60)
    print("Example 2: Time Window Strategy")
    print("=" * 60)

    from data_layer.validation import TimeWindowConfig, TimeWindowStrategy

    # 创建策略
    config = TimeWindowConfig()
    strategy = TimeWindowStrategy(config)

    # 测试不同时间点
    test_times = [
        datetime(2024, 5, 15, 9, 0, 0),  # 刚进入白天
        datetime(2024, 5, 15, 14, 30, 0),  # 白天中间
        datetime(2024, 5, 15, 20, 59, 0),  # 白天快结束
        datetime(2024, 5, 15, 21, 0, 0),  # 刚进入晚上
        datetime(2024, 5, 15, 23, 30, 0),  # 深夜
    ]

    for t in test_times:
        decision = strategy.get_decision(t)
        print(f"\n{t}:")
        print(f"  Mode: {decision.current_mode.value}")
        print(f"  Sources: {decision.active_sources}")
        print(f"  Validate: {decision.should_validate}")


def example_dual_validation():
    """双源校验示例"""
    print("\n" + "=" * 60)
    print("Example 3: Dual Source Validation")
    print("=" * 60)

    from data_layer.crawlers.akshare.base import MarketData
    from data_layer.validation import DualSourceValidator

    # 创建校验器 - 0.5% 阈值
    validator = DualSourceValidator(threshold_pct=0.5, warning_threshold_pct=0.2)

    # 创建模拟数据
    base_date = datetime(2024, 5, 1)

    # 场景1：数据完全一致
    print("\nScenario 1: Perfect data alignment")
    data1_p = []
    data2_p = []
    for i in range(5):
        dt = base_date + timedelta(days=i)
        close = 100.0 + i * 0.5
        data1_p.append(MarketData(symbol="600519.SH", timestamp=dt, close=close, source="akshare"))
        data2_p.append(MarketData(symbol="600519.SH", timestamp=dt, close=close, source="baostock"))
    result1 = validator.validate("600519.SH", data1_p, data2_p, "akshare", "baostock")
    print(f"  Status: {result1.status.value}")
    print(f"  Summary: {result1.summary}")

    # 场景2：有小差异
    print("\nScenario 2: Small discrepancies (<0.5%)")
    data2_s = []
    for i in range(5):
        dt = base_date + timedelta(days=i)
        # 添加 0.1% 差异
        close = 100.0 + i * 0.5 + 0.1
        data2_s.append(MarketData(symbol="600519.SH", timestamp=dt, close=close, source="baostock"))
    result2 = validator.validate("600519.SH", data1_p, data2_s, "akshare", "baostock")
    print(f"  Status: {result2.status.value}")
    print(f"  Max diff: {result2.max_relative_diff_pct:.2f}%")

    # 场景3：有大差异
    print("\nScenario 3: Large discrepancies (>0.5%)")
    data2_l = []
    for i in range(5):
        dt = base_date + timedelta(days=i)
        # 添加 1% 差异
        close = 100.0 + i * 0.5 + 1.0
        data2_l.append(MarketData(symbol="600519.SH", timestamp=dt, close=close, source="baostock"))
    result3 = validator.validate("600519.SH", data1_p, data2_l, "akshare", "baostock")
    print(f"  Status: {result3.status.value}")
    print(f"  Max diff: {result3.max_relative_diff_pct:.2f}%")
    print(f"  Recommended source: {result3.recommended_source}")


def example_adjustment_flags():
    """复权标志示例"""
    print("\n" + "=" * 60)
    print("Example 4: Adjustment Flags")
    print("=" * 60)

    from data_layer.validation import AdjustmentNormalizer, AdjustmentType

    normalizer = AdjustmentNormalizer()

    # 获取不同复权方式的拉取参数
    for adj_type in [AdjustmentType.QFQ, AdjustmentType.HFQ, AdjustmentType.NONE]:
        flags = normalizer.get_fetch_adjustment_flags(adj_type)
        print(f"\n{adj_type.value.upper()}:")
        print(f"  AkShare: '{flags['akshare']}'")
        print(f"  BaoStock: '{flags['baostock']}'")


def example_audit_log():
    """审计日志示例"""
    print("\n" + "=" * 60)
    print("Example 5: Audit Logging")
    print("=" * 60)

    from data_layer.validation import get_audit_logger

    audit = get_audit_logger()

    # 记录一些事件
    print("\nLogging events...")
    audit.log_fetch("600519.SH", "akshare", 250, success=True)
    audit.log_fetch("000001.SZ", "akshare", 0, success=False, error="Network timeout")
    audit.log_merge(
        "600519.SH",
        ["akshare", "baostock"],
        250,
        "akshare",
        validation_passed=True,
    )

    print("\nEvents logged successfully!")
    print("\nNote: Real audit logs are stored in .ai/audit_logs/ directory")


def main():
    """运行示例"""
    print("=" * 60)
    print("Research Workbench Dual Source System - Examples")
    print("=" * 60)

    try:
        example_basic_usage()
        example_time_window()
        example_dual_validation()
        example_adjustment_flags()
        example_audit_log()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        print("\nQuick Reference:")
        print("  - MultiSourceCoordinator: data_layer.coordinator.get_coordinator()")
        print("  - TimeWindowStrategy: data_layer.validation.TimeWindowStrategy")
        print("  - DualSourceValidator: data_layer.validation.DualSourceValidator")
        print("  - BaoStockAdapter: data_layer.crawlers.baostock.BaoStockAdapter")
        print("  - Audit logs: .ai/audit_logs/")
        print("=" * 60)

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
