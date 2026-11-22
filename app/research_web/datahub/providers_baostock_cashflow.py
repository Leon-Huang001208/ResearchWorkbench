"""Reviewed BaoStock cash-flow ratios; pure raw projection shared with storage."""

from __future__ import annotations

import json
import math

from core.observability import get_logger

from .providers import MAX_QUERY_BYTES, ProviderError

log = get_logger(__name__)
CASH_FLOW_SCHEMA = "baostock-quarterly-cash-flow-v1"
CASH_FLOW_FIELDS = (
    "code,pubDate,statDate,CAToAsset,NCAToAsset,tangibleAssetToAsset,"
    "ebitToInterest,CFOToOR,CFOToNP,CFOToGr"
)


def cash_flow_fields() -> dict:
    """Return fresh reviewed field metadata without inferring a numeric scale."""
    return {
        key: {
            "unit": None,
            "currency": None,
            "semantic": "provider_native_ratio",
            "scale": "unverified",
        }
        for key in CASH_FLOW_FIELDS.split(",")[3:]
    }


def cash_flow_metadata() -> dict:
    from .providers_baostock import FINANCIAL_DICTIONARY, FINANCIAL_DICTIONARY_SHA256

    return {
        "schema_version": CASH_FLOW_SCHEMA,
        "provider_semantics_revision": CASH_FLOW_SCHEMA,
        "statement": "cash_flow",
        "upstream_id": "baostock",
        "availability_basis": "first_observed",
        "historical_point_in_time": False,
        "formal_backtest_eligible": False,
        "redistribution_rights": "unverified",
        "projection_scope": "quarterly_cash_flow_ratios_native",
        "reporting_basis": "unverified",
        "field_dictionary_evidence": {
            "source_url": FINANCIAL_DICTIONARY,
            "document_sha256": FINANCIAL_DICTIONARY_SHA256,
            "fields": CASH_FLOW_FIELDS.split(",")[3:],
            "unit": None,
            "currency": None,
            "scale": "unverified",
        },
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def cash_flow_projection(raw: bytes, asset: str, period: str) -> tuple[list[dict], list[str]]:
    """Reject malformed SDK records; blanks are missing, zero/negative stay native."""
    from .providers_baostock import _asset, _financial_date

    if not isinstance(raw, bytes) or len(raw) > MAX_QUERY_BYTES:
        raise ProviderError("vendor_schema_invalid")
    code = _asset(asset)
    _financial_date(period)
    if period < "2017-01-01" or period[5:] not in {"03-31", "06-30", "09-30", "12-31"}:
        raise ProviderError("vendor_schema_invalid")
    try:
        records = json.loads(raw, object_pairs_hook=_unique_object)
        if not isinstance(records, list) or len(records) > 1:
            raise ValueError("invalid_records")
        rows, missing = [], []
        for record in records:
            if not isinstance(record, dict) or set(record) != set(CASH_FLOW_FIELDS.split(",")):
                raise ValueError("invalid_fields")
            if any(not isinstance(value, str) for value in record.values()):
                raise ValueError("nonstring_value")
            if record["code"] != code or record["statDate"] != period:
                raise ValueError("identity_mismatch")
            _financial_date(record["statDate"])
            publication = _financial_date(record["pubDate"]) if record["pubDate"] else None
            if publication is not None and publication < period:
                raise ValueError("publication_precedes_report")
            numbers = {}
            for key in cash_flow_fields():
                value = None if record[key] == "" else float(record[key])
                if value is not None and not math.isfinite(value):
                    raise ValueError("nonfinite_value")
                numbers[key] = value
            if publication is None:
                missing.append("publication_date")
            if all(value is None for value in numbers.values()):
                missing.append("cash_flow_metrics")
            rows.append(
                {
                    **record,
                    **numbers,
                    "asset": asset.upper(),
                    "report_period": period,
                    "publication_date": publication,
                    "publication_precision": "date" if publication is not None else None,
                }
            )
        return rows, missing
    except (ValueError, TypeError, UnicodeError, RecursionError, ProviderError):
        log.warning("baostock_cash_flow_projection_rejected")
        raise ProviderError("vendor_schema_invalid") from None
