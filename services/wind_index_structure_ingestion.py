"""Persist validated Wind index structure probe results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.observability import get_logger
from data_layer.repositories.market_data_repository import MarketDataRepository
from services.wind_index_structure_probe import ProbeSnapshot

logger = get_logger(__name__)

PROVIDER_NAMES = {
    "CSI": "中证指数",
    "CNI": "国证指数",
    "HSI": "恒生指数",
    "WIND": "万得指数",
}


def persist_probe_snapshot(
    repo: MarketDataRepository,
    snapshot: ProbeSnapshot,
    *,
    trade_date: datetime,
    source: str = "wind_probe",
) -> dict[str, int]:
    """Persist successful probe rows into index/ETF structure tables."""
    try:
        grouped = _group_probe_values(snapshot)
        providers = _provider_rows(grouped)
        indices = _index_master_rows(grouped)
        etfs = _etf_master_rows(grouped)
        links = _index_etf_link_rows(grouped, source=source)
        metrics = _etf_metric_rows(grouped, trade_date=trade_date, source=source)

        summary = {
            "index_master": 0,
            "etf_master": 0,
            "index_etf_link": 0,
            "etf_daily_metric": 0,
        }
        if providers:
            repo.upsert_index_providers(providers)
        if indices:
            summary["index_master"] = repo.upsert_index_master_many(indices)
        if etfs:
            summary["etf_master"] = repo.upsert_etf_master_many(etfs)
        if links:
            summary["index_etf_link"] = repo.upsert_index_etf_links(links)
        if metrics:
            summary["etf_daily_metric"] = repo.upsert_etf_daily_metrics(metrics)
        return summary
    except Exception as exc:
        logger.error("Failed to persist Wind index structure probe snapshot: %s", exc)
        raise


def infer_index_id(index_code: str) -> str:
    """Infer provider-prefixed index id from a Wind index code."""
    code = str(index_code or "").strip().upper()
    raw_code = code.split(".", 1)[0]
    suffix = code.split(".", 1)[1] if "." in code else ""
    if suffix == "HI":
        return f"HSI:{raw_code}"
    if suffix == "WI":
        return f"WIND:{raw_code}"
    if suffix == "SZ" and raw_code.startswith("399"):
        return f"CNI:{raw_code}"
    return f"CSI:{raw_code}"


def _group_probe_values(snapshot: ProbeSnapshot) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in snapshot.rows:
        key = (row.domain, row.target_code)
        grouped.setdefault(key, {})[row.formula_key] = row.value
    return grouped


def _provider_rows(grouped: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    providers = set()
    for (domain, code), values in grouped.items():
        if domain == "index" and values.get("index_name_wss"):
            providers.add(infer_index_id(code).split(":", 1)[0])
        if domain == "etf" and values.get("etf_tracking_index_wss"):
            providers.add(infer_index_id(str(values["etf_tracking_index_wss"])).split(":", 1)[0])
    return [
        {
            "provider_code": provider_code,
            "name": PROVIDER_NAMES.get(provider_code, provider_code),
            "source_priority": 10,
            "raw_payload": {"source": "wind_probe"},
        }
        for provider_code in sorted(providers)
    ]


def _index_master_rows(grouped: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for (domain, code), values in grouped.items():
        if domain != "index" or not values.get("index_name_wss"):
            continue
        index_id = infer_index_id(code)
        provider_code, official_code = index_id.split(":", 1)
        rows.append(
            {
                "index_id": index_id,
                "provider_code": provider_code,
                "official_code": official_code,
                "wind_code": code,
                "name_cn": str(values["index_name_wss"]),
                "market": _market_from_code(code),
                "currency": _currency_from_code(code),
                "category": "unknown",
                "is_active": True,
                "raw_payload": values,
            }
        )
    return rows


def _etf_master_rows(grouped: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for (domain, code), values in grouped.items():
        if domain != "etf" or not values.get("etf_name_wss"):
            continue
        rows.append(
            {
                "etf_symbol": code,
                "name": str(values["etf_name_wss"]),
                "exchange": _exchange_from_code(code),
                "market": _market_from_code(code),
                "currency": _currency_from_code(code),
                "status": "active",
                "raw_payload": values,
            }
        )
    return rows


def _index_etf_link_rows(
    grouped: dict[tuple[str, str], dict[str, Any]],
    *,
    source: str,
) -> list[dict[str, Any]]:
    rows = []
    for (domain, code), values in grouped.items():
        if domain != "etf" or not values.get("etf_tracking_index_wss"):
            continue
        rows.append(
            {
                "index_id": infer_index_id(str(values["etf_tracking_index_wss"])),
                "etf_symbol": code,
                "tracking_role": "tracking",
                "link_source": source,
                "confidence": 0.9,
                "raw_payload": values,
            }
        )
    return rows


def _etf_metric_rows(
    grouped: dict[tuple[str, str], dict[str, Any]],
    *,
    trade_date: datetime,
    source: str,
) -> list[dict[str, Any]]:
    rows = []
    for (domain, code), values in grouped.items():
        if domain != "etf":
            continue
        nav = _number(values.get("etf_nav_wss"))
        shares = _number(values.get("etf_shares_unit_total_wss"))
        aum = _number(values.get("etf_aum_netasset_total_wss")) or _number(
            values.get("etf_aum_fund_scale_wss")
        )
        if nav is None and shares is None and aum is None:
            continue
        rows.append(
            {
                "etf_symbol": code,
                "trade_date": trade_date,
                "nav": nav,
                "shares_outstanding": shares,
                "aum": aum,
                "source": source,
                "raw_payload": values,
            }
        )
    return rows


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _exchange_from_code(code: str) -> str | None:
    suffix = str(code or "").strip().upper().split(".")[-1]
    return suffix if suffix in {"SH", "SZ", "HK"} else None


def _market_from_code(code: str) -> str:
    suffix = str(code or "").strip().upper().split(".")[-1]
    if suffix in {"HK", "HI"}:
        return "HK"
    return "CN"


def _currency_from_code(code: str) -> str:
    suffix = str(code or "").strip().upper().split(".")[-1]
    if suffix in {"HK", "HI"}:
        return "HKD"
    return "CNY"
