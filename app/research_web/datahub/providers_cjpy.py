"""Optional CJPY provider extracted from the legacy connector without its ingest lifecycle."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from core.observability import get_logger

from .adjustment_contract import (
    FACTOR_DEFINITIONS,
    contract_metadata,
    validate_adjustment_parameters,
)
from .contracts import BusinessQuery
from .providers import ProviderError, Result

log = get_logger(__name__)
SOURCE_URL = "https://www.chinajoin.com/"
DEADLINE = 15
MAX_ROWS = 5000
SHANGHAI_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="datahub-tinysoft")
_CAPACITY = threading.BoundedSemaphore(1)
_FUTURES: set[Future] = set()
_FUTURES_LOCK = threading.Lock()


def active_futures() -> tuple[Future, ...]:
    """Read-only witness of SDK work still occupying the single provider worker."""
    with _FUTURES_LOCK:
        return tuple(future for future in _FUTURES if not future.done())


async def wait_for_idle(*, timeout: float | None = None) -> bool:
    """Wait for actual SDK completion; timeout/cancellation never cancels threads."""
    futures = active_futures()
    if not futures:
        return True
    try:
        async with asyncio.timeout(timeout):
            await asyncio.shield(
                asyncio.gather(
                    *(asyncio.wrap_future(future) for future in futures),
                    return_exceptions=True,
                )
            )
    except TimeoutError:
        return False
    return not active_futures()


def _observe_async_future(future: asyncio.Future) -> None:
    """Retrieve late SDK exceptions even after the caller timed out or cancelled."""
    if not future.cancelled():
        future.exception()


def _release_capacity(_future: Future) -> None:
    with _FUTURES_LOCK:
        _FUTURES.discard(_future)
    try:
        _CAPACITY.release()
    except ValueError:
        log.error("tinysoft_capacity_release_failed")


def _submit(query: BusinessQuery, token: str | None = None) -> Future | None:
    if not _CAPACITY.acquire(blocking=False):
        return None
    try:
        future = _EXECUTOR.submit(_sync_query, query, token)
    except Exception:
        _CAPACITY.release()
        raise
    with _FUTURES_LOCK:
        _FUTURES.add(future)
    future.add_done_callback(_release_capacity)
    return future


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def canonical_vendor_code(value: str) -> str:
    text = value.strip().upper()
    match = re.fullmatch(r"([0-9]{6})\.(SH|SZ|BJ|OF)", text)
    if match:
        return f"{match[2]}{match[1]}"
    if re.fullmatch(r"(?:SH|SZ|BJ|OF)[0-9]{6}", text):
        return text
    raise ProviderError("invalid_asset_code")


def _effective_token(token: str | None) -> str:
    value = token if token is not None else os.environ.get("CJ_KEY", "")
    value = value.strip()
    if not value:
        raise ProviderError("blocked_config")
    return value


def _required_date(parameters: dict, name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-?[0-9]{2}-?[0-9]{2}", value):
        raise ProviderError("invalid_date_range")
    try:
        compact = value.replace("-", "")
        parsed = date.fromisoformat(f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}")
    except ValueError as exc:
        raise ProviderError("invalid_date_range") from exc
    return parsed.isoformat()


def _required_date_range(parameters: dict) -> tuple[str, str]:
    start = _required_date(parameters, "start_date")
    end = _required_date(parameters, "end_date")
    if start > end:
        raise ProviderError("invalid_date_range")
    return start, end


def _rows(value: Any) -> list[dict]:
    if hasattr(value, "to_dict"):
        try:
            value = value.to_dict(orient="records")
        except TypeError:
            value = value.to_dict()
    if isinstance(value, dict):
        if all(not isinstance(item, (dict, list, tuple)) for item in value.values()):
            value = [{"code": key, "vendor_code": item} for key, item in value.items()]
        else:
            value = [value]
    if not isinstance(value, list):
        raise ProviderError("tinysoft_result_schema")
    rows = [item if isinstance(item, dict) else {"value": item} for item in value]
    if len(rows) > MAX_ROWS:
        raise ProviderError("row_limit")
    return [_json_value(row) for row in rows]


def _contains_secret(value: Any, secret: str) -> bool:
    if isinstance(value, str):
        return secret in value
    if isinstance(value, dict):
        return any(
            _contains_secret(str(key), secret) or _contains_secret(item, secret)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(item, secret) for item in value)
    return False


def _client(token: str | None = None):
    token = _effective_token(token)
    try:
        from cjpy.base import CjClient
    except ImportError as exc:
        raise ProviderError("blocked_dependency") from exc

    class DirectClient(CjClient):
        def _create_session(self):
            session = super()._create_session()
            session.trust_env = False
            return session

    return DirectClient(token=token, timeout=15, verify=True)


def _factor_date(value: Any, *, compact: bool = False) -> str:
    if not isinstance(value, str):
        raise ProviderError("factor_result_invalid")
    pattern = r"[0-9]{8}" if compact else r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
    if re.fullmatch(pattern, value) is None:
        raise ProviderError("factor_result_invalid")
    if compact:
        value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ProviderError("factor_result_invalid") from exc
    if parsed > datetime.now(SHANGHAI_TZ).date():
        raise ProviderError("factor_result_invalid")
    return value


def _verify_factor_definitions(rows: list[dict]) -> None:
    selected = {}
    for row in rows:
        name = row.get("因子名称")
        if not isinstance(name, str):
            raise ProviderError("factor_contract_unverified")
        if name not in FACTOR_DEFINITIONS:
            continue
        if (
            name in selected
            or row.get("公式") != FACTOR_DEFINITIONS[name]
            or any(row.get(key, "") not in (None, "") for key in ("说明", "描述"))
        ):
            raise ProviderError("factor_contract_unverified")
        selected[name] = row
    if set(selected) != set(FACTOR_DEFINITIONS):
        raise ProviderError("factor_contract_unverified")


def _normalized_factor_rows(
    rows: list[dict], parameters: dict, requested_dates: list[str]
) -> list[dict]:
    asset = parameters["assets"][0]
    vendor_code = canonical_vendor_code(asset)
    requested = set(requested_dates)
    seen: set[str] = set()
    normalized = []
    listing_dates = set()
    series = parameters["series"]
    for row in rows:
        if set(row).difference({"截止日", "代码", "名称", "复权因子", "上市日期"}):
            raise ProviderError("factor_result_invalid")
        if row.get("代码") != vendor_code:
            raise ProviderError("factor_result_invalid")
        cutoff = _factor_date(row.get("截止日"), compact=True)
        listing = _factor_date(row.get("上市日期"))
        if cutoff not in requested or cutoff in seen or cutoff < listing:
            raise ProviderError("factor_result_invalid")
        seen.add(cutoff)
        listing_dates.add(listing)
        record = {"asset": asset, "listing_date": listing}
        if series == "adjustment_factors":
            value = row.get("复权因子")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ProviderError("factor_result_invalid")
            factor = float(value)
            if not math.isfinite(factor) or factor <= 0 or (cutoff == listing and factor != 1.0):
                raise ProviderError("factor_result_invalid")
            record.update(date=cutoff, factor=factor)
        normalized.append(record)
    if seen != requested or len(listing_dates) != 1:
        raise ProviderError("factor_result_invalid")
    return sorted(normalized, key=lambda row: row.get("date", ""))


def _sync_adjustment_query(query: BusinessQuery, sdk: Any, client: Any, token: str) -> Result:
    try:
        validate_adjustment_parameters(query.parameters)
    except ValueError as exc:
        raise ProviderError(str(exc)) from exc
    metadata_call = getattr(sdk, "list_factors", None)
    if not callable(metadata_call):
        raise ProviderError("factor_contract_unverified")
    try:
        definitions = _rows(metadata_call(client=client))
    except ProviderError as exc:
        if str(exc) == "tinysoft_result_schema":
            raise ProviderError("factor_contract_unverified") from exc
        raise
    if _contains_secret(definitions, token):
        raise ProviderError("credential_reflection")
    _verify_factor_definitions(definitions)
    policy = contract_metadata()
    result = Result(
        source_url=SOURCE_URL,
        provider_id="tinysoft",
        metadata={"adjustment_contract": policy},
        raw=[json.dumps(definitions, ensure_ascii=False, allow_nan=False).encode()],
    )
    parameters = query.parameters
    series = parameters["series"]
    if series == "adjustment_metadata":
        result.rows = [dict(policy)]
        result.fields = {key: {"unit": None, "currency": None} for key in policy}
    else:
        dates = (
            parameters["dates"]
            if series == "adjustment_factors"
            else [datetime.now(SHANGHAI_TZ).date().isoformat()]
        )
        raw_rows = _rows(
            sdk.get_factor_data(
                code=canonical_vendor_code(parameters["assets"][0]),
                date=dates,
                factors=(
                    ["复权因子", "上市日期"] if series == "adjustment_factors" else ["上市日期"]
                ),
                client=client,
            )
        )
        if _contains_secret(raw_rows, token):
            raise ProviderError("credential_reflection")
        result.rows = _normalized_factor_rows(raw_rows, parameters, dates)
        result.raw.append(json.dumps(raw_rows, ensure_ascii=False, allow_nan=False).encode())
        result.fields = {
            key: {"unit": "dimensionless" if key == "factor" else None, "currency": None}
            for row in result.rows
            for key in row
        }
    log.info("tinysoft_adjustment_normalized", series=series, row_count=len(result.rows))
    return result


def _sync_query(query: BusinessQuery, token: str | None = None):
    effective_token = _effective_token(token)
    client = _client(effective_token)
    try:
        import cjpy
    except ImportError as exc:
        raise ProviderError("blocked_dependency") from exc
    parameters = query.parameters
    if query.capability == "factor_macro":
        try:
            return _sync_adjustment_query(query, cjpy, client, effective_token)
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:
                    log.warning("tinysoft_client_close_failed", error_type=type(exc).__name__)
                    raise ProviderError("provider_close_failed") from exc
    elif query.capability == "search_assets":
        rows = _rows(cjpy.get_stocks(client=client))
        needle = str(parameters.get("query", "")).strip().casefold()
        if needle:
            rows = [row for row in rows if needle in json.dumps(row, ensure_ascii=False).casefold()]
    elif query.capability == "trading_calendar":
        start, end = _required_date_range(parameters)
        rows = _rows(
            cjpy.get_trading_days(
                start=start,
                end=end,
                cycle="D",
                client=client,
            )
        )
    elif query.capability in {"market_bars", "market_snapshot"}:
        asset = parameters.get("asset")
        if asset is None:
            assets = parameters.get("assets")
            if not isinstance(assets, list) or len(assets) != 1:
                raise ProviderError("single_asset_required")
            asset = assets[0]
        if not isinstance(asset, str):
            raise ProviderError("invalid_asset_code")
        adjustment = str(parameters.get("adjustment", "forward"))
        if query.capability == "market_snapshot":
            today = datetime.now(SHANGHAI_TZ).date()
            start = (today - timedelta(days=14)).isoformat()
            end = today.isoformat()
        else:
            start, end = _required_date_range(parameters)
        rows = _rows(
            cjpy.get_market_data(
                code=canonical_vendor_code(asset),
                start=start,
                end=end,
                cycle={"daily": "day", "weekly": "W", "monthly": "M"}.get(
                    parameters.get("frequency"), parameters.get("frequency", "day")
                ),
                rate={
                    "none": "不复权",
                    "forward": "前复权",
                    "backward": "后复权",
                    "qfq": "前复权",
                    "hfq": "后复权",
                }.get(adjustment, adjustment),
                fields=parameters.get("fields"),
                client=client,
            )
        )
        if query.capability == "market_snapshot" and rows:
            rows = rows[-1:]
    else:
        raise ProviderError("tinysoft_capability_unsupported")
    if _contains_secret(rows, effective_token):
        raise ProviderError("credential_reflection")
    return rows


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, ProviderError):
        code = str(exc)
        return code if re.fullmatch(r"[a-z0-9_]{1,64}", code) else "provider_error"
    error_name = type(exc).__name__
    if error_name == "CjConfigError":
        return "blocked_config"
    if error_name == "CjAPIError":
        return "vendor_schema_invalid"
    if error_name == "CjRequestError":
        message = str(exc)
        if re.search(r"HTTP\s+(?:401|407)\b", message):
            return "vendor_auth_failed"
        if re.search(r"HTTP\s+403\b", message):
            return "vendor_permission_denied"
        if re.search(r"HTTP\s+429\b", message):
            return "vendor_rate_limited"
        cause = exc.__cause__
        if cause is not None and type(cause).__name__ in {
            "ConnectTimeout",
            "ConnectionError",
            "ProxyError",
            "ReadTimeout",
            "SSLError",
            "Timeout",
        }:
            return "vendor_unreachable"
        return "vendor_request_failed"
    if isinstance(exc, (TypeError, ValueError)):
        return "provider_contract_error"
    return "provider_error"


async def fetch(query: BusinessQuery, *, token: str | None = None) -> Result:
    result = Result(source_url=SOURCE_URL, provider_id="tinysoft")
    try:
        future = _submit(query, token)
    except Exception as exc:  # noqa: BLE001 - executor/provider submission can fail arbitrarily.
        result.status = "failed"
        result.limitations = ["provider_error"]
        log.warning("tinysoft_submit_failed", error_type=type(exc).__name__)
        return result
    if future is None:
        result.status = "failed"
        result.limitations = ["provider_busy"]
        log.warning("tinysoft_provider_busy", capability=query.capability)
        return result
    try:
        wrapped_future = asyncio.wrap_future(future)
        wrapped_future.add_done_callback(_observe_async_future)
        async with asyncio.timeout(DEADLINE):
            payload = await asyncio.shield(wrapped_future)
        if isinstance(payload, Result):
            result = payload
        else:
            result.rows = payload
            result.raw = [json.dumps(result.rows, ensure_ascii=False).encode()]
        result.raw_bytes = sum(len(part) for part in result.raw)
        result.pages_fetched = len(result.raw)
        result.provider_total = len(result.rows)
        result.pagination_complete = True
        result.status = "complete" if result.rows else "empty"
        result.as_of = datetime.now(UTC).isoformat()
        if not result.fields:
            result.fields = {
                key: {"unit": None, "currency": None} for row in result.rows for key in row
            }
        result.limitations = [
            "天软返回字段保留供应商原值；未从元数据确认的单位不推断。",
            "专业数据权限和覆盖范围以当前本机账户为准。",
        ]
    except TimeoutError:
        result.status = "failed"
        result.limitations = ["deadline"]
    except ProviderError as exc:
        result.status = "failed"
        result.limitations = [str(exc)]
    except Exception as exc:  # noqa: BLE001 - SDK exception types vary by installed version.
        result.status = "failed"
        failure_code = _failure_code(exc)
        result.limitations = [failure_code]
        log.warning(
            "tinysoft_query_failed",
            failure_code=failure_code,
            error_type=type(exc).__name__,
        )
    return result


async def probe(*, token: str | None = None) -> dict:
    query = BusinessQuery(capability="search_assets", source="tinysoft", parameters={})
    result = await fetch(query, token=token)
    return {
        "health": "healthy" if result.status in {"complete", "empty"} else "unavailable",
        "failure_code": result.limitations[-1] if result.status == "failed" else None,
    }
