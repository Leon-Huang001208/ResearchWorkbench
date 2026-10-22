"""Provider selection and strict translation from stable business requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.observability import get_logger

from ..store import StoreError
from .adjustment_contract import validate_adjustment_parameters
from .catalog import build_catalog
from .contracts import BusinessQuery, Query
from .providers import ProviderError
from .providers_akshare import validate_supported_query

log = get_logger(__name__)


@dataclass(frozen=True)
class Resolution:
    provider_id: str
    query: Query | BusinessQuery
    attempted_sources: list[dict]


def resolve_report_weekly(
    query, *, probes=None, connection_statuses=None, environ=None
) -> Resolution:
    """Authorize the private Client API path without broadening public Wind tools.

    The general Excel bindings intentionally remain unavailable when client_api is
    selected. This closed report path checks that exact adapter's dependency later.
    """
    from .providers_wind_api import WindAPIQuery

    if not isinstance(query, WindAPIQuery):
        raise StoreError("周报取数合同无效", "weekly_query_invalid", 400)
    statuses = connection_statuses or {}
    source = next(
        item
        for item in build_catalog(probes=probes, connection_statuses=statuses, environ=environ)[
            "sources"
        ]
        if item["id"] == "wind"
    )
    readiness = source["readiness"]
    if not readiness["allowed"] or not readiness["configured"]:
        raise StoreError("Wind 周报来源未配置或未获允许", "weekly_source_unavailable", 503)
    if statuses.get("wind", {}).get("preferred_adapter") != "client_api":
        raise StoreError("周报 API 需显式选择 Client API", "weekly_client_api_not_selected", 409)
    if (
        not statuses.get("wind", {}).get("credential_store_available", True)
        or readiness["health"] == "unavailable"
    ):
        raise StoreError("Wind 周报来源状态不可用", "weekly_source_unavailable", 503)
    return Resolution(
        "wind",
        query,
        [{"source": "wind", "adapter": "client_api", "status": "selected", "reason": None}],
    )


def _integer(value, name, default, minimum=1, maximum=100):
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise StoreError(f"{name} 参数非法")
    return value


def _wind_financial_query(query: BusinessQuery) -> BusinessQuery:
    """Translate equivalent indicator naming without reducing requested periods."""
    parameters = query.parameters
    statements = parameters.get("statements", ["metrics"])
    periods = parameters.get("periods", [])
    valid = (
        statements in (["indicators"], ["metrics"])
        and isinstance(periods, list)
        and len(periods) <= 1
    )
    if valid and periods:
        try:
            valid = (
                isinstance(periods[0], str)
                and date.fromisoformat(periods[0]).isoformat() == periods[0]
            )
        except (ValueError, TypeError):
            valid = False
    if not valid:
        log.warning("datahub_wind_financial_semantics_rejected")
        raise StoreError(
            "Wind 当前仅支持最新一期或明确指定的单期财务指标", "data_not_equivalent", 400
        )
    return query.model_copy(
        update={
            "source": "wind",
            "parameters": {
                **parameters,
                "statements": ["metrics"],
                "periods": list(periods),
            },
        }
    )


def resolve(
    query: BusinessQuery,
    *,
    probes=None,
    environ=None,
    mysql_status=None,
    connection_statuses=None,
) -> Resolution:
    catalog = build_catalog(
        probes=probes,
        environ=environ,
        mysql_status=mysql_status,
        connection_statuses=connection_statuses,
    )
    bindings = [
        binding for binding in catalog["bindings"] if binding["capability_id"] == query.capability
    ]
    binding_by_source = {binding["source_id"]: binding for binding in bindings}
    sources = {source["id"]: source for source in catalog["sources"]}
    if query.capability == "external_data":
        selected = "ext_registry" if query.source == "auto" else query.source
        if selected not in binding_by_source:
            raise StoreError("指定来源不属于外部数据源目录")
        return Resolution(
            selected,
            query.model_copy(update={"source": selected}),
            [{"source": selected, "status": "selected", "reason": None}],
        )
    if query.source != "auto":
        if query.source not in sources:
            raise StoreError("指定来源不在静态目录白名单")
        if not any(binding["source_id"] == query.source for binding in bindings):
            raise StoreError("指定来源不支持该数据能力")
        ordered = [query.source]
        if query.allow_fallback:
            ordered.extend(
                binding["source_id"] for binding in bindings if binding["source_id"] != query.source
            )
    else:
        ordered = [
            binding["source_id"] for binding in sorted(bindings, key=lambda row: row["priority"])
        ]

    attempts = []
    selected = None
    unsupported_code: str | None = None
    for source_id in ordered:
        readiness = sources[source_id]["readiness"]
        reason = None
        if not binding_by_source[source_id]["implemented"]:
            reason = "capability_not_integrated"
        elif not readiness["integration_completed"]:
            reason = "not_integrated"
        elif not readiness["configured"]:
            reason = "blocked_config"
        elif not readiness["dependency_ready"]:
            reason = "blocked_dependency"
        elif not readiness["allowed"]:
            reason = "disabled"
        elif readiness["health"] == "unavailable":
            reason = "probe_unavailable"
        if reason is None and source_id == "akshare":
            try:
                validate_supported_query(query)
            except ProviderError as exc:
                reason = str(exc)
                unsupported_code = reason
                log.warning("datahub_akshare_query_semantics_rejected", reason=reason)
        if reason is None and source_id == "tinysoft" and query.capability == "factor_macro":
            try:
                validate_adjustment_parameters(query.parameters)
            except ValueError as exc:
                reason = str(exc)
                unsupported_code = reason
                log.warning("datahub_tinysoft_factor_semantics_rejected", reason=reason)
        attempts.append(
            {
                "source": source_id,
                "status": "selected" if reason is None else "skipped",
                "reason": reason,
            }
        )
        if reason is None:
            selected = source_id
            break
        if query.source != "auto" and not query.allow_fallback:
            break
    if selected is None:
        if unsupported_code is not None:
            message = (
                "天软因子请求口径不受支持"
                if query.capability == "factor_macro"
                else "AKShare 请求口径不受支持"
            )
            raise StoreError(message, unsupported_code, 400)
        code = (
            "data_capability_unavailable"
            if any(binding_by_source[source_id]["implemented"] for source_id in ordered)
            else "data_capability_not_integrated"
        )
        log.warning("datahub_source_selection_unavailable", capability=query.capability, code=code)
        raise StoreError("当前没有完成 DataHub 适配且满足配置的数据来源", code, 503)

    parameters = query.parameters
    if query.capability == "fund_data" and selected == "eastmoney_fund":
        aliases = {
            "nav": "fund_nav",
            "profile": "fund_profile",
            "distributions": "fund_distributions",
            "holdings": "fund_holdings",
            "fund_nav": "fund_nav",
            "fund_profile": "fund_profile",
            "fund_distributions": "fund_distributions",
            "fund_holdings": "fund_holdings",
        }
        dataset = parameters.get("dataset")
        if dataset not in aliases:
            raise StoreError("基金数据 dataset 必须是 nav/profile/distributions/holdings")
        legacy = Query(
            source=aliases[dataset],
            code=parameters.get("code"),
            limit=_integer(parameters.get("limit"), "limit", 30),
            start_date=parameters.get("start_date"),
            end_date=parameters.get("end_date"),
            year=parameters.get("year"),
            refresh=query.refresh,
        )
    elif query.capability == "search_news" and selected == "cls":
        legacy = Query(
            source="cls_telegraph",
            limit=_integer(parameters.get("limit"), "limit", 30),
            refresh=query.refresh,
        )
    elif selected == "tinysoft" and query.capability in {
        "search_assets",
        "trading_calendar",
        "market_bars",
        "market_snapshot",
        "factor_macro",
    }:
        legacy = query.model_copy(update={"source": "tinysoft"})
    elif selected == "akshare" and query.capability in {
        "search_assets",
        "market_bars",
        "market_snapshot",
        "financials",
        "market_activity",
    }:
        legacy = query.model_copy(update={"source": "akshare"})
    elif selected == "wind" and query.capability in {
        "market_bars",
        "market_snapshot",
        "index_data",
        "financials",
        "market_activity",
    }:
        legacy = (
            _wind_financial_query(query)
            if query.capability == "financials"
            else query.model_copy(update={"source": "wind"})
        )
    elif selected == "mysql" and query.capability in {"database_schema", "table_query"}:
        legacy = query.model_copy(update={"source": "mysql"})
    else:
        raise StoreError("所选来源已登记但尚未实现按需查询适配")
    return Resolution(selected, legacy, attempts)
