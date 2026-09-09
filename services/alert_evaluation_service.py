"""Deterministic alert evaluation with durable edge and notification state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from core.contracts.asset_observation import (
    AlertEvaluation,
    AlertEvaluationStatus,
    AlertOperator,
    AlertRule,
    AlertRuleStatus,
    NotificationStatus,
)
from core.contracts.platform_shared import FreshnessStatus, ObservationEnvelope
from core.observability import get_logger

logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class LockedAlertRule:
    """Authoritative rule and state read under the database row lock."""

    rule: AlertRule
    state: dict[str, Any]


class AlertEvaluationService:
    """Evaluate one rule while preserving false-to-true edge semantics."""

    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def evaluate(
        self,
        rule: AlertRule,
        observation: ObservationEnvelope,
        *,
        profile_id: str,
        evaluated_at: datetime | None = None,
    ) -> AlertEvaluation:
        now = evaluated_at or _utc_now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        locked = self.lock_rule_for_evaluation(rule.rule_id, profile_id)
        if locked is None:
            return self.not_eligible(rule.rule_id, observation.observation_id, now)
        return self.evaluate_locked(
            locked,
            observation,
            profile_id=profile_id,
            evaluated_at=now,
        )

    def lock_rule_for_evaluation(
        self,
        rule_id: str,
        profile_id: str,
    ) -> LockedAlertRule | None:
        """Lock, fully refresh, and eligibility-check the authoritative rule."""

        row = self._repository.lock_alert_rule(rule_id)
        if row is None:
            return None
        rule = self._repository.to_alert_rule(row)
        state = dict(row.state or {})
        if rule.status is not AlertRuleStatus.ACTIVE:
            return None
        if state.get("profile_id") != profile_id:
            return None
        return LockedAlertRule(rule=rule, state=state)

    def evaluate_locked(
        self,
        locked: LockedAlertRule,
        observation: ObservationEnvelope,
        *,
        profile_id: str,
        evaluated_at: datetime,
    ) -> AlertEvaluation:
        """Evaluate using only rule fields captured by the held row lock."""

        rule = locked.rule
        state = locked.state
        now = evaluated_at

        unusable = self._unusable_status(observation)
        if unusable is not None:
            return self._record_result(rule, observation, state, unusable, now)
        if rule.unit != observation.unit:
            return self._record_result(
                rule,
                observation,
                state,
                AlertEvaluationStatus.FAILED_UNIT_MISMATCH,
                now,
            )

        condition_true = self._matches(rule, observation, state)
        was_true = bool(state.get("condition_true", False))
        if not condition_true:
            if was_true and state.get("open_event_id"):
                self._repository.resolve_alert_event(state["open_event_id"], now)
            state.update(
                {
                    "condition_true": False,
                    "open_event_id": None,
                    "previous_value": observation.value,
                }
            )
            return self._record_result(
                rule,
                observation,
                state,
                AlertEvaluationStatus.NOT_MATCHED,
                now,
            )

        if was_true:
            state["previous_value"] = observation.value
            return self._record_result(
                rule,
                observation,
                state,
                AlertEvaluationStatus.DEDUPLICATED,
                now,
            )

        last_triggered_at = self._parse_datetime(state.get("last_triggered_at"))
        cooldown_active = last_triggered_at is not None and now < last_triggered_at + timedelta(
            seconds=rule.cooldown_seconds
        )
        if cooldown_active:
            state.update(
                {
                    "condition_true": True,
                    "open_event_id": None,
                    "previous_value": observation.value,
                }
            )
            return self._record_result(
                rule,
                observation,
                state,
                AlertEvaluationStatus.DEDUPLICATED,
                now,
            )

        event_id = f"alert-event-{uuid4()}"
        notification_id = f"notification-{uuid4()}"
        event = self._repository.create_alert_event(
            event_id=event_id,
            rule_id=rule.rule_id,
            observation_id=observation.observation_id,
            dedupe_key=f"{rule.rule_id}:{observation.observation_id}",
            status="open",
            triggered_at=now,
            acknowledged_at=None,
            resolved_at=None,
        )
        if event is None:
            active_event = self._repository.get_active_alert_event(rule.rule_id)
            state.update(
                {
                    "condition_true": True,
                    "open_event_id": (active_event.event_id if active_event is not None else None),
                    "previous_value": observation.value,
                }
            )
            return self._record_result(
                rule,
                observation,
                state,
                AlertEvaluationStatus.DEDUPLICATED,
                now,
            )
        self._repository.create_notification(
            notification_id=notification_id,
            alert_event_id=event_id,
            profile_id=profile_id,
            title=self._safe_title(rule),
            body=self._safe_body(rule),
            status=NotificationStatus.PENDING.value,
            delivery_metadata={},
            created_at=now,
            delivered_at=None,
            read_at=None,
        )
        state.update(
            {
                "condition_true": True,
                "open_event_id": event_id,
                "last_triggered_at": now.isoformat(),
                "previous_value": observation.value,
            }
        )
        self._repository.update_rule_state(rule.rule_id, state)
        logger.info(
            "alert evaluation completed",
            rule_id=rule.rule_id,
            asset_id=rule.asset_id,
            observation_id=observation.observation_id,
            freshness_status=observation.freshness_status.value,
            evaluation_status=AlertEvaluationStatus.TRIGGERED.value,
            event_id=event_id,
        )
        return AlertEvaluation(
            rule_id=rule.rule_id,
            observation_id=observation.observation_id,
            status=AlertEvaluationStatus.TRIGGERED,
            evaluated_at=now,
            alert_event_id=event_id,
            notification_id=notification_id,
        )

    def not_eligible(
        self,
        rule_id: str,
        observation_id: str,
        evaluated_at: datetime,
    ) -> AlertEvaluation:
        """Return an explicit skip without mutating a paused, retired, or foreign rule."""

        logger.info(
            "alert evaluation skipped because rule is not eligible",
            rule_id=rule_id,
            observation_id=observation_id,
            evaluation_status=AlertEvaluationStatus.SKIPPED_RULE_NOT_ELIGIBLE.value,
        )
        return AlertEvaluation(
            rule_id=rule_id,
            observation_id=observation_id,
            status=AlertEvaluationStatus.SKIPPED_RULE_NOT_ELIGIBLE,
            evaluated_at=evaluated_at,
        )

    def _record_result(
        self,
        rule: AlertRule,
        observation: ObservationEnvelope,
        state: dict[str, Any],
        status: AlertEvaluationStatus,
        evaluated_at: datetime,
    ) -> AlertEvaluation:
        state["last_evaluation_status"] = status.value
        state["last_evaluated_at"] = evaluated_at.isoformat()
        self._repository.update_rule_state(rule.rule_id, state)
        logger.info(
            "alert evaluation completed",
            rule_id=rule.rule_id,
            asset_id=rule.asset_id,
            observation_id=observation.observation_id,
            freshness_status=observation.freshness_status.value,
            evaluation_status=status.value,
        )
        return AlertEvaluation(
            rule_id=rule.rule_id,
            observation_id=observation.observation_id,
            status=status,
            evaluated_at=evaluated_at,
        )

    @staticmethod
    def _unusable_status(
        observation: ObservationEnvelope,
    ) -> AlertEvaluationStatus | None:
        if observation.freshness_status is FreshnessStatus.UNAVAILABLE:
            return AlertEvaluationStatus.SKIPPED_DATA_UNAVAILABLE
        if observation.freshness_status in {
            FreshnessStatus.STALE,
            FreshnessStatus.QUARANTINED,
        }:
            return AlertEvaluationStatus.SKIPPED_DATA_STALE
        if any("conflict" in flag.lower() for flag in observation.quality_flags):
            return AlertEvaluationStatus.SKIPPED_DATA_STALE
        return None

    @staticmethod
    def _matches(
        rule: AlertRule,
        observation: ObservationEnvelope,
        state: dict[str, Any],
    ) -> bool:
        current = observation.value
        threshold = rule.threshold
        if rule.operator is AlertOperator.GT:
            return bool(current is not None and current > threshold)
        if rule.operator is AlertOperator.GTE:
            return bool(current is not None and current >= threshold)
        if rule.operator is AlertOperator.LT:
            return bool(current is not None and current < threshold)
        if rule.operator is AlertOperator.LTE:
            return bool(current is not None and current <= threshold)
        previous = state.get("previous_value")
        if previous is None or current is None:
            return False
        if rule.operator is AlertOperator.CROSSES_ABOVE:
            return bool(previous <= threshold < current)
        if rule.operator is AlertOperator.CROSSES_BELOW:
            return bool(previous >= threshold > current)
        if rule.operator is AlertOperator.PCT_CHANGE:
            if not isinstance(previous, (int, float)) or previous == 0:
                return False
            pct_change = (float(current) - float(previous)) / abs(float(previous)) * 100
            return pct_change >= float(threshold)
        return False

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed

    @staticmethod
    def _safe_title(rule: AlertRule) -> str:
        return f"{rule.metric_type} 提醒"[:160]

    @staticmethod
    def _safe_body(rule: AlertRule) -> str:
        return f"{rule.asset_id} 的 {rule.metric_key} 已满足已配置条件"[:500]
