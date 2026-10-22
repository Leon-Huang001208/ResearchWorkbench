"""Deterministic daily history validation and fixed-anchor adjustment.

No vendor calls or filesystem paths enter this module. Original supplier rows
remain in the immutable input manifests; only explicitly known OHLCV fields are
projected into the canonical series.
"""

from __future__ import annotations

import calendar
import math
import re
from datetime import date

from .store import StoreError

HISTORY_VERSION = "asset-history-1"
FLOOR = date(1990, 1, 1)
ACTIVE = {"queued", "running", "cancelling", "draining"}
TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
ALIASES = {
    "open": ("open", "开盘", "开盘价"),
    "high": ("high", "最高", "最高价"),
    "low": ("low", "最低", "最低价"),
    "close": ("close", "收盘", "收盘价"),
    "volume": ("volume", "vol", "成交量"),
    "amount": ("amount", "成交额", "成交金额"),
}


def fail(code: str, message: str, status: int = 409) -> StoreError:
    return StoreError(message, code, status)


def shift_years(value: date, years: int) -> date:
    year = value.year + years
    return value.replace(year=year, day=min(value.day, calendar.monthrange(year, value.month)[1]))


def chunks_near_first(start: date, end: date) -> list[dict]:
    """At most four calendar years per request, sharing the boundary day."""
    result = []
    while end >= start:
        lower = max(start, shift_years(end, -4))
        result.append({"start_date": lower.isoformat(), "end_date": end.isoformat()})
        if lower == start:
            break
        end = lower
    return result


def canonical_asset(asset: str, asset_type: str) -> str:
    if asset_type != "stock" or not re.fullmatch(
        r"(?:(?:600|601|603|605|688|689)[0-9]{3}\.SH|(?:000|001|002|003|300|301)[0-9]{3}\.SZ)",
        asset,
    ):
        raise fail("history_asset_unsupported", "历史任务仅支持规范沪深 A 股代码", 400)
    return asset


def iso_date(value) -> str:
    if not isinstance(value, str):
        raise fail("history_date_invalid", "历史日期格式无法核验")
    if re.fullmatch(r"[0-9]{8}", value):
        value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
    elif re.match(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:T| )", value):
        value = value[:10]
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise fail("history_date_invalid", "历史日期格式无法核验") from exc


def normalize_rows(rows: list[dict], asset: str, interval: dict) -> list[dict]:
    if len(rows) > 5000:
        raise fail("history_chunk_row_limit", "单块历史超出 5000 行边界")
    output: dict[str, dict] = {}
    for row in rows:
        day = iso_date(
            next((row[k] for k in ("date", "时间", "日期", "datetime") if k in row), None)
        )
        if not interval["start_date"] <= day <= interval["end_date"]:
            raise fail("history_out_of_range", "供应商历史含区间外日期")
        identity = next(
            (row[k] for k in ("asset", "code", "stock_code", "证券代码", "代码") if k in row), None
        )
        if identity is not None and str(identity).upper() not in {
            asset,
            asset[:6],
            asset[-2:] + asset[:6],
        }:
            raise fail("history_asset_mismatch", "供应商历史证券身份不一致")
        result = {"asset": asset, "date": day}
        for key, aliases in ALIASES.items():
            value = next((row[name] for name in aliases if name in row), None)
            if value is None and key in {"volume", "amount"}:
                continue
            if value is None or isinstance(value, bool):
                raise fail("history_number_invalid", "供应商历史数值无法核验")
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise fail("history_number_invalid", "供应商历史数值无法核验") from exc
            if not math.isfinite(number) or (
                number <= 0 if key in {"open", "high", "low", "close"} else number < 0
            ):
                raise fail("history_number_invalid", "供应商历史数值无法核验")
            result[key] = number
        if result["high"] < max(result["open"], result["close"], result["low"]) or result[
            "low"
        ] > min(result["open"], result["close"]):
            raise fail("history_ohlc_invalid", "供应商历史 OHLC 范围无效")
        if day in output and output[day] != result:
            raise fail("history_overlap_conflict", "同日历史冲突，保留输入与原规范数据")
        output[day] = result
    return [output[day] for day in sorted(output)]


def merge_rows(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged = {row["date"]: row for row in existing}
    for row in incoming:
        if row["date"] in merged and merged[row["date"]] != row:
            raise fail("history_overlap_conflict", "同日历史冲突，保留输入与原规范数据")
        merged[row["date"]] = row
    return [merged[day] for day in sorted(merged)]


def factor_map(rows: list[dict], asset: str, days: list[str], listing: str) -> dict[str, float]:
    output = {}
    for row in rows:
        day, value = row.get("date"), row.get("factor")
        if (
            row.get("asset") != asset
            or row.get("listing_date") != listing
            or day not in days
            or day in output
            or isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise fail("history_factor_invalid", "复权因子身份、日期或正值验证失败")
        output[day] = float(value)
    if set(output) != set(days):
        raise fail("history_factor_missing", "复权因子没有精确覆盖全部交易日期")
    return output


def adjust_rows(
    rows: list[dict], factors: dict, mode: str, anchor: str | None, listing: str | None
) -> list[dict]:
    if not rows:
        return []
    if mode == "none":
        return [dict(row) for row in rows]
    anchor_day = anchor if mode == "qfq" else listing
    divisor = factors.get(anchor_day)
    if divisor is None or not math.isfinite(divisor) or divisor <= 0:
        raise fail("history_anchor_missing", "固定复权锚点因子缺失")
    result = []
    for row in rows:
        multiplier = factors.get(row["date"])
        if multiplier is None:
            raise fail("history_factor_missing", "复权因子缺失；不填充或回退原始价格")
        ratio = multiplier / divisor
        if not math.isfinite(ratio) or ratio <= 0:
            raise fail("history_adjustment_invalid", "复权比例超出可表示的有效正值范围")
        value = dict(row)
        for key in ("open", "high", "low", "close"):
            price = row[key] * ratio
            if not math.isfinite(price) or price <= 0:
                raise fail("history_adjustment_invalid", "复权价格超出可表示的有效正值范围")
            value[key] = price
        result.append(value)
    return result
