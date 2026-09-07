"""Static DataHub capability/source catalog. Reads configuration only; never imports providers."""

from __future__ import annotations

import os
from datetime import datetime
from importlib.util import find_spec
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import BUSINESS_TOOLS, DataCapabilityId

IntegrationState = Literal["ready", "blocked_config", "blocked_dependency", "disabled", "error"]
HealthState = Literal["untested", "checking", "healthy", "degraded", "unavailable"]


class SourceReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_exists: bool
    integration_completed: bool
    configured: bool
    dependency_ready: bool
    allowed: bool
    callable: bool
    integration_state: IntegrationState
    health: HealthState = "untested"
    last_checked_at: datetime | None = None
    failure_code: str | None = Field(default=None, pattern=r"^[a-z0-9_]+$")
    duration_ms: int | None = Field(default=None, ge=0)


class DataSourceDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    family: Literal["formal", "datahub", "legacy"]
    source_type: Literal["official", "professional", "public", "library", "search", "local"]
    description: str
    auth_type: Literal["none", "api_key", "account", "terminal", "local"]
    config_keys: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)
    fee: Literal["free", "account", "possibly_metered", "unknown"]
    limitations: list[str] = Field(default_factory=list)
    readiness: SourceReadiness


class ProviderBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    source_id: str
    datasets: list[str]
    priority: int = Field(ge=1)
    markets: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    coverage: str
    implemented: bool


class DataCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    category: str
    description: str
    tool_id: str
    parameters: list[dict]
    fields: list[str]
    markets: list[str]
    assets: list[str]
    source_count: int = 0
    callable_source_count: int = 0


SourceSpec = tuple[str, str, str, str, str, list[str], list[str], list[str], str, str]
CapabilitySpec = tuple[DataCapabilityId, str, str, str, list[str], list[str], list[str], list[str]]

