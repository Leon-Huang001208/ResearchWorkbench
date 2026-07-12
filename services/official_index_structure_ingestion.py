"""Ingest official CSI/CNI index constituents into structure tables."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime, time
from typing import Any, Iterable

from core.observability import get_logger
from data_layer.repositories.market_data_repository import MarketDataRepository

logger = get_logger(__name__)

PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)

PROVIDER_ROWS = {
    "CSI": {
        "provider_code": "CSI",
        "name": "中证指数",
        "official_site": "https://www.csindex.com.cn",
        "source_priority": 10,
        "raw_payload": {"source": "csindex_official_akshare"},
    },
    "CNI": {
        "provider_code": "CNI",
        "name": "国证指数",
        "official_site": "https://www.cnindex.com.cn",
        "source_priority": 10,
        "raw_payload": {"source": "cnindex_official_akshare"},
    },
}


def ingest_csi_index_components(
    repo: MarketDataRepository,
    index_code: str,
    *,
    ak_module: Any | None = None,
) -> dict[str, int]:
    """Fetch CSI constituents/weights via AKShare's CSIndex wrapper and persist them."""
    code = _clean_index_code(index_code)
    try:
        ak = ak_module or _import_akshare()
        frame = _call_without_proxy(ak.index_stock_cons_weight_csindex, code)
        components = _csi_component_rows(frame, code)
        indices = _csi_index_master_rows(frame, code)
        return _persist_rows(repo, [PROVIDER_ROWS["CSI"]], indices, components)
    except Exception as exc:
        logger.error("Failed to ingest CSI index components: %s", exc)
        raise


def ingest_cni_index_components(
    repo: MarketDataRepository,
    index_code: str,
    *,
    ak_module: Any | None = None,
) -> dict[str, int]:
    """Fetch CNI historical sample detail via AKShare's CNIndex wrapper and persist it."""
    code = _clean_index_code(index_code)
    try:
        ak = ak_module or _import_akshare()
        frame = _call_without_proxy(ak.index_detail_hist_cni, code)
        index_name = _lookup_cni_index_name(ak, code)
        components = _cni_component_rows(frame, code)
        indices = [
            {
                "index_id": f"CNI:{code}",
                "provider_code": "CNI",
                "official_code": code,
                "wind_code": f"{code}.SZ",
                "name_cn": index_name or f"国证指数{code}",
                "market": "CN",
                "currency": "CNY",
                "category": "unknown",
                "is_active": True,
                "raw_payload": {"source": "cnindex_official_akshare", "index_code": code},
            }
        ]
        return _persist_rows(repo, [PROVIDER_ROWS["CNI"]], indices, components)
    except Exception as exc:
        logger.error("Failed to ingest CNI index components: %s", exc)
        raise


def ingest_official_index_components(
    repo: MarketDataRepository,
    *,
    provider: str,
    index_codes: Iterable[str],
    ak_module: Any | None = None,
) -> dict[str, int]:
    """Batch ingest official constituents for one provider."""
    provider_code = provider.strip().upper()
    summary = {"index_master": 0, "index_component_snapshot": 0, "errors": 0}
    for index_code in index_codes:
        try:
            if provider_code == "CSI":
                result = ingest_csi_index_components(repo, index_code, ak_module=ak_module)
            elif provider_code == "CNI":
                result = ingest_cni_index_components(repo, index_code, ak_module=ak_module)
            else:
                raise ValueError(f"Unsupported official provider: {provider}")
            summary["index_master"] += result["index_master"]
            summary["index_component_snapshot"] += result["index_component_snapshot"]
        except Exception as exc:
            summary["errors"] += 1
            logger.error(
                "Official index component ingestion failed for %s:%s: %s",
                provider_code,
                index_code,
                exc,
            )
    return summary


def discover_official_index_codes(
    provider: str,
    *,
    max_count: int | None = None,
    ak_module: Any | None = None,
) -> list[str]:
    """Discover active official index codes from CSI/CNI catalogs."""
    provider_code = provider.strip().upper()
    ak = ak_module or _import_akshare()
    try:
        if provider_code == "CSI":
            frame = _call_without_proxy(ak.index_csindex_all)
            keys = ("指数代码", "index_code", "指数代码Index Code")
        elif provider_code == "CNI":
            frame = _call_without_proxy(ak.index_all_cni)
            keys = ("指数代码", "index_code")
        else:
            raise ValueError(f"Unsupported official provider: {provider}")
    except Exception as exc:
        logger.error("Failed to discover official index codes for %s: %s", provider_code, exc)
        raise

    codes = []
    seen = set()
    for raw in _records(frame):
        code = _clean_index_code(_value(raw, *keys))
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
        if max_count is not None and max_count > 0 and len(codes) >= max_count:
            break
    return codes


def _csi_component_rows(frame: Any, index_code: str) -> list[dict[str, Any]]:
    rows = []
    for position, raw in enumerate(_weight_ranked_records(frame), start=1):
        component_code = _clean_stock_code(_value(raw, "成分券代码", "证券代码", "样本代码"))
        if not component_code:
            continue
        trade_date = _parse_datetime(_value(raw, "日期", "交易日期"))
        exchange = str(_value(raw, "交易所", "市场", default="") or "")
        symbol = _stock_symbol(component_code, exchange)
        rows.append(
            {
                "index_id": f"CSI:{index_code}",
                "index_symbol": index_code,
                "provider_code": "CSI",
                "component_symbol": symbol,
                "component_name": _text(_value(raw, "成分券名称", "证券简称", "样本简称")),
                "market": _market_from_symbol(symbol),
                "weight": _number(_value(raw, "权重", "权重(%)", "weight")),
                "weight_pct": _number(_value(raw, "权重", "权重(%)", "weight")),
                "rank": position,
                "as_of": trade_date,
                "trade_date": trade_date,
                "source": "csindex_official_akshare",
                "source_scope": "full",
                "raw_payload": _jsonable(raw),
            }
        )
    return rows


