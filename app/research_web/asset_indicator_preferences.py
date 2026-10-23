"""Closed, account-scoped display preferences; never vendor formulas or queries."""

from __future__ import annotations

import copy
import math

from core.observability import get_logger

log = get_logger(__name__)

# (default, minimum, maximum, integral). Mirrored by the browser catalog contract test.
INDICATOR_RULES: dict[str, dict[str, tuple[int | float, int | float, int | float, bool]]] = {
    "volume": {"short": (5, 1, 250, True), "long": (10, 1, 250, True)},
    "macd": {"fast": (12, 1, 250, True), "slow": (26, 2, 250, True), "signal": (9, 1, 250, True)},
    "kdj": {"period": (9, 1, 250, True), "k": (3, 1, 250, True), "d": (3, 1, 250, True)},
    "rsi": {"period": (14, 1, 250, True)},
    "boll": {"period": (20, 2, 250, True), "deviation": (2, 0.1, 10, False)},
    "wr": {"long": (10, 2, 250, True), "short": (6, 1, 249, True)},
    "sar": {"step": (0.02, 0.001, 1, False), "maximum": (0.2, 0.001, 1, False)},
    "dmi": {"period": (14, 2, 250, True), "adx": (6, 1, 250, True)},
    "cci": {"period": (14, 2, 250, True)},
    "bias": {"short": (6, 1, 248, True), "middle": (12, 2, 249, True), "long": (24, 3, 250, True)},
    "roc": {"period": (12, 1, 250, True), "average": (6, 1, 250, True)},
    "obv": {"average": (30, 1, 250, True)},
    "vr": {"period": (26, 1, 250, True), "average": (6, 1, 250, True)},
    "emv": {"period": (14, 1, 250, True), "average": (9, 1, 250, True)},
    "atr": {"period": (14, 1, 250, True)},
}
INDICATOR_IDS = tuple(INDICATOR_RULES)
DEFAULT_FAVORITES = ("volume", "macd", "kdj", "rsi", "boll", "wr", "sar")


def validate_indicator_ids(value, *, name="panels") -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > len(INDICATOR_IDS)
        or any(not isinstance(item, str) or item not in INDICATOR_RULES for item in value)
        or len(set(value)) != len(value)
    ):
        log.warning("asset_indicator_ids_rejected", extra={"field": name})
        raise ValueError(f"{name} must contain unique supported indicator IDs")
    return list(value)


def normalize_indicator_settings(value) -> dict:
    if not isinstance(value, dict) or any(key not in INDICATOR_RULES for key in value):
        log.warning("asset_indicator_settings_rejected")
        raise ValueError("unknown indicator settings")
    result = {}
    for indicator, rules in INDICATOR_RULES.items():
        supplied = value.get(indicator, {})
        if not isinstance(supplied, dict) or any(key not in rules for key in supplied):
            raise ValueError("unknown indicator parameter")
        settings = {}
        for key, (default, minimum, maximum, integral) in rules.items():
            number = supplied.get(key, default)
            if (
                isinstance(number, bool)
                or not isinstance(number, (int, float))
                or not minimum <= number <= maximum
                or not math.isfinite(number)
                or integral
                and number != math.trunc(number)
            ):
                raise ValueError("indicator parameter outside its declared range")
            settings[key] = int(number) if integral else number
        if indicator in {"volume", "wr"} and settings["short"] >= settings["long"]:
            raise ValueError("short period must be below long period")
        if indicator == "macd" and settings["fast"] >= settings["slow"]:
            raise ValueError("MACD fast period must be below slow period")
        if indicator == "bias" and not settings["short"] < settings["middle"] < settings["long"]:
            raise ValueError("BIAS periods must be increasing")
        if indicator == "sar" and settings["step"] > settings["maximum"]:
            raise ValueError("SAR step must not exceed its maximum")
        result[indicator] = settings
    return copy.deepcopy(result)
