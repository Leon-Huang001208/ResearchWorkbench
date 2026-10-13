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


def test_fallback_explicit_no_traceback_keeps_synthetic_secret_out_of_logs(caplog, monkeypatch):
    from unittest.mock import MagicMock

    from core.observability.logger import _SimpleLoggerWrapper
    from data_layer.adapters.wind import wind_adapter
    from data_layer.adapters.wind.wind_adapter import WindAdapter

    fallback = _SimpleLoggerWrapper(logging.getLogger("synthetic-wind-fallback"))
    monkeypatch.setattr(wind_adapter, "logger", fallback)
    client = MagicMock()
    client.heartbeat.side_effect = RuntimeError("synthetic-credential-must-not-be-logged")
    with caplog.at_level(logging.ERROR):
        assert WindAdapter(client).is_available() is False
    event = next(record for record in caplog.records if record.name == "synthetic-wind-fallback")
    assert event.exc_info is False
    assert "wind_heartbeat_failed" in event.getMessage()
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
