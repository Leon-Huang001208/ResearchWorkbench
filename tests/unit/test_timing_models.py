
"""Tests for timing models"""

from timing_engine import TimingContext, TimingModelRegistry
from timing_engine.models.regime_model import RegimeModel
from timing_engine.models.flow_model import FlowModel
from timing_engine.models.theme_diffusion_model import ThemeDiffusionModel
from timing_engine.models.sentiment_model import SentimentModel
from timing_engine.models.market_structure_model import MarketStructureModel
from timing_engine.models.liquidity_model import LiquidityModel
from timing_engine.models.crowding_model import CrowdingModel
from timing_engine.models.expectation_gap_model import ExpectationGapModel
from timing_engine.models.alpha_decay_model import AlphaDecayModel


def test_regime_model_score():
    """Test RegimeModel score method"""
    model = RegimeModel()
    context = TimingContext(signal_id="test-1", market_regime="ai_growth")
    score = model.score(context)
    assert score.model_name == "regime"
    assert 0 <= score.score <= 1
    assert 0 <= score.confidence <= 1


def test_flow_model_score():
    """Test FlowModel score method"""
    model = FlowModel()
    context = TimingContext(signal_id="test-1", flow_data={"net_inflow": 1000000000})
    score = model.score(context)
    assert score.model_name == "flow"
    assert 0 <= score.score <= 1
    assert 0 <= score.confidence <= 1


def test_theme_diffusion_model_score():
    """Test ThemeDiffusionModel score method"""
    model = ThemeDiffusionModel()
    context = TimingContext(signal_id="test-1", diffusion_data={"stage": 0})
    score = model.score(context)
    assert score.model_name == "theme_diffusion"
    assert 0 <= score.score <= 1
    assert 0 <= score.confidence <= 1


def test_sentiment_model_score():
    """Test SentimentModel score method"""
    model = SentimentModel()
    context = TimingContext(signal_id="test-1", sentiment_data={"consecutive_limit_up": 5, "limit_up_failure_rate": 0.1})
    score = model.score(context)
    assert score.model_name == "sentiment"
    assert 0 <= score.score <= 1
    assert 0 <= score.confidence <= 1


def test_market_structure_model_score():
    """Test MarketStructureModel score method"""
    model = MarketStructureModel()
    context = TimingContext(signal_id="test-1", price_data={"trend": "up", "breakout": True})
    score = model.score(context)
    assert score.model_name == "market_structure"
    assert 0 <= score.score <= 1
    assert 0 <= score.confidence <= 1


def test_liquidity_model_score():
    """Test LiquidityModel score method"""
    model = LiquidityModel()
    context = TimingContext(signal_id="test-1", macro_data={"interest_rate": 0.02, "m2_growth": 0.1})
    score = model.score(context)
    assert score.model_name == "liquidity"
    assert 0 <= score.score <= 1
    assert 0 <= score.confidence <= 1


def test_crowding_model_score():
    """Test CrowdingModel score method"""
    model = CrowdingModel()
    context = TimingContext(signal_id="test-1", sentiment_data={"search_hotness": 90})
    score = model.score(context)
    assert score.model_name == "crowding"
    assert 0 <= score.score <= 1
    assert 0 <= score.confidence <= 1


def test_expectation_gap_model_score():
    """Test ExpectationGapModel score method"""
    model = ExpectationGapModel()
    context = TimingContext(signal_id="test-1", agent_views=[{"contrarian": True}, {"contrarian": True}])
    score = model.score(context)
    assert score.model_name == "expectation_gap"
    assert 0 <= score.score <= 1
    assert 0 <= score.confidence <= 1


def test_alpha_decay_model_score():
    """Test AlphaDecayModel score method"""
    model = AlphaDecayModel()
    context = TimingContext(signal_id="test-1", event_signal={"hours_since_event": 12})
    score = model.score(context)
    assert score.model_name == "alpha_decay"
    assert 0 <= score.score <= 1
    assert 0 <= score.confidence <= 1


def test_registry_list_models():
    """Test TimingModelRegistry list_models method"""
    registry = TimingModelRegistry()
    models = registry.list_models()
    assert len(models) == 9
    assert "regime" in models
    assert "flow" in models
    assert "theme_diffusion" in models
    assert "sentiment" in models
    assert "market_structure" in models
    assert "liquidity" in models
    assert "crowding" in models
    assert "expectation_gap" in models
    assert "alpha_decay" in models


def test_registry_score_all():
    """Test TimingModelRegistry score_all method"""
    registry = TimingModelRegistry()
    context = TimingContext(signal_id="test-1")
    scores = registry.score_all(context)
    assert len(scores) == 9

