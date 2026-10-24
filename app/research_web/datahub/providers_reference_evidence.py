"""Pinned public reference descriptors; no network access or financial cell values.

These narrowly scoped observations establish selected units and definitions, never
historical availability, independent upstreams or formal backtest eligibility.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from core.observability import get_logger

log = get_logger(__name__)

GDP_AMOUNT_FIELDS = (
    "DOMESTICL_PRODUCT_BASE",
    "FIRST_PRODUCT_BASE",
    "SECOND_PRODUCT_BASE",
    "THIRD_PRODUCT_BASE",
)
GDP_GROWTH_FIELDS = ("SUM_SAME", "FIRST_SAME", "SECOND_SAME", "THIRD_SAME")
GDP_REFERENCE: dict[str, Any] = {
    "field_mapping_document": {
        "url": "https://data.eastmoney.com/newstatic/js/cjsj/cn/gdp.js",
        "sha256": "e38fa8f47c56c384901e9f61292aba32e1c9cb8af875fb11ef488414e286cf61",
        "observed_script_page": "https://data.eastmoney.com/cjsj/gdp.html",
        "observed_script_page_sha256": "c675467b1afb05932577bb3100f844c43693dc41f85fe8101bf13372084eabe1",
        "report_name": "RPT_ECONOMY_GDP",
    },
    "price_basis_document": {
        "url": "https://www.stats.gov.cn/sj/zxfb/202507/t20250716_1960426.html",
        "sha256": "9a770677d59a781751b4d7c0070c250a4fa53210afccdda5efac0a12ce156f64",
        "absolute_values": "current_prices",
        "growth_rates": "comparable_prices",
    },
    "field_mapping": {
        **{
            field: {
                "source_header_unit": "亿元",
                "unit": "CNY_100million",
                "currency": "CNY",
                "price_basis": "current_prices",
            }
            for field in GDP_AMOUNT_FIELDS
        },
        **{
            field: {
                "source_format": "%",
                "unit": "percent",
                "currency": None,
                "price_basis": "comparable_prices",
            }
            for field in GDP_GROWTH_FIELDS
        },
    },
    "aggregation": "year_to_date",
    "cross_source_equivalence": "unverified",
}

SINA_REFERENCE: dict[str, Any] = {
    "scope": {
        "asset": "600600.SH",
        "period": "2025-06-30",
        "statement": "income_statement",
        "rCurrency": "CNY",
        "rType": "合并期末",
        "consolidation": "group",
        "aggregation": "year_to_date",
        "start": "2025-01-01",
        "end": "2025-06-30",
    },
    "document_url": "https://www.tsingtao.com.cn/TsingTao/upload/Attachment/20250922/%E5%85%AC%E5%8F%B82025%E5%B9%B4%E4%B8%AD%E6%9C%9F%E6%8A%A5%E5%91%8A%E5%8D%B0%E5%88%B7%E6%96%87%E6%9C%AC-20250922.pdf",
    "document_sha256": "03a5bff81cabce1fad69167d4155ce349d2400c818d4a04d10e10f60ff589121",
    "pdf_page_1_based": 5,
    "display_page": "4",
    "issuer_release_date_claim": "2025-08-26",
    "issuer_news_url": "https://www.tsingtao.com.cn/MT/news/7cc9514e-bbb1-44dd-b3d7-c57ac18085be.html",
    "issuer_news_sha256": "01817853f8228e3a51658c60a99c58cc9ba2912de14c56aafdd3f8e634140a4c",
    "document_available_at": None,
    "original_release_bytes_proven": False,
    "historical_point_in_time": False,
    "formal_backtest_eligible": False,
    "cells": {
        "BIZINCO": {
            "canonical_decimal_sha256": "c71059b1ac9b50206c87cfa96cd52365fa21e41654785005af14923902f4e89b",
            "reference_label": "一、營業收入",
            "column": "2025年半年度合併",
            "unit": "CNY",
            "currency": "CNY",
            "scale": "1",
        },
        "NETPROFIT": {
            "canonical_decimal_sha256": "26487702648f10a819f403b32ac730ede65a505912f6f7aed9f0b773790d04b4",
            "reference_label": "四、淨利潤",
            "column": "2025年半年度合併",
            "unit": "CNY",
            "currency": "CNY",
            "scale": "1",
        },
    },
}


def reference_digest(reference: dict) -> str:
    """Hash the complete descriptor ledger independently of runtime observations."""
    return hashlib.sha256(
        json.dumps(reference, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def canonical_decimal_sha256(value: object) -> str | None:
    """Hash exact decimal strings or integers; binary floats cannot prove exactness."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value)
    if (
        isinstance(value, str)
        and re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", text) is None
    ):
        return None
    try:
        number = Decimal(text)
        if not number.is_finite():
            return None
        canonical = format(number, "f")
        if "." in canonical:
            canonical = canonical.rstrip("0").rstrip(".")
        if number.is_zero():
            canonical = "0"
        return hashlib.sha256(canonical.encode("ascii")).hexdigest()
    except (InvalidOperation, ValueError, OverflowError):
        log.warning("datahub_reference_decimal_invalid")
        return None


