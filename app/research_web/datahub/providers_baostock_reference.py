"""Pure original-bound profitability projection and narrowly scoped issuer reference."""

from __future__ import annotations

import hashlib
import json

from core.observability import get_logger

from .providers import MAX_QUERY_BYTES, ProviderError, numeric
from .providers_baostock_cashflow import _unique_object

log = get_logger(__name__)
REFERENCE_PDF_URL = "https://static.cninfo.com.cn/finalpage/2026-08-28/1225521898.PDF"
REFERENCE_PDF_SHA256 = "01f41e69ad9dc1b348204b3aa0acf615b2343d402ac00a0ae3895f56e7010f66"
REFERENCE_CELL_HASHES = {
    "netProfit": "5cb7a0f32aea591420bd65e7c5852b8a09963ff42b2c18493917e3d2598ab51c",
    "MBRevenue": "d16fb7aed913dbf8840cf951ca1c2ea6a94949034160f161604f69059a0a0a84",
}

ISSUER_CELL_HASHES = {
    "netProfit": "1a6b52c088200196c636a76fba8990a837969de50f823a4c67a26c88128690a1",
    "MBRevenue": "f4799a462c8169101d6600aeeeeced03b7eded665069ec5ddb6382f132e3a35a",
}


def reference_dictionary() -> dict:
    """Only hashes of reviewed exact vendor strings are distributed with code."""
    return {
        "asset": "600000.SH",
        "report_period": "2026-06-30",
        "source_url": REFERENCE_PDF_URL,
        "document_sha256": REFERENCE_PDF_SHA256,
        "vendor_cell_sha256": dict(REFERENCE_CELL_HASHES),
        "issuer_cell_sha256": dict(ISSUER_CELL_HASHES),
        "issuer_cell_hash_encoding": "sha256_utf8_pdf_text_group_current_column",
        "vendor_cell_hash_encoding": "sha256_utf8_exact_original_string",
        "pdf_pages_one_based": [111, 112],
    }


def _reference(record: dict, asset: str, period: str) -> dict | None:
    if asset.upper() != "600000.SH" or period != "2026-06-30":
        return None
    if any(
        not isinstance(record.get(field), str)
        or hashlib.sha256(record[field].encode()).hexdigest() != digest
        for field, digest in REFERENCE_CELL_HASHES.items()
    ):
        return None
    evidence = {
        **reference_dictionary(),
        "fields": ["netProfit", "MBRevenue"],
        "status": "verified_reference_value_match",
        "equality_scope": "one_asset_one_period_two_fields_not_general_equivalence",
        "period_start": "2026-01-01",
        "period_end": "2026-06-30",
        "reporting_basis": "year_to_date",
        "report_scope": "consolidated_group",
        "issuer_unit": "CNY_million",
        "issuer_unit_scale": 1000000,
        "source_unit": "CNY",
        "netProfit_parent_attributable": False,
        "historical_point_in_time": False,
        "formal_backtest_eligible": False,
        "historical_vintage_verified": False,
        "global_cross_source_equivalence": False,
    }
    if record.get("pubDate") == "2026-08-28":
        evidence["date_conflict"] = {
            "vendor_publication_date": "2026-08-28",
            "issuer_listing_claim": {
                "source_url": "https://news.spdb.com.cn/investor_relation/periodic_report/",
                "date": "2026-08-27",
                "evidence_status": "prior_archive_claim_not_newly_captured",
                "raw_capture_verified": False,
            },
            "exact_publication_instant_verified": False,
            "availability_inferred": False,
        }
    return evidence


def profitability_fields() -> dict:
    from .providers_baostock import FINANCIAL_FIELDS

    fields: dict[str, dict[str, str | None]] = {
        key: {"unit": None, "currency": None} for key in FINANCIAL_FIELDS.split(",")[3:]
    }
    fields.update({key: {"unit": "CNY", "currency": "CNY"} for key in ("netProfit", "MBRevenue")})
    return fields


def profitability_metadata() -> dict:
    from .providers_baostock import (
        FINANCIAL_DICTIONARY,
        FINANCIAL_DICTIONARY_SHA256,
        FINANCIAL_SCHEMA,
    )

    return {
        "schema_version": FINANCIAL_SCHEMA,
        "provider_semantics_revision": FINANCIAL_SCHEMA,
        "statement": "profitability",
        "upstream_id": "baostock",
        "availability_basis": "first_observed",
        "historical_point_in_time": False,
        "formal_backtest_eligible": False,
        "redistribution_rights": "unverified",
        "field_dictionary_evidence": {
            "source_url": FINANCIAL_DICTIONARY,
            "document_sha256": FINANCIAL_DICTIONARY_SHA256,
            "fields": ["netProfit", "MBRevenue"],
            "unit": "CNY",
            "currency": "CNY",
        },
        "reference_dictionary": reference_dictionary(),
    }


def profitability_projection(raw: bytes, asset: str, period: str) -> tuple[list[dict], list[str]]:
    """Reparse SDK strings; a narrow reference never changes original numeric values."""
    from .providers_baostock import FINANCIAL_FIELDS, _asset, _financial_date

    if not isinstance(raw, bytes) or len(raw) > MAX_QUERY_BYTES:
        raise ProviderError("vendor_schema_invalid")
    try:
        code = _asset(asset)
        _financial_date(period)
        if period < "2017-01-01" or period[5:] not in {"03-31", "06-30", "09-30", "12-31"}:
            raise ValueError("invalid_period")
        records = json.loads(raw, object_pairs_hook=_unique_object)
        if not isinstance(records, list) or len(records) > 1:
            raise ValueError("invalid_records")
        rows, missing = [], []
        for record in records:
            if not isinstance(record, dict) or set(record) != set(FINANCIAL_FIELDS.split(",")):
                raise ValueError("invalid_fields")
            if any(not isinstance(value, str) for value in record.values()):
                raise ValueError("nonstring_value")
            if record["code"] != code or record["statDate"] != period:
                raise ValueError("identity_mismatch")
            publication = _financial_date(record["pubDate"]) if record["pubDate"] else None
            if publication is not None and publication < period:
                raise ValueError("publication_precedes_report")
            numbers = {key: numeric(record[key]) for key in profitability_fields()}
            if publication is None:
                missing.append("publication_date")
            if all(value is None for value in numbers.values()):
                missing.append("profitability_metrics")
            row = {
                **record,
                **numbers,
                "asset": asset.upper(),
                "report_period": period,
                "publication_date": publication,
                "publication_precision": "date" if publication is not None else None,
            }
            evidence = _reference(record, asset, period)
            if evidence is not None:
                row["reference_evidence"] = evidence
            rows.append(row)
        return rows, missing
    except (ValueError, TypeError, UnicodeError, RecursionError, ProviderError):
        log.warning("baostock_profitability_projection_rejected")
        raise ProviderError("vendor_schema_invalid") from None
