"""Closed WGC monthly tonnes projection; reference periods are not publication times."""

import calendar
import json
import math
import re
from datetime import UTC, date, datetime
from typing import Any

from core.observability import get_logger

from .providers import MAX_RESPONSE_BYTES, MAX_ROWS, ProviderError

log = get_logger(__name__)
WGC_NUMERIC_CONTRACT = "wgc-etf-monthly-tonnes-v1"
WGC_DATASETS = frozenset({"etf-holdings", "etf-flows"})
WGC_UNITS = {field: "tonnes" for field in ("north_america", "europe", "asia", "other")}
_REGIONS = ("North America", "Europe", "Asia", "Other")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """JSON duplicate keys would make the source's identity ambiguous."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _envelope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("invalid_envelope")
    if (
        value.get("success") is False
        or value.get("error")
        or value.get("errors")
        or any(
            value.get(key) not in (None, 0, "0")
            for key in ("errorcode", "error_code", "errcode", "errno")
        )
        or value.get("code") not in (None, 0, "0", 200, "200")
    ):
        raise ValueError("business_error")
    return value


def _number(value: Any, *, holdings: bool) -> int | float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("invalid_number")
    if holdings and value < 0:
        raise ValueError("negative_holdings")
    return value


def _period(stamp: Any) -> date:
    if type(stamp) is not int:
        raise ValueError("invalid_timestamp")
    instant = datetime.fromtimestamp(stamp / 1000, tz=UTC)
    period = instant.date()
    if (
        instant.hour
        or instant.minute
        or instant.second
        or instant.microsecond
        or period.day != calendar.monthrange(period.year, period.month)[1]
    ):
        raise ValueError("not_month_end_utc_midnight")
    return period


def _points(points: Any, *, width: int, holdings: bool) -> tuple[list[int], list[list[Any]]]:
    if not isinstance(points, list) or not 1 <= len(points) <= MAX_ROWS:
        raise ValueError("observation_count")
    timestamps = []
    observations = []
    previous = None
    for point in points:
        if not isinstance(point, list) or len(point) != width:
            raise ValueError("invalid_observation_shape")
        period = _period(point[0])
        month = period.year * 12 + period.month
        if previous is not None and month != previous + 1:
            raise ValueError("not_contiguous_ordered_months")
        previous = month
        timestamps.append(point[0])
        # Gold price is validated as a source number but never projected as tonnes.
        observations.append(
            [
                _number(value, holdings=holdings and index < 4)
                for index, value in enumerate(point[1:])
            ]
        )
    return timestamps, observations


def wgc_projection(raw: bytes, dataset: str) -> list[dict[str, Any]]:
    """Validate the entire selected monthly-tonnes slice before applying any row limit."""
    try:
        if (
            dataset not in WGC_DATASETS
            or not isinstance(raw, bytes)
            or len(raw) > MAX_RESPONSE_BYTES
        ):
            raise ValueError("unsupported_projection")
        body = _envelope(json.loads(raw, object_pairs_hook=_object))
        chart = _envelope(body["chartData"])
        source_as_of = chart["asOfDate"]
        if (
            not isinstance(source_as_of, str)
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", source_as_of) is None
        ):
            raise ValueError("invalid_as_of")
        as_of_date = date.fromisoformat(source_as_of)
        monthly = _envelope(_envelope(chart["data"])["Monthly"])
        if dataset == "etf-holdings":
            tonnes = _envelope(monthly["tonnes"])
            if tonnes["columns"] != ["Date", *_REGIONS, "Gold, US$/oz"]:
                raise ValueError("invalid_columns")
            timestamps, values = _points(tonnes["set"], width=6, holdings=True)
        else:
            series = _envelope(monthly["series"])["tonnes"]
            if not isinstance(series, list) or len(series) != 5:
                raise ValueError("invalid_series_count")
            by_name = {}
            for item in series:
                item = _envelope(item)
                name = item["name"]
                if name not in (*_REGIONS, "Gold Price (rhs)") or name in by_name:
                    raise ValueError("invalid_series_name")
                by_name[name] = _points(item["data"], width=2, holdings=False)
            timestamps = by_name[_REGIONS[0]][0]
            if any(stamps != timestamps for stamps, _ in by_name.values()):
                raise ValueError("misaligned_series")
            values = [
                [by_name[region][1][index][0] for region in _REGIONS]
                for index in range(len(timestamps))
            ]
        if as_of_date < _period(timestamps[-1]):
            raise ValueError("as_of_before_latest_period")
        if not any(value is not None for row in values for value in row[:4]):
            raise ValueError("no_numeric_region_observations")
        rows = [
            {
                "reference_date": _period(stamp).isoformat(),
                "source_timestamp": stamp,
                "source_as_of_date": source_as_of,
                "frequency": "Monthly",
                "metric": "holdings" if dataset == "etf-holdings" else "flows",
                **dict(zip(WGC_UNITS, values[index][:4], strict=True)),
            }
            for index, stamp in enumerate(timestamps)
        ]
        log.info("wgc_monthly_projection_validated", dataset=dataset, rows=len(rows))
        return rows
    except (ValueError, TypeError, KeyError, OverflowError, OSError, RecursionError):
        log.warning("wgc_numeric_envelope_invalid", source="ext_wgc", dataset=dataset)
        raise ProviderError("wgc_numeric_schema_invalid") from None


def wgc_fields() -> dict[str, dict[str, str]]:
    """Fresh metadata shared by both fixed datasets; no price or inferred release field."""
    return {
        "reference_date": {
            "type": "date",
            "unit": "date",
            "role": "reference_period_not_available_at",
        },
        "source_timestamp": {
            "type": "integer",
            "unit": "milliseconds_since_epoch",
            "role": "reference_period_not_available_at",
        },
        "source_as_of_date": {"type": "date", "unit": "date", "role": "source_original"},
        "frequency": {"type": "string", "unit": "source_frequency"},
        "metric": {"type": "string", "unit": "source_metric"},
        **{field: {"type": "number", "unit": unit} for field, unit in WGC_UNITS.items()},
    }
