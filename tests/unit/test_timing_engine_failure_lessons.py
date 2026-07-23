"""MetaTimingEngine 失败教训应用测试"""

from memory_learning.contracts import FailureMemory
from timing_engine.meta import MetaTimingEngine


def test_apply_failure_lessons_increases_crowding_weight_for_crowding_error():
    """测试对于 crowding_error 增加 crowding 权重"""
    engine = MetaTimingEngine()
    failure = FailureMemory(
        failure_id="test-failure-001",
        source_id="test-signal-001",
        failure_type="crowding_error",
        root_cause="Too crowded",
        corrective_action="Avoid crowded trades",
    )

    adjusted_weights = engine.apply_failure_lessons([failure])
    # Original crowding weight is 0.08, should be increased by 50% to 0.12 (then normalized)
    # Total original base weights sum to 1.0, after increase: 0.08 * 1.5 = 0.12, so total sum is 1.04
    # Normalized crowding weight should be 0.12 / 1.04 ≈ 0.1154
    assert adjusted_weights["crowding"] > MetaTimingEngine.BASE_WEIGHTS["crowding"]


def test_apply_failure_lessons_reduces_regime_weight_for_timing_error():
    """测试对于 timing_error 降低 regime 权重"""
    engine = MetaTimingEngine()
    failure = FailureMemory(
        failure_id="test-failure-002",
        source_id="test-signal-002",
        failure_type="timing_error",
        root_cause="Bad timing",
        corrective_action="Adjust timing model",
    )

    adjusted_weights = engine.apply_failure_lessons([failure])
    # Original regime weight is 0.2, should be reduced by 20% to 0.16 (then normalized)
    # Total original base weights sum to 1.0, after reduction: 0.2 * 0.8 = 0.16, so total sum is 0.96
    # Normalized regime weight should be 0.16 / 0.96 ≈ 0.1667
    assert adjusted_weights["regime"] < MetaTimingEngine.BASE_WEIGHTS["regime"]


def test_apply_failure_lessons_does_nothing_when_no_failures():
    """测试当没有失败记忆时，返回基础权重（归一化后）"""
    engine = MetaTimingEngine()
    adjusted_weights = engine.apply_failure_lessons([])
    # Should return normalized base weights, which are the same as base weights (since they already sum to 1)
    assert adjusted_weights == engine.weights_for_regime("unknown")
