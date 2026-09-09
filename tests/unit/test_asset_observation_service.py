"""Behavior tests for the asset-observation and deterministic alert services."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine, insert, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from core.contracts.asset_observation import (
    AlertEventStatus,
    AlertOperator,
    AlertRule,
    AlertRuleStatus,
)
from core.contracts.platform_shared import (
    AssetRef,
    FreshnessStatus,
    ObservationEnvelope,
    SourceRef,
)

NOW = datetime(2026, 9, 1, 9, 30, tzinfo=UTC)
SOURCE = SourceRef(
    source_id="wind",
    name="Wind",
    tier="licensed",
    content_hash="sha256:asset-observation-test",
)


class FakeAssetRepository:
    """Small stateful repository double exposing domain-shaped records."""

    def __init__(self, asset_type: str = "stock") -> None:
        self.asset_type = asset_type
        self.identifiers = ["600519.SH"]
        self.watchlist_item = None

    def get_asset_projection(self, asset_id: str) -> dict[str, Any] | None:
        if asset_id == "missing":
            return None
        peer_dimensions = {
            "stock": {"industry_level3": "白酒"},
            "index": {"category": "broad_based"},
            "etf": {"tracking_index": "index-csi300"},
            "active_fund": {"fund_type": "混合型", "benchmark": "沪深300"},
        }
        return {
            "asset": AssetRef(
                asset_id=asset_id,
                asset_type=self.asset_type,
                display_name="示例资产",
            ),
            "identifiers": list(self.identifiers),
            "market_data": {"last": 101.0},
            "history": [{"as_of": NOW.isoformat(), "value": 100.0}],
            "events": [],
            "themes": ["消费"],
            "type_payload": peer_dimensions[self.asset_type],
            "as_of": NOW,
            "observed_at": NOW,
            "available_at": NOW,
            "source_refs": [SOURCE],
            "freshness_status": FreshnessStatus.FRESH,
            "quality_flags": [],
        }

    def list_peer_assets(
        self,
        *,
        asset_id: str,
        asset_type: str,
        dimension: str,
        value: str,
    ) -> list[AssetRef]:
        return [
            AssetRef(asset_id=asset_id, asset_type=asset_type, display_name="示例资产"),
            AssetRef(asset_id="peer-1", asset_type=asset_type, display_name=value),
        ]

    def add_watchlist_item(
        self,
        *,
        watchlist_id: str,
        asset_id: str,
        position: int,
        note: str | None,
    ) -> Any:
        if self.watchlist_item is None:
            self.watchlist_item = SimpleNamespace(
                item_id="item-1",
                watchlist_id=watchlist_id,
                asset_id=asset_id,
                position=position,
                note=note,
                created_at=NOW,
            )
        return self.watchlist_item


class FakeAlertRepository:
    """Persist alert state, events, and notifications for edge tests."""

    def __init__(self) -> None:
        self.rule = _rule()
        self.state: dict[str, Any] = {"profile_id": "local"}
        self.events: dict[str, Any] = {}
        self.notifications: dict[str, Any] = {}
        self.lock_calls = 0

    def lock_rule_state(self, rule_id: str) -> dict[str, Any]:
        self.lock_calls += 1
        return dict(self.state)

    def lock_alert_rule(self, rule_id: str) -> Any:
        self.lock_calls += 1
        return SimpleNamespace(
            **self.rule.model_dump(mode="python"),
            state=dict(self.state),
        )

    @staticmethod
    def to_alert_rule(row: Any) -> AlertRule:
        return AlertRule.model_validate(row, from_attributes=True)

    def get_rule_state(self, rule_id: str) -> dict[str, Any]:
        return dict(self.state)

    def update_rule_state(self, rule_id: str, state: dict[str, Any]) -> None:
        self.state = dict(state)

    def create_alert_event(self, **values: Any) -> Any:
        event = SimpleNamespace(**values)
        self.events[event.event_id] = event
        return event

    def create_notification(self, **values: Any) -> Any:
        notification = SimpleNamespace(**values)
        self.notifications[notification.notification_id] = notification
        return notification

    def resolve_alert_event(self, event_id: str, resolved_at: datetime) -> Any:
        event = self.events[event_id]
        event.status = AlertEventStatus.RESOLVED.value
        event.resolved_at = resolved_at
        return event


def _rule(**overrides: Any) -> AlertRule:
    payload: dict[str, Any] = {
        "rule_id": "rule-1",
        "asset_id": "asset-1",
        "metric_type": "price",
        "metric_key": "last",
        "operator": AlertOperator.GT,
        "threshold": 100.0,
        "unit": "CNY/share",
        "required_freshness": FreshnessStatus.FRESH,
        "cooldown_seconds": 300,
        "status": AlertRuleStatus.ACTIVE,
    }
    payload.update(overrides)
    return AlertRule(**payload)


def _observation(
    value: float,
    *,
    observation_id: str = "obs-1",
    freshness: FreshnessStatus = FreshnessStatus.FRESH,
    unit: str = "CNY/share",
    quality_flags: list[str] | None = None,
) -> ObservationEnvelope:
    return ObservationEnvelope(
        observation_id=observation_id,
        subject_ref="asset:asset-1",
        metric_key="last",
        value=value,
        unit=unit,
        as_of=NOW,
        observed_at=NOW,
        available_at=NOW,
        source_refs=[SOURCE],
        freshness_status=freshness,
        quality_flags=quality_flags or [],
    )


@pytest.mark.parametrize("asset_type", ["stock", "index", "etf", "active_fund"])
def test_asset_snapshot_preserves_fact_context_for_all_four_asset_types(asset_type: str):
    from services.asset_observation_service import AssetObservationService

    service = AssetObservationService(FakeAssetRepository(asset_type))

    snapshot = service.get_asset_snapshot("asset-1")

    assert snapshot.asset.asset_type.value == asset_type
    assert snapshot.identifiers == ["600519.SH"]
    assert snapshot.market_data == {"last": 101.0}
    assert snapshot.freshness_status is FreshnessStatus.FRESH
    assert snapshot.source_refs == [SOURCE]


@pytest.mark.parametrize(
    ("asset_type", "expected_rule"),
    [
        ("stock", "stock:sw_industry_level3"),
        ("index", "index:category"),
        ("etf", "etf:tracking_index_or_theme"),
        ("active_fund", "active_fund:classification_and_benchmark"),
    ],
)
def test_peer_set_exposes_transparent_type_specific_rule(
    asset_type: str,
    expected_rule: str,
):
    from services.asset_observation_service import AssetObservationService

    peers = AssetObservationService(FakeAssetRepository(asset_type)).get_peer_set("asset-1")

    assert peers.rule == expected_rule
    assert peers.sample_size == 2
    assert peers.asset_refs[0].asset_id == "asset-1"


def test_watchlist_item_survives_vendor_identifier_change():
    from services.asset_observation_service import AssetObservationService

    repository = FakeAssetRepository()
    service = AssetObservationService(repository)
    original = service.add_watchlist_item("watchlist-1", "asset-1")

    repository.identifiers = ["600519.CN"]
    current = service.get_asset_snapshot("asset-1")

    assert original.asset_id == "asset-1"
    assert repository.watchlist_item.asset_id == "asset-1"
    assert current.identifiers == ["600519.CN"]


@pytest.mark.parametrize(
    ("freshness", "expected"),
    [
        (FreshnessStatus.STALE, "skipped_data_stale"),
        (FreshnessStatus.QUARANTINED, "skipped_data_stale"),
        (FreshnessStatus.UNAVAILABLE, "skipped_data_unavailable"),
    ],
)
def test_unusable_fact_never_triggers_alert_and_records_skip(
    freshness: FreshnessStatus,
    expected: str,
):
    from services.alert_evaluation_service import AlertEvaluationService

    repository = FakeAlertRepository()
    result = AlertEvaluationService(repository).evaluate(
        _rule(),
        _observation(101, freshness=freshness),
        profile_id="local",
        evaluated_at=NOW,
    )

    assert result.status.value == expected
    assert result.notification_id is None
    assert repository.events == {}
    assert repository.notifications == {}
    assert repository.state["last_evaluation_status"] == expected


def test_alert_fires_only_on_false_to_true_transition_and_persists_notification():
    from services.alert_evaluation_service import AlertEvaluationService

    repository = FakeAlertRepository()
    service = AlertEvaluationService(repository)

    first = service.evaluate(
        _rule(), _observation(101, observation_id="obs-1"), profile_id="local", evaluated_at=NOW
    )
    duplicate = service.evaluate(
        _rule(),
        _observation(102, observation_id="obs-2"),
        profile_id="local",
        evaluated_at=NOW + timedelta(seconds=10),
    )

    assert first.status.value == "triggered"
    assert first.alert_event_id in repository.events
    assert first.notification_id in repository.notifications
    assert duplicate.status.value == "deduplicated"
    assert repository.lock_calls == 2
    assert len(repository.events) == 1
    assert len(repository.notifications) == 1


def test_false_resolves_open_event_and_new_edge_still_respects_cooldown():
    from services.alert_evaluation_service import AlertEvaluationService

    repository = FakeAlertRepository()
    service = AlertEvaluationService(repository)
    triggered = service.evaluate(
        _rule(), _observation(101, observation_id="obs-1"), profile_id="local", evaluated_at=NOW
    )

    cleared = service.evaluate(
        _rule(),
        _observation(99, observation_id="obs-2"),
        profile_id="local",
        evaluated_at=NOW + timedelta(seconds=20),
    )
    suppressed_edge = service.evaluate(
        _rule(),
        _observation(101, observation_id="obs-3"),
        profile_id="local",
        evaluated_at=NOW + timedelta(seconds=30),
    )

    assert cleared.status.value == "not_matched"
    assert repository.events[triggered.alert_event_id].status == "resolved"
    assert suppressed_edge.status.value == "deduplicated"
    assert len(repository.events) == 1


def test_after_false_reset_a_new_edge_triggers_when_cooldown_has_elapsed():
    from services.alert_evaluation_service import AlertEvaluationService

    repository = FakeAlertRepository()
    service = AlertEvaluationService(repository)
    service.evaluate(
        _rule(), _observation(101, observation_id="obs-1"), profile_id="local", evaluated_at=NOW
    )
    service.evaluate(
        _rule(),
        _observation(99, observation_id="obs-2"),
        profile_id="local",
        evaluated_at=NOW + timedelta(seconds=20),
    )
    second = service.evaluate(
        _rule(),
        _observation(101, observation_id="obs-3"),
        profile_id="local",
        evaluated_at=NOW + timedelta(seconds=301),
    )

    assert second.status.value == "triggered"
    assert len(repository.events) == 2
    assert len(repository.notifications) == 2


def test_alert_rejects_unit_mismatch_without_creating_event():
    from services.alert_evaluation_service import AlertEvaluationService

    repository = FakeAlertRepository()
    result = AlertEvaluationService(repository).evaluate(
        _rule(),
        _observation(101, unit="USD/share"),
        profile_id="local",
        evaluated_at=NOW,
    )

    assert result.status.value == "failed_unit_mismatch"
    assert repository.events == {}


def test_repository_reuses_existing_stock_facts_and_never_commits():
    from data_layer.repositories.asset_observation_repository import (
        AssetObservationRepository,
    )
    from data_layer.repositories.base import Base
    from data_layer.repositories.models import (
        AssetIdentifierDB,
        AssetRegistryDB,
        StockMasterDB,
        StockQuoteSnapshotDB,
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            AssetRegistryDB.__table__,
            AssetIdentifierDB.__table__,
            StockMasterDB.__table__,
            StockQuoteSnapshotDB.__table__,
        ],
    )
    with Session(engine) as session:
        session.add(
            AssetRegistryDB(
                asset_id="asset-stock-1",
                asset_type="stock",
                canonical_name="贵州茅台",
            )
        )
        session.add(
            AssetIdentifierDB(
                identifier_id="identifier-alias-wrong",
                asset_id="asset-stock-1",
                scheme="alias",
                value="WRONG",
                market="CN",
                valid_from=NOW - timedelta(days=30),
            )
        )
        session.add(
            AssetIdentifierDB(
                identifier_id="identifier-1",
                asset_id="asset-stock-1",
                scheme="wind",
                value="600519.SH",
                market="CN",
                valid_from=NOW - timedelta(days=30),
            )
        )
        session.add(
            StockMasterDB(
                symbol="600519.SH",
                raw_code="600519",
                name="贵州茅台",
                industry_level3="白酒",
                source="wind",
                updated_at=NOW,
                created_at=NOW,
            )
        )
        session.add(
            StockQuoteSnapshotDB(
                symbol="600519.SH",
                quote_time=NOW,
                last_price=1500,
                change_pct=1.2,
                source="wind",
                created_at=NOW,
            )
        )
        session.flush()
        repository = AssetObservationRepository(session)

        projection = repository.get_asset_projection("asset-stock-1", as_of=NOW)

        assert projection is not None
        assert projection["identifiers"] == ["WRONG", "600519.SH"]
        assert projection["market_data"]["last"] == 1500.0
        assert projection["type_payload"]["industry_level3"] == "白酒"
        assert session.in_transaction()


def test_due_alert_entry_evaluates_authoritative_facts_and_skips_stale_or_missing():
    from data_layer.repositories.asset_observation_repository import (
        AssetObservationRepository,
    )
    from data_layer.repositories.base import Base
    from data_layer.repositories.models import (
        AlertEventDB,
        AlertRuleDB,
        AssetIdentifierDB,
        AssetRegistryDB,
        NotificationDB,
        StockMasterDB,
        StockQuoteSnapshotDB,
    )
    from services.asset_observation_service import (
        AssetObservationConflictError,
        AssetObservationService,
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            AssetRegistryDB.__table__,
            AssetIdentifierDB.__table__,
            StockMasterDB.__table__,
            StockQuoteSnapshotDB.__table__,
            AlertRuleDB.__table__,
            AlertEventDB.__table__,
            NotificationDB.__table__,
        ],
    )
    with Session(engine) as session:
        for suffix, quote_time, last_price in (
            ("fresh", NOW, 150.0),
            ("stale", NOW - timedelta(minutes=2), 150.0),
        ):
            asset_id = f"asset-{suffix}"
            symbol = f"{suffix}.SH"
            session.add(
                AssetRegistryDB(
                    asset_id=asset_id,
                    asset_type="stock",
                    canonical_name=suffix,
                    updated_at=NOW,
                )
            )
            session.add(
                AssetIdentifierDB(
                    identifier_id=f"identifier-{suffix}",
                    asset_id=asset_id,
                    scheme="wind",
                    value=symbol,
                    market="CN",
                    valid_from=NOW - timedelta(days=1),
                )
            )
            session.add(
                StockMasterDB(
                    symbol=symbol,
                    raw_code=suffix,
                    name=suffix,
                    market="CN",
                    source="wind",
                    updated_at=quote_time,
                    created_at=quote_time,
                )
            )
            session.add(
                StockQuoteSnapshotDB(
                    symbol=symbol,
                    quote_time=quote_time,
                    last_price=last_price,
                    source="wind",
                    created_at=quote_time,
                )
            )

        rules = (
            ("rule-fresh", "asset-fresh", "last", "gt"),
            ("rule-invalid", "asset-fresh", "last", "invalid"),
            ("rule-stale", "asset-stale", "last", "gt"),
            ("rule-missing", "asset-fresh", "missing_metric", "gt"),
        )
        for rule_id, asset_id, metric_key, operator in rules:
            session.add(
                AlertRuleDB(
                    rule_id=rule_id,
                    asset_id=asset_id,
                    metric_type="price",
                    metric_key=metric_key,
                    operator=operator,
                    threshold=100,
                    unit="CNY/share",
                    required_freshness="fresh",
                    cooldown_seconds=0,
                    status="active",
                    state={"condition_true": False, "profile_id": "local"},
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        session.commit()

        service = AssetObservationService(AssetObservationRepository(session))
        summary = service.evaluate_due_alerts("local", NOW)

        assert summary.model_dump() == {
            "evaluated": 4,
            "triggered": 1,
            "deduplicated": 0,
            "skipped": 2,
            "failed": 1,
        }
        assert session.query(AlertEventDB).count() == 1
        assert session.query(NotificationDB).count() == 1
        notification_id = session.query(NotificationDB.notification_id).scalar()

        claimed = service.mark_notification_delivery(
            notification_id,
            "desktop_delivering",
            expected_status="pending",
        )
        assert claimed.status.value == "desktop_delivering"
        assert claimed.delivery_claim_token
        assert claimed.delivery_claimed_at is not None
        assert claimed.delivery_attempt == 1
        with pytest.raises(AssetObservationConflictError, match="conflict"):
            service.mark_notification_delivery(
                notification_id,
                "desktop_delivering",
                expected_status="pending",
            )


def test_due_alert_reloads_locked_rule_after_candidate_is_paused(tmp_path):
    from data_layer.repositories.asset_observation_repository import (
        AssetObservationRepository,
    )
    from data_layer.repositories.base import Base
    from data_layer.repositories.models import (
        AlertEventDB,
        AlertRuleDB,
        AssetIdentifierDB,
        AssetRegistryDB,
        NotificationDB,
        StockMasterDB,
        StockQuoteSnapshotDB,
    )
    from services.asset_observation_service import AssetObservationService

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'pause-race.sqlite'}")
    Base.metadata.create_all(
        engine,
        tables=[
            AssetRegistryDB.__table__,
            AssetIdentifierDB.__table__,
            StockMasterDB.__table__,
            StockQuoteSnapshotDB.__table__,
            AlertRuleDB.__table__,
            AlertEventDB.__table__,
            NotificationDB.__table__,
        ],
    )
    with Session(engine) as seed:
        seed.add(
            AssetRegistryDB(
                asset_id="asset-race",
                asset_type="stock",
                canonical_name="Race Asset",
                updated_at=NOW,
            )
        )
        seed.add(
            AssetIdentifierDB(
                identifier_id="identifier-race",
                asset_id="asset-race",
                scheme="wind",
                value="race.SH",
                market="CN",
                valid_from=NOW - timedelta(days=1),
            )
        )
        seed.add(
            StockMasterDB(
                symbol="race.SH",
                raw_code="race",
                name="Race Asset",
                market="CN",
                source="wind",
                updated_at=NOW,
                created_at=NOW,
            )
        )
        seed.add(
            StockQuoteSnapshotDB(
                symbol="race.SH",
                quote_time=NOW,
                last_price=150,
                source="wind",
                created_at=NOW,
            )
        )
        seed.add(
            AlertRuleDB(
                rule_id="rule-race",
                asset_id="asset-race",
                metric_type="price",
                metric_key="last",
                operator="gt",
                threshold=100,
                unit="CNY/share",
                required_freshness="fresh",
                cooldown_seconds=0,
                status="active",
                state={"condition_true": False, "profile_id": "local"},
                created_at=NOW,
                updated_at=NOW,
            )
        )
        seed.commit()

    class PauseAfterListRepository(AssetObservationRepository):
        def list_active_alert_rules(self, profile_id: str) -> list[Any]:
            candidates = super().list_active_alert_rules(profile_id)
            with Session(engine) as writer:
                writer.execute(
                    update(AlertRuleDB)
                    .where(AlertRuleDB.rule_id == "rule-race")
                    .values(status="paused", updated_at=NOW + timedelta(seconds=1))
                )
                writer.commit()
            return candidates

    with Session(engine) as reader:
        summary = AssetObservationService(PauseAfterListRepository(reader)).evaluate_due_alerts(
            "local", NOW + timedelta(seconds=2)
        )

        assert summary.evaluated == 1
        assert summary.skipped == 1
        assert summary.triggered == 0
        assert reader.query(AlertEventDB).count() == 0
        assert reader.query(NotificationDB).count() == 0


def test_alert_rule_lock_statement_compiles_to_postgresql_for_update():
    from data_layer.repositories.asset_observation_repository import (
        AssetObservationRepository,
    )

    statement = AssetObservationRepository.alert_rule_for_update_statement("rule-1")
    ddl = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in ddl


def test_notification_delivery_lease_recovers_crash_and_rejects_old_token():
    from data_layer.repositories.asset_observation_repository import (
        AssetObservationRepository,
    )
    from data_layer.repositories.base import Base
    from data_layer.repositories.models import (
        AlertEventDB,
        AlertRuleDB,
        AssetRegistryDB,
        NotificationDB,
    )
    from services.asset_observation_service import (
        AssetObservationConflictError,
        AssetObservationService,
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            AssetRegistryDB.__table__,
            AlertRuleDB.__table__,
            AlertEventDB.__table__,
            NotificationDB.__table__,
        ],
    )
    with Session(engine) as session:
        session.add(
            AssetRegistryDB(
                asset_id="asset-notification",
                asset_type="stock",
                canonical_name="Notification Asset",
                updated_at=NOW,
            )
        )
        session.add(
            AlertRuleDB(
                rule_id="rule-notification",
                asset_id="asset-notification",
                metric_type="price",
                metric_key="last",
                operator="gt",
                threshold=100,
                unit="CNY/share",
                status="active",
                state={"profile_id": "local"},
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            AlertEventDB(
                event_id="event-notification",
                rule_id="rule-notification",
                observation_id="obs-notification",
                dedupe_key="dedupe-notification",
                status="open",
                triggered_at=NOW,
            )
        )
        session.add(
            NotificationDB(
                notification_id="notification-lease",
                alert_event_id="event-notification",
                profile_id="local",
                title="Lease",
                body="Lease body",
                status="pending",
                delivery_metadata={},
                created_at=NOW,
            )
        )
        session.commit()

        service = AssetObservationService(AssetObservationRepository(session))
        first_claim = service.mark_notification_delivery(
            "notification-lease",
            "desktop_delivering",
            expected_status="pending",
        )
        first_token = first_claim.delivery_claim_token
        assert first_token
        session.execute(
            update(NotificationDB)
            .where(NotificationDB.notification_id == "notification-lease")
            .values(delivery_claimed_at=datetime.now(UTC) - timedelta(seconds=121))
        )
        session.commit()

        recovered = service.list_notifications("local", status="pending")
        assert [item.notification_id for item in recovered] == ["notification-lease"]
        assert recovered[0].delivery_claim_token is None

        second_claim = service.mark_notification_delivery(
            "notification-lease",
            "desktop_delivering",
            expected_status="pending",
        )
        second_token = second_claim.delivery_claim_token
        assert second_token and second_token != first_token
        assert second_claim.delivery_attempt == 2

        with pytest.raises(AssetObservationConflictError, match="conflict"):
            service.mark_notification_delivery(
                "notification-lease",
                "desktop_delivered",
                expected_status="desktop_delivering",
                delivery_claim_token=first_token,
            )

        completed = service.mark_notification_delivery(
            "notification-lease",
            "desktop_delivered",
            expected_status="desktop_delivering",
            delivery_claim_token=second_token,
        )
        assert completed.status.value == "desktop_delivered"
        assert completed.delivery_claim_token is None
        assert completed.delivery_claimed_at is None


def test_active_fund_projection_excludes_future_trading_day_and_future_available_nav():
    from data_layer.repositories.asset_observation_repository import (
        AssetObservationRepository,
    )
    from data_layer.repositories.base import Base
    from data_layer.repositories.fund_repository import (
        fund_master_table,
        fund_metadata,
        fund_nav_daily_table,
    )
    from data_layer.repositories.models import AssetIdentifierDB, AssetRegistryDB

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[AssetRegistryDB.__table__, AssetIdentifierDB.__table__],
    )
    fund_metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            AssetRegistryDB(
                asset_id="asset-fund-1",
                asset_type="active_fund",
                canonical_name="点时基金",
                updated_at=NOW,
            )
        )
        session.add(
            AssetIdentifierDB(
                identifier_id="identifier-fund-1",
                asset_id="asset-fund-1",
                scheme="wind",
                value="000001.OF",
                market="CN",
                valid_from=NOW - timedelta(days=30),
            )
        )
        session.execute(
            insert(fund_master_table).values(
                symbol="000001.OF",
                name="点时基金",
                fund_type="混合型",
                benchmark="沪深300",
                updated_at=NOW - timedelta(days=1),
            )
        )
        session.execute(
            insert(fund_nav_daily_table),
            [
                {
                    "symbol": "000001.OF",
                    "trading_day": (NOW - timedelta(days=2)).date(),
                    "unit_nav": 1.1,
                    "updated_at": NOW - timedelta(days=1),
                },
                {
                    "symbol": "000001.OF",
                    "trading_day": (NOW + timedelta(days=1)).date(),
                    "unit_nav": 9.9,
                    "updated_at": NOW - timedelta(hours=1),
                },
                {
                    "symbol": "000001.OF",
                    "trading_day": (NOW - timedelta(days=1)).date(),
                    "unit_nav": 8.8,
                    "updated_at": NOW + timedelta(hours=1),
                },
            ],
        )
        session.commit()

        projection = AssetObservationRepository(session).get_asset_projection(
            "asset-fund-1",
            as_of=NOW,
        )

        assert projection is not None
        assert projection["market_data"]["unit_nav"] == 1.1
        assert projection["observed_at"] <= NOW
        assert projection["available_at"] <= NOW


def test_repository_add_watchlist_item_is_idempotent_by_canonical_asset_id():
    from data_layer.repositories.asset_observation_repository import (
        AssetObservationRepository,
    )
    from data_layer.repositories.base import Base
    from data_layer.repositories.models import (
        AssetRegistryDB,
        WatchlistDB,
        WatchlistItemDB,
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            AssetRegistryDB.__table__,
            WatchlistDB.__table__,
            WatchlistItemDB.__table__,
        ],
    )
    with Session(engine) as session:
        session.add(
            AssetRegistryDB(
                asset_id="asset-stock-1",
                asset_type="stock",
                canonical_name="贵州茅台",
            )
        )
        session.add(
            WatchlistDB(
                watchlist_id="watchlist-1",
                profile_id="local",
                name="核心观察",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.flush()
        repository = AssetObservationRepository(session)

        first = repository.add_watchlist_item(
            watchlist_id="watchlist-1",
            asset_id="asset-stock-1",
            position=0,
            note=None,
        )
        second = repository.add_watchlist_item(
            watchlist_id="watchlist-1",
            asset_id="asset-stock-1",
            position=9,
            note="保留同一条目",
        )

        assert second.item_id == first.item_id
        assert second.asset_id == "asset-stock-1"
        assert session.query(WatchlistItemDB).count() == 1


def test_active_event_unique_conflict_uses_savepoint_and_keeps_session_usable(tmp_path):
    from data_layer.repositories.asset_observation_repository import (
        AssetObservationRepository,
    )
    from data_layer.repositories.base import Base
    from data_layer.repositories.models import (
        AlertEventDB,
        AlertRuleDB,
        AssetRegistryDB,
        NotificationDB,
    )

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'alert-conflict.sqlite'}")
    Base.metadata.create_all(
        engine,
        tables=[
            AssetRegistryDB.__table__,
            AlertRuleDB.__table__,
            AlertEventDB.__table__,
            NotificationDB.__table__,
        ],
    )
    with Session(engine) as session:
        session.add(
            AssetRegistryDB(
                asset_id="asset-1",
                asset_type="stock",
                canonical_name="资产一",
            )
        )
        session.add(
            AlertRuleDB(
                rule_id="rule-1",
                asset_id="asset-1",
                metric_type="price",
                metric_key="last",
                operator="gt",
                threshold=100,
                status="active",
                state={"condition_true": False},
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.commit()

    with Session(engine) as first_session:
        first = AssetObservationRepository(first_session).create_alert_event(
            event_id="event-open",
            rule_id="rule-1",
            observation_id="obs-1",
            dedupe_key="rule-1:obs-1",
            status="open",
            triggered_at=NOW,
            acknowledged_at=None,
            resolved_at=None,
        )
        assert first is not None
        first_session.commit()

    with Session(engine) as second_session:
        repository = AssetObservationRepository(second_session)
        duplicate = repository.create_alert_event(
            event_id="event-acknowledged",
            rule_id="rule-1",
            observation_id="obs-2",
            dedupe_key="rule-1:obs-2",
            status="acknowledged",
            triggered_at=NOW + timedelta(seconds=1),
            acknowledged_at=NOW + timedelta(seconds=1),
            resolved_at=None,
        )

        assert duplicate is None
        repository.update_rule_state("rule-1", {"condition_true": True})
        second_session.commit()

    with Session(engine) as verification_session:
        assert verification_session.query(AlertEventDB).count() == 1
        assert verification_session.query(NotificationDB).count() == 0
        assert verification_session.get(AlertRuleDB, "rule-1").state == {"condition_true": True}


def test_event_unique_conflict_returns_deduplicated_without_notification():
    from services.alert_evaluation_service import AlertEvaluationService

    class ConflictingRepository(FakeAlertRepository):
        def create_alert_event(self, **values: Any) -> None:
            self.events["event-existing"] = SimpleNamespace(
                event_id="event-existing",
                rule_id=values["rule_id"],
                status="open",
            )

        def get_active_alert_event(self, rule_id: str) -> Any:
            return self.events["event-existing"]

    repository = ConflictingRepository()
    result = AlertEvaluationService(repository).evaluate(
        _rule(),
        _observation(101),
        profile_id="local",
        evaluated_at=NOW,
    )

    assert result.status.value == "deduplicated"
    assert result.notification_id is None
    assert repository.notifications == {}
    assert repository.state["open_event_id"] == "event-existing"
