"""Thin FastAPI routes for canonical asset observation and personal alerts."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.contracts.asset_observation import (
    AlertBatchEvaluationSummary,
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
from core.observability import get_logger
from data_layer.repositories.base import get_db
from services.asset_observation_service import (
    AssetNotFoundError,
    AssetObservationConflictError,
    AssetObservationService,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/asset-observation", tags=["asset-observation"])


class WatchlistCreateRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=160)


class WatchlistItemCreateRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=160)
    position: int = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class AlertRuleCreateRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=160)
    metric_type: Literal[
        "price",
        "nav",
        "change",
        "flow",
        "valuation",
        "holding",
        "announcement",
        "theme_event",
    ]
    metric_key: str = Field(min_length=1, max_length=160)
    operator: Literal[
        "gt",
        "gte",
        "lt",
        "lte",
        "crosses_above",
        "crosses_below",
        "pct_change",
    ]
    threshold: float | int | str
    unit: str | None = Field(default=None, max_length=64)
    cooldown_seconds: int = Field(default=0, ge=0, le=31_536_000)
    status: AlertRuleStatus = AlertRuleStatus.DRAFT
    profile_id: str = Field(default="local", min_length=1, max_length=128)


class AlertRuleStatusRequest(BaseModel):
    status: AlertRuleStatus


class NotificationDeliveryRequest(BaseModel):
    status: NotificationStatus
    expected_status: NotificationStatus


class DueAlertEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(default="local", min_length=1, max_length=128)
    evaluated_at: AwareDatetime | None = None


DBSession = Annotated[Session, Depends(get_db)]
ProfileIdQuery = Annotated[str, Query(min_length=1, max_length=128)]


def get_asset_observation_service(db: DBSession) -> AssetObservationService:
    """Build the request-scoped asset observation service lazily."""

    from data_layer.repositories.asset_observation_repository import (
        AssetObservationRepository,
    )

    return AssetObservationService(AssetObservationRepository(db))


AssetObservationServiceDependency = Annotated[
    AssetObservationService,
    Depends(get_asset_observation_service),
]


def _raise_safe_http_error(exc: Exception) -> None:
    if isinstance(exc, AssetNotFoundError):
        raise HTTPException(status_code=404, detail="Asset not found") from exc
    if isinstance(exc, (AssetObservationConflictError, IntegrityError)):
        raise HTTPException(status_code=409, detail="Asset observation conflict") from exc
    if isinstance(exc, (ValueError, TypeError)):
        raise HTTPException(status_code=400, detail="Invalid asset observation request") from exc
    logger.error(
        "asset observation API failed",
        error_type=type(exc).__name__,
    )
    raise HTTPException(status_code=500, detail="Asset observation request failed") from exc


@router.get("/assets/{asset_id}", response_model=AssetSnapshotEnvelope)
async def get_asset_snapshot(
    asset_id: str,
    service: AssetObservationServiceDependency,
) -> AssetSnapshotEnvelope:
    try:
        return service.get_asset_snapshot(asset_id)
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.get("/assets/{asset_id}/peers", response_model=PeerSet)
async def get_asset_peers(
    asset_id: str,
    service: AssetObservationServiceDependency,
) -> PeerSet:
    try:
        return service.get_peer_set(asset_id)
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.post(
    "/watchlists",
    response_model=Watchlist,
    status_code=status.HTTP_201_CREATED,
)
async def create_watchlist(
    request: WatchlistCreateRequest,
    service: AssetObservationServiceDependency,
) -> Watchlist:
    try:
        result = service.create_watchlist(request.profile_id, request.name)
        logger.info(
            "asset observation write completed",
            operation="create_watchlist",
            profile_id=request.profile_id,
            watchlist_id=result.watchlist_id,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.get("/watchlists", response_model=list[Watchlist])
async def list_watchlists(
    profile_id: ProfileIdQuery,
    service: AssetObservationServiceDependency,
) -> list[Watchlist]:
    try:
        return service.list_watchlists(profile_id)
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.post(
    "/watchlists/{watchlist_id}/items",
    response_model=WatchlistItem,
    status_code=status.HTTP_201_CREATED,
)
async def add_watchlist_item(
    watchlist_id: str,
    request: WatchlistItemCreateRequest,
    service: AssetObservationServiceDependency,
) -> WatchlistItem:
    try:
        result = service.add_watchlist_item(
            watchlist_id,
            request.asset_id,
            request.position,
            request.note,
        )
        logger.info(
            "asset observation write completed",
            operation="add_watchlist_item",
            watchlist_id=watchlist_id,
            asset_id=request.asset_id,
            item_id=result.item_id,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.post(
    "/alert-rules",
    response_model=AlertRule,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert_rule(
    request: AlertRuleCreateRequest,
    service: AssetObservationServiceDependency,
) -> AlertRule:
    try:
        result = service.create_alert_rule(**request.model_dump())
        logger.info(
            "asset observation write completed",
            operation="create_alert_rule",
            rule_id=result.rule_id,
            asset_id=result.asset_id,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.get("/alert-rules", response_model=list[AlertRule])
async def list_alert_rules(
    service: AssetObservationServiceDependency,
    asset_id: str | None = None,
) -> list[AlertRule]:
    try:
        return service.list_alert_rules(asset_id)
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.post(
    "/alert-rules/evaluate-due",
    response_model=AlertBatchEvaluationSummary,
)
async def evaluate_due_alerts(
    request: DueAlertEvaluationRequest,
    service: AssetObservationServiceDependency,
) -> AlertBatchEvaluationSummary:
    try:
        result = service.evaluate_due_alerts(request.profile_id, request.evaluated_at)
        logger.info(
            "asset observation write completed",
            operation="evaluate_due_alerts",
            profile_id=request.profile_id,
            evaluated=result.evaluated,
            triggered=result.triggered,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.patch("/alert-rules/{rule_id}/status", response_model=AlertRule)
async def update_alert_rule_status(
    rule_id: str,
    request: AlertRuleStatusRequest,
    service: AssetObservationServiceDependency,
) -> AlertRule:
    try:
        result = service.update_alert_rule_status(rule_id, request.status)
        logger.info(
            "asset observation write completed",
            operation="update_alert_rule_status",
            rule_id=rule_id,
            rule_status=request.status.value,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.get("/alert-events", response_model=list[AlertEvent])
async def list_alert_events(
    service: AssetObservationServiceDependency,
    rule_id: str | None = None,
) -> list[AlertEvent]:
    try:
        return service.list_alert_events(rule_id)
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.post("/alert-events/{event_id}/acknowledge", response_model=AlertEvent)
async def acknowledge_alert_event(
    event_id: str,
    service: AssetObservationServiceDependency,
) -> AlertEvent:
    try:
        return service.acknowledge_alert_event(event_id)
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.post("/alert-events/{event_id}/resolve", response_model=AlertEvent)
async def resolve_alert_event(
    event_id: str,
    service: AssetObservationServiceDependency,
) -> AlertEvent:
    try:
        return service.resolve_alert_event(event_id)
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.get("/notifications", response_model=list[Notification])
async def list_notifications(
    profile_id: ProfileIdQuery,
    service: AssetObservationServiceDependency,
    unread_only: bool = False,
    status_filter: Annotated[NotificationStatus | None, Query(alias="status")] = None,
) -> list[Notification]:
    try:
        return service.list_notifications(
            profile_id,
            unread_only,
            status_filter.value if status_filter is not None else None,
        )
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)


@router.patch("/notifications/{notification_id}/delivery", response_model=Notification)
async def mark_notification_delivery(
    notification_id: str,
    request: NotificationDeliveryRequest,
    service: AssetObservationServiceDependency,
) -> Notification:
    try:
        result = service.mark_notification_delivery(
            notification_id,
            request.status.value,
            expected_status=request.expected_status.value,
        )
        logger.info(
            "asset observation write completed",
            operation="mark_notification_delivery",
            notification_id=notification_id,
            notification_channel="desktop",
            delivery_status=request.status.value,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - translate unexpected failures to a safe 500
        _raise_safe_http_error(exc)
