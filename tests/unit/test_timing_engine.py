"""Unit tests for the new unified timing engine and event study implementation"""
import pytest

from core.contracts.timing_engine import EventStudyMetrics, ReadinessScore, TimingFactors


class TestTimingFactors:
    """Tests for TimingFactors model"""

    def test_overall_timing_fit_average(self):
        """Test that overall timing fit is the average of four factors"""
        factors = TimingFactors(regime=0.8, flow=0.8, theme_diffusion=0.8, crowding=0.8)
        assert factors.overall_timing_fit() == pytest.approx(0.8)

    def test_overall_timing_fit_mixed(self):
        """Test average calculation with mixed values"""
        factors = TimingFactors(regime=1.0, flow=0.0, theme_diffusion=0.5, crowding=0.5)
        assert factors.overall_timing_fit() == pytest.approx(0.5)


class TestEventStudyMetrics:
    """Tests for EventStudyMetrics model"""

    def test_historical_edge_zero_with_no_events(self):
        """Edge score should be zero when there are no historical events"""
        metrics = EventStudyMetrics(
            event_count=0, average_excess_return=0.1, win_rate=0.5, max_drawdown_after_entry=-0.05
        )
        assert metrics.historical_edge_score() == 0.0

    def test_historical_edge_high_with_good_performance(self):
        """High edge score when win rate and excess return are good"""
        metrics = EventStudyMetrics(
            event_count=10, average_excess_return=0.1, win_rate=0.8, max_drawdown_after_entry=-0.05
        )
        # 0.5 * 0.8 + 0.5 * (0.1 / 0.1) = 0.4 + 0.5 = 0.9
        assert metrics.historical_edge_score() == pytest.approx(0.9)

    def test_historical_edge_mixed(self):
        """Test mixed case: good win rate but low excess return"""
        metrics = EventStudyMetrics(
            event_count=20, average_excess_return=0.05, win_rate=0.7, max_drawdown_after_entry=-0.1
        )
        # 0.5*0.7 + 0.5*(0.05/0.1) = 0.35 + 0.25 = 0.6
        assert metrics.historical_edge_score() == pytest.approx(0.6)


class TestReadinessScore:
    """Tests for ReadinessScore calculation"""

    def test_calculate_correct_formula(self):
        """Test that the formula is applied correctly: 0.35 thesis + 0.35 historical + 0.30 timing"""
        readiness = ReadinessScore.calculate(
            thesis_quality=1.0, historical_edge=1.0, timing_fit=1.0
        )
        assert readiness.overall_score == pytest.approx(1.0)
        assert readiness.recommendation == "PROCEED"

    def test_calculate_block_low_score(self):
        """Score below 0.5 should recommend BLOCK"""
        readiness = ReadinessScore.calculate(
            thesis_quality=0.4, historical_edge=0.4, timing_fit=0.4
        )
        # 0.35*0.4 + 0.35*0.4 + 0.3*0.4 = 0.4
        assert readiness.overall_score == pytest.approx(0.4)
        assert readiness.recommendation == "BLOCK"

    def test_calculate_caution_middle_score(self):
        """Score 0.5 to 0.7 should give CAUTION"""
        readiness = ReadinessScore.calculate(
            thesis_quality=0.6, historical_edge=0.6, timing_fit=0.6
        )
        assert readiness.overall_score == pytest.approx(0.6)
        assert readiness.recommendation == "CAUTION"

    def test_should_block(self):
        """Test should_block() method works correctly"""
        block_readiness = ReadinessScore.calculate(
            thesis_quality=0.3, historical_edge=0.3, timing_fit=0.3
        )
        assert block_readiness.should_block() is True

        proceed_readiness = ReadinessScore.calculate(
            thesis_quality=0.8, historical_edge=0.8, timing_fit=0.8
        )
        assert proceed_readiness.should_block() is False

    def test_get_blocking_reason(self):
        """Test blocking reason generation"""
        readiness = ReadinessScore.calculate(
            thesis_quality=0.3, historical_edge=0.2, timing_fit=0.2
        )
        reason = readiness.get_blocking_reason()
        assert reason is not None
        assert "Thesis quality" in reason
        assert "Historical edge" in reason
        assert "market timing" in reason

    def test_get_blocking_reason_none_when_not_blocked(self):
        """No reason when not blocked"""
        readiness = ReadinessScore.calculate(
            thesis_quality=0.8, historical_edge=0.8, timing_fit=0.8
        )
        assert readiness.get_blocking_reason() is None

    def test_get_blocking_reason_only_overall_score(self):
        """Reason mentions overall score when no specific dimension is too low"""
        readiness = ReadinessScore.calculate(
            thesis_quality=0.5, historical_edge=0.5, timing_fit=0.4
        )
        # 0.35*0.5 + 0.35*0.5 + 0.3*0.4 = 0.35 + 0.12 = 0.47 (BLOCK)
        reason = readiness.get_blocking_reason()
        assert reason is not None
        assert "Overall readiness score" in reason


class TestTimingEngineIntegration:
    """Integration tests for full timing engine workflow"""

    def test_full_workflow_proceed(self):
        """Full happy path: all good → PROCEED, no blocking"""
        timing = TimingFactors(regime=0.8, flow=0.8, theme_diffusion=0.8, crowding=0.8)
        historical = EventStudyMetrics(
            event_count=15, average_excess_return=0.08, win_rate=0.7, max_drawdown_after_entry=-0.07
        )
        readiness = ReadinessScore.calculate(
            thesis_quality=0.8,
            historical_edge=historical.historical_edge_score(),
            timing_fit=timing.overall_timing_fit(),
        )

        assert readiness.overall_score > 0.7
        assert readiness.recommendation == "PROCEED"
        assert not readiness.should_block()

    def test_full_workflow_block(self):
        """Low readiness → BLOCK and reason should be given"""
        timing = TimingFactors(regime=0.2, flow=0.2, theme_diffusion=0.3, crowding=0.2)
        historical = EventStudyMetrics(
            event_count=3, average_excess_return=0.01, win_rate=0.3, max_drawdown_after_entry=-0.2
        )
        readiness = ReadinessScore.calculate(
            thesis_quality=0.4,
            historical_edge=historical.historical_edge_score(),
            timing_fit=timing.overall_timing_fit(),
        )

        assert readiness.overall_score < 0.5
        assert readiness.recommendation == "BLOCK"
        assert readiness.should_block()
        reason = readiness.get_blocking_reason()
        assert reason is not None
        assert "Thesis quality" in reason
        assert "Historical edge" in reason
        assert "market timing" in reason