SOURCE_SPECS: tuple[SourceSpec, ...] = (
    (
        "wind",
        "Wind",
        "formal",
        "professional",
        "terminal",
        ["CJ_KEY"],
        ["WindPy/xlwings"],
        ["A股", "港股", "债券", "基金"],
        "account",
        "专业终端；仅在本机授权会话可用。",
    ),
    (
        "tinysoft",
        "天软",
        "formal",
        "professional",
        "terminal",
        [],
        ["cjpy"],
        ["A股", "基金目录"],
        "account",
        "已接入证券目录、交易日历、历史行情和实时快照；其他登记能力不会被自动路由选中。",
    ),
    (
        "ifind",
        "iFinD",
        "legacy",
        "professional",
        "terminal",
        ["IFIND_ACCOUNTS_JSON", "IFIND_USERNAME"],
        ["iFinDPy"],
        ["A股", "宏观"],
        "account",
        "旧适配器，尚未完成 DataHub 查询边界。",
    ),
    (
        "akshare",
        "AKShare",
        "formal",
        "library",
        "none",
        [],
        ["akshare"],
        ["A股", "基金", "宏观"],
        "free",
        "公开聚合库；上游口径与可用性可能变化。",
    ),
    (
        "baostock",
        "BaoStock",
        "formal",
        "library",
        "none",
        [],
        ["baostock"],
        ["A股"],
        "free",
        "历史行情为主；实时与新闻覆盖有限。",
    ),
    (
        "tushare",
        "Tushare",
        "legacy",
        "professional",
        "api_key",
        ["TUSHARE_TOKEN"],
        ["tushare"],
        ["A股"],
        "possibly_metered",
        "旧多源行情适配器中的来源，积分与权限影响覆盖。",
    ),
    (
        "yahoo",
        "Yahoo Finance",
        "formal",
        "public",
        "none",
        [],
        ["yfinance"],
        ["美股", "港股", "全球指数"],
        "free",
        "非官方聚合入口；中国市场字段覆盖有限。",
    ),
    (
        "chinastock",
        "ChinaStock",
        "legacy",
        "library",
        "none",
        [],
        [],
        ["A股", "宏观"],
        "unknown",
        "旧聚合适配器，尚未完成 DataHub 查询边界。",
    ),
    (
        "local_cache",
        "本地数据 / 缓存",
        "legacy",
        "local",
        "local",
        [],
        [],
        ["已缓存范围"],
        "free",
        "只读取已授权的会话快照，不跨会话复用。",
    ),
    (
        "csindex",
        "中证指数",
        "formal",
        "official",
        "none",
        [],
        [],
        ["中证指数"],
        "free",
        "官方指数成分与估值页面；尚未迁入按需 DataHub。",
    ),
    (
        "szse",
        "深交所",
        "formal",
        "official",
        "none",
        [],
        [],
        ["深市"],
        "free",
        "现有 SourceSpec 已停用，恢复前不可调用。",
    ),
    (
        "cninfo",
        "巨潮资讯",
        "formal",
        "official",
        "none",
        [],
        [],
        ["A股公告"],
        "free",
        "现有 SourceSpec 已停用，恢复前不可调用。",
    ),
    (
        "cls",
        "财联社",
        "datahub",
        "public",
        "none",
        [],
        [],
        ["中国市场资讯"],
        "free",
        "当前仅财联社电报完成 DataHub 适配。",
    ),
    (
        "cnstock_flash",
        "中国证券网快讯",
        "formal",
        "public",
        "none",
        [],
        [],
        ["中国市场资讯"],
        "free",
        "正式 Connector 存在，尚未迁入按需 DataHub。",
    ),
    (
        "cnstock_news",
        "中国证券网新闻",
        "formal",
        "public",
        "none",
        [],
        [],
        ["中国市场资讯"],
        "free",
        "正式 Connector 存在，尚未迁入按需 DataHub。",
    ),
    (
        "zhiqiu_reports",
        "知丘研报",
        "formal",
        "public",
        "account",
        ["ZQ_ACCOUNTS_JSON", "ZQ_ACCOUNTS"],
        [],
        ["A股研报"],
        "account",
        "需要有效授权；不向模型暴露会话凭据。",
    ),
    (
        "zhiqiu_wechat",
        "知丘公众号",
        "formal",
        "public",
        "account",
        ["ZQ_ACCOUNTS_JSON", "ZQ_ACCOUNTS"],
        [],
        ["公众号文章"],
        "account",
        "需要有效授权；不向模型暴露会话凭据。",
    ),
    (
        "zhiqiu_transcript",
        "知丘纪要",
        "formal",
        "public",
        "account",
        ["ZQ_ACCOUNTS_JSON", "ZQ_ACCOUNTS"],
        [],
        ["会议纪要"],
        "account",
        "需要有效授权；不向模型暴露会话凭据。",
    ),
    (
        "eastmoney_fund",
        "东方财富基金",
        "datahub",
        "public",
        "none",
        [],
        [],
        ["公募基金"],
        "free",
        "净值、基本资料、分红与已披露持仓已完成按需适配。",
    ),
    (
        "tavily",
        "Tavily",
        "legacy",
        "search",
        "api_key",
        ["TAVILY_API_KEY"],
        [],
        ["公开网页"],
        "possibly_metered",
        "旧网页搜索 Provider，尚未接入 DataHub 业务工具。",
    ),
    (
        "bing",
        "Bing Search",
        "legacy",
        "search",
        "api_key",
        ["BING_API_KEY"],
        [],
        ["公开网页"],
        "possibly_metered",
        "旧网页搜索 Provider，尚未接入 DataHub 业务工具。",
    ),
)

