"""Wind-aligned business domains; the domain is the catalog skeleton, not a tool prefix."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from core.observability import get_logger

log = get_logger(__name__)

DomainStatus = Literal["available", "reserved"]
_ID = re.compile(r"^[a-z][a-z0-9_]{0,47}$")


@dataclass(frozen=True)
class BusinessDomain:
    """One Wind business directory with an explicit, ordered tool inventory."""

    id: str
    name: str
    description: str
    tools: tuple[str, ...]
    status: DomainStatus

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.id):
            raise ValueError("invalid_domain_id")
        if not self.name.strip() or not self.description.strip():
            raise ValueError("invalid_domain_metadata")
        if self.status not in {"available", "reserved"}:
            raise ValueError("invalid_domain_status")
        if len(set(self.tools)) != len(self.tools):
            raise ValueError("duplicate_domain_tool")
        if self.status == "reserved" and self.tools:
            raise ValueError("reserved_domain_has_tools")


DOMAINS: tuple[BusinessDomain, ...] = (
    BusinessDomain(
        id="stock_data",
        name="股票数据",
        description="A 股日 K、行情快照、财务与个股活动。",
        tools=(
            "get_stock_kline",
            "get_stock_quote",
            "get_stock_financials",
            "get_stock_activity",
            "search_assets",
            "get_trading_calendar",
        ),
        status="available",
    ),
    BusinessDomain(
        id="fund_data",
        name="基金数据",
        description="基金净值、档案、分红与已披露持仓。",
        tools=("get_fund_detail",),
        status="available",
    ),
    BusinessDomain(
        id="index_data",
        name="指数与板块数据",
        description="指数最新行情快照；当前不包含历史 K 线或板块排名。",
        tools=("get_index_quote",),
        status="available",
    ),
    BusinessDomain(
        id="bond_data",
        name="债券数据",
        description="保留域；尚未定义并验收可交付工具。",
        tools=(),
        status="reserved",
    ),
    BusinessDomain(
        id="financial_docs",
        name="公告、新闻与研究文档",
        description="新闻与公告检索；当前无可用绑定，暂不注册占位工具。",
        tools=(),
        status="available",
    ),
    BusinessDomain(
        id="economic_data",
        name="宏观与行业数据",
        description="中国 CPI、GDP、PMI 与 M2 等宏观序列。",
        tools=("get_economic_series",),
        status="available",
    ),
    BusinessDomain(
        id="analytics_data",
        name="通用结构化取数",
        description="保留域；不开放自然语言通用取数兜底。",
        tools=(),
        status="reserved",
    ),
)


def _catalog_index(domain_catalog: Iterable[BusinessDomain]) -> dict[str, BusinessDomain]:
    index: dict[str, BusinessDomain] = {}
    owners: dict[str, str] = {}
    for item in domain_catalog:
        if item.id in index:
            raise ValueError("duplicate_domain_id")
        index[item.id] = item
        for tool in item.tools:
            if tool in owners:
                raise ValueError("duplicate_tool_ownership")
            owners[tool] = item.id
    return index


_BY_ID = MappingProxyType(_catalog_index(DOMAINS))


def _owner_map(
    task_names: Iterable[str] | None = None,
    domain_catalog: Iterable[BusinessDomain] = DOMAINS,
) -> dict[str, str]:
    """Return tool -> domain, rejecting orphans and duplicate ownership."""

    index = _catalog_index(domain_catalog)
    owners: dict[str, str] = {}
    for item in index.values():
        for tool in item.tools:
            owners[tool] = item.id
    if task_names is None:
        return owners
    registered = set(task_names)
    missing = sorted(set(owners) - registered)
    orphaned = sorted(registered - set(owners))
    if missing:
        raise ValueError(f"unknown_domain_tools:{','.join(missing)}")
    if orphaned:
        raise ValueError(f"unowned_business_tools:{','.join(orphaned)}")
    return owners


def validate_domains(
    task_names: Iterable[str],
    domain_catalog: Iterable[BusinessDomain] = DOMAINS,
) -> None:
    """Validate the catalog against the registered tool names."""

    try:
        _owner_map(task_names, domain_catalog)
    except ValueError as exc:
        log.error("business_domain_catalog_invalid", reason=str(exc))
        raise


def domains() -> tuple[BusinessDomain, ...]:
    return DOMAINS


def domain(domain_id: str) -> BusinessDomain:
    try:
        return _BY_ID[domain_id]
    except KeyError:
        raise KeyError("unknown_business_domain") from None


def tools_in(domain_id: str) -> tuple[str, ...]:
    return domain(domain_id).tools


def domain_of(tool: str) -> str:
    try:
        return _owner_map()[tool]
    except KeyError:
        raise KeyError("unknown_business_tool") from None
