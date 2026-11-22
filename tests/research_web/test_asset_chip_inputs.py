"""Deterministic chip joins; no vendor credentials or network."""

from copy import deepcopy

import pytest

from app.research_web.asset_chip_inputs import chip_rows, normalize_chip_settings
from app.research_web.store import StoreError


def inputs():
    raw = [
        {
            "asset": "603986.SH",
            "date": "2026-01-05",
            "open": 10,
            "high": 12,
            "low": 10,
            "close": 11,
            "volume": 100,
            "amount": 1100,
        }
    ]
    adjusted = [{**raw[0], "open": 20, "high": 24, "low": 20, "close": 22}]
    rates = [{"asset": "603986.SH", "date": "2026-01-05", "turnover_rate_pct": 0}]
    return raw, adjusted, rates


def test_turnover_and_vwap_are_frozen_in_same_adjusted_price_basis_without_changing_inputs():
    raw, adjusted, rates = inputs()
    before = deepcopy((raw, adjusted, rates))
    rows, metadata = chip_rows(raw, adjusted, rates, units_verified=True)
    assert rows[0]["turnover_rate_pct"] == 0 and rows[0]["vwap"] == 22
    assert rows[0]["volume"] == 100 and rows[0]["amount"] == 1100
    assert (raw, adjusted, rates) == before
    assert metadata["contract_version"] == "chip-turnover-1"
    assert metadata["turnover_unit"] == "percent" and metadata["vwap_unit"] == "元/股"


def test_unknown_units_and_zero_volume_do_not_create_a_mean_price():
    raw, adjusted, rates = inputs()
    assert chip_rows(raw, adjusted, rates, units_verified=False)[0][0]["vwap"] is None
    raw[0]["volume"] = 0
    assert chip_rows(raw, adjusted, rates, units_verified=True)[0][0]["vwap"] is None


def test_flat_ohlc_price_is_exact_despite_rounded_transaction_amount():
    raw, adjusted, rates = inputs()
    raw[0].update(open=11, high=11, low=11, close=11, amount=1100.1)
    adjusted[0].update(open=22, high=22, low=22, close=22)
    assert chip_rows(raw, adjusted, rates, units_verified=True)[0][0]["vwap"] == 22


@pytest.mark.parametrize(
    "mutation", ["asset", "date", "duplicate", "missing", "negative", "boolean", "huge"]
)
def test_ambiguous_or_incomplete_turnover_is_not_joined(mutation):
    raw, adjusted, rates = inputs()
    if mutation == "asset":
        rates[0]["asset"] = "600519.SH"
    if mutation == "date":
        rates[0]["date"] = "2026-01-06"
    if mutation == "duplicate":
        rates.append(dict(rates[0]))
    if mutation == "missing":
        rates.clear()
    if mutation == "negative":
        rates[0]["turnover_rate_pct"] = -1
    if mutation == "huge":
        rates[0]["turnover_rate_pct"] = 10**400
    if mutation == "boolean":
        rates[0]["turnover_rate_pct"] = False
    with pytest.raises(StoreError, match="换手率"):
        chip_rows(raw, adjusted, rates, units_verified=True)


def test_chip_settings_are_strict_and_default_arrays_are_not_shared():
    expected = normalize_chip_settings({})
    assert expected["algorithm"] == "triangle" and expected["ageLong"] == 100
    expected["visibleAges"].clear()
    assert len(normalize_chip_settings({})["visibleAges"]) == 4
    for value in (
        {"decay": True},
        {"decay": "1"},
        {"ageShort": 0},
        {"ageLong": 10},
        {"showPeak": 1},
        {"visibleAges": ["long", "long"]},
        {"extra": 1},
    ):
        with pytest.raises(ValueError):
            normalize_chip_settings(value)


def test_large_json_integers_are_validation_errors_not_overflow_errors():
    from pydantic import ValidationError

    from app.research_web.asset_routes import ChartPreferencesRequest

    for field in ("decay", "ageLong"):
        with pytest.raises(ValidationError):
            ChartPreferencesRequest(panels=[], chip_settings={field: 10**400})