def _cni_component_rows(frame: Any, index_code: str) -> list[dict[str, Any]]:
    rows = []
    for position, raw in enumerate(_weight_ranked_records(frame), start=1):
        component_code = _clean_stock_code(_value(raw, "样本代码", "证券代码", "成分券代码"))
        if not component_code:
            continue
        trade_date = _parse_datetime(_value(raw, "日期", "交易日期"))
        symbol = _stock_symbol(component_code, "")
        rows.append(
            {
                "index_id": f"CNI:{index_code}",
                "index_symbol": index_code,
                "provider_code": "CNI",
                "component_symbol": symbol,
                "component_name": _text(_value(raw, "样本简称", "证券简称", "成分券名称")),
                "market": _text(_value(raw, "所属行业")) or _market_from_symbol(symbol),
                "weight": _number(_value(raw, "权重", "权重(%)", "weight")),
                "weight_pct": _number(_value(raw, "权重", "权重(%)", "weight")),
                "rank": position,
                "as_of": trade_date,
                "trade_date": trade_date,
                "source": "cnindex_official_akshare",
                "source_scope": "full",
                "raw_payload": _jsonable(raw),
            }
        )
    return rows


def _csi_index_master_rows(frame: Any, index_code: str) -> list[dict[str, Any]]:
    records = _records(frame)
    first = records[0] if records else {}
    return [
        {
            "index_id": f"CSI:{index_code}",
            "provider_code": "CSI",
            "official_code": index_code,
            "wind_code": _wind_code_for_index("CSI", index_code),
            "name_cn": _text(_value(first, "指数名称")) or f"中证指数{index_code}",
            "name_en": _text(_value(first, "指数英文名称")),
            "market": "CN",
            "currency": "CNY",
            "category": "unknown",
            "is_active": True,
            "raw_payload": {"source": "csindex_official_akshare", "index_code": index_code},
        }
    ]


def _lookup_cni_index_name(ak: Any, index_code: str) -> str | None:
    try:
        frame = _call_without_proxy(ak.index_all_cni)
        for raw in _records(frame):
            if _clean_index_code(_value(raw, "指数代码")) == index_code:
                return _text(_value(raw, "指数简称", "指数名称"))
    except Exception as exc:
        logger.warning("Failed to fetch CNI index catalog for %s: %s", index_code, exc)
    return None


def _persist_rows(
    repo: MarketDataRepository,
    providers: list[dict[str, Any]],
    indices: list[dict[str, Any]],
    components: list[dict[str, Any]],
) -> dict[str, int]:
    if providers:
        repo.upsert_index_providers(providers)
    summary = {"index_master": 0, "index_component_snapshot": 0}
    if indices:
        summary["index_master"] = repo.upsert_index_master_many(indices)
    if components:
        summary["index_component_snapshot"] = repo.upsert_index_components(components)
    return summary


def _import_akshare() -> Any:
    try:
        import akshare as ak

        return ak
    except Exception as exc:
        logger.error("AKShare import failed: %s", exc)
        raise


def _call_without_proxy(func: Any, *args: Any, **kwargs: Any) -> Any:
    with _without_proxy_env():
        return func(*args, **kwargs)


@contextmanager
def _without_proxy_env():
    original = {key: os.environ.get(key) for key in PROXY_ENV_VARS}
    try:
        for key in PROXY_ENV_VARS:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    return list(frame)


def _weight_ranked_records(frame: Any) -> list[dict[str, Any]]:
    records = _records(frame)
    return sorted(
        records,
        key=lambda raw: _number(_value(raw, "权重", "权重(%)", "weight")) or 0.0,
        reverse=True,
    )


def _value(raw: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return default


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10] if fmt != "%Y%m%d" else text[:8], fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def _clean_index_code(value: Any) -> str:
    code = str(value or "").strip().upper().split(".", 1)[0]
    if code.isdigit():
        return code.zfill(6)
    return code


def _clean_stock_code(value: Any) -> str:
    text = str(value or "").strip().upper().split(".", 1)[0]
    if not text or text == "NAN":
        return ""
    return text.zfill(6) if text.isdigit() else text


def _stock_symbol(code: str, exchange: str) -> str:
    if code.endswith((".SH", ".SZ", ".BJ", ".HK")):
        return code
    exchange_text = str(exchange or "")
    if "深圳" in exchange_text or code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if "北京" in exchange_text or code.startswith(("4", "8")):
        return f"{code}.BJ"
    if "上海" in exchange_text or code.startswith(("5", "6", "9")):
        return f"{code}.SH"
    return code


def _market_from_symbol(symbol: str) -> str:
    suffix = symbol.rsplit(".", 1)[-1] if "." in symbol else ""
    return {"SH": "上海证券交易所", "SZ": "深圳证券交易所", "BJ": "北京证券交易所"}.get(
        suffix,
        "CN",
    )


def _wind_code_for_index(provider: str, index_code: str) -> str:
    if provider == "CNI" or index_code.startswith("399"):
        return f"{index_code}.SZ"
    return f"{index_code}.SH"


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _jsonable(raw: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if value in (None, ""):
            cleaned[key] = None
        elif isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        elif isinstance(value, datetime):
            cleaned[key] = value.isoformat()
        elif isinstance(value, date):
            cleaned[key] = value.isoformat()
        else:
            cleaned[key] = str(value)
    return cleaned
