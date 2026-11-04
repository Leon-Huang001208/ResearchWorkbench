"""Trusted Host contexts and stable validation identities, never HTTP payloads."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .engine import digest, stamp
from .profiles import PROFILE_VERSION, profile_for


@dataclass(frozen=True)
class ScoreContext:
    index_id: str
    as_of: str
    proxy: object
    source_contract_digest: str
    source_refs: tuple[dict, ...]
    qualification_receipts: tuple[str, ...]


@dataclass(frozen=True)
class FactorPoint:
    index_id: str
    as_of: str
    inputs_sha256: str
    axes: dict
    source_receipts: dict


@dataclass(frozen=True)
class OverlayContext:
    index_id: str
    as_of: str
    calendar: object
    events: tuple[dict, ...]
    holidays: tuple[dict, ...]
    source_refs: tuple[dict, ...]
    source_version: str
    qualification_receipts: tuple[str, ...]


def qualified_receipts(context):
    return (
        isinstance(context.qualification_receipts, tuple)
        and 1 <= len(context.qualification_receipts) <= 200
        and all(isinstance(value, str) and value for value in context.qualification_receipts)
        and isinstance(context.source_refs, tuple)
        and 1 <= len(context.source_refs) <= 200
    )


def scoring_identity(index_id, proxy, *, role="base_score", family=None, direction=None, rule=None):
    """Derive structural identity; training bytes and today's data are separate."""
    from ..event_studies.contracts import (
        SOURCE_CONTRACT_DIGEST,
        STRATEGY_PROTOCOL,
        Proxy,
        execution_contract,
        proxy_identity,
        rule_contract,
    )

    if not isinstance(proxy, Proxy) or proxy.index_id != index_id or not proxy.exact_tracking:
        raise ValueError("market_score_proxy_identity_invalid")
    return {
        "index_id": index_id,
        "horizon": 20,
        "role": role,
        "profile_sha256": digest(profile_for(index_id)),
        "signal_rule_sha256": digest(rule_contract(role, PROFILE_VERSION, family, direction, rule)),
        "execution_rule_sha256": digest(execution_contract()),
        "proxy_identity_sha256": digest(proxy_identity(proxy)),
        "strategy_protocol": STRATEGY_PROTOCOL,
        "source_contract_digest": SOURCE_CONTRACT_DIGEST,
    }


def context_identity(
    context, index_id, as_of, *, role="base_score", family=None, direction=None, rule=None
):
    from ..event_studies.contracts import SOURCE_CONTRACT_DIGEST, Proxy

    if not isinstance(context, ScoreContext) or not isinstance(context.proxy, Proxy):
        raise TypeError("market_score_context_required")
    cutoff = stamp(as_of)
    if (
        context.index_id != index_id
        or stamp(context.as_of) != cutoff
        or not qualified_receipts(context)
    ):
        raise ValueError("market_score_context_binding_invalid")
    if (
        context.source_contract_digest != SOURCE_CONTRACT_DIGEST
        or stamp(context.proxy.known_at.isoformat()) > cutoff
    ):
        raise ValueError("market_score_source_contract_invalid")
    day = cutoff.astimezone(ZoneInfo(profile_for(index_id)["timezone"])).date()
    if context.proxy.listed_on > day or not any(
        rule.from_date <= day <= rule.until_date and rule.known_at <= cutoff
        for rule in context.proxy.rules
    ):
        raise ValueError("market_score_current_proxy_rules_unknown")
    return scoring_identity(
        index_id, context.proxy, role=role, family=family, direction=direction, rule=rule
    )
