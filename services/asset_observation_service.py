"""Application service for canonical asset observation and personal watch state."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from core.contracts.asset_observation import (
    AlertBatchEvaluationSummary,
    AlertEvaluationStatus,
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
from core.contracts.platform_shared import (
    AssetType,
    FreshnessStatus,
    ObservationEnvelope,
)
from core.observability import get_logger

logger = get_logger(__name__)

_DESKTOP_DELIVERY_LEASE = timedelta(seconds=120)


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

    def evaluate_due_alerts(
        self,
        profile_id: str,
        evaluated_at: datetime | None = None,
    ) -> AlertBatchEvaluationSummary:
        """Evaluate active rules only against server-side authoritative facts."""

        from services.alert_evaluation_service import AlertEvaluationService

        if not profile_id.strip():
            raise ValueError("profile_id is required")
        now = evaluated_at or _utc_now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        counts = {
            "evaluated": 0,
            "triggered": 0,
            "deduplicated": 0,
            "skipped": 0,
            "failed": 0,
        }
        evaluator = AlertEvaluationService(self._repository)
        for row in self._repository.list_active_alert_rules(profile_id.strip()):
            counts["evaluated"] += 1
            try:
                with self._repository.evaluation_savepoint():
                    candidate_id = row.rule_id
                    locked = evaluator.lock_rule_for_evaluation(
                        candidate_id,
                        profile_id.strip(),
                    )
                    if locked is None:
                        result = evaluator.not_eligible(
                            candidate_id,
                            f"alert-rule:{candidate_id}:not-eligible",
                            now,
                        )
                    else:
                        rule = locked.rule
                        projection = self._repository.get_asset_projection(
                            rule.asset_id,
                            as_of=now,
                        )
                        observation = self._build_rule_observation(rule, projection, now)
                        result = evaluator.evaluate_locked(
                            locked,
                            observation,
                            profile_id=profile_id.strip(),
                            evaluated_at=now,
                        )
                if result.status is AlertEvaluationStatus.TRIGGERED:
                    counts["triggered"] += 1
                elif result.status is AlertEvaluationStatus.DEDUPLICATED:
                    counts["deduplicated"] += 1
                elif result.status in {
                    AlertEvaluationStatus.SKIPPED_DATA_STALE,
                    AlertEvaluationStatus.SKIPPED_DATA_UNAVAILABLE,
                    AlertEvaluationStatus.SKIPPED_RULE_NOT_ELIGIBLE,
                }:
                    counts["skipped"] += 1
                elif result.status is AlertEvaluationStatus.FAILED_UNIT_MISMATCH:
                    counts["failed"] += 1
            except Exception as exc:  # noqa: BLE001 - one bad rule must not stop the batch
                counts["failed"] += 1
                logger.error(
                    "due alert evaluation failed",
                    rule_id=getattr(row, "rule_id", "unknown"),
                    asset_id=getattr(row, "asset_id", "unknown"),
                    error_type=type(exc).__name__,
                )
        logger.info(
            "due alert batch evaluated",
            profile_id=profile_id.strip(),
            **counts,
        )
        return AlertBatchEvaluationSummary(**counts)

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
        status: str | None = None,
    ) -> list[Notification]:
        notification_status = NotificationStatus(status) if status is not None else None
        if notification_status is NotificationStatus.PENDING:
            recovered = self._repository.requeue_expired_delivery_claims(
                profile_id,
                _utc_now() - _DESKTOP_DELIVERY_LEASE,
            )
            if recovered:
                logger.info(
                    "expired desktop notification claims recovered",
                    profile_id=profile_id,
                    recovered_count=recovered,
                )
        return [
            self._to_notification(row)
            for row in self._repository.list_notifications(
                profile_id,
                unread_only=unread_only,
                status=notification_status,
            )
        ]

    def mark_notification_delivery(
        self,
        notification_id: str,
        status: str,
        *,
        expected_status: str,
        delivery_claim_token: str | None = None,
    ) -> Notification:
        delivery_status = NotificationStatus(status)
        expected_delivery_status = NotificationStatus(expected_status)
        allowed_transitions = {
            NotificationStatus.PENDING: {
                NotificationStatus.DESKTOP_DELIVERING,
                NotificationStatus.DESKTOP_PERMISSION_DENIED,
                NotificationStatus.DESKTOP_FAILED,
            },
            NotificationStatus.DESKTOP_DELIVERING: {
                NotificationStatus.DESKTOP_DELIVERED,
                NotificationStatus.DESKTOP_FAILED,
            },
        }
        if delivery_status not in allowed_transitions.get(expected_delivery_status, set()):
            raise ValueError("invalid notification delivery transition")
        now = _utc_now()
        if delivery_status is NotificationStatus.DESKTOP_DELIVERING:
            if delivery_claim_token is not None:
                raise ValueError("claim token is server generated")
            row = self._repository.claim_notification_delivery(
                notification_id,
                secrets.token_urlsafe(32),
                now,
            )
        elif expected_delivery_status is NotificationStatus.DESKTOP_DELIVERING:
            if not delivery_claim_token:
                raise ValueError("delivery claim token is required")
            row = self._repository.complete_notification_delivery(
                notification_id,
                delivery_status,
                delivery_claim_token,
                now,
            )
        else:
            row = self._repository.mark_pending_notification_outcome(
                notification_id,
                delivery_status,
                now,
            )
        if row is None:
            if self._repository.get_notification(notification_id) is None:
                raise AssetNotFoundError(notification_id)
            raise AssetObservationConflictError("notification delivery conflict")
        logger.info(
            "notification delivery state updated",
            notification_id=notification_id,
            notification_channel="desktop",
            status=delivery_status.value,
        )
        return self._to_notification(row)

    @staticmethod
    def _build_rule_observation(
        rule: AlertRule,
        projection: dict[str, Any] | None,
        evaluated_at: datetime,
    ) -> ObservationEnvelope:
        if projection is None:
            raise AssetNotFoundError(rule.asset_id)
        market_data = projection.get("market_data") or {}
        metric_units = projection.get("metric_units") or {}
        value = market_data.get(rule.metric_key)
        unit = metric_units.get(rule.metric_key)
        freshness = projection["freshness_status"]
        quality_flags = list(projection.get("quality_flags") or [])
        missing_reason = None
        if value is None:
            missing_reason = "authoritative_metric_unavailable"
        elif unit is None:
            value = None
            missing_reason = "authoritative_unit_unavailable"
        if missing_reason is not None:
            unit = None
            freshness = FreshnessStatus.UNAVAILABLE
            quality_flags.append(missing_reason)
        if projection["observed_at"] > evaluated_at or projection["available_at"] > evaluated_at:
            value = None
            unit = None
            missing_reason = "future_fact_unavailable"
            freshness = FreshnessStatus.UNAVAILABLE
            quality_flags.append(missing_reason)
        return ObservationEnvelope(
            observation_id=(
                f"alert-fact:{rule.rule_id}:{rule.metric_key}:"
                f"{projection['available_at'].isoformat()}"
            ),
            subject_ref=f"asset:{rule.asset_id}",
            metric_key=rule.metric_key,
            value=value,
            unit=unit,
            missing_reason=missing_reason,
            as_of=evaluated_at,
            observed_at=projection["observed_at"],
            available_at=projection["available_at"],
            source_refs=projection["source_refs"],
            freshness_status=freshness,
            quality_flags=quality_flags,
        )

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