CAPABILITY_SPECS: tuple[CapabilitySpec, ...] = (
    (
        "search_assets",
        "证券目录",
        "基础资料",
        "识别股票、基金和指数代码。",
        ["query", "market", "asset_type"],
        ["asset_id", "code", "name", "market", "asset_type"],
        ["A股", "基金"],
        ["股票", "基金", "指数"],
    ),
    (
        "trading_calendar",
        "交易日历",
        "市场基础",
        "读取交易日与开闭市标记。",
        ["market", "start_date", "end_date"],
        ["date", "is_open"],
        ["A股"],
        ["市场"],
    ),
    (
        "market_bars",
        "历史行情",
        "行情",
        "读取日线等历史行情及复权口径。",
        ["asset", "start_date", "end_date", "frequency", "adjustment"],
        ["date", "open", "high", "low", "close", "volume"],
        ["A股", "港股", "美股"],
        ["股票", "指数", "ETF"],
    ),
    (
        "market_snapshot",
        "实时快照",
        "行情",
        "读取当前或最近可得行情快照。",
        ["assets", "fields"],
        ["as_of", "price", "change_pct", "volume"],
        ["A股", "港股", "美股"],
        ["股票", "指数", "ETF"],
    ),
    (
        "index_data",
        "指数数据",
        "指数",
        "读取指数行情、成分和估值。",
        ["index", "dataset", "date"],
        ["date", "constituent", "weight", "valuation"],
        ["A股", "全球"],
        ["指数"],
    ),
    (
        "financials",
        "财务数据",
        "财务",
        "读取财务报表与标准化指标。",
        ["asset", "statements", "periods"],
        ["report_period", "field", "value", "unit"],
        ["A股", "港股", "美股"],
        ["股票"],
    ),
    (
        "market_activity",
        "资金与交易事件",
        "市场活动",
        "读取资金流、融资融券、大宗交易和股东信息。",
        ["asset", "dataset", "start_date", "end_date"],
        ["date", "event_type", "value", "unit"],
        ["A股"],
        ["股票", "市场"],
    ),
    (
        "factor_macro",
        "因子与宏观",
        "因子宏观",
        "读取因子表、技术指标和宏观序列。",
        ["series", "assets", "start_date", "end_date"],
        ["date", "series", "value", "unit"],
        ["A股", "宏观"],
        ["股票", "宏观"],
    ),
    (
        "fund_data",
        "基金数据",
        "基金",
        "读取基金净值、基本资料、分红、持仓或目录。",
        ["dataset", "code", "start_date", "end_date", "year", "limit"],
        ["date", "value", "report_period", "disclosure_date"],
        ["中国公募"],
        ["主动基金", "ETF"],
    ),
    (
        "search_news",
        "新闻与快讯",
        "资讯",
        "按关键词或最新时间读取结构化新闻与电报。",
        ["query", "limit", "start_date", "end_date"],
        ["published_at", "title", "content", "source_url"],
        ["中国市场", "全球"],
        ["新闻"],
    ),
    (
        "search_announcements",
        "公司公告",
        "公告",
        "搜索交易所或法定披露公告。",
        ["asset", "query", "start_date", "end_date"],
        ["published_at", "title", "document_url"],
        ["A股"],
        ["公告"],
    ),
    (
        "search_research",
        "研究资料",
        "研究",
        "搜索研报、公众号和会议纪要。",
        ["query", "document_type", "limit"],
        ["published_at", "title", "summary", "source_url"],
        ["A股"],
        ["研报", "纪要", "公众号"],
    ),
    (
        "search_web",
        "网页搜索",
        "网页",
        "通过已配置的受控搜索供应商检索公开网页。",
        ["query", "limit"],
        ["title", "snippet", "url"],
        ["公开网页"],
        ["网页"],
    ),
)

