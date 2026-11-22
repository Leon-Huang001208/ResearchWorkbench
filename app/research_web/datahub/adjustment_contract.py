"""Pure, closed Tinysoft adjustment policy; no SDK, credentials or runtime probes.

The price relation was verified against bounded two-stock evidence. It is a
product policy and an empirical acceptance scope, not a vendor SDK guarantee.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

CONTRACT_VERSION = "tinysoft-adjustment-v1"
MAX_FACTOR_DATES = 500
FACTOR_DEFINITIONS = {
    "复权因子": "stock_Adjust_ForwardPriceFactor_Cal(EndT,firstday(), 1)",
    "上市日期": "datetostr(Firstday())",
}
DEFINITION_SHA256 = hashlib.sha256(
    json.dumps(
        FACTOR_DEFINITIONS, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
).hexdigest()
SERIES = ("adjustment_metadata", "listing_date", "adjustment_factors")


def contract_metadata() -> dict:
    """Return a fresh JSON policy declaration, independent of private log files."""
    return {
        "contract_version": CONTRACT_VERSION,
        "definition_sha256": DEFINITION_SHA256,
        "sdk_version": "0.5.2",
        "factor_name": "复权因子",
        "factor_formula": FACTOR_DEFINITIONS["复权因子"],
        "listing_name": "上市日期",
        "listing_formula": FACTOR_DEFINITIONS["上市日期"],
        "hfq_formula": "P(t)*A(t)/A(listing_date)",
        "qfq_formula": "P(t)*A(t)/A(as_of)",
        "ipo_factor": 1.0,
        "vendor_guarantee": False,
        "empirical_scope": "two stocks, 676 trading days during 2024-2026; not all-stock/full-history proof",
        "reviewed_preflight_report_sha256": "85fc23ae55255cdaec3e693753d4202c972a56ba29b9bd41b93750c273849cf3",
        "ohlc_unit": None,
        "ohlc_currency": None,
    }


def validate_adjustment_parameters(parameters: dict) -> None:
    """Reject requests outside the exact three-series single-Shanghai/Shenzhen scope."""
    series = parameters.get("series")
    if series not in SERIES:
        raise ValueError("factor_series_unsupported")
    allowed = {"series"}
    if series != "adjustment_metadata":
        allowed.add("assets")
    if series == "adjustment_factors":
        allowed.add("dates")
    if set(parameters) != allowed:
        raise ValueError("factor_parameters_invalid")
    if series == "adjustment_metadata":
        return
    assets = parameters["assets"]
    if not isinstance(assets, list) or len(assets) != 1:
        raise ValueError("single_asset_required")
    asset = assets[0]
    if (
        not isinstance(asset, str)
        or re.fullmatch(
            r"(?:(?:600|601|603|605|688|689)[0-9]{3}\.SH|(?:000|001|002|003|300|301)[0-9]{3}\.SZ)",
            asset,
        )
        is None
    ):
        raise ValueError("invalid_asset_code")
    if series == "listing_date":
        return
    dates = parameters["dates"]
    if not isinstance(dates, list) or not 1 <= len(dates) <= MAX_FACTOR_DATES:
        raise ValueError("factor_dates_invalid")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    seen = set()
    for value in dates:
        if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
            raise ValueError("factor_dates_invalid")
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("factor_dates_invalid") from exc
        if parsed > today or value in seen:
            raise ValueError("factor_dates_invalid")
        seen.add(value)
