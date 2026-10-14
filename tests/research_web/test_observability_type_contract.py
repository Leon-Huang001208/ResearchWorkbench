"""Shared structured logging must accept the tracer and metric event fields."""

import logging

from core.observability.metrics import MetricsCollector
from core.observability.tracer import Tracer


def test_tracer_events_work_with_debug_logging_enabled(caplog):
    with caplog.at_level(logging.DEBUG):
        tracer = Tracer()
        identifier = tracer.start_span("type-contract")
        tracer.end_span(identifier)
    span = tracer.get_span(identifier)
    assert span is not None and span.end_time is not None and span.status == "ok"


def test_metric_events_work_with_debug_logging_enabled(caplog):
    collector = MetricsCollector()
    before = collector.get_counter("type-contract-count")
    with caplog.at_level(logging.DEBUG):
        collector.increment("type-contract-count", tags={"kind": "synthetic"})
        collector.record("type-contract-value", 2.5, tags={"kind": "synthetic"})
    assert collector.get_counter("type-contract-count") == before + 1
    assert collector.get_histogram_stats("type-contract-value")["max"] == 2.5


def test_span_and_metric_timestamps_preserve_naive_utc_contract():
    from datetime import UTC, datetime

    from core.observability.metrics import Metric

    before = datetime.now(UTC).replace(tzinfo=None)
    tracer = Tracer()
    identifier = tracer.start_span("naive-utc-contract")
    tracer.end_span(identifier)
    metric = Metric("naive-utc-contract", 1)
    after = datetime.now(UTC).replace(tzinfo=None)
    span = tracer.get_span(identifier)
    assert span.start_time.tzinfo is None and span.end_time.tzinfo is None
    assert metric.timestamp.tzinfo is None
    assert before <= span.start_time <= span.end_time <= after
    assert before <= metric.timestamp <= after


def test_fallback_explicit_no_traceback_keeps_synthetic_secret_out_of_logs(caplog):
    from core.observability.logger import _SimpleLoggerWrapper

    fallback = _SimpleLoggerWrapper(logging.getLogger("synthetic-private-fallback"))
    with caplog.at_level(logging.ERROR):
        try:
            raise RuntimeError("synthetic-credential-must-not-be-logged")
        except RuntimeError as error:
            fallback.exception(
                "private_operation_failed", error_type=type(error).__name__, exc_info=False
            )
    event = next(record for record in caplog.records if record.name == "synthetic-private-fallback")
    assert event.exc_info is False
    assert "private_operation_failed" in event.getMessage()
    assert "RuntimeError" in event.getMessage()
    assert "synthetic-credential-must-not-be-logged" not in caplog.text


def test_fallback_exception_preserves_default_traceback_semantics(caplog):
    from core.observability.logger import _SimpleLoggerWrapper

    fallback = _SimpleLoggerWrapper(logging.getLogger("synthetic-default-traceback"))
    with caplog.at_level(logging.ERROR):
        try:
            raise ValueError("synthetic-default-error")
        except ValueError:
            fallback.exception("default_traceback_preserved")
    event = next(
        record for record in caplog.records if record.name == "synthetic-default-traceback"
    )
    assert event.exc_info is not None and event.exc_info[0] is ValueError