BINDING_SPECS = {
    "search_assets": [
        ("tinysoft", ["stock_list", "fund_list"]),
        ("akshare", ["stock_master"]),
        ("baostock", ["stock_master"]),
        ("szse", ["listed_companies"]),
        ("tushare", ["stock_basic"]),
        ("chinastock", ["asset_search"]),
        ("local_cache", ["asset_cache"]),
    ],
    "trading_calendar": [
        ("tinysoft", ["trading_days"]),
        ("akshare", ["trading_calendar"]),
        ("baostock", ["trade_dates"]),
        ("tushare", ["trade_cal"]),
    ],
    "market_bars": [
        ("tinysoft", ["daily_quotes"]),
        ("wind", ["daily_quotes"]),
        ("ifind", ["quotes"]),
        ("akshare", ["stock_daily", "index_daily"]),
        ("baostock", ["stock_daily"]),
        ("tushare", ["daily"]),
        ("yahoo", ["stock_daily"]),
        ("chinastock", ["quotes"]),
        ("local_cache", ["price_cache"]),
    ],
    "market_snapshot": [
        ("tinysoft", ["table_data"]),
        ("wind", ["realtime"]),
        ("ifind", ["quotes"]),
        ("akshare", ["spot"]),
        ("yahoo", ["stock_info"]),
        ("chinastock", ["quotes"]),
    ],
    "index_data": [
        ("csindex", ["index_constituents", "index_valuation"]),
        ("tinysoft", ["daily_quotes"]),
        ("wind", ["index_data"]),
        ("akshare", ["index_daily"]),
        ("yahoo", ["index_daily"]),
    ],
    "financials": [
        ("tinysoft", ["table_data"]),
        ("wind", ["financial_statements"]),
        ("ifind", ["financials"]),
        ("akshare", ["financials"]),
        ("baostock", ["financials"]),
        ("tushare", ["fina_indicator"]),
        ("yahoo", ["financials"]),
        ("chinastock", ["financials"]),
    ],
    "market_activity": [
        ("wind", ["fund_flow", "margin_trading", "block_trades", "holder_data"]),
        ("ifind", ["fund_flow", "industry"]),
        ("chinastock", ["fund_flow", "sentiment"]),
        ("akshare", ["fund_flow"]),
    ],
    "factor_macro": [
        ("tinysoft", ["factor_data", "table_data"]),
        ("ifind", ["macro", "technical"]),
        ("chinastock", ["macro", "technical"]),
        ("akshare", ["macro"]),
    ],
    "fund_data": [
        ("eastmoney_fund", ["fund_nav", "fund_profile", "fund_distributions", "fund_holdings"]),
        ("tinysoft", ["fund_list"]),
    ],
    "search_news": [
        ("cls", ["telegram"]),
        ("cnstock_flash", ["flash"]),
        ("cnstock_news", ["news"]),
        ("zhiqiu_wechat", ["news"]),
        ("akshare", ["news"]),
        ("yahoo", ["news"]),
        ("baostock", ["news"]),
    ],
    "search_announcements": [("cninfo", ["announcements"]), ("szse", ["company_info"])],
    "search_research": [
        ("zhiqiu_reports", ["report"]),
        ("zhiqiu_transcript", ["meeting"]),
        ("zhiqiu_wechat", ["news"]),
    ],
    "search_web": [("tavily", ["web_search"]), ("bing", ["web_search"])],
}

INTEGRATED = {"eastmoney_fund", "cls", "tinysoft", "akshare"}
DISABLED = {"szse", "cninfo"}
IMPLEMENTED_BINDINGS = {
    ("tinysoft", "search_assets"),
    ("tinysoft", "trading_calendar"),
    ("tinysoft", "market_bars"),
    ("tinysoft", "market_snapshot"),
    ("akshare", "search_assets"),
    ("akshare", "market_bars"),
    ("akshare", "market_snapshot"),
    ("akshare", "financials"),
    ("akshare", "market_activity"),
}


def _configured(auth: str, keys: list[str], environ: dict[str, str]) -> bool:
    if auth in {"none", "local"}:
        return True
    if not keys:
        return False
    return any(bool(environ.get(key, "").strip()) for key in keys)


def _dependency_ready(source_id: str, dependencies: list[str]) -> bool:
    if not dependencies:
        return True
    if source_id in {"tinysoft", "akshare"}:
        try:
            return find_spec("cjpy" if source_id == "tinysoft" else "akshare") is not None
        except (ImportError, AttributeError, ValueError):
            return False
    return False


