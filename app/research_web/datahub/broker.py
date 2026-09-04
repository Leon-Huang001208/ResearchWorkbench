"""Provider selection and strict translation from stable business requests."""

from __future__ import annotations

from dataclasses import dataclass

from ..store import StoreError
from .catalog import build_catalog
from .contracts import BusinessQuery, Query


@dataclass(frozen=True)
class Resolution:
    provider_id: str
    query: Query
    attempted_sources: list[dict]


def _integer(value, name, default, minimum=1, maximum=100):
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise StoreError(f"{name} 参数非法")
    return value


def resolve(query: BusinessQuery, *, probes=None, environ=None) -> Resolution:
    catalog = build_catalog(probes=probes, environ=environ)
    bindings = [
        binding for binding in catalog["bindings"] if binding["capability_id"] == query.capability
    ]
    sources = {source["id"]: source for source in catalog["sources"]}
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
    for source_id in ordered:
        readiness = sources[source_id]["readiness"]
        reason = None
        if not readiness["integration_completed"]:
            reason = "not_integrated"
        elif not readiness["configured"]:
            reason = "blocked_config"
        elif not readiness["dependency_ready"]:
            reason = "blocked_dependency"
        elif not readiness["allowed"]:
            reason = "disabled"
        elif readiness["health"] == "unavailable":
            reason = "probe_unavailable"
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
        raise StoreError("当前没有完成 DataHub 适配且满足配置的数据来源")

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
    else:
        raise StoreError("所选来源已登记但尚未实现按需查询适配")
    return Resolution(selected, legacy, attempts)