def gdp_reference_evidence() -> dict:
    return {**copy.deepcopy(GDP_REFERENCE), "ledger_sha256": reference_digest(GDP_REFERENCE)}


def sina_reference_dictionary() -> dict:
    return {
        "ledger_sha256": reference_digest(SINA_REFERENCE),
        "ledger": copy.deepcopy(SINA_REFERENCE),
        "all_other_item_units": "unknown",
        "match_policy": "exact_scope_and_exact_decimal_string_or_integer_sha256_no_float",
    }


def enrich_sina_reference(row: dict) -> dict:
    """Deterministic row metadata, bound again by the shared raw snapshot parser."""
    enriched: dict[str, Any] = {
        **row,
        "publication_date_role": "supplier_date_not_verified_original_release",
        "reference_evidence": [],
    }
    scope = SINA_REFERENCE["scope"]
    if not (
        row.get("asset") == scope["asset"]
        and row.get("report_period") == scope["period"]
        and row.get("rCurrency") == scope["rCurrency"]
        and row.get("rType") == scope["rType"]
    ):
        return enriched
    enriched["scoped_date_evidence"] = {
        "issuer_release_date_claim": SINA_REFERENCE["issuer_release_date_claim"],
        "date_precision": "day",
        "issuer_news_url": SINA_REFERENCE["issuer_news_url"],
        "issuer_news_sha256": SINA_REFERENCE["issuer_news_sha256"],
        "supplier_date": row.get("publication_date"),
        "conflict": row.get("publication_date") is not None
        and row["publication_date"] != SINA_REFERENCE["issuer_release_date_claim"],
        "document_available_at": None,
        "original_release_bytes_proven": False,
        "historical_point_in_time": False,
        "formal_backtest_eligible": False,
    }
    for item in row["data"]:
        field = item["item_field"]
        reference = SINA_REFERENCE["cells"].get(field)
        if reference is None or item["item_source"] != "lrb":
            continue
        matched = (
            canonical_decimal_sha256(item["item_value"]) == reference["canonical_decimal_sha256"]
        )
        enriched["reference_evidence"].append(
            {
                "item_field": field,
                "status": (
                    "verified_reference_value_match" if matched else "unmatched_reference_value"
                ),
                "unit": reference["unit"] if matched else None,
                "currency": reference["currency"] if matched else None,
                "scale": reference["scale"] if matched else None,
                "reference_label": reference["reference_label"],
                "column": reference["column"],
                "canonical_decimal_sha256": reference["canonical_decimal_sha256"],
                "scope": copy.deepcopy(scope),
                "consolidation": scope["consolidation"] if matched else None,
                "aggregation": scope["aggregation"] if matched else None,
                "document_url": SINA_REFERENCE["document_url"],
                "document_sha256": SINA_REFERENCE["document_sha256"],
                "pdf_page_1_based": SINA_REFERENCE["pdf_page_1_based"],
                "display_page": SINA_REFERENCE["display_page"],
                "document_available_at": None,
                "original_release_bytes_proven": False,
                "historical_point_in_time": False,
                "formal_backtest_eligible": False,
            }
        )
    return enriched
