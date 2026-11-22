"""Join frozen date-bound turnover and same-version prices without mutating evidence."""

from __future__ import annotations

import hashlib
import json
import math
from typing import TypeGuard

from core.observability import get_logger

from .asset_history import fail

log = get_logger(__name__)
CHIP_INPUT_VERSION = "chip-turnover-1"
CHIP_AGES = ("long", "middle", "short", "ultra")
CHIP_SETTINGS_DEFAULTS = {
    "algorithm": "triangle",
    "decay": 1,
    "peakUpperPct": 10,
    "peakLowerPct": 10,
    "showPeak": True,
    "ageShort": 2,
    "ageMiddle": 10,
    "ageLong": 100,
    "visibleAges": ["long", "middle", "short", "ultra"],
    "overlayEnabled": False,
    "overlayDays": 100,
}


def normalize_chip_settings(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - set(CHIP_SETTINGS_DEFAULTS):
        raise ValueError("筹码设置字段非法")
    settings = {**CHIP_SETTINGS_DEFAULTS, **value}
    for key, minimum, maximum, integer in [
        ("decay", 0, 10, False),
        ("peakUpperPct", 0, 100, False),
        ("peakLowerPct", 0, 100, False),
        *[(k, 1, 10000, True) for k in ("ageShort", "ageMiddle", "ageLong", "overlayDays")],
    ]:
        n = settings[key]
        if (
            isinstance(n, bool)
            or not isinstance(n, (int, float))
            or not minimum <= n <= maximum
            or not math.isfinite(n)
            or (integer and not isinstance(n, int))
        ):
            raise ValueError("筹码设置数值超界")
    ages = settings["visibleAges"]
    if (
        not isinstance(settings["algorithm"], str)
        or settings["algorithm"] not in {"triangle", "uniform"}
        or not settings["ageShort"] < settings["ageMiddle"] < settings["ageLong"]
        or any(not isinstance(settings[k], bool) for k in ("showPeak", "overlayEnabled"))
        or not isinstance(ages, list)
        or len(ages) > 4
        or any(not isinstance(a, str) or a not in CHIP_AGES for a in ages)
        or len(set(ages)) != len(ages)
    ):
        raise ValueError("筹码设置口径非法")
    return {
        **settings,
        "visibleAges": [a for a in CHIP_AGES if a in ages],
    }


def _finite(value: object) -> TypeGuard[int | float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def chip_rows(raw: list[dict], adjusted: list[dict], rates: list[dict], *, units_verified: bool):
    expected = {(r["asset"], r["date"]) for r in raw}
    by_date = {}
    for row in rates:
        key, value = (row.get("asset"), row.get("date")), row.get("turnover_rate_pct")
        if key not in expected or key in by_date or not _finite(value) or value < 0:
            log.warning("asset_chip_turnover_join_rejected")
            raise fail("chip_turnover_invalid", "换手率身份、日期或数值无法核验")
        by_date[key] = value
    if len(expected) != len(raw) or set(by_date) != expected or len(adjusted) != len(raw):
        raise fail("chip_turnover_incomplete", "换手率未精确覆盖同版本全部日线")
    result = []
    for original, price in zip(raw, adjusted, strict=True):
        key = original["asset"], original["date"]
        if key != (price.get("asset"), price.get("date")):
            raise fail("chip_price_identity_changed", "换手率与价格版本身份不一致")
        volume, amount = original.get("volume"), original.get("amount")
        # A flat OHLC interval has exactly one possible transaction price;
        # integer-rounded vendor amount cannot move that atom outside itself.
        vwap = price["low"] if price["low"] == price["high"] else None
        if units_verified and _finite(volume) and _finite(amount) and volume > 0 and amount > 0:
            mean = amount / volume * (price["close"] / original["close"])
            if (
                vwap is None
                and math.isfinite(mean)
                and price["low"] - 1e-6 <= mean <= price["high"] + 1e-6
            ):
                vwap = mean
        result.append({**price, "turnover_rate_pct": by_date[key], "vwap": vwap})
    digest = hashlib.sha256(
        json.dumps(rates, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    metadata = {
        "status": "complete",
        "contract_version": CHIP_INPUT_VERSION,
        "turnover_unit": "percent",
        "turnover_sha256": digest,
        "row_count": len(result),
        "vwap_unit": "元/股" if units_verified else None,
        "vwap_basis": "raw amount/volume times same-day adjusted/raw close ratio; flat OHLC determines its unique price",
        "vwap_valid_rows": sum(r["vwap"] is not None for r in result),
    }
    log.info("asset_chip_inputs_joined", rows=len(result), vwap_rows=metadata["vwap_valid_rows"])
    return result, metadata
