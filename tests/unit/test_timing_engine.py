"""
Timing Engine 测试

Timing 负责判断市场现在会不会认可某个逻辑，不负责解释世界，也不负责历史统计验证。
"""
import pytest
from pydantic import ValidationError

from timing_engine import MetaTimingEngine, TimingModelScore


def test_timing_score_rejects_unknown_model_name():
    """择时模型必须来自统一 ontology"""
    with pytest.raises(ValidationError):
        TimingModelScore(
            model_name="llm_chat",
            score=0.8,
            confidence=0.7,
            rationale="自由聊天不是择时模型",
        )


def test_meta_timing_engine_allows_entry_when_market_clock_is_supportive():
    """多模型状态支持且拥挤度低时，应允许进入"""
    engine = MetaTimingEngine()
    decision = engine.evaluate(
        [
            TimingModelScore(model_name="regime", score=0.82, confidence=0.8, rationale="AI成长风格"),
            TimingModelScore(model_name="flow", score=0.76, confidence=0.7, rationale="资金流入AI链"),
            TimingModelScore(
                model_name="theme_diffusion",
                score=0.81,
                confidence=0.75,
                rationale="主题从光模块扩散到铜连接",
            ),
            TimingModelScore(model_name="crowding", score=0.24, confidence=0.7, rationale="拥挤度不高"),
            TimingModelScore(
                model_name="expectation_gap",
                score=0.78,
                confidence=0.72,
                rationale="推理需求预期差仍在",
            ),
        ],
        signal_id="event_sig_001",
    )

    assert decision.action == "enter"
    assert decision.readiness_score > 0.65
    assert decision.signal_id == "event_sig_001"
    assert "crowding" not in decision.blockers


def test_meta_timing_engine_blocks_when_crowding_and_risk_off_dominate():
    """高拥挤和风险 off 应阻止交易，即使叙事仍然好听"""
    engine = MetaTimingEngine()
    decision = engine.evaluate(
        [
            TimingModelScore(model_name="regime", score=0.22, confidence=0.85, rationale="风险off"),
            TimingModelScore(model_name="flow", score=0.31, confidence=0.74, rationale="资金流出成长"),
            TimingModelScore(
                model_name="theme_diffusion",
                score=0.66,
                confidence=0.72,
                rationale="市场仍讨论AI",
            ),
            TimingModelScore(model_name="crowding", score=0.91, confidence=0.82, rationale="龙头交易拥挤"),
            TimingModelScore(model_name="sentiment", score=0.28, confidence=0.8, rationale="炸板率升高"),
        ]
    )

    assert decision.action == "block"
    assert "crowding" in decision.blockers
    assert "regime" in decision.blockers


def test_meta_timing_engine_uses_hot_money_weights_for_speculation_regime():
    """游资题材阶段应更相信情绪和主题扩散"""
    engine = MetaTimingEngine()
    weights = engine.weights_for_regime("hot_money_theme")

    assert weights["sentiment"] > weights["liquidity"]
    assert weights["theme_diffusion"] > weights["expectation_gap"]


def test_meta_timing_engine_requires_at_least_one_score():
    """没有任何择时输入时应显式报错"""
    engine = MetaTimingEngine()

    with pytest.raises(ValueError, match="at least one"):
        engine.evaluate([])
