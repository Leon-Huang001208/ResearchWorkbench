"""Regression tests for observability primitives."""

import logging

from core.observability.metrics import MetricsCollector
from core.observability.tracer import Tracer


def test_metrics_collector_emits_structured_debug_context(caplog):
    """Metric logs retain names, values, and tags through stdlib logging."""
    collector = MetricsCollector()

    with caplog.at_level(logging.DEBUG):
        collector.increment("signals_created", tags={"status": "approved"})
        collector.record("backtest_duration", 1.25, tags={"strategy": "test"})

    records = [record for record in caplog.records if record.name.endswith("metrics")]
    assert records[0].metric_name == "signals_created"
    assert records[0].value == 1
    assert records[0].tags == {"status": "approved"}
    assert records[1].metric_name == "backtest_duration"
    assert records[1].value == 1.25
    assert records[1].tags == {"strategy": "test"}


def test_tracer_emits_structured_debug_context(caplog):
    """Span logs retain the trace identifiers when using stdlib logging."""
    tracer = Tracer()

    with caplog.at_level(logging.DEBUG):
        span_id = tracer.start_span("report_generation", trace_id="trace-1")
        tracer.end_span(span_id)

    records = [record for record in caplog.records if record.name.endswith("tracer")]
    assert records[0].span_name == "report_generation"
    assert records[0].trace_id == "trace-1"
    assert records[0].span_id == span_id
    assert records[1].span_name == "report_generation"
    assert records[1].trace_id == "trace-1"
    assert records[1].span_id == span_id
    assert records[1].duration is not None
