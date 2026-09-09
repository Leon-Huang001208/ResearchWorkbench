"""Optional CJPY provider extracted from the legacy connector without its ingest lifecycle."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import ProviderError, Result

log = get_logger(__name__)
SOURCE_URL = "https://www.chinajoin.com/"
DEADLINE = 15
MAX_ROWS = 5000
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="datahub-tinysoft")
_CAPACITY = threading.BoundedSemaphore(1)


def _release_capacity(_future: Future) -> None:
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


def _client(token: str | None = None):
    token = token if token is not None else os.environ.get("CJ_KEY", "").strip()
    if not token:
        raise ProviderError("blocked_config")
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


def _sync_query(query: BusinessQuery, token: str | None = None):
    client = _client(token)
    try:
        import cjpy
    except ImportError as exc:
        raise ProviderError("blocked_dependency") from exc
    parameters = query.parameters
    if query.capability == "search_assets":
        rows = _rows(cjpy.get_stocks(client=client))
        needle = str(parameters.get("query", "")).strip().casefold()
        if needle:
            rows = [row for row in rows if needle in json.dumps(row, ensure_ascii=False).casefold()]
    elif query.capability == "trading_calendar":
        rows = _rows(
            cjpy.get_trading_days(
                start=parameters.get("start_date"),
                end=parameters.get("end_date"),
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
        rows = _rows(
            cjpy.get_market_data(
                code=canonical_vendor_code(asset),
                start=parameters.get("start_date"),
                end=parameters.get("end_date"),
                cycle=parameters.get("frequency", "day"),
                rate={
                    "none": "不复权",
                    "forward": "前复权",
                    "backward": "后复权",
                }.get(adjustment, adjustment),
                fields=parameters.get("fields"),
                client=client,
            )
        )
        if query.capability == "market_snapshot" and rows:
            rows = rows[-1:]
    else:
        raise ProviderError("tinysoft_capability_unsupported")
    return rows


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
        async with asyncio.timeout(DEADLINE):
            result.rows = await asyncio.wrap_future(future)
        result.raw = [json.dumps(result.rows, ensure_ascii=False).encode()]
        result.raw_bytes = len(result.raw[0])
        result.pages_fetched = 1
        result.provider_total = len(result.rows)
        result.pagination_complete = True
        result.status = "complete" if result.rows else "empty"
        result.as_of = datetime.now(UTC).isoformat()
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
        result.limitations = ["provider_error"]
        log.warning("tinysoft_query_failed", error_type=type(exc).__name__)
    return result


async def probe(*, token: str | None = None) -> dict:
    query = BusinessQuery(capability="search_assets", source="tinysoft", parameters={})
    result = await fetch(query, token=token)
    return {
        "health": "healthy" if result.status in {"complete", "empty"} else "unavailable",
        "failure_code": result.limitations[-1] if result.status == "failed" else None,
    }
