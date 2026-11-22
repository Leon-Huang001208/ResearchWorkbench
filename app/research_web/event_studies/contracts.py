"""Strict internal study inputs. HTTP accepts evidence references, never these arrays."""

from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from itertools import pairwise
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.observability import get_logger

log = get_logger(__name__)
POLICY = "event-study-v1"
STRATEGY_PROTOCOL = "long-only-score-weight-next-open-v1"
SOURCE_CONTRACT_DIGEST = sha256(
    b"index-factor-pit-proxy-unadjusted-actions-datedrules-v1"
).hexdigest()


def rule_contract(role, profile_version, family=None, direction=None, rule=None):
    return {
        "role": role,
        "family": family,
        "direction": direction,
        "rule": rule,
        "horizon": 20,
        "profile_version": profile_version,
        "policy_version": POLICY,
        "strategy_protocol": STRATEGY_PROTOCOL,
    }


def execution_contract():
    return {
        "strategy_protocol": STRATEGY_PROTOCOL,
        "commission_bps": 10,
        "slippage_bps": 10,
        "base_weight": "score/100",
        "rebalance": "daily_next_open",
        "taxlotsettlement": "verified_dated_rules",
    }


def proxy_identity(proxy):
    if proxy is None:
        return None
    return {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in proxy.model_dump().items()
        if key
        in {
            "symbol",
            "index_id",
            "market",
            "currency",
            "exchange",
            "listed_on",
            "exact_tracking",
            "price_basis",
        }
    }


class StudyError(ValueError):
    def __init__(self, code: str):
        self.code = code
        log.warning("event_study_rejected", code=code)
        super().__init__(code)


def stamp(value):
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise StudyError("timezone_required") from None


def number(value):
    try:
        if isinstance(value, bool):
            raise TypeError
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError
        return result
    except (ValueError, ArithmeticError, TypeError):
        raise StudyError("invalid_number") from None


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Session(Contract):
    day: date
    opens: datetime
    closes: datetime
    half_day: bool = False
    known_at: datetime | None = None
    announcement_version_ref: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def coherent(self):
        if stamp(self.opens) >= stamp(self.closes):
            raise ValueError("session_times_invalid")
        if (self.known_at is None) != (self.announcement_version_ref is None):
            raise ValueError("session_announcement_pair_required")
        if self.known_at is not None:
            stamp(self.known_at)
        return self


class Calendar(Contract):
    exchange: str = Field(min_length=1, max_length=32)
    timezone: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=128)
    source_ref: str = Field(min_length=1, max_length=256)
    known_at: datetime
    announcement_known_at: datetime | None = None
    announcement_version_ref: str | None = Field(default=None, max_length=256)
    sessions: list[Session] = Field(min_length=2, max_length=20000)

    @model_validator(mode="after")
    def coherent(self):
        zone = ZoneInfo(self.timezone)
        stamp(self.known_at)
        if (self.announcement_known_at is None) != (self.announcement_version_ref is None):
            raise ValueError("calendar_announcement_pair_required")
        if self.announcement_known_at is not None:
            stamp(self.announcement_known_at)
        days = [s.day for s in self.sessions]
        if days != sorted(set(days)):
            raise ValueError("calendar_not_strictly_ordered")
        for session in self.sessions:
            if any(
                t.astimezone(zone).date() != session.day for t in (session.opens, session.closes)
            ):
                raise ValueError("session_local_day_mismatch")
        return self


class TradingRule(Contract):
    from_date: date
    until_date: date
    lot: int = Field(ge=1, le=100000)
    settlement_sessions: int = Field(ge=0, le=10)
    sell_after_sessions: int = Field(default=0, ge=0, le=10)
    tax_buy_bps: Decimal = Field(ge=0, le=1000)
    tax_sell_bps: Decimal = Field(ge=0, le=1000)
    price_tick: Decimal = Field(default=Decimal(".01"), gt=0)
    source_ref: str = Field(min_length=1, max_length=256)
    known_at: datetime

    @model_validator(mode="after")
    def coherent(self):
        stamp(self.known_at)
        if self.from_date > self.until_date:
            raise ValueError("trading_rule_range_invalid")
        return self


class Proxy(Contract):
    symbol: str = Field(min_length=1, max_length=64)
    index_id: str
    market: Literal["CN", "US", "HK"]
    currency: Literal["CNY", "USD", "HKD"]
    exchange: str
    source_ref: str = Field(min_length=1, max_length=256)
    known_at: datetime
    listed_on: date
    exact_tracking: bool
    price_basis: Literal["unadjusted"]
    rules: list[TradingRule] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def coherent(self):
        from .registry import INDICES

        stamp(self.known_at)
        identity = INDICES.get(self.index_id)
        if identity is None or any(getattr(self, k) != identity[k] for k in ("market", "currency")):
            raise ValueError("proxy_index_identity_mismatch")
        rules = sorted(self.rules, key=lambda r: r.from_date)
        if any(a.until_date >= b.from_date for a, b in pairwise(rules)):
            raise ValueError("trading_rules_overlap")
        return self


class StudySpec(Contract):
    title: str = Field(min_length=1, max_length=200)
    role: Literal["base_score", "event_overlay", "calendar_overlay"]
    index_id: str
    horizon: Literal[20] = 20
    profile_version: str = Field(min_length=1, max_length=128)
    frozen_event_ref: dict | None = None
    bundle_ref: dict
    hypothesis: str = Field(min_length=1, max_length=256)
    family_id: str = Field(default="event-calendar-v1", min_length=1, max_length=128)
    family: str | None = Field(default=None, max_length=100)
    direction: int | None = Field(default=None, strict=True, ge=-1, le=1)
    rule: str | None = Field(default=None, max_length=100)
    objective: Literal["risk_return_improvement"] = "risk_return_improvement"

    @model_validator(mode="after")
    def coherent(self):
        from ..market_scoring.profiles import PROFILE_VERSION
        from .registry import INDICES

        if self.index_id not in INDICES:
            raise ValueError("index_unknown")
        if self.profile_version != PROFILE_VERSION:
            raise ValueError("study_profile_version_unknown")
        if self.role == "event_overlay" and self.frozen_event_ref is None:
            raise ValueError("event_freeze_required")
        if self.role != "base_score":
            from .calendars import EVENT_RULES, FAMILIES

            if (
                self.family not in FAMILIES
                or type(self.direction) is not int
                or self.direction not in (-1, 1)
            ):
                raise ValueError("overlay_family_and_direction_required")
            if self.rule is not None and self.rule not in FAMILIES[self.family]:
                raise ValueError("overlay_rule_family_mismatch")
            if (self.role == "event_overlay") != (FAMILIES[self.family] == EVENT_RULES):
                raise ValueError("overlay_role_family_mismatch")
        elif self.family is not None or self.direction is not None or self.rule is not None:
            raise ValueError("base_score_has_no_event_rule")
        if any(
            set(ref) != {"id", "revision"}
            or not isinstance(ref["id"], str)
            or isinstance(ref["revision"], bool)
            or not isinstance(ref["revision"], int)
            or ref["revision"] < 1
            for ref in [self.bundle_ref]
            + ([self.frozen_event_ref] if self.frozen_event_ref else [])
        ):
            raise ValueError("immutable_reference_required")
        return self
