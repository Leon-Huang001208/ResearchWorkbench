"""Deterministic research scores from receipt-bound observations and holdouts.

Source receipts are created by a trusted Host verifier, never by the HTTP caller.
Historical validation here does not activate a production score or allocation.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .profiles import AXES, PROFILE_VERSION, VALIDATION_POLICY, profile_for

log = get_logger(__name__)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def stamp(value):
    if not isinstance(value, str):
        raise TypeError("market_score_time_invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("market_score_time_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("market_score_timezone_required")
    return parsed


def _number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def _ref(value):
    return (
        isinstance(value, dict)
        and isinstance(value.get("id"), str)
        and re.fullmatch(r"[a-f0-9]{32}", value["id"])
        and isinstance(value.get("sha256"), str)
        and re.fullmatch(r"[a-f0-9]{64}", value["sha256"])
    )


def _validate_observation(observation, definition, profile, cutoff, receipt):
    if not isinstance(observation, dict):
        return ["observation_missing"]
    reasons = []
    if observation.get("metric") != definition["metric"]:
        reasons.append("metric_not_in_frozen_profile")
    if observation.get("unit") != definition["unit"]:
        reasons.append("metric_unit_mismatch")
    if observation.get("provider") not in definition["providers"]:
        reasons.append("provider_not_in_frozen_profile")
    scope_id = profile["index_id"] if definition["scope"] == "index" else profile["market"]
    if observation.get("scope") != definition["scope"] or observation.get("scope_id") != scope_id:
        reasons.append("scope_mismatch")
    if not _ref(observation.get("source_ref")):
        reasons.append("source_reference_invalid")
    value = observation.get("value")
    if not _number(value):
        reasons.append("non_finite_metric")
    elif definition["metric"] in {"volatility_20d", "put_call_volume_ratio"} and value < 0:
        reasons.append("metric_domain_invalid")
    elif definition["metric"] in {"median_positive_pe", "index_positive_pe"} and value <= 0:
        reasons.append("positive_valuation_required")
    try:
        observed, public, known, expiry = [
            stamp(observation.get(key))
            for key in ("as_of", "published_at", "known_at", "valid_until")
        ]
        if not observed <= public <= known <= cutoff < expiry:
            reasons.append("source_time_ineligible")
    except (TypeError, ValueError):
        reasons.append("source_time_invalid")
    try:
        bound = digest(observation)
    except (TypeError, ValueError):
        bound = None
    if not isinstance(receipt, dict) or receipt.get("status") != "qualified":
        reasons.append("host_source_receipt_required")
    elif not (
        receipt.get("source_ref") == observation.get("source_ref")
        and receipt.get("observation_sha256") == bound
        and receipt.get("scope_id") == scope_id
        and isinstance(receipt.get("authorization_revision"), str)
        and bool(receipt["authorization_revision"])
        and isinstance(receipt.get("pit_receipt"), str)
        and bool(receipt["pit_receipt"])
    ):
        reasons.append("observation_receipt_mismatch")
    return reasons


def _historical_values(observation, definition, cutoff, timezone):
    history = observation.get("history")
    if not isinstance(history, list) or len(history) > 20000:
        raise ValueError("history_missing_or_oversized")
    prior = {}
    zone = ZoneInfo(timezone)
    observed = stamp(observation["as_of"])
    for row in history:
        if (
            not isinstance(row, dict)
            or not _number(row.get("value"))
            or row.get("unit") != definition["unit"]
        ):
            raise ValueError("history_metric_invalid")
        moment, known = stamp(row.get("as_of")), stamp(row.get("known_at"))
        if moment.astimezone(zone).date() >= observed.astimezone(zone).date() or known > cutoff:
            continue
        if known < moment:
            raise ValueError("history_time_invalid")
        day = moment.astimezone(zone).date().isoformat()
        if day in prior and prior[day][1] != row["value"]:
            raise ValueError("history_revision_conflict")
        prior[day] = (moment, row["value"])
    return [value for _, value in sorted(prior.values())[-definition["lookback_observations"] :]]


def _axis_score(observation, definition, profile, cutoff, receipt):
    reasons = _validate_observation(observation, definition, profile, cutoff, receipt)
    if reasons:
        return {"score": None, "status": "DATA_INELIGIBLE", "reasons": reasons}
    value, normalization = observation["value"], definition["normalization"]
    if normalization in {"share", "signed_share"}:
        minimum = 0 if normalization == "share" else -1
        if not minimum <= value <= 1:
            return {"score": None, "status": "DATA_INELIGIBLE", "reasons": ["share_out_of_range"]}
        score = 100 * value if normalization == "share" else 50 * (1 + value)
        return {
            "score": score,
            "status": "QUALIFIED",
            "reasons": [],
            "sample_count": None,
            "metric": definition["metric"],
        }
    try:
        history = _historical_values(observation, definition, cutoff, profile["timezone"])
    except (TypeError, ValueError) as exc:
        return {"score": None, "status": "DATA_INELIGIBLE", "reasons": [str(exc)]}
    if len(history) < definition["minimum_observations"]:
        return {
            "score": None,
            "status": "INSUFFICIENT_SAMPLE",
            "reasons": ["normalization_history_insufficient"],
            "sample_count": len(history),
        }
    rank = (
        100
        * (sum(item < value for item in history) + 0.5 * sum(item == value for item in history))
        / len(history)
    )
    return {
        "score": 100 - rank if definition["inverse"] else rank,
        "status": "QUALIFIED",
        "reasons": [],
        "sample_count": len(history),
        "metric": definition["metric"],
    }


def validation_reasons(
    report, index_id, evidence_sha256, cutoff, *, role="base_score", identity=None
):
    if not isinstance(report, dict):
        return ["holdout_validation_required"]
    reasons = []
    expected = {
        "status": "VALIDATED",
        "role": role,
        "index_id": index_id,
        "horizon": 20,
        "profile_version": PROFILE_VERSION,
        "policy_version": VALIDATION_POLICY,
    }
    if any(report.get(key) != value for key, value in expected.items()):
        reasons.append("validation_binding_mismatch")
    if any(
        not isinstance(report.get(key), str) or not report[key]
        for key in ("policy_version", "study_id", "holdout_id")
    ):
        reasons.append("sealed_holdout_identity_required")
    historical = report.get("training_holdout_evidence_sha256")
    if (
        not isinstance(historical, str)
        or not re.fullmatch(r"[a-f0-9]{64}", historical)
        or report.get("evidence_sha256", historical) != historical
    ):
        reasons.append("training_holdout_audit_digest_required")
    if report.get("rules_digest") != report.get("signal_rule_sha256"):
        reasons.append("frozen_signal_rule_digest_mismatch")
    from ..event_studies.contracts import (
        SOURCE_CONTRACT_DIGEST,
        STRATEGY_PROTOCOL,
        execution_contract,
        rule_contract,
    )

    structural = {
        "index_id": index_id,
        "horizon": 20,
        "role": role,
        "profile_sha256": digest(profile_for(index_id)),
        "signal_rule_sha256": digest(
            rule_contract(
                role,
                PROFILE_VERSION,
                report.get("family"),
                report.get("direction"),
                report.get("rule"),
            )
        ),
        "execution_rule_sha256": digest(execution_contract()),
        "strategy_protocol": STRATEGY_PROTOCOL,
        "source_contract_digest": SOURCE_CONTRACT_DIGEST,
    }
    if not isinstance(identity, dict) or any(
        identity.get(key) != value or report.get(key) != value for key, value in structural.items()
    ):
        reasons.append("current_strategy_identity_mismatch")
    elif (
        not isinstance(identity.get("proxy_identity_sha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", identity["proxy_identity_sha256"])
        or report.get("proxy_identity_sha256") != identity["proxy_identity_sha256"]
    ):
        reasons.append("current_proxy_identity_mismatch")
    try:
        if not stamp(report.get("valid_from")) <= cutoff < stamp(report.get("expires_at")):
            reasons.append("validation_expired_or_not_yet_valid")
    except (TypeError, ValueError):
        reasons.append("validation_time_invalid")
    return reasons


def compute_score(
    index_id,
    as_of,
    axes,
    *,
    validation=None,
    overlays=(),
    source_receipts=None,
    evidence_sha256=None,
    validation_identity=None,
    overlay_identities=None,
    applicability=None,
):
    """Compute from Host-verified inputs; this function performs no I/O or activation."""
    profile, cutoff = profile_for(index_id), stamp(as_of)
    if not isinstance(axes, dict) or not isinstance(overlays, (list, tuple)) or len(overlays) > 200:
        raise ValueError("market_score_input_invalid")
    receipts = source_receipts if isinstance(source_receipts, dict) else {}
    results = {
        axis: _axis_score(
            axes.get(axis), profile["axes"][axis], profile, cutoff, receipts.get(axis)
        )
        for axis in AXES
    }
    source_days = {
        stamp(axes[axis]["as_of"]).astimezone(ZoneInfo(profile["timezone"])).date()
        for axis in AXES
        if results[axis]["score"] is not None
    }
    if len(source_days) > 1:
        for axis in AXES:
            results[axis] = {
                **results[axis],
                "score": None,
                "status": "DATA_INELIGIBLE",
                "reasons": [*results[axis]["reasons"], "axis_observation_dates_mismatch"],
            }
    ready = all(result["score"] is not None for result in results.values())
    candidate = math.fsum(result["score"] for result in results.values()) / 6 if ready else None
    evidence_sha256 = evidence_sha256 or digest(
        {"profile": profile, "index_id": index_id, "as_of": as_of, "axes": axes}
    )
    reasons = validation_reasons(
        validation, index_id, evidence_sha256, cutoff, identity=validation_identity
    )
    base = candidate if ready and not reasons else None
    families, rejected, activity_evidence = {}, [], []
    if base is not None:
        for overlay in overlays:
            overlay_digest = digest(overlay)
            overlay_role = overlay.get("role") if isinstance(overlay, dict) else None
            invalid = (
                validation_reasons(
                    overlay,
                    index_id,
                    evidence_sha256,
                    cutoff,
                    role=overlay_role,
                    identity=(overlay_identities or {}).get(overlay_digest),
                )
                if overlay_role in {"event_overlay", "calendar_overlay"}
                else ["overlay_role_invalid"]
            )
            from .applicability import applicability_reasons

            invalid.extend(
                applicability_reasons(
                    (applicability or {}).get(overlay_digest), overlay, index_id, as_of
                )
            )
            family, direction = overlay.get("family") if isinstance(overlay, dict) else None, (
                overlay.get("direction") if isinstance(overlay, dict) else None
            )
            if (
                invalid
                or not isinstance(family, str)
                or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,100}", family)
                or type(direction) is not int
                or direction not in {-1, 1}
            ):
                rejected.append(
                    {
                        "family": family,
                        "reasons": invalid or ["overlay_family_or_direction_invalid"],
                    }
                )
                continue
            proof = applicability[overlay_digest]
            activity_evidence.append(
                {
                    "family": family,
                    "report_sha256": overlay_digest,
                    "source_version": proof.source_version,
                    "source_refs_sha256": proof.source_refs_sha256,
                    "context_sha256": proof.context_sha256,
                    "event_versions": list(proof.event_versions),
                    "window_start": proof.window_start,
                    "window_end": proof.window_end,
                }
            )
            if family in families and families[family] != direction:
                families[family] = 0
            else:
                families.setdefault(family, direction)
    delta = max(-5, min(5, sum(families.values())))
    status = (
        "VALIDATED"
        if base is not None
        else (
            "DATA_INELIGIBLE"
            if any(result["status"] == "DATA_INELIGIBLE" for result in results.values())
            else "INSUFFICIENT_SAMPLE" if not ready else "VALIDATION_REQUIRED"
        )
    )
    log.info("market_score_computed", index_id=index_id, status=status)
    return {
        "version": PROFILE_VERSION,
        "index_id": index_id,
        "market": profile["market"],
        "horizon": 20,
        "as_of": as_of,
        "axes": results,
        "candidate_score": candidate,
        "base_score": base,
        "overlay_delta": delta,
        "active_families": families,
        "rejected_overlays": rejected,
        "applicability_evidence": activity_evidence,
        "total_score": max(0, min(100, base + delta)) if base is not None else None,
        "status": status,
        "validation_reasons": reasons,
        "evidence_sha256": evidence_sha256,
        "profile_sha256": digest(profile),
        "formal_score_enabled": base is not None,
        "production_enabled": False,
        "allocation": None,
        "cross_market_ranking": False,
    }


def study_signals(index_id, inputs_record_payload, profile_version=PROFILE_VERSION):
    """Compile a trusted frozen series for evaluation; never enables a live score."""
    if (
        profile_version != PROFILE_VERSION
        or not isinstance(inputs_record_payload, dict)
        or inputs_record_payload.get("index_id") != index_id
    ):
        raise ValueError("market_score_profile_or_index_mismatch")
    if inputs_record_payload.get("profile_sha256") is not None and inputs_record_payload[
        "profile_sha256"
    ] != digest(profile_for(index_id)):
        raise ValueError("market_score_profile_changed")
    series = inputs_record_payload.get("series")
    if series is None:
        series = [inputs_record_payload]
    if not isinstance(series, list) or not 1 <= len(series) <= 20000:
        raise ValueError("market_score_series_invalid")
    if any(not isinstance(row, dict) for row in series):
        raise ValueError("market_score_series_invalid")
    signals, seen = [], set()
    bundle_sha256 = digest(inputs_record_payload)
    for row in sorted(series, key=lambda item: stamp(item.get("as_of"))):
        at = stamp(row.get("as_of"))
        if at in seen:
            raise ValueError("market_score_duplicate_time")
        seen.add(at)
        score = compute_score(
            index_id,
            row["as_of"],
            row.get("axes"),
            source_receipts=row.get("source_receipts"),
            evidence_sha256=bundle_sha256,
        )
        signals.append(
            {
                "as_of": row["as_of"],
                "score": score["candidate_score"],
                "status": score["status"],
                "candidate_only": True,
                "evidence_sha256": bundle_sha256,
            }
        )
    return signals
