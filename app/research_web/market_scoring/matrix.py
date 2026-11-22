"""Bounded causal factor matrices; histories are reconstructed, never duplicated."""

import math
from statistics import fmean
from zoneinfo import ZoneInfo

from .engine import _number, _validate_observation, digest, stamp
from .native_inputs import reject
from .profiles import AXES, PROFILE_VERSION, profile_for

FORMAT = "factor-matrix-v1"
REFERENCE_FORMAT = "factor-matrix-ref-v1"


def validate_matrix(native, index_id):
    if len(native.rows) != 1 or not isinstance(native.rows[0], dict):
        reject("event_factor_matrix_contract_invalid")
    value = native.rows[0].get("factor_bundle")
    if (
        not isinstance(value, dict)
        or value.get("format") != FORMAT
        or value.get("index_id") != index_id
        or value.get("profile_version") != PROFILE_VERSION
    ):
        reject("event_factor_matrix_contract_invalid")
    columns, rows = value.get("columns"), value.get("rows")
    if (
        not isinstance(columns, dict)
        or not columns
        or set(columns) - set(AXES)
        or not isinstance(rows, list)
        or not 1 <= len(rows) <= 20000
    ):
        reject("event_factor_matrix_dimensions_invalid")
    definitions = profile_for(index_id)["axes"]
    days, zone = [], ZoneInfo(profile_for(index_id)["timezone"])
    for axis, column in columns.items():
        definition = definitions[axis]
        if (
            not isinstance(column, dict)
            or any(column.get(key) != definition[key] for key in ("metric", "unit", "scope"))
            or native.manifest.get("fields", {}).get(column["metric"], {}).get("unit")
            != column["unit"]
        ):
            reject("event_factor_matrix_unit_or_metric_invalid")
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("values"), dict)
            or set(row["values"]) != set(columns)
            or any(not _number(number) for number in row["values"].values())
        ):
            reject("event_factor_matrix_values_invalid")
        days.append(stamp(row.get("as_of")).astimezone(zone).date())
        if stamp(row.get("observed_at", row["as_of"])).astimezone(zone).date() != days[-1]:
            reject("event_factor_matrix_observed_day_mismatch")
        for axis, scalar in row["values"].items():
            definition = definitions[axis]
            if (
                (definition["normalization"] == "share" and not 0 <= scalar <= 1)
                or (definition["normalization"] == "signed_share" and not -1 <= scalar <= 1)
                or (
                    definition["metric"] in {"volatility_20d", "put_call_volume_ratio"}
                    and scalar < 0
                )
                or (
                    definition["metric"] in {"median_positive_pe", "index_positive_pe"}
                    and scalar <= 0
                )
            ):
                reject("event_factor_matrix_metric_domain_invalid")
    if days != sorted(set(days)):
        reject("event_factor_matrix_dates_invalid")
    return value


def observation(native, reference, index_id, matrix, row, axis):
    from datetime import timedelta

    column = matrix["columns"][axis]
    observed = stamp(row.get("observed_at", row["as_of"]))
    day = (
        stamp(row["as_of"])
        .astimezone(ZoneInfo(profile_for(index_id)["timezone"]))
        .date()
        .isoformat()
    )
    floor = native.floor(day, column["metric"])
    published = max(stamp(row.get("published_at", observed.isoformat())), floor)
    known = max(published, stamp(row.get("known_at", published.isoformat())), floor)
    return {
        **column,
        "provider": native.manifest["provider"],
        "value": row["values"][axis],
        "as_of": observed.isoformat(),
        "published_at": published.isoformat(),
        "known_at": known.isoformat(),
        "valid_until": min(
            stamp(row.get("valid_until", (observed + timedelta(days=1)).isoformat())),
            observed + timedelta(days=7),
        ).isoformat(),
        "source_ref": reference,
    }


def receipt(native, item):
    return {
        "status": "qualified",
        "source_ref": item["source_ref"],
        "observation_sha256": digest(item),
        "scope_id": item["scope_id"],
        "authorization_revision": native.configuration,
        "pit_receipt": (
            "canonical-warehouse:" + native.formal_digest
            if native.formal_digest
            else "first-observed:" + native.manifest["manifest_sha256"]
        ),
    }


def point(native, reference, index_id, as_of):
    matrix = validate_matrix(native, index_id)
    cutoff, zone = stamp(as_of), ZoneInfo(profile_for(index_id)["timezone"])
    matched = [row for row in matrix["rows"] if stamp(row["as_of"]) == cutoff]
    if len(matched) != 1:
        reject("event_factor_matrix_cutoff_missing")
    axes, receipts = {}, {}
    for axis in matrix["columns"]:
        item = observation(native, reference, index_id, matrix, matched[0], axis)
        history = []
        for row in matrix["rows"]:
            if stamp(row["as_of"]).astimezone(zone).date() >= cutoff.astimezone(zone).date():
                break
            previous = observation(native, reference, index_id, matrix, row, axis)
            if stamp(previous["known_at"]) <= cutoff:
                history.append(
                    {key: previous[key] for key in ("as_of", "known_at", "value", "unit")}
                )
        item["history"] = history[-profile_for(index_id)["axes"][axis]["lookback_observations"] :]
        axes[axis], receipts[axis] = item, receipt(native, item)
    return axes, receipts


def stream_signals(native, reference, index_id):
    """O(rows²) scalar filtering, O(rows) storage, no duplicated histories/JSON.

    At 20k maximum rows, late-known facts stay excluded until their actual
    availability. A future revision never replaces earlier missing knowledge.
    """
    matrix, profile = validate_matrix(native, index_id), profile_for(index_id)
    previous = {axis: [] for axis in matrix["columns"]}
    for row in matrix["rows"]:
        cutoff, scores, counts, invalid = stamp(row["as_of"]), {}, {}, False
        for axis in matrix["columns"]:
            item = observation(native, reference, index_id, matrix, row, axis)
            definition = profile["axes"][axis]
            if _validate_observation(item, definition, profile, cutoff, receipt(native, item)):
                invalid = True
                continue
            history = [number for known, number in previous[axis] if known <= cutoff][
                -definition["lookback_observations"] :
            ]
            counts[axis] = len(history)
            value, mode = item["value"], definition["normalization"]
            if mode in {"share", "signed_share"}:
                low = 0 if mode == "share" else -1
                if not low <= value <= 1:
                    invalid = True
                else:
                    scores[axis] = 100 * value if mode == "share" else 50 * (1 + value)
            elif len(history) >= definition["minimum_observations"]:
                rank = (
                    100
                    * (
                        sum(number < value for number in history)
                        + 0.5 * sum(number == value for number in history)
                    )
                    / len(history)
                )
                scores[axis] = 100 - rank if definition["inverse"] else rank
        score = (
            fmean(scores.values())
            if set(scores) == set(AXES) and all(math.isfinite(value) for value in scores.values())
            else None
        )
        yield {
            "as_of": row["as_of"],
            "score": score,
            "candidate_only": True,
            "status": (
                "DATA_INELIGIBLE"
                if invalid
                else "ready" if score is not None else "INSUFFICIENT_SAMPLE"
            ),
            "counts": counts,
        }
        for axis in matrix["columns"]:
            item = observation(native, reference, index_id, matrix, row, axis)
            previous[axis].append((stamp(item["known_at"]), item["value"]))
