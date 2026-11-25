"""Source-qualified Gangtise raw daily bars through the fixed finance gateway."""

import json
from datetime import date

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import ProviderError, Result, cn_stock_identity, numeric
from .providers_finance_mcp import ENDPOINT, SOURCE, fetch, tool_payload

log = get_logger(__name__)
SCHEMA = "finance-gangtise-raw-daily-v1"


def validate_supported_query(query):
    p = query.parameters
    if (
        query.capability != "market_bars"
        or query.as_of is not None
        or query.purpose == "backtest"
        or p.get("asset_type") != "stock"
        or p.get("frequency") != "daily"
        or p.get("adjustment") != "none"
    ):
        raise ProviderError("data_not_equivalent")
    cn_stock_identity(p.get("asset"))
    try:
        start, end = date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"])
        if start > end or (end - start).days > 366:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ProviderError("workload_too_large") from None


def project(query, rows, total):
    """Reject truncation, mixed identities, duplicated dates and invalid OHLC."""
    validate_supported_query(query)
    if type(total) is not int or total != len(rows):
        raise ProviderError("finance_market_pagination_incomplete")
    output, seen = [], set()
    for native in rows:
        day = native.get("tradeDate")
        if (
            native.get("securityCode") != query.parameters["asset"]
            or not isinstance(day, str)
            or date.fromisoformat(day).isoformat() != day
            or not query.parameters["start_date"] <= day <= query.parameters["end_date"]
            or day in seen
        ):
            raise ProviderError("finance_market_identity_invalid")
        seen.add(day)
        row = {"asset": query.parameters["asset"], "date": day, "adjustment": "none"}
        for target, origin in (
            ("open", "open"),
            ("high", "high"),
            ("low", "low"),
            ("close", "close"),
            ("volume", "volume"),
            ("turnover", "amount"),
        ):
            value = numeric(native.get(origin), required=True)
            if value < 0:
                raise ProviderError("finance_market_number_invalid")
            row[target] = value
        if (
            not row["low"]
            <= min(row["open"], row["close"])
            <= max(row["open"], row["close"])
            <= row["high"]
        ):
            raise ProviderError("finance_market_ohlc_invalid")
        row["turnover_rate_pct"] = None
        output.append(row)
    return sorted(output, key=lambda row: row["date"])


async def fetch_market(query, *, transport=None, connections=None):
    validate_supported_query(query)
    p = query.parameters
    native = BusinessQuery(
        capability="external_data",
        source=SOURCE,
        parameters={
            "dataset": "gangtise_query",
            "arguments_json": json.dumps(
                {
                    "operation": "查询A股日K线",
                    "arguments": {
                        "securityList": [p["asset"]],
                        "startDate": p["start_date"],
                        "endDate": p["end_date"],
                    },
                },
                ensure_ascii=False,
            ),
            "limit": 5000,
        },
    )
    result = await fetch(native, transport=transport, connections=connections)
    if result.status == "failed":
        return result
    try:
        value = tool_payload(json.loads(result.raw[0]))
        total = value["data"]["data"]["total"]
        result.rows = project(query, result.rows, total)
        result.status = "complete" if result.rows else "empty"
        result.pagination_complete = True
        result.provider_total = total
        result.fields = {
            **{
                key: {"unit": "currency_per_share", "currency": "CNY"}
                for key in ("open", "high", "low", "close")
            },
            "volume": {"unit": "share", "currency": None},
            "turnover": {"unit": "currency", "currency": "CNY"},
            "turnover_rate_pct": {"unit": "percent", "currency": None},
        }
        result.limitations = [
            "historical_pit_not_verified",
            "units_verified_by_cross_source_sample",
            "adjustment_factor_not_interpreted",
        ]
        result.metadata = {
            "schema_version": SCHEMA,
            "upstream_id": "gangtise",
            "upstream_service": "查询A股日K线",
            "historical_point_in_time": False,
            "quality_accepted": True,
            "formal_backtest_eligible": False,
            "units_evidence": "2026-11-25:600519.SH:2026-11-10..13:baostock-raw-daily",
        }
        log.info("finance_market_completed", rows=total)
    except (ProviderError, ValueError, KeyError, TypeError, IndexError) as exc:
        code = str(exc) if isinstance(exc, ProviderError) else "finance_market_schema_invalid"
        result = Result(
            status="failed",
            provider_id=SOURCE,
            source_url=ENDPOINT,
            raw=result.raw,
            limitations=[code],
            metadata={"quality_accepted": False},
        )
        log.warning("finance_market_rejected", code=code)
    return result
