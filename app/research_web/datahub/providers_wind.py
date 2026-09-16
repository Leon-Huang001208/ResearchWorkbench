"""Restricted Wind DataHub provider using only reviewed adapter methods."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import re
import threading
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import (
    MAX_QUERY_BYTES,
    MAX_ROWS,
    ProviderError,
    Result,
    numeric,
    valid_date,
)

log = get_logger(__name__)
_ASSET = re.compile(r"^[0-9]{6}\.(?:SH|SZ|BJ)$")
_ADJUSTMENTS = {"none": 1, "backward": 2, "forward": 3, "hfq": 2, "qfq": 3}
MAX_HISTORY_CALENDAR_DAYS = 60
WIND_PROVIDER_DEADLINE_SECONDS = 18.0
FieldSpec = tuple[str, str, str, str | None, str | None]
Schema = tuple[tuple[FieldSpec, ...], frozenset[str]]

_WIND_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="research-wind"
)
_WIND_LOCK = threading.Lock()
_WIND_OUTSTANDING: concurrent.futures.Future[Any] | None = None
_WIND_POISONED = False

# Each reviewed adapter result is projected through one immutable schema. The
# first tuple is (output field, adapter field, type, unit, currency); allowed
# adapter fields may include reviewed values intentionally omitted from output.
_SCHEMAS: dict[tuple[str, str], Schema] = {
    ("market_bars", "daily_quotes"): (
        (
            ("asset", "code", "asset", None, None),
            ("date", "date", "date", None, None),
            ("open", "open", "number", "currency_per_share", "CNY"),
            ("high", "high", "number", "currency_per_share", "CNY"),
            ("low", "low", "number", "currency_per_share", "CNY"),
            ("close", "close", "number", "currency_per_share", "CNY"),
            ("volume", "volume", "number", "share", None),
            ("turnover", "amount", "number", "currency", "CNY"),
            ("turnover_rate_pct", "turnover", "number", "percent", None),
            ("adjustment", "$adjustment", "string", None, None),
        ),
        frozenset(
            {
                "code",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "turnover",
                "adj_factor",
                "vwap",
                "pct_change",
                "amplitude",
            }
        ),
    ),
    ("market_snapshot", "realtime"): (
        (
            ("asset", "code", "asset", None, None),
            ("as_of", "trade_date", "date", None, None),
            ("price", "close", "number", "currency_per_share", "CNY"),
            ("turnover_rate_pct", "turnover", "number", "percent", None),
            ("pe_ttm", "pe_ttm", "number", "ratio", None),
            ("pb", "pb", "number", "ratio", None),
            ("pcf_ocf_ttm", "pcf_ocf_ttm", "number", "ratio", None),
            ("total_shares", "total_shares", "number", "share", None),
        ),
        frozenset(
            {
                "code",
                "trade_date",
                "close",
                "turnover",
                "pe_ttm",
                "pb",
                "pcf_ocf_ttm",
                "total_shares",
            }
        ),
    ),
    ("index_data", "quotes"): (
        (
            ("asset", "code", "asset", None, None),
            ("as_of", "trade_date", "date", None, None),
            ("name", "name", "string", None, None),
            ("price", "close", "number", "points", None),
            ("change_pct", "pct_change", "number", "percent", None),
        ),
        frozenset({"code", "trade_date", "name", "close", "pct_change"}),
    ),
    ("financials", "financial_statements"): (
        (
            ("asset", "code", "asset", None, None),
            ("as_of", "trade_date", "date", None, None),
            ("report_period", "report_date", "date", None, None),
            ("revenue", "revenue", "number", "currency", "CNY"),
            ("net_profit", "net_profit", "number", "currency", "CNY"),
            ("eps", "eps", "number", "currency_per_share", "CNY"),
            ("operating_cost", "operating_cost", "number", "currency", "CNY"),
            ("gross_profit", "gross_profit", "number", "currency", "CNY"),
            ("gross_profit_ttm", "gross_profit_ttm", "number", "currency", "CNY"),
            ("gross_profit_margin", "gross_profit_margin", "number", "percent", None),
            ("roe", "roe", "number", "percent", None),
            ("total_assets", "total_assets", "number", "currency", "CNY"),
            ("free_cf", "free_cf", "number", "currency", "CNY"),
            ("free_cf_per_share", "free_cf_per_share", "number", "currency_per_share", "CNY"),
            ("equity", "equity", "number", "currency", "CNY"),
        ),
        frozenset(
            {
                "code",
                "trade_date",
                "report_date",
                "revenue",
                "net_profit",
                "eps",
                "operating_cost",
                "gross_profit",
                "gross_profit_ttm",
                "gross_profit_margin",
                "roe",
                "total_assets",
                "free_cf",
                "free_cf_per_share",
                "equity",
            }
        ),
    ),
    ("market_activity", "fund_flow"): (
        (
            ("asset", "code", "asset", None, None),
            ("date", "date", "date", None, None),
            ("main_force_inflow", "main_force_inflow", "number", "currency", "CNY"),
            ("main_force_open", "main_force_open", "number", "currency", "CNY"),
            ("main_force_close", "main_force_close", "number", "currency", "CNY"),
            ("north_bound_shares", "north_bound_shares", "number", "share", None),
            ("north_bound_pct", "north_bound_pct", "number", "percent", None),
        ),
        frozenset(
            {
                "code",
                "date",
                "main_force_inflow",
                "main_force_open",
                "main_force_close",
                "north_bound_shares",
                "north_bound_pct",
            }
        ),
    ),
    ("market_activity", "margin_trading"): (
        (
            ("asset", "code", "asset", None, None),
            ("date", "date", "date", None, None),
            ("margin_balance", "margin_balance", "number", "currency", "CNY"),
            ("short_balance", "short_balance", "number", "share", None),
            ("margin_buy", "margin_buy", "number", "currency", "CNY"),
            ("margin_repay", "margin_repay", "number", "currency", "CNY"),
            ("short_sell_vol", "short_sell_vol", "number", "share", None),
            ("short_repay_vol", "short_repay_vol", "number", "share", None),
        ),
        frozenset(
            {
                "code",
                "date",
                "margin_balance",
                "short_balance",
                "margin_buy",
                "margin_repay",
                "short_sell_vol",
                "short_repay_vol",
            }
        ),
    ),
    ("market_activity", "holder_data"): (
        (
            ("asset", "code", "asset", None, None),
            ("report_period", "report_date", "date", None, None),
            ("holder_count", "holder_num", "number", "count", None),
            ("average_holding", "holder_avg_hold", "number", "share", None),
            ("average_holding_pct", "holder_avg_pct", "number", "percent", None),
            ("top10_pct", "top10_pct", "number", "percent", None),
            ("top10_quantity", "top10_quantity", "number", "share", None),
            ("institutional_holding", "institutional_hold", "number", "share", None),
            ("institutional_pct", "institutional_pct", "number", "percent", None),
        ),
        frozenset(
            {
                "code",
                "report_date",
                "holder_num",
                "holder_avg_hold",
                "holder_avg_pct",
                "top10_pct",
                "top10_quantity",
                "institutional_hold",
                "institutional_pct",
            }
        ),
    ),
}

_MINIMUM_OUTPUT_FIELDS: dict[tuple[str, str], frozenset[str]] = {
    ("market_bars", "daily_quotes"): frozenset({"close"}),
    ("market_snapshot", "realtime"): frozenset({"price"}),
    ("index_data", "quotes"): frozenset({"price"}),
    ("financials", "financial_statements"): frozenset({"revenue"}),
    ("market_activity", "fund_flow"): frozenset({"main_force_inflow"}),
    ("market_activity", "margin_trading"): frozenset({"margin_balance"}),
    ("market_activity", "holder_data"): frozenset({"holder_count"}),
}


def _asset(value: Any) -> str:
    if not isinstance(value, str) or _ASSET.fullmatch(value.upper()) is None:
        raise ProviderError("invalid_asset_code")
    return value.upper()


def _day(value: Any) -> str:
    if not isinstance(value, str):
        raise ProviderError("invalid_date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ProviderError("invalid_date") from exc
    if parsed > datetime.now(ZoneInfo("Asia/Shanghai")).date():
        raise ProviderError("invalid_date")
    return value


def _bounded_history_range(parameters: dict[str, Any]) -> tuple[str, str]:
    raw_start = parameters.get("start_date")
    raw_end = parameters.get("end_date")
    if not isinstance(raw_start, str) or not isinstance(raw_end, str):
        raise ProviderError("data_not_equivalent")
    start = _day(raw_start)
    end = _day(raw_end)
    start_day = date.fromisoformat(start)
    end_day = date.fromisoformat(end)
    if start_day > end_day:
        raise ProviderError("data_not_equivalent")
    if (end_day - start_day).days + 1 > MAX_HISTORY_CALENDAR_DAYS:
        raise ProviderError("workload_too_large")
    return start, end


def _preflight(query: BusinessQuery) -> None:
    parameters = query.parameters
    if query.capability in {"market_bars", "market_snapshot"}:
        if parameters.get("asset_type") != "stock":
            raise ProviderError("data_not_equivalent")
        if query.capability == "market_bars":
            _bounded_history_range(parameters)
    elif query.capability == "market_activity" and parameters.get("dataset") in {
        "fund_flow",
        "margin_trading",
    }:
        _bounded_history_range(parameters)


def _schema_key(query: BusinessQuery) -> tuple[str, str]:
    if query.capability == "market_bars":
        return (query.capability, "daily_quotes")
    if query.capability == "market_snapshot":
        return (query.capability, "realtime")
    if query.capability == "index_data":
        return (query.capability, str(query.parameters.get("dataset")))
    if query.capability == "financials":
        return (query.capability, "financial_statements")
    if query.capability == "market_activity":
        return (query.capability, str(query.parameters.get("dataset")))
    raise ProviderError("data_not_equivalent")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 256 or any(ord(char) < 32 for char in value):
        raise ProviderError("wind_response_invalid")
    return value


def _provider_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        value = value.isoformat()
    return valid_date(value)


def _field_value(kind: str, value: Any) -> Any:
    if kind == "asset":
        return _asset(value)
    if kind == "date":
        return _provider_date(value)
    if kind == "number":
        return numeric(value)
    if kind == "string":
        return _text(value)
    raise ProviderError("wind_response_invalid")


def _schema(query: BusinessQuery) -> Schema:
    schema = _SCHEMAS.get(_schema_key(query))
    if schema is None:
        raise ProviderError("data_not_equivalent")
    return schema


def _field_metadata(query: BusinessQuery) -> dict[str, dict[str, str | None]]:
    fields, _allowed = _schema(query)
    return {
        output: {
            "type": "string" if kind == "asset" else kind,
            "unit": unit,
            "currency": currency,
        }
        for output, _source, kind, unit, currency in fields
    }


def _equivalent_asset(value: Any, expected: set[str]) -> None:
    try:
        actual = _asset(value)
    except ProviderError as exc:
        raise ProviderError("data_not_equivalent") from exc
    if actual not in expected:
        raise ProviderError("data_not_equivalent")


def _equivalent_day(value: Any, *, start: str | None = None, end: str | None = None) -> str:
    try:
        actual = _provider_date(value)
    except ProviderError as exc:
        raise ProviderError("data_not_equivalent") from exc
    if (
        actual is None
        or (start is not None and actual < start)
        or (end is not None and actual > end)
    ):
        raise ProviderError("data_not_equivalent")
    return actual


def _validate_record_identity(row: dict[str, Any], query: BusinessQuery) -> None:
    parameters = query.parameters
    if query.capability == "market_snapshot":
        expected_assets = {_asset(value) for value in parameters.get("assets", [])}
    elif query.capability == "index_data":
        expected_assets = {_asset(parameters.get("index"))}
    else:
        expected_assets = {_asset(parameters.get("asset"))}
    _equivalent_asset(row.get("code"), expected_assets)

    if query.capability == "market_bars" or (
        query.capability == "market_activity"
        and parameters.get("dataset") in {"fund_flow", "margin_trading"}
    ):
        _equivalent_day(
            row.get("date"),
            start=parameters.get("start_date"),
            end=parameters.get("end_date"),
        )
    elif query.capability in {"market_snapshot", "index_data"}:
        _equivalent_day(row.get("trade_date"))
    elif query.capability == "financials":
        _equivalent_day(row.get("trade_date"))
        periods = parameters.get("periods", [])
        if periods and _equivalent_day(row.get("report_date")) != periods[0]:
            raise ProviderError("data_not_equivalent")
    elif (
        query.capability == "market_activity"
        and parameters.get("dataset") == "holder_data"
        and _equivalent_day(row.get("report_date")) != parameters.get("end_date")
    ):
        raise ProviderError("data_not_equivalent")


def _records(frame: Any, query: BusinessQuery) -> list[dict[str, Any]]:
    try:
        records = frame.to_dict(orient="records")
    except (AttributeError, TypeError, ValueError) as exc:
        raise ProviderError("wind_response_invalid") from exc
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ProviderError("wind_response_invalid")
    if len(records) > MAX_ROWS:
        raise ProviderError("row_limit")
    fields, allowed = _schema(query)
    normalized: list[dict[str, Any]] = []
    for row in records:
        if set(row).difference(allowed):
            raise ProviderError("data_not_equivalent")
        _validate_record_identity(row, query)
        output: dict[str, Any] = {}
        for output_name, source_name, kind, _unit, _currency in fields:
            value = (
                query.parameters.get("adjustment", "none")
                if source_name == "$adjustment"
                else row.get(source_name)
            )
            if hasattr(value, "item"):
                try:
                    value = value.item()
                except (TypeError, ValueError, AttributeError) as exc:
                    raise ProviderError("wind_response_invalid") from exc
            output[output_name] = _field_value(kind, value)
        normalized.append(output)
    encoded = json.dumps(normalized, ensure_ascii=False, default=str).encode()
    if len(encoded) > MAX_QUERY_BYTES:
        raise ProviderError("query_size_limit")
    return normalized


def _requested_output_fields(query: BusinessQuery) -> frozenset[str]:
    if query.capability != "market_snapshot":
        return _MINIMUM_OUTPUT_FIELDS[_schema_key(query)]
    requested = query.parameters.get("fields", [])
    fields, _allowed = _schema(query)
    source_to_output = {source: output for output, source, *_rest in fields}
    projected = {
        source_to_output[field]
        for field in requested
        if field in source_to_output and field not in {"code", "trade_date"}
    }
    return frozenset(projected) or _MINIMUM_OUTPUT_FIELDS[_schema_key(query)]


def _quality_limitations(rows: list[dict[str, Any]], query: BusinessQuery) -> list[str]:
    if not rows:
        return []
    minimum = _MINIMUM_OUTPUT_FIELDS[_schema_key(query)]
    if not any(any(row.get(field) is not None for field in minimum) for row in rows):
        raise ProviderError("critical_fields_missing")
    requested = _requested_output_fields(query)
    limitations = []
    if any(any(row.get(field) is None for field in requested) for row in rows):
        limitations.append("partial_fields_missing")
    if query.capability == "market_bars" or (
        query.capability == "market_activity"
        and query.parameters.get("dataset") in {"fund_flow", "margin_trading"}
    ):
        end_date = query.parameters["end_date"]
        returned_end = max(
            (row["date"] for row in rows if row.get("date") is not None), default=None
        )
        if returned_end != end_date:
            limitations.append("incomplete_requested_range")
    return limitations


def _make_adapter() -> Any:
    from data_layer.adapters.wind import WindAdapter, WindExcelClient

    client = WindExcelClient(
        visible=False,
        isolated_workbook=True,
        isolated_app=True,
    )
    return WindAdapter(client=client)


def _run_adapter(query: BusinessQuery, adapter: Any | None) -> Any:
    global _WIND_POISONED
    active = adapter if adapter is not None else _make_adapter()
    try:
        if not active.is_available():
            raise ProviderError("wind_not_logged_in")
        return _invoke(query, active)
    finally:
        close = getattr(active, "close", None)
        if callable(close):
            try:
                close()
            except Exception as exc:
                with _WIND_LOCK:
                    _WIND_POISONED = True
                log.error(
                    "datahub_wind_cleanup_unconfirmed",
                    error_type=type(exc).__name__,
                )
                raise ProviderError("wind_cleanup_failed") from exc


def _clear_outstanding(future: concurrent.futures.Future[Any]) -> None:
    global _WIND_OUTSTANDING
    with _WIND_LOCK:
        if _WIND_OUTSTANDING is future and not _WIND_POISONED:
            _WIND_OUTSTANDING = None


def _submit(query: BusinessQuery, adapter: Any | None) -> concurrent.futures.Future[Any]:
    global _WIND_OUTSTANDING
    with _WIND_LOCK:
        if _WIND_POISONED or (_WIND_OUTSTANDING is not None and not _WIND_OUTSTANDING.done()):
            raise ProviderError("provider_busy")
        future = _WIND_EXECUTOR.submit(_run_adapter, query, adapter)
        _WIND_OUTSTANDING = future
    future.add_done_callback(_clear_outstanding)
    return future


def _invoke(query: BusinessQuery, adapter: Any) -> Any:
    parameters = query.parameters
    if query.capability == "market_bars":
        frequency = parameters.get("frequency", "1d")
        adjustment = parameters.get("adjustment", "none")
        if (
            parameters.get("asset_type") != "stock"
            or not isinstance(frequency, str)
            or frequency not in {"1d", "day", "daily"}
            or not isinstance(adjustment, str)
            or adjustment not in _ADJUSTMENTS
        ):
            raise ProviderError("data_not_equivalent")
        start_date, end_date = _bounded_history_range(parameters)
        return adapter.fetch_daily_quotes(
            codes=[_asset(parameters.get("asset"))],
            start_date=start_date,
            end_date=end_date,
            adj_type=_ADJUSTMENTS[adjustment],
        )
    if query.capability == "market_snapshot":
        assets = parameters.get("assets")
        fields = parameters.get("fields", [])
        allowed_fields = {
            "code",
            "trade_date",
            "close",
            "turnover",
            "pe_ttm",
            "pb",
            "pcf_ocf_ttm",
            "total_shares",
        }
        if (
            parameters.get("asset_type") != "stock"
            or not isinstance(assets, list)
            or not 1 <= len(assets) <= 50
            or not isinstance(fields, list)
            or any(not isinstance(field, str) or field not in allowed_fields for field in fields)
        ):
            raise ProviderError("data_not_equivalent")
        return adapter.fetch_market_snapshot(codes=[_asset(value) for value in assets])
    if query.capability == "index_data":
        # The reviewed adapter returns a real-time index snapshot. A requested
        # historical date or constituent/valuation dataset is not equivalent.
        if parameters.get("dataset") != "quotes" or parameters.get("date") is not None:
            raise ProviderError("data_not_equivalent")
        return adapter.fetch_index_quotes(
            codes=[_asset(parameters.get("index"))],
        )
    if query.capability == "financials":
        statements = parameters.get("statements", ["metrics"])
        periods = parameters.get("periods", [])
        if statements != ["metrics"] or not isinstance(periods, list) or len(periods) > 1:
            raise ProviderError("data_not_equivalent")
        return adapter.fetch_financial_statements(
            codes=[_asset(parameters.get("asset"))],
            report_date=_day(periods[0]) if periods else None,
        )
    if query.capability == "market_activity":
        dataset = parameters.get("dataset")
        asset = _asset(parameters.get("asset"))
        if dataset in {"fund_flow", "margin_trading"}:
            start_date, end_date = _bounded_history_range(parameters)
        if dataset == "fund_flow":
            return adapter.fetch_fund_flow(
                codes=[asset],
                start_date=start_date,
                end_date=end_date,
            )
        if dataset == "margin_trading":
            return adapter.fetch_margin_trading(
                codes=[asset],
                start_date=start_date,
                end_date=end_date,
            )
        if dataset == "holder_data" and parameters.get("end_date"):
            return adapter.fetch_holder_data(
                codes=[asset], report_date=_day(parameters.get("end_date"))
            )
        raise ProviderError("data_not_equivalent")
    # Existing reviewed adapter has no equivalent macro/rate, fund-holdings,
    # index-constituent, or arbitrary formula method. These remain fail closed.
    raise ProviderError("data_not_equivalent")


async def fetch(query: BusinessQuery, *, adapter: Any | None = None) -> Result:
    result = Result(provider_id="wind", source_url="wind://local-session")
    try:
        _preflight(query)
        future = _submit(query, adapter)
        try:
            frame = await asyncio.wait_for(
                asyncio.shield(asyncio.wrap_future(future)),
                timeout=WIND_PROVIDER_DEADLINE_SECONDS,
            )
        except TimeoutError as exc:
            raise ProviderError("deadline") from exc
        result.rows = _records(frame, query)
        quality_limitations = _quality_limitations(result.rows, query)
        result.raw = [json.dumps(result.rows, ensure_ascii=False, default=str).encode()]
        result.raw_bytes = len(result.raw[0])
        result.pages_fetched = 1
        result.provider_total = len(result.rows)
        result.pagination_complete = True
        result.status = (
            "partial" if quality_limitations else ("complete" if result.rows else "empty")
        )
        result.as_of = max(
            (
                str(row.get("as_of") or row.get("date") or row.get("report_period"))
                for row in result.rows
                if row.get("as_of") or row.get("date") or row.get("report_period")
            ),
            default=None,
        )
        result.fields = _field_metadata(query)
        result.limitations = quality_limitations + [
            "Wind 字段单位、日期与复权口径仅按当前封闭映射返回；未声明口径不推断。",
            "专业数据覆盖与权限以当前本机登录会话为准。",
        ]
    except asyncio.CancelledError:
        log.info("datahub_wind_cancelled", capability=query.capability)
        raise
    except ProviderError as exc:
        result.status = "failed"
        result.rows = []
        result.limitations = [str(exc)]
        log.warning("datahub_wind_rejected", capability=query.capability, reason=str(exc))
    except (AttributeError, TypeError) as exc:
        result.status = "failed"
        result.rows = []
        result.limitations = ["wind_method_unavailable"]
        log.warning("datahub_wind_method_unavailable", error_type=type(exc).__name__)
    except Exception as exc:  # noqa: BLE001 - installed Wind/Excel errors vary by version.
        code = (
            "wind_not_logged_in"
            if type(exc).__name__ in {"WindNotConnectedError", "WindSessionExpiredError"}
            else "wind_provider_error"
        )
        result.status = "failed"
        result.rows = []
        result.limitations = [code]
        log.warning("datahub_wind_failed", error_type=type(exc).__name__)
    return result
