"""Fixed OpenBB SDK reads in a separately installed interpreter.

OpenBB is a large optional dependency tree (217 packages in the reviewed
install), so it is never imported into the Web Host. Each request starts an
owned child process with a minimal environment and a fixed module command.
This is a lifetime and environment boundary, not an OS sandbox.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import MAX_QUERY_BYTES, MAX_ROWS, ProviderError, Result

log = get_logger(__name__)
DEADLINE = 30
PROBE_DEADLINE = 12
CONTRACT = "openbb-equity-v2"
PYTHON_ENV = "RWB_OPENBB_PYTHON"
PRICE_DATASET = "equity_daily"
FUNDAMENTAL_DATASETS = {
    "equity_income": ("income", "income_statement"),
    "equity_balance": ("balance", "balance_sheet"),
    "equity_cash": ("cash", "cash_flow"),
    "equity_ratios": ("ratios", "ratios"),
}
DATASETS = frozenset({PRICE_DATASET, *FUNDAMENTAL_DATASETS})
PERIODS = frozenset({"annual", "quarter"})
PROVIDERS = frozenset({"nasdaq", "cboe", "tmx"})
SAFE_CODES = frozenset(
    {
        "deadline",
        "vendor_unreachable",
        "missing_dependency",
        "vendor_schema_invalid",
        "data_not_equivalent",
        "data_operation_unsupported",
        "invalid_date_range",
        "invalid_asset",
        "invalid_provider",
        "invalid_frequency",
        "invalid_adjustment",
        "invalid_period",
        "invalid_limit",
        "row_limit",
        "openbb_historical_semantics_unsupported",
        "openbb_arguments_unsupported",
        "external_arguments_invalid",
        "external_arguments_forbidden",
    }
)
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="datahub-openbb")
_CAPACITY = threading.BoundedSemaphore(1)
_FUTURES: set[Future] = set()
_FUTURES_LOCK = threading.Lock()


def active_futures() -> tuple[Future, ...]:
    """Witness actual SDK work independently of cancelled coroutine waiters."""
    with _FUTURES_LOCK:
        return tuple(future for future in _FUTURES if not future.done())


def interpreter() -> str | None:
    """The explicitly configured OpenBB interpreter; never the Host interpreter."""
    configured = os.environ.get(PYTHON_ENV, "").strip()
    if not configured:
        return None
    path = Path(configured).expanduser()
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        return None
    return str(path)


def _release_capacity(_future: Future) -> None:
    with _FUTURES_LOCK:
        _FUTURES.discard(_future)
    try:
        _CAPACITY.release()
    except ValueError:
        log.error("datahub_openbb_capacity_release_failed")


def _submit(query: BusinessQuery) -> Future | None:
    if interpreter() is None:
        raise ProviderError("missing_dependency")
    if not _CAPACITY.acquire(blocking=False):
        return None
    try:
        future = _EXECUTOR.submit(_invoke, query)
    except Exception:
        _CAPACITY.release()
        raise
    with _FUTURES_LOCK:
        _FUTURES.add(future)
    future.add_done_callback(_release_capacity)
    return future


def _invoke(query: BusinessQuery) -> Result:
    executable = interpreter()
    if executable is None:
        raise ProviderError("missing_dependency")
    with tempfile.TemporaryDirectory(prefix="rwb-openbb-") as private:
        environment = {
            "PATH": os.pathsep.join((str(Path(executable).parent), "/usr/bin", "/bin")),
            "HOME": private,
            "TMPDIR": private,
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": str(Path(__file__).resolve().parents[3]),
            "RESEARCH_RUN_MODE": "web-prod",
            "RESEARCH_PROJECT_ROOT": private,
        }
        try:
            response = subprocess.run(
                [executable, "-m", __name__.rsplit(".", 1)[0] + ".public_worker", "openbb"],
                input=query.model_dump_json().encode(),
                capture_output=True,
                timeout=DEADLINE,
                cwd=private,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired:
            log.warning("datahub_openbb_deadline")
            raise ProviderError("deadline") from None
        except OSError:
            log.warning("datahub_openbb_start_failed")
            raise ProviderError("vendor_unreachable") from None
    if response.returncode != 0 or len(response.stdout) > MAX_QUERY_BYTES * 2:
        raise ProviderError("vendor_schema_invalid")
    try:
        value = json.loads(response.stdout)
        if not value.get("ok"):
            code = value.get("code")
            raise ProviderError(code if code in SAFE_CODES else "vendor_unreachable")
        payload = value["result"]
        if set(payload) != set(Result.__dataclass_fields__):
            raise ValueError("result_schema")
        if not isinstance(payload["rows"], list) or len(payload["rows"]) > MAX_ROWS:
            raise ValueError("row_limit")
        payload["raw"] = [base64.b64decode(part, validate=True) for part in payload["raw"]]
        if sum(len(part) for part in payload["raw"]) > MAX_QUERY_BYTES:
            raise ValueError("raw_limit")
        if payload["provider_id"] != "openbb" or payload["status"] not in {
            "complete",
            "empty",
            "partial",
            "failed",
            "snapshot",
        }:
            raise ValueError("provider_identity")
        return Result(**payload)
    except ProviderError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ProviderError("vendor_schema_invalid") from None


def validate(query: BusinessQuery) -> None:
    """Reject everything outside the reviewed fixed equity datasets."""
    if query.source != "openbb" or query.capability != "external_data":
        raise ProviderError("data_operation_unsupported")
    dataset = query.parameters.get("dataset")
    if dataset not in DATASETS:
        raise ProviderError("data_operation_unsupported")
    _arguments(query.parameters.get("arguments_json"))
    if query.parameters.get("limit") not in (None, MAX_ROWS):
        raise ProviderError("openbb_arguments_unsupported")
    if query.required_semantics is not None or query.as_of is not None:
        raise ProviderError("openbb_historical_semantics_unsupported")
    if query.purpose == "backtest":
        raise ProviderError("openbb_historical_semantics_unsupported")


def _arguments(value) -> dict:
    """Fixed business inputs only; no endpoint, header, credential or module."""
    from .providers_external import arguments

    parsed = arguments(value)
    if set(parsed) - {"params", "query"}:
        raise ProviderError("openbb_arguments_unsupported")
    params = parsed.get("params", {})
    query_args = parsed.get("query", {})
    if set(params) - {"symbol", "provider", "period", "limit"}:
        raise ProviderError("openbb_arguments_unsupported")
    symbol = params.get("symbol")
    provider = params.get("provider")
    period = params.get("period", "annual")
    limit = params.get("limit", 4)
    if (
        not isinstance(symbol, str)
        or len(symbol) > 32
        or not re.fullmatch(r"[A-Za-z0-9.\-]{1,32}", symbol)
    ):
        raise ProviderError("invalid_asset")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ProviderError("invalid_provider")
    if not isinstance(period, str) or period not in PERIODS:
        raise ProviderError("invalid_period")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ProviderError("invalid_limit")

    def _day(name: str) -> str:
        value = query_args.get(name)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ProviderError("invalid_date_range")
        try:
            date.fromisoformat(value)
        except ValueError:
            raise ProviderError("invalid_date_range") from None
        return value

    if query_args:
        if set(query_args) != {"start_date", "end_date"}:
            raise ProviderError("openbb_arguments_unsupported")
        start, end = _day("start_date"), _day("end_date")
        if start > end:
            raise ProviderError("invalid_date_range")
        return {
            "symbol": symbol,
            "provider": provider,
            "period": period,
            "limit": limit,
            "start": start,
            "end": end,
        }
    return {"symbol": symbol, "provider": provider, "period": period, "limit": limit}


async def fetch(query: BusinessQuery, *, connections=None) -> Result:
    validate(query)
    future = _submit(query)
    if future is None:
        raise ProviderError("datahub_busy")
    try:
        return await asyncio.shield(asyncio.wrap_future(future))
    except asyncio.CancelledError:
        # The child is bounded by DEADLINE below and will exit on its own; keep
        # capacity held until it actually ends so a retry never overlaps it.
        log.info("datahub_openbb_cancelled")
        raise


async def probe() -> dict:
    end = datetime.now(UTC).date() - timedelta(days=1)
    start = end - timedelta(days=10)
    query = BusinessQuery(
        capability="external_data",
        source="openbb",
        parameters={
            "dataset": PRICE_DATASET,
            "arguments_json": json.dumps(
                {
                    "params": {"symbol": "AAPL", "provider": "nasdaq"},
                    "query": {"start_date": start.isoformat(), "end_date": end.isoformat()},
                }
            ),
        },
        purpose="display",
    )
    try:
        result = await asyncio.wait_for(fetch(query), timeout=PROBE_DEADLINE)
    except (TimeoutError, ProviderError) as exc:
        reason = (
            str(exc) if isinstance(exc, ProviderError) and str(exc) in SAFE_CODES else "deadline"
        )
        return {"health": "unavailable", "failure_code": reason}
    accepted = result.status in {"snapshot", "complete"} and bool(result.rows)
    return {
        "health": "healthy" if accepted else "unavailable",
        "failure_code": None if accepted else "partial_or_empty",
        "rows": len(result.rows),
    }


def invoke(query: BusinessQuery) -> Result:
    """Child-side execution; only fixed calls, no caller-provided expressions."""
    from openbb import obb

    inputs = _arguments(query.parameters.get("arguments_json"))
    symbol = inputs["symbol"]
    provider = inputs["provider"]
    dataset = query.parameters.get("dataset")
    if dataset == PRICE_DATASET:
        if not {"start", "end"}.issubset(inputs):
            raise ProviderError("invalid_date_range")
        output = obb.equity.price.historical(
            symbol, start_date=inputs["start"], end_date=inputs["end"], provider=provider
        )
        source_url = "https://docs.openbb.co/python/reference/equity/price/historical"
        dataset_fields = {
            "date": {"type": "date", "unit": "date"},
            "open": {"type": "number", "unit": "currency_per_share"},
            "high": {"type": "number", "unit": "currency_per_share"},
            "low": {"type": "number", "unit": "currency_per_share"},
            "close": {"type": "number", "unit": "currency_per_share"},
            "volume": {"type": "number", "unit": "share"},
        }
        extra_limitations = ["未声明币种，未认证历史修订与 PIT。"]
    else:
        if inputs.get("start") or inputs.get("end"):
            raise ProviderError("openbb_arguments_unsupported")
        method, statement = FUNDAMENTAL_DATASETS[dataset]
        call = getattr(obb.equity.fundamental, method)
        output = call(
            symbol,
            period=inputs["period"],
            limit=inputs["limit"],
            provider=provider,
        )
        source_url = f"https://docs.openbb.co/python/reference/equity/fundamental/{method}"
        dataset_fields = {
            "symbol": {"type": "string", "unit": "identifier"},
            "period_ending": {"type": "date", "unit": "date"},
            "fiscal_period": {"type": "string", "unit": "period"},
            "fiscal_year": {"type": "integer", "unit": "year"},
        }
        extra_limitations = [
            f"报表口径为 {statement}；金额单位与币种未由 OpenBB 统一声明。",
            "period_ending 是财务期间截止日，不等于公告日或可得日。",
            "未认证历史修订、重述与 PIT。",
        ]
    frame = output.to_dataframe().reset_index()
    raw = frame.to_csv(index=False).encode()
    rows = []
    for record in frame.to_dict(orient="records"):
        observed = {
            str(key): (value.isoformat() if hasattr(value, "isoformat") else value)
            for key, value in record.items()
        }
        for value in observed.values():
            if isinstance(value, float) and not math.isfinite(value):
                raise ProviderError("vendor_schema_invalid")
        rows.append(observed)
    result = Result(
        rows=rows,
        raw=[raw],
        source_url=source_url,
        status="snapshot" if rows else "empty",
        pages_fetched=1,
        pagination_complete=True,
        provider_id="openbb",
        fields=dataset_fields,
        limitations=[
            "经 OpenBB 的 provider 转发；OpenBB 不是原始来源，需按原始来源单独核验。",
            *extra_limitations,
        ],
        metadata={
            "schema_version": CONTRACT,
            "upstream_id": "openbb",
            "openbb_provider": provider,
            "openbb_dataset": dataset,
            "openbb_period": inputs["period"] if dataset != PRICE_DATASET else None,
            "openbb_limit": inputs["limit"] if dataset != PRICE_DATASET else None,
            "transport": "openbb_sdk_subprocess",
            "independent_source": False,
        },
    )
    return result


def main() -> int:
    try:
        content = sys.stdin.buffer.read(32769)
        if len(content) > 32768:
            raise ProviderError("vendor_schema_invalid")
        query = BusinessQuery.model_validate_json(content)
        validate(query)
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink):
            result = invoke(query)
        payload = asdict(result)
        payload["raw"] = [base64.b64encode(part).decode() for part in result.raw]
        encoded = json.dumps({"ok": True, "result": payload}, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > MAX_QUERY_BYTES * 2:
            raise ProviderError("vendor_schema_invalid")
        print(encoded)
    except Exception as exc:  # noqa: BLE001 - never relay SDK exception text or environment.
        code = (
            str(exc)
            if isinstance(exc, ProviderError) and str(exc) in SAFE_CODES
            else "vendor_unreachable"
        )
        print(json.dumps({"ok": False, "code": code}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
