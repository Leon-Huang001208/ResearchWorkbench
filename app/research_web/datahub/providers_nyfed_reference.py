"""Pure NYFed raw projection and fixed, source-qualified SOFRAI dictionary.

Publication schedules describe methodology, never historical availability.
"""

import copy
import json
import math
from datetime import datetime

from core.observability import get_logger

log = get_logger(__name__)
NYFED_RATES_CONTRACT = "nyfed-rates-native-v3"
SOFRAI_FIELDS = frozenset({"average30day", "average90day", "average180day", "index"})
RATE_PERCENT_FIELDS = frozenset(
    {
        "percentRate",
        "percentPercentile1",
        "percentPercentile25",
        "percentPercentile75",
        "percentPercentile99",
        "targetRateFrom",
        "targetRateTo",
        "intraDayLow",
        "intraDayHigh",
        "standardDeviation",
    }
)
_REFERENCES = (
    (
        "methods",
        "https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates",
        "f6e7ee14b49c8d436bcd9e549db00b5b769e1a365040f0b88cf25e3f504f052f",
    ),
    (
        "averages",
        "https://www.newyorkfed.org/markets/reference-rates/sofr-averages-and-index",
        "d1569ec94b0380d600c8466267554e255f0ad939a2035d30cdcdae1ea3ec69ab",
    ),
    (
        "launch",
        "https://www.newyorkfed.org/markets/opolicy/operating_policy_200212",
        "eef93fca61c11c889ad5a83368f8ee21516e503868b550b2fef81a7b632ccf32",
    ),
    (
        "api_documentation",
        "https://markets.newyorkfed.org/static/docs/markets-api.html",
        "c1ab76a0e006e7f16c5ba4660716f2ade0f8a76e58dbbe7124d73a9fbf98cd2c",
    ),
    (
        "api_schema",
        "https://markets.newyorkfed.org/static/docs/markets-api.yml",
        "5dbb331d86b91bfc115be9b5fe9c46735833a4f7280d33e4327e8acf7ad30d2b",
    ),
)


def nyfed_metadata():
    """Return fresh fixed metadata; reference hashes cover original decoded HTTP bodies."""
    return {
        "schema_version": NYFED_RATES_CONTRACT,
        "provider_semantics_revision": NYFED_RATES_CONTRACT,
        "availability_basis": "first_observed",
        "revision_policy": "first_observed_not_historical_vintage",
        "historical_point_in_time": False,
        "formal_backtest_eligible": False,
        "field_dictionary_evidence": {
            "references": [
                {
                    "name": name,
                    "url": url,
                    "sha256": digest,
                    "hash_scope": "original_http_decoded_body",
                }
                for name, url, digest in _REFERENCES
            ],
            "api_schema": {
                "reference": "api_schema",
                "documentation_reference": "api_documentation",
                "component": "components.schemas.sofrai-record",
                "schema_document_version": "1.0",
                "type_selector": {"field": "type", "value": "SOFRAI", "schema_type": "string"},
                "number_fields": ["average30day", "average90day", "average180day", "index"],
                "revision_indicator": {"field": "revisionIndicator", "schema_type": "string"},
                "search_path": "/api/rates/all/search.{format}",
                "date_filters": {"startDate": "inclusive", "endDate": "inclusive"},
            },
            "sofrai": {
                "applies_to_type": "SOFRAI",
                "average_fields": ["average30day", "average90day", "average180day"],
                "average_unit": "percent",
                "day_count": "ACT/360",
                "windows": [30, 90, 180],
                "window_unit": "calendar_days",
                "compounding": "daily_business_day_compounded_trailing_average_annualized",
                "nonbusiness_days": "simple_interest_at_preceding_business_day_rate",
                "average_rounding_decimals": 5,
                "index_unit": "index",
                "index_meaning": "dimensionless_cumulative_compound_factor",
                "index_base_value": "1.00000000",
                "index_base_date": "2018-04-02",
                "index_rounding_decimals": 8,
                "first_official_publication_date": "2020-03-02",
                "value_policy": "source_values_unchanged_no_recalculation",
                "rounded_index_averages": "fifth_decimal_equality_not_guaranteed_no_reconstruction",
            },
            "publication": {
                "applies_to_type": "SOFRAI",
                "effectiveDate": "value_reference_date_not_available_at",
                "sofrai_publication_day": "same_business_day_as_value_date",
                "sofr_overnight_publication_day": "next_business_day_after_value_date",
                "scheduled_publication": "shortly_after_approximately_08:00_America/New_York",
                "same_day_revision": "approximately_14:30_America/New_York",
                "actual_record_availability": False,
                "historical_vintage_evidence": False,
            },
            "revisionIndicator": {
                "meaning": "source_flag_preserved_unknown_flags_not_interpreted",
                "revision_timestamp": False,
                "historical_revision_proof": False,
            },
        },
    }


def nyfed_fields(rows):
    """Apply SOFRAI units only to its fields; retain ordinary rate field meanings."""
    fields = {key: {"type": "source", "unit": "provider_defined"} for row in rows for key in row}
    fields["effectiveDate"] = {
        "type": "date",
        "unit": "date",
        "role": "reference_period_not_available_at",
    }
    for key in fields:
        if key in SOFRAI_FIELDS:
            fields[key] = {
                "type": "number",
                "unit": "index" if key == "index" else "percent",
                "applies_to_type": "SOFRAI",
            }
        elif key in RATE_PERCENT_FIELDS:
            fields[key] = {"type": "number", "unit": "percent"}
        elif key == "volumeInBillions":
            fields[key] = {"type": "number", "unit": "USD_billion"}
    return fields


def _day(value):
    if (
        not isinstance(value, str)
        or datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") != value
    ):
        raise ValueError("invalid_date")
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("invalid_json_constant")


def nyfed_projection(raw, args):
    """Validate strict original JSON and bounded observation identities without coercion."""
    try:
        body = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject_constant)
        if (
            not isinstance(body, dict)
            or set(body) != {"refRates"}
            or not isinstance(body["refRates"], list)
        ):
            raise ValueError("invalid_nyfed_envelope")
        start, end = (_day(args["params"][key]) for key in ("start", "end"))
        if start > end:
            raise ValueError("invalid_date_range")
        rows, seen = body["refRates"], set()
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError("invalid_rate_row")
            day, kind = _day(row["effectiveDate"]), row["type"]
            if (
                not isinstance(kind, str)
                or kind not in {"EFFR", "OBFR", "TGCR", "BGCR", "SOFR", "SOFRAI"}
                or not start <= day <= end
                or (day, kind) in seen
            ):
                raise ValueError("rate_identity_mismatch")
            if kind != "SOFRAI" and SOFRAI_FIELDS & row.keys():
                raise ValueError("sofrai_field_scope_mismatch")
            required = SOFRAI_FIELDS if kind == "SOFRAI" else {"percentRate", "volumeInBillions"}
            for key in required | (RATE_PERCENT_FIELDS & row.keys()):
                value = row[key]
                if (
                    value is not None
                    and value != "null"
                    and (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float, str))
                        or not math.isfinite(float(value))
                    )
                ):
                    raise ValueError("invalid_rate_numeric")
            if "revisionIndicator" in row and not isinstance(row["revisionIndicator"], str):
                raise ValueError("invalid_revision_flag")
            seen.add((day, kind))
        return copy.deepcopy(rows)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        log.warning("nyfed_projection_invalid", error_type=type(exc).__name__)
        raise ValueError("nyfed_projection_invalid") from exc