def build_catalog(*, probes: dict[str, dict] | None = None, environ=None) -> dict:
    """Return a fresh JSON-ready catalog without importing or constructing any connector."""
    env = dict(os.environ if environ is None else environ)
    probe_map = probes or {}
    sources = []
    for source_spec in SOURCE_SPECS:
        sid, name, family, source_type, auth, keys, deps, markets, fee, limitation = source_spec
        integrated = sid in INTEGRATED
        configured = _configured(auth, keys, env)
        dependency_ready = _dependency_ready(sid, deps)
        allowed = integrated and sid not in DISABLED
        if sid in DISABLED or not integrated:
            state: IntegrationState = "disabled"
        elif not configured:
            state = "blocked_config"
        elif not dependency_ready:
            state = "blocked_dependency"
        else:
            state = "ready"
        probe = probe_map.get(sid, {})
        health = probe.get("health", "untested")
        callable_now = state == "ready" and allowed and health not in {"unavailable"}
        sources.append(
            DataSourceDescriptor(
                id=sid,
                name=name,
                family=family,
                source_type=source_type,
                description=limitation,
                auth_type=auth,
                config_keys=keys,
                dependencies=deps,
                markets=markets,
                fee=fee,
                limitations=[limitation],
                readiness=SourceReadiness(
                    code_exists=True,
                    integration_completed=integrated,
                    configured=configured,
                    dependency_ready=dependency_ready,
                    allowed=allowed,
                    callable=callable_now,
                    integration_state=state,
                    health=health,
                    last_checked_at=probe.get("last_checked_at"),
                    failure_code=probe.get("failure_code"),
                    duration_ms=probe.get("duration_ms"),
                ),
            ).model_dump(mode="json")
        )
    by_source = {source["id"]: source for source in sources}
    bindings = []
    for capability_id, candidates in BINDING_SPECS.items():
        for priority, (source_id, datasets) in enumerate(candidates, 1):
            source = by_source[source_id]
            implemented = source_id in INTEGRATED and (
                source_id not in {"tinysoft", "akshare"}
                or (source_id, capability_id) in IMPLEMENTED_BINDINGS
            )
            bindings.append(
                ProviderBinding(
                    capability_id=capability_id,
                    source_id=source_id,
                    datasets=datasets,
                    priority=priority,
                    markets=source["markets"],
                    assets=[],
                    coverage=source["description"],
                    implemented=implemented,
                ).model_dump(mode="json")
            )
    capabilities = []
    for capability_spec in CAPABILITY_SPECS:
        cid, name, category, description, parameters, fields, markets, assets = capability_spec
        linked = [binding for binding in bindings if binding["capability_id"] == cid]
        callable_count = sum(
            binding["implemented"] and by_source[binding["source_id"]]["readiness"]["callable"]
            for binding in linked
        )
        capabilities.append(
            DataCapability(
                id=cid,
                name=name,
                category=category,
                description=description,
                tool_id=BUSINESS_TOOLS[cid],
                parameters=[
                    {
                        "name": value,
                        "required": value
                        in {
                            "asset",
                            "assets",
                            "index",
                            "series",
                            "dataset",
                            *(
                                {"query"}
                                if cid in {"search_assets", "search_research", "search_web"}
                                else set()
                            ),
                        },
                    }
                    for value in parameters
                ],
                fields=fields,
                markets=markets,
                assets=assets,
                source_count=len(linked),
                callable_source_count=callable_count,
            ).model_dump(mode="json")
        )
    summary = {
        "capabilities": len(capabilities),
        "sources": len(sources),
        "callable_sources": sum(source["readiness"]["callable"] for source in sources),
        "needs_configuration": sum(not source["readiness"]["configured"] for source in sources),
        "unavailable": sum(source["readiness"]["health"] == "unavailable" for source in sources),
    }
    return {
        "summary": summary,
        "capabilities": capabilities,
        "sources": sources,
        "bindings": bindings,
    }


def catalog_detail(kind: Literal["capability", "source"], item_id: str, **kwargs) -> dict | None:
    catalog = build_catalog(**kwargs)
    key = "capabilities" if kind == "capability" else "sources"
    item = next((row for row in catalog[key] if row["id"] == item_id), None)
    if item is None:
        return None
    if kind == "capability":
        links = [binding for binding in catalog["bindings"] if binding["capability_id"] == item_id]
        return {
            **item,
            "bindings": [
                {
                    **binding,
                    "source": next(
                        source
                        for source in catalog["sources"]
                        if source["id"] == binding["source_id"]
                    ),
                }
                for binding in links
            ],
        }
    links = [binding for binding in catalog["bindings"] if binding["source_id"] == item_id]
    return {
        **item,
        "bindings": [
            {
                **binding,
                "capability": next(
                    cap for cap in catalog["capabilities"] if cap["id"] == binding["capability_id"]
                ),
            }
            for binding in links
        ],
    }
