"""
Unit tests for rebuild derived state functionality
"""

from scripts.rebuild_derived_state import (
    RebuildReporter,
)


def test_reporter_initialization():
    """Test that reporter initializes with correct empty stats."""
    reporter = RebuildReporter()
    
    assert reporter.stats["phases_executed"] == 0
    assert reporter.stats["total_events_processed"] == 0
    assert reporter.stats["signals_rebuilt"] == 0
    assert reporter.stats["signals_skipped"] == 0
    assert reporter.stats["signals_failed"] == 0
    assert reporter.stats["timing_decisions_recomputed"] == 0
    assert reporter.stats["outcomes_rebuilt"] == 0
    assert all(v == 0 for v in reporter.stats.values())
    
    assert all(len(v) == 0 for v in reporter.details.values())


def test_reporter_add_signal_results():
    """Test reporter correctly collects signal rebuild stats."""
    reporter = RebuildReporter()
    
    reporter.add_signal_result("event1", rebuilt=True)
    reporter.add_signal_result("event2", rebuilt=False)
    reporter.add_signal_result("event3", rebuilt=False, failed=True, reason="Test failure")
    
    assert reporter.stats["signals_rebuilt"] == 1
    assert reporter.stats["signals_skipped"] == 1
    assert reporter.stats["signals_failed"] == 1
    assert len(reporter.details["failed_signals"]) == 1
    assert reporter.details["failed_signals"][0]["event_id"] == "event3"
    assert reporter.details["failed_signals"][0]["reason"] == "Test failure"


def test_reporter_add_timing_results():
    """Test reporter correctly collects timing recomputation stats."""
    reporter = RebuildReporter()
    
    reporter.add_timing_result("signal1", recomputed=True)
    reporter.add_timing_result("signal2", recomputed=False)
    reporter.add_timing_result("signal3", recomputed=False, failed=True, reason="Missing data")
    
    assert reporter.stats["timing_decisions_recomputed"] == 1
    assert reporter.stats["timing_decisions_skipped"] == 1
    assert reporter.stats["timing_decisions_failed"] == 1
    assert len(reporter.details["failed_timing_decisions"]) == 1


def test_reporter_add_outcome_results():
    """Test reporter correctly collects outcome rebuild stats."""
    reporter = RebuildReporter()
    
    reporter.add_outcome_result("signal1", rebuilt=True)
    reporter.add_outcome_result("signal2", rebuilt=False)
    reporter.add_outcome_result("signal3", rebuilt=False, missing_market=True, reason="No price data")
    
    assert reporter.stats["outcomes_rebuilt"] == 1
    assert reporter.stats["outcomes_skipped"] == 1
    assert reporter.stats["outcomes_missing_market_data"] == 1
    assert len(reporter.details["missing_market_data_outcomes"]) == 1
    assert len(reporter.details["manual_required"]) == 1
    assert reporter.details["manual_required"][0]["id"] == "signal3"


def test_reporter_add_phase_executed():
    """Test that adding phases increments count correctly."""
    reporter = RebuildReporter()
    
    assert reporter.stats["phases_executed"] == 0
    reporter.add_phase_executed()
    assert reporter.stats["phases_executed"] == 1
    reporter.add_phase_executed()
    assert reporter.stats["phases_executed"] == 2


def test_reporter_print_summary():
    """Test that reporter prints summary without errors."""
    reporter = RebuildReporter()
    
    # Add some test data
    reporter.add_phase_executed()
    reporter.add_signal_result("event1", rebuilt=True)
    reporter.add_signal_result("event2", rebuilt=False)
    reporter.add_outcome_result("signal3", rebuilt=False, missing_market=True, reason="No market data")
    
    # Should print without errors - this just confirms no exception is thrown
    reporter.print_summary()
