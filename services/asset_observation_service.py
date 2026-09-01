"""Application service for canonical asset observation and personal watch state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from core.contracts.asset_observation import (
    AlertEvent,
    AlertRule,
    AlertRuleStatus,
    AssetSnapshotEnvelope,
    Notification,
    NotificationStatus,
    PeerSet,
    Watchlist,
    WatchlistItem,
)
from core.contracts.platform_shared import AssetType
from core.observability import get_logger

logger = get_logger(__name__)


class AssetObservationError(Exception):
    """Base exception safe for route-level classification."""


class AssetNotFoundError(AssetObservationError):
    """Requested canonical asset or observation object was not found."""


class AssetObservationConflictError(AssetObservationError):
    """A unique personal-observation identity already exists."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AssetObservationService:
    """Compose facts without copying them and manage user-owned observation state."""

    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def get_asset_snapshot(self, asset_id: str) -> AssetSnapshotEnvelope:
        projection = self._repository.get_asset_projection(asset_id)
        if projection is None:
            raise AssetNotFoundError(asset_id)
        try:
            return AssetSnapshotEnvelope.model_validate(projection)
        except Exception as exc:
            logger.error(
                "asset projection validation failed",
                asset_id=asset_id,
                error_type=type(exc).__name__,
            )
            raise

    def get_peer_set(self, asset_id: str) -> PeerSet:
        snapshot = self.get_asset_snapshot(asset_id)
        dimension, value, rule = self._peer_dimension(snapshot)
        if value is None:
            peers = []
        else:
            peers = self._repository.list_peer_assets(
                asset_id=asset_id,
                asset_type=snapshot.asset.asset_type.value,
                dimension=dimension,
                value=value,
            )
        return PeerSet(
            peer_set_id=f"peer-set:{asset_id}:{rule}",
            asset_id=asset_id,
            rule=rule,
            sample_size=len(peers),
            asset_refs=peers,
            as_of=snapshot.as_of,
        )

    def create_watchlist(self, profile_id: str, name: str) -> Watchlist:
        if not profile_id.strip() or not name.strip():
            raise ValueError("profile_id and name are required")
        try:
            row = self._repository.create_watchlist(
                profile_id=profile_id.strip(),
                name=name.strip(),
            )
            return self._to_watchlist(row)
        except IntegrityError as exc:
            raise AssetObservationConflictError("watchlist identity conflict") from exc

    def list_watchlists(self, profile_id: str) -> list[Watchlist]:
        if not profile_id.strip():
            raise ValueError("profile_id is required")
        return [self._to_watchlist(row) for row in self._repository.list_watchlists(profile_id)]

    def add_watchlist_item(
        self,
        watchlist_id: str,
        asset_id: str,
        position: int = 0,
        note: str | None = None,
    ) -> WatchlistItem:
        if position < 0:
            raise ValueError("position must be non-negative")
        get_watchlist = getattr(self._repository, "get_watchlist", None)
        if callable(get_watchlist) and get_watchlist(watchlist_id) is None:
            raise AssetNotFoundError(watchlist_id)
        get_asset = getattr(self._repository, "get_asset", None)
        if callable(get_asset) and get_asset(asset_id) is None:
            raise AssetNotFoundError(asset_id)
        try:
            row = self._repository.add_watchlist_item(
                watchlist_id=watchlist_id,
                asset_id=asset_id,
                position=position,
                note=note,
            )
            return self._to_watchlist_item(row)
        except IntegrityError as exc:
            raise AssetObservationConflictError("watchlist item conflict") from exc

    def create_alert_rule(
        self,
        *,
        asset_id: str,
        metric_type: str,
        metric_key: str,
        operator: str,
        threshold: float | str,
        unit: str | None,
        cooldown_seconds: int = 0,
        status: AlertRuleStatus = AlertRuleStatus.DRAFT,
        profile_id: str = "local",
    ) -> AlertRule:
        get_asset = getattr(self._repository, "get_asset", None)
        if callable(get_asset) and get_asset(asset_id) is None:
            raise AssetNotFoundError(asset_id)
        rule = AlertRule(
            rule_id=f"alert-rule-{uuid4()}",
            asset_id=asset_id,
            metric_type=metric_type,
            metric_key=metric_key,
            operator=operator,
            threshold=threshold,
            unit=unit,
            cooldown_seconds=cooldown_seconds,
            status=status,
        )
        try:
            row = self._repository.create_alert_rule(
                rule,
                state={"condition_true": False, "profile_id": profile_id},
            )
            return self._to_alert_rule(row)
        except IntegrityError as exc:
            raise AssetObservationConflictError("alert rule conflict") from exc

    def list_alert_rules(self, asset_id: str | None = None) -> list[AlertRule]:
        return [self._to_alert_rule(row) for row in self._repository.list_alert_rules(asset_id)]

    def update_alert_rule_status(
        self,
        rule_id: str,
        status: AlertRuleStatus,
    ) -> AlertRule:
        row = self._repository.update_alert_rule_status(rule_id, status)
        if row is None:
            raise AssetNotFoundError(rule_id)
        return self._to_alert_rule(row)

    def list_alert_events(self, rule_id: str | None = None) -> list[AlertEvent]:
        return [self._to_alert_event(row) for row in self._repository.list_alert_events(rule_id)]

    def acknowledge_alert_event(self, event_id: str) -> AlertEvent:
        row = self._repository.acknowledge_alert_event(event_id, _utc_now())
        if row is None:
            raise AssetNotFoundError(event_id)
        logger.info("alert event acknowledged", event_id=event_id)
        return self._to_alert_event(row)

    def resolve_alert_event(self, event_id: str) -> AlertEvent:
        row = self._repository.resolve_alert_event(event_id, _utc_now())
        if row is None:
            raise AssetNotFoundError(event_id)
        logger.info("alert event resolved", event_id=event_id)
        return self._to_alert_event(row)

    def list_notifications(
        self,
        profile_id: str,
        unread_only: bool = False,
    ) -> list[Notification]:
        return [
            self._to_notification(row)
            for row in self._repository.list_notifications(
                profile_id,
                unread_only=unread_only,
            )
        ]

    def mark_notification_delivery(
        self,
        notification_id: str,
        status: str,
    ) -> Notification:
        delivery_status = NotificationStatus(status)
        if delivery_status is NotificationStatus.PENDING:
            raise ValueError("pending is not a delivery outcome")
        row = self._repository.mark_notification_delivery(
            notification_id,
            delivery_status,
            _utc_now(),
        )
        if row is None:
            raise AssetNotFoundError(notification_id)
        logger.info(
            "notification delivery state updated",
            notification_id=notification_id,
            notification_channel="desktop",
            status=delivery_status.value,
        )
        return self._to_notification(row)

    def _to_watchlist(self, row: Any) -> Watchlist:
        converter = getattr(self._repository, "to_watchlist", None)
        if callable(converter):
            return converter(row)
        return Watchlist.model_validate(row, from_attributes=True)

    def _to_watchlist_item(self, row: Any) -> WatchlistItem:
        converter = getattr(self._repository, "to_watchlist_item", None)
        if callable(converter):
            return converter(row)
        return WatchlistItem.model_validate(row, from_attributes=True)

    def _to_alert_rule(self, row: Any) -> AlertRule:
        converter = getattr(self._repository, "to_alert_rule", None)
        if callable(converter):
            return converter(row)
        return AlertRule.model_validate(row, from_attributes=True)

    def _to_alert_event(self, row: Any) -> AlertEvent:
        converter = getattr(self._repository, "to_alert_event", None)
        if callable(converter):
            return converter(row)
        return AlertEvent.model_validate(row, from_attributes=True)

    def _to_notification(self, row: Any) -> Notification:
        converter = getattr(self._repository, "to_notification", None)
        if callable(converter):
            return converter(row)
        return Notification.model_validate(row, from_attributes=True)

    @staticmethod
    def _peer_dimension(snapshot: AssetSnapshotEnvelope) -> tuple[str, str | None, str]:
        payload = snapshot.type_payload
        if snapshot.asset.asset_type is AssetType.STOCK:
            for dimension, label in (
                ("industry_level3", "stock:sw_industry_level3"),
                ("industry_level2", "stock:sw_industry_level2"),
                ("industry_level1", "stock:sw_industry_level1"),
            ):
                if payload.get(dimension):
                    return dimension, str(payload[dimension]), label
            return "industry_level3", None, "stock:sw_industry_level3"
        if snapshot.asset.asset_type is AssetType.INDEX:
            return "category", payload.get("category"), "index:category"
        if snapshot.asset.asset_type is AssetType.ETF:
            value = payload.get("tracking_index") or payload.get("theme")
            return "tracking_index_or_theme", value, "etf:tracking_index_or_theme"
        value = f"{payload.get('fund_type')}|{payload.get('benchmark')}"
        if value == "None|None":
            value = None
        return (
            "classification_and_benchmark",
            value,
            "active_fund:classification_and_benchmark",
        )
