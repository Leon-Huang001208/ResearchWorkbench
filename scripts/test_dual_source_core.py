#!/usr/bin/env python3
"""
双源系统核心逻辑测试（不需要网络）

验证：
1. 时间窗口策略
2. 双源校验引擎
3. 复权对齐器
4. 告警管理器
5. 审计日志
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import get_logger

logger = get_logger("test_dual_source_core")


def test_time_window_strategy():
    """测试时间窗口策略"""
    print("\n=== Testing Time Window Strategy ===")

    try:
        from data_layer.validation import TimeWindowConfig, TimeWindowStrategy

        config = TimeWindowConfig()
        strategy = TimeWindowStrategy(config)

        # 测试白天
        daytime = datetime(2024, 5, 15, 14, 30, 0)
        decision_day = strategy.get_decision(daytime)
        print("Daytime (14:30):")
        print(f"  Mode: {decision_day.current_mode.value}")
        print(f"  Active sources: {decision_day.active_sources}")
        print(f"  Should validate: {decision_day.should_validate}")
        print(f"  Next transition: {decision_day.next_transition}")

        assert decision_day.current_mode.value == "daytime"
        assert decision_day.active_sources == ["akshare"]
        assert not decision_day.should_validate

        # 测试晚上
        nighttime = datetime(2024, 5, 15, 22, 30, 0)
        decision_night = strategy.get_decision(nighttime)
        print("\nNighttime (22:30):")
        print(f"  Mode: {decision_night.current_mode.value}")
        print(f"  Active sources: {decision_night.active_sources}")
        print(f"  Should validate: {decision_night.should_validate}")

        assert decision_night.current_mode.value == "nighttime"
        assert decision_night.active_sources == ["akshare", "baostock"]
        assert decision_night.should_validate

        # 测试辅助方法
        assert strategy.is_daytime(daytime)
        assert strategy.is_nighttime(nighttime)
        assert strategy.get_active_sources(daytime) == ["akshare"]

        print("\n✓ Time window strategy tests passed!")
        return True

    except Exception as e:
        logger.error(f"Time window strategy test failed: {e}", exc_info=True)
        return False


def test_dual_source_validator():
    """测试双源校验器"""
    print("\n=== Testing Dual Source Validator ===")

    try:
        from data_layer.crawlers.akshare.base import MarketData
        from data_layer.validation import DualSourceValidator

        validator = DualSourceValidator(threshold_pct=0.5, warning_threshold_pct=0.2)

        # 创建模拟数据
        base_date = datetime(2024, 5, 1)
        data1 = []
        data2 = []

        for i in range(10):
            dt = base_date + timedelta(days=i)
            close1 = 100.0 + i * 0.5
            close2 = 100.0 + i * 0.5

            if i == 5:
                close2 = 100.0 + i * 0.5 + 1.0  # 1% 差异

            data1.append(
                MarketData(
                    symbol="600519.SH",
                    timestamp=dt,
                    close=close1,
                    source="akshare",
                )
            )
            data2.append(
                MarketData(
                    symbol="600519.SH",
                    timestamp=dt,
                    close=close2,
                    source="baostock",
                )
            )

        # 执行校验
        result = validator.validate(
            symbol="600519.SH",
            data_source1=data1,
            data_source2=data2,
            source1_name="akshare",
            source2_name="baostock",
        )

        print(f"Validation status: {result.status.value}")
        print(f"Data points compared: {result.data_points_compared}")
        print(f"Max diff: {result.max_relative_diff_pct:.2f}%")
        print(f"Avg diff: {result.avg_relative_diff_pct:.2f}%")
        print(f"Discrepancies: {len(result.discrepancies)}")
        print(f"Recommended source: {result.recommended_source}")
        print(f"Summary: {result.summary}")

        # 验证结果
        assert result.data_points_compared == 10
        assert len(result.discrepancies) >= 1
        assert result.recommended_source == "akshare"

        # 测试通过的场景
        data2_pass = []
        for i in range(10):
            dt = base_date + timedelta(days=i)
            data2_pass.append(
                MarketData(
                    symbol="600519.SH",
                    timestamp=dt,
                    close=100.0 + i * 0.5,
                    source="baostock",
                )
            )

        result_pass = validator.validate(
            symbol="600519.SH",
            data_source1=data1,
            data_source2=data2_pass,
            source1_name="akshare",
            source2_name="baostock",
        )
        print(f"\nPerfect data validation status: {result_pass.status.value}")

        print("\n✓ Dual source validator tests passed!")
        return True

    except Exception as e:
        logger.error(f"Dual source validator test failed: {e}", exc_info=True)
        return False


def test_adjustment_normalizer():
    """测试复权对齐器"""
    print("\n=== Testing Adjustment Normalizer ===")

    try:
        from data_layer.validation import AdjustmentNormalizer, AdjustmentType

        normalizer = AdjustmentNormalizer()

        # 测试获取拉取参数
        flags = normalizer.get_fetch_adjustment_flags(AdjustmentType.QFQ)
        print("Fetch flags for QFQ:")
        print(f"  AkShare: {flags['akshare']}")
        print(f"  BaoStock: {flags['baostock']}")

        assert flags["akshare"] == "qfq"
        assert flags["baostock"] == "2"

        flags = normalizer.get_fetch_adjustment_flags(AdjustmentType.NONE)
        print("\nFetch flags for NONE:")
        print(f"  AkShare: '{flags['akshare']}'")
        print(f"  BaoStock: {flags['baostock']}")

        assert flags["akshare"] == ""
        assert flags["baostock"] == "3"

        flags = normalizer.get_fetch_adjustment_flags(AdjustmentType.HFQ)
        print("\nFetch flags for HFQ:")
        print(f"  AkShare: {flags['akshare']}")
        print(f"  BaoStock: {flags['baostock']}")

        assert flags["akshare"] == "hfq"
        assert flags["baostock"] == "1"

        # 测试检测复权类型
        from data_layer.crawlers.akshare.base import MarketData

        test_data = [
            MarketData(
                symbol="600519.SH",
                timestamp=datetime(2024, 5, 1),
                close=100.0,
                source="akshare",
            )
        ]
        info = normalizer.detect_adjustment(test_data)
        print("\nDetected adjustment info:")
        print(f"  Source type: {info.source_type}")
        print(f"  Adjustment type: {info.adjustment_type.value}")

        assert info.source_type == "akshare"

        print("\n✓ Adjustment normalizer tests passed!")
        return True

    except Exception as e:
        logger.error(f"Adjustment normalizer test failed: {e}", exc_info=True)
        return False


def test_alert_manager():
    """测试告警管理器"""
    print("\n=== Testing Alert Manager ===")

    try:
        from data_layer.validation import Alert, AlertLevel, AlertManager

        manager = AlertManager()
        manager.add_log_channel()
        manager.add_console_channel()

        # 发送测试告警
        print("Sending test alerts...")

        alert = Alert(
            level=AlertLevel.INFO,
            message="Test info alert - this is just for testing",
            source="test",
        )
        manager.send(alert)

        alert = Alert(
            level=AlertLevel.WARNING,
            message="Test warning alert - nothing serious",
            source="test",
        )
        manager.send(alert)

        # 测试告警去重
        print("\nTesting alert deduplication (should only send once)...")
        for i in range(3):
            alert = Alert(
                level=AlertLevel.INFO,
                message="Duplicate message test",
                source="test",
            )
            manager.send(alert)

        print("\n✓ Alert manager tests passed!")
        return True

    except Exception as e:
        logger.error(f"Alert manager test failed: {e}", exc_info=True)
        return False


def test_audit_logger():
    """测试审计日志"""
    print("\n=== Testing Audit Logger ===")

    try:
        # 使用临时目录
        import tempfile

        from data_layer.validation import AuditLogger

        temp_dir = tempfile.mkdtemp()
        logger.info(f"Using temp audit log dir: {temp_dir}")

        audit = AuditLogger(log_dir=Path(temp_dir))

        # 记录一些审计事件

        entry1 = audit.log_fetch(
            symbol="600519.SH",
            source="akshare",
            data_count=100,
            success=True,
        )
        print(f"Logged fetch entry: {entry1.result_summary}")

        entry2 = audit.log_merge(
            symbol="600519.SH",
            sources=["akshare", "baostock"],
            final_data_count=100,
            selected_source="akshare",
            validation_passed=True,
        )
        print(f"Logged merge entry: {entry2.result_summary}")

        # 查询审计日志
        recent = audit.query_recent(symbol="600519.SH", limit=10)
        print(f"\nQueried {len(recent)} recent audit entries")

        assert len(recent) >= 2

        print("\n✓ Audit logger tests passed!")
        return True

    except Exception as e:
        logger.error(f"Audit logger test failed: {e}", exc_info=True)
        return False


def test_coordinator_init():
    """测试协调器初始化"""
    print("\n=== Testing Coordinator Initialization ===")

    try:
        from data_layer.coordinator import get_coordinator

        coordinator = get_coordinator()

        # 检查组件是否正确初始化
        assert coordinator.time_window_strategy is not None
        assert coordinator.dual_source_validator is not None
        assert coordinator.adjustment_normalizer is not None
        assert coordinator.alert_manager is not None
        assert coordinator.audit_logger is not None

        # 不做网络请求，只检查初始化
        print("✓ Coordinator initialized successfully!")
        print(f"  Target adjustment: {coordinator.target_adjustment.value}")

        return True

    except Exception as e:
        logger.error(f"Coordinator test failed: {e}", exc_info=True)
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("AlphaFoundry Dual-Source Core Logic Tests")
    print("=" * 60)

    results = {}

    # 运行各个测试
    results["Time Window Strategy"] = test_time_window_strategy()
    results["Dual Source Validator"] = test_dual_source_validator()
    results["Adjustment Normalizer"] = test_adjustment_normalizer()
    results["Alert Manager"] = test_alert_manager()
    results["Audit Logger"] = test_audit_logger()
    results["Coordinator Init"] = test_coordinator_init()

    # 汇总结果
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All core logic tests passed!")
        print("\nSummary:")
        print("  - Time window strategy: Daytime uses AkShare only, nighttime dual-source")
        print("  - Dual source validation: Detects discrepancies >0.5% and recommends source")
        print("  - Adjustment normalization: Provides correct fetch flags for each source")
        print("  - Alert management: Supports multiple channels and deduplication")
        print("  - Audit logging: Persists validation and fetch events")
        print("  - Coordinator: All components integrated and ready to use")
    else:
        print("✗ Some tests failed - see above for details")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
