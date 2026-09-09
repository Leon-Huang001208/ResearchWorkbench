"""Production bindings for market-close and asset-alert durable jobs."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.contracts.platform_shared import ScheduledJob, ScheduledJobStatus
from data_layer.repositories.base import Base
from data_layer.repositories.market_home_repository import MarketHomeRepository
from data_layer.repositories.models import (
    AlertEventDB,
    AlertRuleDB,
    AssetIdentifierDB,
    AssetRegistryDB,
    MarketHomeSnapshotDB,
    NotificationDB,
    ScheduledJobDB,
    StockMasterDB,
    StockQuoteSnapshotDB,
)
from services.asset_alert_scheduler import (
    AssetAlertSchedulerBindings,
    register_default_asset_alert_scheduler,
)
from services.market_home_invalidation import (
    CjpyAShareTradingCalendar,
    MarketHomeSchedulerBindings,
    register_default_market_home_scheduler,
)
from services.market_home_service import MarketHomeService
from services.scheduler_coordinator import DurableSchedulerRuntime

NOW = datetime(2026, 9, 1, 8, 0, 42, tzinfo=UTC)


class RecordingRuntime:
    def __init__(self) -> None:
        self.materializers: dict[str, object] = {}
        self.handlers: dict[str, object] = {}

    def register_materializer(self, name: str, callback) -> None:
        self.materializers[name] = callback

    def register_handler(self, job_type: str, callback) -> None:
        self.handlers[job_type] = callback


def test_default_domain_bindings_register_on_one_runtime_before_start() -> None:
    runtime = RecordingRuntime()

    register_default_market_home_scheduler(runtime)
    register_default_asset_alert_scheduler(runtime)

    assert set(runtime.materializers) == {"market-home-close", "asset-alert-evaluation"}
    assert set(runtime.handlers) == {
        "market_home.close_snapshot",
        "asset_alert.evaluate",
    }


def _session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)


def _job(job_type: str, payload: dict[str, str]) -> ScheduledJob:
    return ScheduledJob(
        job_id=f"job-{job_type}",
        owner=job_type,
        job_type=job_type,
        idempotency_key=f"key-{job_type}",
        status=ScheduledJobStatus.IDLE,
        scheduled_for=NOW,
        payload=payload,
    )


def test_market_materializer_is_workday_idempotent_and_handler_writes_five_rows() -> None:
    engine, factory = _session_factory()
    local_close = datetime(2026, 9, 1, 16, 0, tzinfo=MarketHomeService.SHANGHAI_TZ)
    bindings = MarketHomeSchedulerBindings(
        factory,
        is_trading_day=lambda day: day == date(2026, 9, 1),
        service_factory=lambda db, _now: MarketHomeService(
            MarketHomeRepository(db),
            now_provider=lambda: local_close,
        ),
    )
    try:
        first = bindings.materialize(NOW)
        second = bindings.materialize(NOW + timedelta(seconds=10))
        weekend = bindings.materialize(datetime(2026, 9, 5, 8, tzinfo=UTC))

        assert first is not None
        assert second is not None
        assert first.job_id == second.job_id
        assert first.scheduled_for == datetime(2026, 9, 1, 7, 5, tzinfo=UTC)
        assert weekend is None

        snapshots = bindings.handle(first)
        bindings.handle(first)
        with Session(engine) as verification:
            assert verification.query(ScheduledJobDB).count() == 1
            assert verification.query(MarketHomeSnapshotDB).count() == 5
        assert len(snapshots) == 5
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_market_materializer_fails_closed_without_calendar_and_skips_weekday_holiday() -> None:
    engine, factory = _session_factory()
    try:
        unavailable = MarketHomeSchedulerBindings(factory)
        holiday = MarketHomeSchedulerBindings(factory, is_trading_day=lambda _day: False)

        assert unavailable.materialize(NOW) is None
        assert holiday.materialize(NOW) is None
        with factory() as verification:
            assert verification.query(ScheduledJobDB).count() == 0
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_cjpy_calendar_uses_exact_authoritative_day_and_fails_closed() -> None:
    class Adapter:
        def __init__(self, result=None, failure: Exception | None = None) -> None:
            self.result = result
            self.failure = failure

        def fetch_trading_days(self, start: str, end: str, **_kwargs):
            if self.failure is not None:
                raise self.failure
            return self.result

    trading_day = date(2026, 10, 9)

    assert (
        CjpyAShareTradingCalendar(lambda: Adapter(["20261009"])).is_trading_day(trading_day) is True
    )
    assert CjpyAShareTradingCalendar(lambda: Adapter([])).is_trading_day(trading_day) is False
    assert (
        CjpyAShareTradingCalendar(
            lambda: Adapter(failure=RuntimeError("calendar unavailable"))
        ).is_trading_day(trading_day)
        is None
    )


def test_alert_materializer_enqueues_all_profiles_once_per_minute() -> None:
    engine, factory = _session_factory()
    try:
        with factory() as db:
            db.add(
                AssetRegistryDB(
                    asset_id="asset-1",
                    asset_type="stock",
                    canonical_name="Asset",
                    updated_at=NOW,
                )
            )
            for rule_id, profile_id, status in (
                ("rule-a", "profile-a", "active"),
                ("rule-a-duplicate", "profile-a", "active"),
                ("rule-b", "profile-b", "active"),
                ("rule-draft", "profile-draft", "draft"),
            ):
                db.add(
                    AlertRuleDB(
                        rule_id=rule_id,
                        asset_id="asset-1",
                        metric_type="price",
                        metric_key="last",
                        operator="gt",
                        threshold=100,
                        unit="CNY/share",
                        required_freshness="fresh",
                        cooldown_seconds=0,
                        status=status,
                        state={"condition_true": False, "profile_id": profile_id},
                        created_at=NOW,
                        updated_at=NOW,
                    )
                )
            db.commit()

        bindings = AssetAlertSchedulerBindings(factory, capacity_per_minute=240)
        first = bindings.materialize(NOW)
        duplicate = bindings.materialize(NOW + timedelta(seconds=15))
        next_bucket = bindings.materialize(NOW + timedelta(minutes=1))

        assert [job.payload["profile_id"] for job in first] == ["profile-a", "profile-b"]
        assert [job.job_id for job in duplicate] == [job.job_id for job in first]
        assert len(next_bucket) == 2
        with factory() as verification:
            assert verification.query(ScheduledJobDB).count() == 4
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_alert_handler_commits_triggered_event_and_notification() -> None:
    engine, factory = _session_factory()
    try:
        with factory() as db:
            db.add_all(
                [
                    AssetRegistryDB(
                        asset_id="asset-stock",
                        asset_type="stock",
                        canonical_name="Stock",
                        updated_at=NOW,
                    ),
                    AssetIdentifierDB(
                        identifier_id="asset-stock-wind",
                        asset_id="asset-stock",
                        scheme="wind",
                        value="000001.SZ",
                        market="CN",
                        valid_from=NOW - timedelta(days=1),
                    ),
                    StockMasterDB(
                        symbol="000001.SZ",
                        raw_code="000001",
                        name="Stock",
                        market="CN",
                        source="wind",
                        updated_at=NOW,
                        created_at=NOW,
                    ),
                    StockQuoteSnapshotDB(
                        symbol="000001.SZ",
                        quote_time=NOW,
                        last_price=150,
                        source="wind",
                        created_at=NOW,
                    ),
                    AlertRuleDB(
                        rule_id="rule-trigger",
                        asset_id="asset-stock",
                        metric_type="price",
                        metric_key="last",
                        operator="gt",
                        threshold=100,
                        unit="CNY/share",
                        required_freshness="fresh",
                        cooldown_seconds=0,
                        status="active",
                        state={"condition_true": False, "profile_id": "profile-a"},
                        created_at=NOW,
                        updated_at=NOW,
                    ),
                ]
            )
            db.commit()

        result = AssetAlertSchedulerBindings(factory).handle(
            _job(
                "asset_alert.evaluate",
                {"profile_id": "profile-a", "evaluated_at": NOW.isoformat()},
            )
        )

        assert result.triggered == 1
        with factory() as verification:
            assert verification.query(AlertEventDB).count() == 1
            assert verification.query(NotificationDB).count() == 1
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_alert_handler_rolls_back_and_closes_session_on_failure() -> None:
    calls: list[str] = []

    class FakeSession:
        def commit(self) -> None:
            calls.append("commit")

        def rollback(self) -> None:
            calls.append("rollback")

        def close(self) -> None:
            calls.append("close")

    class FailingService:
        def evaluate_due_alerts(self, _profile_id: str, _evaluated_at: datetime):
            raise RuntimeError("evaluation failed")

    bindings = AssetAlertSchedulerBindings(
        FakeSession,
        service_factory=lambda _db: FailingService(),
    )

    with pytest.raises(RuntimeError, match="evaluation failed"):
        bindings.handle(
            _job(
                "asset_alert.evaluate",
                {"profile_id": "profile-a", "evaluated_at": NOW.isoformat()},
            )
        )

    assert calls == ["rollback", "close"]


def test_shared_runtime_default_poll_keeps_alert_latency_within_sixty_seconds() -> None:
    runtime = DurableSchedulerRuntime(session_factory=lambda: None)

    assert runtime.poll_seconds <= 60
    assert runtime.jobs_per_minute_capacity_for(max_execution_seconds=1.0) == 60
    assert runtime.jobs_per_minute_capacity_for(max_execution_seconds=10.0) == 6


def test_alert_handler_execution_budget_breach_latches_fail_closed_readiness() -> None:
    calls: list[str] = []

    class FakeSession:
        def commit(self) -> None:
            calls.append("commit")

        def rollback(self) -> None:
            calls.append("rollback")

        def close(self) -> None:
            calls.append("close")

    class SlowService:
        def evaluate_due_alerts(self, _profile_id: str, _evaluated_at: datetime):
            time.sleep(0.02)

    bindings = AssetAlertSchedulerBindings(
        FakeSession,
        service_factory=lambda _db: SlowService(),
        capacity_per_minute=1,
        max_execution_seconds=0.005,
    )

    bindings.handle(
        _job(
            "asset_alert.evaluate",
            {"profile_id": "slow-profile", "evaluated_at": NOW.isoformat()},
        )
    )

    assert calls == ["commit", "close"]
    assert bindings.is_ready is False
    assert bindings.last_health is not None
    assert bindings.last_health.status == "degraded_execution_budget"
    assert bindings.last_health.last_execution_seconds > 0.005
    assert bindings.materialize(NOW + timedelta(minutes=1)) == []
    assert bindings.last_health.status == "blocked_execution_budget"


def test_alert_materializer_blocks_unserviceable_minute_and_reports_capacity() -> None:
    engine, factory = _session_factory()
    try:
        with factory() as db:
            db.add(
                AssetRegistryDB(
                    asset_id="capacity-asset",
                    asset_type="stock",
                    canonical_name="Capacity Asset",
                    updated_at=NOW,
                )
            )
            for index in range(5):
                db.add(
                    AlertRuleDB(
                        rule_id=f"capacity-rule-{index}",
                        asset_id="capacity-asset",
                        metric_type="price",
                        metric_key="last",
                        operator="gt",
                        threshold=100,
                        unit="CNY/share",
                        required_freshness="fresh",
                        cooldown_seconds=0,
                        status="active",
                        state={"condition_true": False, "profile_id": f"profile-{index}"},
                        created_at=NOW,
                        updated_at=NOW,
                    )
                )
            db.commit()

        bindings = AssetAlertSchedulerBindings(factory, capacity_per_minute=4)

        assert bindings.materialize(NOW) == []
        assert bindings.last_health is not None
        assert bindings.last_health.status == "blocked_capacity"
        assert bindings.last_health.active_profiles == 5
        assert bindings.last_health.jobs_per_minute_capacity == 4
        with factory() as verification:
            assert verification.query(ScheduledJobDB).count() == 0
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_alert_backlog_drains_in_deterministic_batches_within_one_minute(tmp_path) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'alert-backlog.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    minute_start = NOW.replace(second=0, microsecond=0)
    evaluated: list[str] = []

    class Service:
        def evaluate_due_alerts(self, profile_id: str, _evaluated_at: datetime):
            time.sleep(0.01)
            evaluated.append(profile_id)

    try:
        with factory() as db:
            db.add(
                AssetRegistryDB(
                    asset_id="backlog-asset",
                    asset_type="stock",
                    canonical_name="Backlog Asset",
                    updated_at=NOW,
                )
            )
            for index in range(3):
                db.add(
                    AlertRuleDB(
                        rule_id=f"backlog-rule-{index}",
                        asset_id="backlog-asset",
                        metric_type="price",
                        metric_key="last",
                        operator="gt",
                        threshold=100,
                        unit="CNY/share",
                        required_freshness="fresh",
                        cooldown_seconds=0,
                        status="active",
                        state={"condition_true": False, "profile_id": f"profile-{index}"},
                        created_at=NOW,
                        updated_at=NOW,
                    )
                )
            db.commit()

        current = [minute_start]
        runtime = DurableSchedulerRuntime(
            session_factory=factory,
            worker_id="alert-capacity",
            poll_seconds=30,
            batch_limit=2,
            clock=lambda: current[0],
        )
        bindings = AssetAlertSchedulerBindings(
            factory,
            service_factory=lambda _db: Service(),
            max_execution_seconds=0.05,
        )
        bindings.register(runtime)

        first = runtime.tick(now=current[0])
        current[0] += timedelta(seconds=30)
        second = runtime.tick(now=current[0])

        assert len(first) == 2
        assert len(second) == 1
        assert sorted(evaluated) == ["profile-0", "profile-1", "profile-2"]
        assert bindings.last_health is not None
        assert bindings.last_health.status == "ready"
        assert bindings.last_health.jobs_per_minute_capacity == 4
        assert bindings.is_ready is True
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_shared_runtime_does_not_forget_a_thread_that_missed_shutdown_deadline() -> None:
    class StuckThread:
        def join(self, timeout: float | None = None) -> None:
            return None

        def is_alive(self) -> bool:
            return True

    runtime = DurableSchedulerRuntime(session_factory=lambda: None)
    stuck = StuckThread()
    runtime._thread = stuck  # type: ignore[assignment]

    runtime.stop(timeout_seconds=0.01)

    assert runtime._thread is stuck


def test_one_runtime_tick_materializes_and_handles_market_and_alert_jobs(tmp_path) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'shared-runtime.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    local_close = datetime(2026, 9, 1, 16, 0, tzinfo=MarketHomeService.SHANGHAI_TZ)
    try:
        with factory() as db:
            db.add_all(
                [
                    AssetRegistryDB(
                        asset_id="runtime-stock",
                        asset_type="stock",
                        canonical_name="Runtime Stock",
                        updated_at=NOW,
                    ),
                    AssetIdentifierDB(
                        identifier_id="runtime-stock-wind",
                        asset_id="runtime-stock",
                        scheme="wind",
                        value="000002.SZ",
                        market="CN",
                        valid_from=NOW - timedelta(days=1),
                    ),
                    StockMasterDB(
                        symbol="000002.SZ",
                        raw_code="000002",
                        name="Runtime Stock",
                        market="CN",
                        source="wind",
                        updated_at=NOW.replace(second=0),
                        created_at=NOW.replace(second=0),
                    ),
                    StockQuoteSnapshotDB(
                        symbol="000002.SZ",
                        quote_time=NOW.replace(second=0),
                        last_price=150,
                        source="wind",
                        created_at=NOW.replace(second=0),
                    ),
                    AlertRuleDB(
                        rule_id="runtime-rule",
                        asset_id="runtime-stock",
                        metric_type="price",
                        metric_key="last",
                        operator="gt",
                        threshold=100,
                        unit="CNY/share",
                        required_freshness="fresh",
                        cooldown_seconds=0,
                        status="active",
                        state={"condition_true": False, "profile_id": "runtime-profile"},
                        created_at=NOW,
                        updated_at=NOW,
                    ),
                ]
            )
            db.commit()

        runtime = DurableSchedulerRuntime(
            session_factory=factory,
            worker_id="one-runtime",
            clock=lambda: NOW,
        )
        market = MarketHomeSchedulerBindings(
            factory,
            is_trading_day=lambda _day: True,
            service_factory=lambda db, _now: MarketHomeService(
                MarketHomeRepository(db),
                now_provider=lambda: local_close,
            ),
        )
        alerts = AssetAlertSchedulerBindings(factory)
        market.register(runtime)
        alerts.register(runtime)

        completed = runtime.tick(now=NOW)

        assert {job.job_type for job in completed} == {
            "market_home.close_snapshot",
            "asset_alert.evaluate",
        }
        with factory() as verification:
            assert verification.query(MarketHomeSnapshotDB).count() == 5
            assert verification.query(NotificationDB).count() == 1
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_api_registers_all_domains_before_starting_single_runtime(monkeypatch) -> None:
    from app.api import main
    from services import (
        agent_schedule_runtime,
        asset_alert_scheduler,
        market_home_invalidation,
        scheduler_coordinator,
    )

    calls: list[str] = []

    class Runtime:
        def start(self) -> None:
            calls.append("start")

        def stop(self) -> None:
            calls.append("stop")

    runtime = Runtime()
    monkeypatch.setattr(main, "_durable_scheduler_runtime", None)
    monkeypatch.setattr(
        scheduler_coordinator,
        "get_default_scheduler_runtime",
        lambda: calls.append("get") or runtime,
    )
    monkeypatch.setattr(
        market_home_invalidation,
        "register_default_market_home_scheduler",
        lambda received: calls.append("market") or received,
    )
    monkeypatch.setattr(
        asset_alert_scheduler,
        "register_default_asset_alert_scheduler",
        lambda received: calls.append("alert") or received,
    )
    monkeypatch.setattr(
        agent_schedule_runtime,
        "register_default_agent_schedule_runtime",
        lambda received: calls.append("agent") or received,
    )

    main._start_durable_scheduler_runtime()
    main._start_durable_scheduler_runtime()
    main._stop_durable_scheduler_runtime()

    assert calls == ["get", "market", "alert", "agent", "start", "start", "stop"]


def test_api_registration_failure_does_not_cache_an_incomplete_runtime(monkeypatch) -> None:
    from app.api import main
    from services import (
        agent_schedule_runtime,
        asset_alert_scheduler,
        market_home_invalidation,
        scheduler_coordinator,
    )

    calls: list[str] = []

    class Runtime:
        def start(self) -> None:
            calls.append("start")

    runtime = Runtime()
    attempts = iter([RuntimeError("alert registration failed"), None])
    monkeypatch.setattr(main, "_durable_scheduler_runtime", None)
    monkeypatch.setattr(
        scheduler_coordinator,
        "get_default_scheduler_runtime",
        lambda: runtime,
    )
    monkeypatch.setattr(
        market_home_invalidation,
        "register_default_market_home_scheduler",
        lambda received: calls.append("market") or received,
    )

    def register_alert(received):
        calls.append("alert")
        failure = next(attempts)
        if failure is not None:
            raise failure
        return received

    monkeypatch.setattr(
        asset_alert_scheduler,
        "register_default_asset_alert_scheduler",
        register_alert,
    )
    monkeypatch.setattr(
        agent_schedule_runtime,
        "register_default_agent_schedule_runtime",
        lambda received: calls.append("agent") or received,
    )

    with pytest.raises(RuntimeError, match="alert registration failed"):
        main._start_durable_scheduler_runtime()
    assert main._durable_scheduler_runtime is None

    main._start_durable_scheduler_runtime()

    assert calls == ["market", "alert", "market", "alert", "agent", "start"]
