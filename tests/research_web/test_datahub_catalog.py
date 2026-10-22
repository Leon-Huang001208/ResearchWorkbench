"""Static full-source catalog, manual probes and business routing."""

import asyncio
import re
import sys
import threading
from datetime import date, datetime, timedelta
from importlib import import_module
from types import ModuleType

import httpx
import pytest
from fastapi.testclient import TestClient
from test_api import NativeFixture

from app.research_web.datahub import BusinessQuery, DataHub
from app.research_web.datahub.catalog import build_catalog
from app.research_web.datahub.external_sources import EXTERNAL_SOURCES
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store, StoreError


@pytest.mark.parametrize("source", ["auto", "tavily", "bing"])
def test_web_search_without_integrated_provider_is_unavailable_not_invalid_query(source):
    from app.research_web.datahub.broker import resolve

    with pytest.raises(StoreError) as caught:
        resolve(
            BusinessQuery(capability="search_web", source=source, parameters={"query": "CSV"}),
            environ={},
        )
    assert caught.value.code == "data_capability_not_integrated"
    assert caught.value.status == 503


def test_integrated_provider_missing_configuration_is_unavailable():
    from app.research_web.datahub.broker import resolve

    with pytest.raises(StoreError) as caught:
        resolve(
            BusinessQuery(capability="database_schema", source="mysql", parameters={}),
            environ={},
            connection_statuses={},
        )
    assert caught.value.code == "data_capability_unavailable"
    assert caught.value.status == 503


def test_catalog_contains_all_declared_sources_without_constructing_connectors(
    monkeypatch,
):
    import app.research_web.datahub.catalog as module

    monkeypatch.setattr(module.os, "environ", {})
    monkeypatch.setattr(module, "find_spec", lambda name: object() if name == "akshare" else None)
    catalog = build_catalog()
    assert catalog["summary"] == {
        "capabilities": 16,
        "sources": 64,
        "callable_sources": 40,
        "needs_configuration": 15,
        "unavailable": 0,
    }
    ids = {source["id"] for source in catalog["sources"]}
    assert ids == {
        "wind",
        "tinysoft",
        "ifind",
        "akshare",
        "baostock",
        "tushare",
        "yahoo",
        "chinastock",
        "local_cache",
        "csindex",
        "szse",
        "cninfo",
        "cls",
        "cnstock_flash",
        "cnstock_news",
        "zhiqiu_reports",
        "zhiqiu_wechat",
        "zhiqiu_transcript",
        "eastmoney_fund",
        "tavily",
        "bing",
        "mysql",
        "ext_registry",
        *EXTERNAL_SOURCES,
    }
    assert all(source["readiness"]["code_exists"] for source in catalog["sources"])
    assert {source["id"] for source in catalog["sources"] if source["readiness"]["callable"]} == {
        "akshare",
        "cls",
        "eastmoney_fund",
        "ext_registry",
        *[
            sid
            for sid, item in EXTERNAL_SOURCES.items()
            if any(
                not endpoint.get("auth") and not endpoint.get("specialAuth")
                for endpoint in item.get("endpoints", [])
            )
        ],
    }
    wind = next(source for source in catalog["sources"] if source["id"] == "wind")
    assert wind["readiness"]["integration_completed"] is True
    assert wind["readiness"]["callable"] is False
    tinysoft = next(source for source in catalog["sources"] if source["id"] == "tinysoft")
    assert tinysoft["readiness"]["integration_completed"] is True
    assert tinysoft["readiness"]["dependency_ready"] is False
    assert tinysoft["readiness"]["integration_state"] == "blocked_config"
    assert tinysoft["readiness"]["callable"] is False
    fund = next(cap for cap in catalog["capabilities"] if cap["id"] == "fund_data")
    assert fund["tool_id"] == "datahub_get_fund_data"
    assert fund["source_count"] == 2 and fund["callable_source_count"] == 1
    tinysoft_bindings = {
        row["capability_id"]: row["implemented"]
        for row in catalog["bindings"]
        if row["source_id"] == "tinysoft"
    }
    assert {key for key, implemented in tinysoft_bindings.items() if implemented} == {
        "search_assets",
        "trading_calendar",
        "market_bars",
        "market_snapshot",
        "factor_macro",
        "financials",
        "market_activity",
    }
    assert tinysoft_bindings["fund_data"] is False
    akshare_bindings = {
        row["capability_id"]: row["implemented"]
        for row in catalog["bindings"]
        if row["source_id"] == "akshare"
    }
    assert {key for key, implemented in akshare_bindings.items() if implemented} == {
        "search_assets",
        "market_bars",
        "market_snapshot",
        "financials",
        "market_activity",
    }
    mysql = next(source for source in catalog["sources"] if source["id"] == "mysql")
    assert mysql["name"] == "用户 MySQL 数据库"
    assert mysql["readiness"]["integration_state"] == "blocked_config"
    assert {
        item["tool_id"]
        for item in catalog["capabilities"]
        if item["id"] in {"database_schema", "table_query"}
    } == {"datahub_get_database_schema", "datahub_query_table"}


def test_provider_deadlines_are_unified_below_bridge_timeout():
    import app.research_web.datahub.providers_akshare as akshare_provider
    import app.research_web.datahub.providers_cjpy as tinysoft_provider
    from app.research_web.datahub import PROBE_TIMEOUT

    assert akshare_provider.DEADLINE == tinysoft_provider.DEADLINE == 15
    assert akshare_provider.PROBE_DEADLINE < PROBE_TIMEOUT
    assert akshare_provider.DEADLINE < 22


def test_mysql_tools_become_callable_only_with_local_profile_secret_and_dependencies(monkeypatch):
    import app.research_web.datahub.catalog as module

    monkeypatch.setattr(
        module, "find_spec", lambda name: object() if name in {"pymysql", "keyring"} else None
    )
    status = {
        "configured": True,
        "secret_configured": True,
        "credential_store_available": True,
    }
    catalog = build_catalog(environ={}, mysql_status=status)
    mysql = next(source for source in catalog["sources"] if source["id"] == "mysql")
    assert mysql["readiness"]["integration_state"] == "ready"
    assert mysql["readiness"]["callable"] is True
    capabilities = {item["id"]: item for item in catalog["capabilities"]}
    assert capabilities["database_schema"]["callable_source_count"] == 1
    assert capabilities["table_query"]["callable_source_count"] == 1

    blocked = build_catalog(
        environ={}, mysql_status={**status, "credential_store_available": False}
    )
    source = next(item for item in blocked["sources"] if item["id"] == "mysql")
    assert source["readiness"]["callable"] is False
    assert source["readiness"]["integration_state"] == "blocked_config"

    missing_secret = build_catalog(
        environ={},
        mysql_status={
            "configured": True,
            "secret_configured": False,
            "credential_store_available": True,
        },
    )
    source = next(item for item in missing_secret["sources"] if item["id"] == "mysql")
    assert source["readiness"]["callable"] is False
    assert source["readiness"]["integration_state"] == "blocked_config"


def test_tinysoft_rejects_the_public_cjpy_version_with_a_specific_failure(monkeypatch):
    import app.research_web.datahub.catalog as module

    monkeypatch.setattr(
        module,
        "find_spec",
        lambda name: object() if name in {"cjpy", "requests", "urllib3"} else None,
    )
    monkeypatch.setattr(
        module.importlib_metadata,
        "version",
        lambda name: "0.3.6" if name == "cjpy" else "1.0.0",
    )

    catalog = build_catalog(
        environ={},
        connection_statuses={
            "tinysoft": {
                "configured": True,
                "secret_configured": True,
                "credential_store_available": True,
            }
        },
    )
    source = next(item for item in catalog["sources"] if item["id"] == "tinysoft")

    assert source["readiness"]["dependency_ready"] is False
    assert source["readiness"]["integration_state"] == "blocked_dependency"
    assert source["readiness"]["failure_code"] == "dependency_version_mismatch"
    assert source["readiness"]["callable"] is False


def test_tinysoft_requires_the_cjpy_transport_dependencies(monkeypatch):
    import app.research_web.datahub.catalog as module

    monkeypatch.setattr(
        module,
        "find_spec",
        lambda name: object() if name in {"cjpy", "requests"} else None,
    )
    monkeypatch.setattr(module.importlib_metadata, "version", lambda _name: "0.5.2")

    catalog = build_catalog(
        environ={},
        connection_statuses={
            "tinysoft": {
                "configured": True,
                "secret_configured": True,
                "credential_store_available": True,
            }
        },
    )
    source = next(item for item in catalog["sources"] if item["id"] == "tinysoft")

    assert source["readiness"]["dependency_ready"] is False
    assert source["readiness"]["failure_code"] == "blocked_dependency"


def test_tinysoft_accepts_only_the_complete_052_dependency_set(monkeypatch):
    import app.research_web.datahub.catalog as module

    monkeypatch.setattr(
        module,
        "find_spec",
        lambda name: object() if name in {"cjpy", "requests", "urllib3"} else None,
    )
    monkeypatch.setattr(module.importlib_metadata, "version", lambda _name: "0.5.2")

    catalog = build_catalog(
        environ={},
        connection_statuses={
            "tinysoft": {
                "configured": True,
                "secret_configured": True,
                "credential_store_available": True,
            }
        },
    )
    source = next(item for item in catalog["sources"] if item["id"] == "tinysoft")

    assert source["readiness"]["dependency_ready"] is True
    assert source["readiness"]["integration_state"] == "ready"
    assert source["readiness"]["failure_code"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module_name", "entrypoint", "capability"),
    [
        ("app.research_web.datahub.providers_akshare", "_invoke", "search_assets"),
        ("app.research_web.datahub.providers_cjpy", "_sync_query", "search_assets"),
    ],
)
async def test_provider_timeout_is_bounded_busy_then_recovers(
    monkeypatch, module_name, entrypoint, capability
):
    provider = import_module(module_name)
    started = threading.Event()
    release = threading.Event()
    invoke_count = 0

    class EmptyFrame:
        def to_dict(self, orient):
            assert orient == "records"
            return []

    def blocking_query(*_args, **_kwargs):
        nonlocal invoke_count
        invoke_count += 1
        if invoke_count == 1:
            started.set()
            release.wait(timeout=1)
        if module_name.endswith("providers_akshare"):
            return EmptyFrame(), lambda rows, _query: rows
        return []

    monkeypatch.setattr(provider, "DEADLINE", 0.005)
    monkeypatch.setattr(provider, entrypoint, blocking_query)
    first = await provider.fetch(
        BusinessQuery(capability=capability, source="auto", parameters={"query": ""})
    )
    assert started.is_set()
    assert first.status == "failed"
    assert "deadline" in first.limitations

    second = await provider.fetch(
        BusinessQuery(capability=capability, source="auto", parameters={"query": ""})
    )
    assert second.status == "failed"
    assert "provider_busy" in second.limitations
    assert invoke_count == 1

    release.set()
    monkeypatch.setattr(provider, "DEADLINE", 0.2)
    for _ in range(50):
        await asyncio.sleep(0.005)
        recovered = await provider.fetch(
            BusinessQuery(capability=capability, source="auto", parameters={"query": ""})
        )
        if "provider_busy" not in recovered.limitations:
            break
    assert recovered.status == "empty"
    assert invoke_count == 2


@pytest.mark.asyncio
async def test_akshare_provider_normalizes_business_data_without_legacy_run(
    monkeypatch,
):
    import pandas as pd

    import app.research_web.datahub.providers_akshare as provider

    package = ModuleType("akshare")
    package.stock_zh_a_daily = lambda **kwargs: pd.DataFrame(
        [
            {
                "日期": "2026-09-04",
                "开盘": 10.0,
                "收盘": 10.5,
                "最高": 10.8,
                "最低": 9.9,
                "成交量": 1000,
                "成交额": 10500,
                "换手率": 1.2,
            }
        ]
    )
    monkeypatch.setitem(sys.modules, "akshare", package)
    result = await provider.fetch(
        BusinessQuery(
            capability="market_bars",
            source="akshare",
            parameters={
                "asset": "600519.SH",
                "start_date": "2026-09-01",
                "end_date": "2026-09-05",
                "frequency": "daily",
                "adjustment": "qfq",
            },
        )
    )
    assert result.status == "complete"
    assert result.provider_id == "akshare"
    assert result.rows == [
        {
            "asset": "600519.SH",
            "date": "2026-09-04",
            "open": 10.0,
            "close": 10.5,
            "high": 10.8,
            "low": 9.9,
            "volume": 1000.0,
            "turnover": 10500.0,
            "turnover_rate_pct": 1.2,
        }
    ]
    assert result.fields["close"] == {"unit": "CNY", "currency": "CNY"}


@pytest.mark.asyncio
async def test_akshare_financials_normalize_boolean_missing_sentinels(monkeypatch):
    import pandas as pd

    import app.research_web.datahub.providers_akshare as provider

    package = ModuleType("akshare")
    package.stock_financial_abstract_ths = lambda **kwargs: pd.DataFrame(
        [
            {
                "报告期": "1998-12-31",
                "净利润": "1.47亿",
                "净利润同比增长率": False,
                "扣非净利润": True,
            }
        ]
    )
    monkeypatch.setitem(sys.modules, "akshare", package)

    result = await provider.fetch(
        BusinessQuery(
            capability="financials",
            source="akshare",
            parameters={"asset": "600519", "statements": ["indicators"], "periods": 8},
        )
    )

    assert result.status == "complete"
    assert result.rows == [
        {
            "asset": "600519",
            "报告期": "1998-12-31",
            "净利润": "1.47亿",
            "净利润同比增长率": None,
            "扣非净利润": None,
            "report_period": "1998-12-31",
            "revenue": None,
            "net_profit": 147000000.0,
            "roe": None,
            "gross_profit_margin": None,
        }
    ]
    assert (
        provider._normalize_generic(
            [{"provider_boolean": False}],
            BusinessQuery(
                capability="market_activity",
                source="akshare",
                parameters={"asset": "600519", "dataset": "fund_flow"},
            ),
        )[0]["provider_boolean"]
        is False
    )


@pytest.mark.asyncio
async def test_akshare_provider_sanitizes_unexpected_transport_failure(monkeypatch):
    import app.research_web.datahub.providers_akshare as provider

    monkeypatch.setattr(provider, "_invoke", lambda query: (_ for _ in ()).throw(OSError("secret")))
    result = await provider.fetch(
        BusinessQuery(
            capability="search_assets",
            source="akshare",
            parameters={"query": ""},
        )
    )
    assert result.status == "failed"
    assert result.limitations[-1] == "vendor_unreachable"
    assert "secret" not in str(result.limitations)


@pytest.mark.asyncio
async def test_akshare_probe_uses_lightweight_remote_trade_calendar(monkeypatch):
    import app.research_web.datahub.providers_akshare as provider

    calls = []
    package = ModuleType("akshare")

    async def fetch_probe_payload():
        calls.append(provider.PROBE_URL)
        return b'var datelist="fixture";var KLC_TD_SH=datelist;'

    monkeypatch.setitem(sys.modules, "akshare", package)
    monkeypatch.setattr(provider, "_fetch_probe_payload", fetch_probe_payload)

    result = await provider.probe()

    assert result == {"health": "healthy", "failure_code": None}
    assert calls == [provider.PROBE_URL]


@pytest.mark.asyncio
async def test_akshare_probe_preserves_safe_provider_failure_code(monkeypatch):
    import app.research_web.datahub.providers_akshare as provider

    async def blocked_dependency():
        raise provider.ProviderError("blocked_dependency")

    monkeypatch.setattr(provider, "_probe_remote", blocked_dependency)

    assert await provider.probe() == {
        "health": "unavailable",
        "failure_code": "blocked_dependency",
    }


@pytest.mark.asyncio
async def test_akshare_probe_deadline_cancels_stream_and_releases_shared_capacity(monkeypatch):
    import app.research_web.datahub.providers_akshare as provider

    started = asyncio.Event()

    async def blocked_probe():
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(provider, "_probe_remote", blocked_probe)
    monkeypatch.setattr(provider, "PROBE_DEADLINE", 0.2)
    first_probe = asyncio.create_task(provider.probe())
    await asyncio.wait_for(started.wait(), timeout=1)

    busy_query = await provider.fetch(
        BusinessQuery(capability="search_assets", source="akshare", parameters={})
    )
    assert busy_query.status == "failed"
    assert busy_query.limitations[-1] == "provider_busy"
    assert await first_probe == {"health": "unavailable", "failure_code": "deadline"}

    assert provider._CAPACITY.acquire(blocking=False)
    provider._CAPACITY.release()


def test_business_query_rejects_provider_escape_hatches():
    for parameters in (
        {"url": "https://evil.test"},
        {"headers": {"Authorization": "secret"}},
        {"module": "os"},
        {"path": "/etc/passwd"},
        {"api_key": "secret"},
    ):
        with pytest.raises(ValueError):
            BusinessQuery(capability="search_news", parameters=parameters)
    with pytest.raises(ValueError):
        BusinessQuery(capability="search_news", source="../../evil")
    with pytest.raises(ValueError):
        BusinessQuery(capability="search_news", parameters={"asset": "000001.SZ"})


@pytest.mark.asyncio
async def test_tinysoft_provider_uses_business_contract_without_legacy_lifecycle(
    monkeypatch,
):
    import app.research_web.datahub.providers_cjpy as provider

    package = ModuleType("cjpy")
    base = ModuleType("cjpy.base")

    class Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def _create_session(self):
            return type("Session", (), {"trust_env": True})()

    base.CjClient = Client
    package.base = base
    package.get_market_data = lambda **kwargs: [
        {"证券代码": kwargs["code"], "日期": "2026-09-04", "收盘价": 12.3}
    ]
    monkeypatch.setitem(sys.modules, "cjpy", package)
    monkeypatch.setitem(sys.modules, "cjpy.base", base)
    monkeypatch.setenv("CJ_KEY", "fixture-key")
    result = await provider.fetch(
        BusinessQuery(
            capability="market_bars",
            source="tinysoft",
            parameters={
                "asset": "600000.SH",
                "start_date": "2026-09-01",
                "end_date": "2026-09-04",
            },
        )
    )
    assert result.status == "complete"
    assert result.provider_id == "tinysoft"
    assert result.rows == [{"证券代码": "SH600000", "日期": "2026-09-04", "收盘价": 12.3}]
    assert result.fields["收盘价"] == {"unit": None, "currency": None}
    assert all("fixture-key" not in item.decode() for item in result.raw)


@pytest.mark.asyncio
async def test_tinysoft_snapshot_supplies_a_recent_vendor_date_window(monkeypatch):
    import app.research_web.datahub.providers_cjpy as provider

    package = ModuleType("cjpy")
    base = ModuleType("cjpy.base")
    captured = {}

    class Client:
        def __init__(self, **_kwargs):
            pass

        def _create_session(self):
            return type("Session", (), {"trust_env": True})()

    def market_data(**kwargs):
        captured.update(kwargs)
        return [{"close": 1}, {"close": 2}]

    base.CjClient = Client
    package.base = base
    package.get_market_data = market_data
    monkeypatch.setitem(sys.modules, "cjpy", package)
    monkeypatch.setitem(sys.modules, "cjpy.base", base)

    result = await provider.fetch(
        BusinessQuery(
            capability="market_snapshot",
            source="tinysoft",
            parameters={"assets": ["600000.SH"]},
        ),
        token="fixture-key",
    )

    assert result.status == "complete"
    assert result.rows == [{"close": 2}]
    assert re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", captured["start"])
    assert re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", captured["end"])
    assert date.fromisoformat(captured["end"]) - date.fromisoformat(captured["start"]) == timedelta(
        days=14
    )
    assert date.fromisoformat(captured["end"]) == datetime.now(provider.SHANGHAI_TZ).date()


@pytest.mark.parametrize(
    "parameters",
    [
        {"start_date": "2026-02-30", "end_date": "2026-03-01"},
        {"start_date": "2026-03-02", "end_date": "2026-03-01"},
    ],
)
def test_tinysoft_rejects_invalid_or_reversed_date_ranges(parameters):
    import app.research_web.datahub.providers_cjpy as provider

    with pytest.raises(provider.ProviderError, match="invalid_date_range"):
        provider._required_date_range(parameters)


@pytest.mark.asyncio
async def test_tinysoft_missing_key_is_safe_blocked_config(monkeypatch):
    import app.research_web.datahub.providers_cjpy as provider

    monkeypatch.delenv("CJ_KEY", raising=False)
    result = await provider.fetch(
        BusinessQuery(capability="search_assets", source="tinysoft", parameters={"query": ""})
    )
    assert result.status == "failed"
    assert result.limitations == ["blocked_config"]


@pytest.mark.asyncio
async def test_tinysoft_vendor_errors_are_classified_without_leaking_details(monkeypatch):
    import app.research_web.datahub.providers_cjpy as provider

    class CjRequestError(Exception):
        pass

    monkeypatch.setattr(
        provider,
        "_sync_query",
        lambda *_args: (_ for _ in ()).throw(
            CjRequestError("HTTP 401 response contains secret-token")
        ),
    )
    result = await provider.fetch(
        BusinessQuery(capability="search_assets", source="tinysoft", parameters={}),
        token="secret-token",
    )

    assert result.status == "failed"
    assert result.limitations == ["vendor_auth_failed"]
    assert "secret-token" not in str(result.limitations)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "vendor_row",
    [
        {"debug": "Bearer secret-token"},
        {"Bearer secret-token": "debug"},
        {"nested": {"Bearer secret-token": "debug"}},
    ],
)
async def test_tinysoft_rejects_token_reflected_by_successful_vendor_response(
    monkeypatch, vendor_row
):
    import app.research_web.datahub.providers_cjpy as provider

    package = ModuleType("cjpy")
    base = ModuleType("cjpy.base")

    class Client:
        def __init__(self, **_kwargs):
            pass

        def _create_session(self):
            return type("Session", (), {"trust_env": True})()

    base.CjClient = Client
    package.base = base
    package.get_stocks = lambda **_kwargs: [vendor_row]
    monkeypatch.setitem(sys.modules, "cjpy", package)
    monkeypatch.setitem(sys.modules, "cjpy.base", base)

    result = await provider.fetch(
        BusinessQuery(capability="search_assets", source="tinysoft", parameters={}),
        token="secret-token",
    )

    assert result.status == "failed"
    assert result.limitations == ["credential_reflection"]
    assert result.rows == []
    assert result.raw == []


@pytest.mark.asyncio
async def test_business_query_routes_only_integrated_sources_and_snapshots(tmp_path):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "errno": 0,
                "data": {
                    "roll_data": [
                        {"id": 123, "ctime": 1788326831, "content": "基金新闻"},
                        {"id": 124, "ctime": 1788326830, "content": "其他电报"},
                    ]
                },
            },
        )

    store = Store(tmp_path)
    sid = store.create("claw", "catalog")["id"]
    hub = DataHub(store, transport=httpx.MockTransport(respond))
    result = await hub.query(
        sid,
        "business-news",
        BusinessQuery(
            capability="search_news",
            parameters={"query": "基金", "limit": 2},
        ),
    )
    assert result["provider"] == "cls"
    assert result["capability"] == "search_news"
    assert result["row_count"] == 1
    assert result["attempted_sources"] == [{"source": "cls", "status": "selected", "reason": None}]
    assert len(calls) == 1
    with pytest.raises(StoreError, match="指定来源不支持"):
        await hub.query(
            sid,
            "bad-source",
            BusinessQuery(capability="search_news", source="wind", parameters={}),
        )
    with pytest.raises(StoreError, match="没有完成 DataHub 适配"):
        await hub.query(
            sid,
            "not-integrated",
            BusinessQuery(capability="factor_macro", parameters={"series": "CPI"}),
        )
    await hub.close()


def test_catalog_api_and_manual_probe_are_idempotent_and_sanitized(tmp_path, monkeypatch):
    from test_mcp_runtime_integration import FakeKeyring

    from app.research_web.credential_backend import CredentialBackendError, SystemKeyringBackend

    def unavailable(*_args, **_kwargs):
        raise CredentialBackendError("credential_store_unavailable")

    for operation in ("get_password", "set_password", "delete_password"):
        monkeypatch.setattr(SystemKeyringBackend, operation, unavailable)
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path), mcp_keyring_backend=FakeKeyring())
    external = []

    def respond(request):
        external.append(request.url.host)
        return httpx.Response(
            200,
            json={
                "errno": 0,
                "data": {"roll_data": [{"id": 123, "ctime": 1788326831, "content": "news"}]},
            },
        )

    service.datahub.transport = httpx.MockTransport(respond)
    with TestClient(create_app(service)) as client:
        catalog = client.get("/api/research/data/catalog")
        assert catalog.status_code == 200
        assert external == []
        assert client.get("/api/research/data/capabilities/search_news").json()["source_count"] == 7
        assert client.get("/api/research/data/sources/cls").json()["bindings"]
        headers = {"Idempotency-Key": "probe-cls-0001"}
        first = client.post("/api/research/data/sources/cls/probes", headers=headers)
        second = client.post("/api/research/data/sources/cls/probes", headers=headers)
        assert first.status_code == 202
        assert first.json()["id"] == second.json()["id"]
        probe_id = first.json()["id"]
        for _ in range(100):
            value = client.get(f"/api/research/data/probes/{probe_id}").json()
            if value["status"] == "completed":
                break
            asyncio.run(asyncio.sleep(0.01))
        assert value["health"] == "healthy"
        assert value["failure_code"] is None
        assert len(external) == 1 and external[0] == "www.cls.cn"
        serialized = str(value)
        assert "token" not in serialized and "roll_data" not in serialized


def test_probe_for_unconfigured_wind_source_never_touches_network(tmp_path):
    calls = []
    hub = DataHub(
        Store(tmp_path),
        transport=httpx.MockTransport(lambda request: calls.append(request)),
    )

    async def run():
        probe = hub.start_probe("wind", "probe-wind-0001")
        await hub.probe_tasks[probe["id"]]
        return hub.probe(probe["id"])

    result = asyncio.run(run())
    assert result["health"] == "unavailable"
    assert result["failure_code"] == "blocked_config"
    assert calls == []


@pytest.mark.parametrize(
    "asset,symbol",
    [
        ("000300.SH", "sh000300"),
        ("399001.SZ", "sz399001"),
        ("600519.SH", "sh600519"),
        ("430047.BJ", "bj430047"),
    ],
)
def test_akshare_explicit_exchange_suffix_wins(asset, symbol):
    from app.research_web.datahub.providers_akshare import _exchange_symbol

    assert _exchange_symbol(asset) == symbol


@pytest.mark.asyncio
async def test_akshare_index_filters_full_history_before_cap_and_uses_points(monkeypatch):
    import pandas as pd

    import app.research_web.datahub.providers_akshare as provider

    package = ModuleType("akshare")

    def index(**kwargs):
        assert kwargs == {"symbol": "sh000300"}
        return pd.DataFrame(
            {
                "date": pd.date_range("2000-01-01", periods=10000).date,
                "close": [4000] * 10000,
                "volume": [100] * 10000,
            }
        )

    package.stock_zh_index_daily = index
    monkeypatch.setitem(sys.modules, "akshare", package)
    result = await provider.fetch(
        BusinessQuery(
            capability="market_bars",
            source="akshare",
            parameters={
                "asset": "000300.SH",
                "asset_type": "index",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "frequency": "daily",
                "adjustment": "none",
            },
        )
    )
    assert result.status == "complete"
    assert [row["date"] for row in result.rows] == ["2026-01-01", "2026-01-02"]
    assert all(row["asset"] == "000300.SH" for row in result.rows)
    assert result.fields["close"] == {"unit": "points", "currency": None}


@pytest.mark.asyncio
async def test_akshare_etf_uses_fund_feed_and_marks_native_volume(monkeypatch):
    import pandas as pd

    import app.research_web.datahub.providers_akshare as provider

    package = ModuleType("akshare")

    def etf(**kwargs):
        assert kwargs == {
            "symbol": "510300",
            "period": "daily",
            "start_date": "20261001",
            "end_date": "20261002",
            "adjust": "",
        }
        return pd.DataFrame([{"日期": "2026-10-01", "收盘": 4.5, "成交量": 123}])

    package.fund_etf_hist_em = etf
    monkeypatch.setitem(sys.modules, "akshare", package)
    result = await provider.fetch(
        BusinessQuery(
            capability="market_bars",
            source="akshare",
            parameters={
                "asset": "510300.SH",
                "asset_type": "etf",
                "start_date": "2026-10-01",
                "end_date": "2026-10-02",
                "frequency": "daily",
                "adjustment": "none",
            },
        )
    )
    assert result.status == "complete" and result.rows[0]["volume"] == 123
    assert result.fields["volume"]["unit"] == "provider_defined"
    assert "volume_unit_not_verified" in result.limitations
    assert result.fields["close"] == {"unit": "CNY", "currency": "CNY"}


@pytest.mark.parametrize(
    "parameters,reason",
    [
        ({"frequency": "weekly", "adjustment": "none"}, "invalid_frequency"),
        ({"frequency": "daily", "adjustment": "qfq"}, "invalid_adjustment"),
    ],
)
@pytest.mark.asyncio
async def test_akshare_index_rejects_unsupported_semantics_before_feed(
    monkeypatch, parameters, reason
):
    import app.research_web.datahub.providers_akshare as provider

    monkeypatch.setitem(sys.modules, "akshare", ModuleType("akshare"))
    result = await provider.fetch(
        BusinessQuery(
            capability="market_bars",
            source="akshare",
            parameters={"asset": "000300.SH", "asset_type": "index", **parameters},
        )
    )
    assert result.status == "failed" and result.limitations[-1] == reason
    assert result.rows == [] and result.raw == []


@pytest.mark.asyncio
async def test_akshare_index_fallback_is_bounded_and_retains_unknown_volume_unit(monkeypatch):
    import pandas as pd

    import app.research_web.datahub.providers_akshare as provider

    package = ModuleType("akshare")
    calls = []

    def primary(**kwargs):
        calls.append(("primary", kwargs["symbol"]))
        raise ValueError("synthetic vendor failure")

    def alternate(**kwargs):
        calls.append(("alternate", kwargs["symbol"]))
        return pd.DataFrame([{"date": "2026-10-01", "close": 4000, "volume": 123}])

    package.stock_zh_index_daily = primary
    package.stock_zh_index_daily_em = alternate
    monkeypatch.setitem(sys.modules, "akshare", package)
    monkeypatch.setattr(provider.time, "sleep", lambda _delay: None)
    result = await provider.fetch(
        BusinessQuery(
            capability="market_bars",
            source="akshare",
            parameters={
                "asset": "000300.SH",
                "asset_type": "index",
                "frequency": "daily",
                "adjustment": "none",
            },
        )
    )
    assert result.status == "complete"
    assert calls == [("primary", "sh000300"), ("primary", "sh000300"), ("alternate", "sh000300")]
    assert result.rows[0]["volume"] == 123
    assert result.fields["volume"]["unit"] == "provider_defined"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "capability,parameters",
    [
        ("market_activity", {"asset": "600519.SH", "dataset": "northbound"}),
        ("market_activity", {"asset": "600519.SH", "dataset": "money_flow"}),
        ("market_snapshot", {"assets": ["600519.SH"], "asset_type": "index"}),
        ("market_snapshot", {"assets": ["510300.SH"], "asset_type": "etf"}),
    ],
)
async def test_akshare_nonequivalent_queries_fail_before_vendor(
    capability, parameters, monkeypatch
):
    import pandas as pd

    import app.research_web.datahub.providers_akshare as provider

    package = ModuleType("akshare")
    calls = []

    def reply(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame([{"date": "2026-10-13", "close": 10}])

    package.stock_individual_fund_flow = reply
    package.stock_zh_a_daily = reply
    monkeypatch.setitem(sys.modules, "akshare", package)
    result = await provider.fetch(
        BusinessQuery(capability=capability, source="akshare", parameters=parameters)
    )
    assert result.status == "failed" and result.limitations[-1] == "data_not_equivalent"
    assert calls == [] and result.rows == [] and result.raw == []


@pytest.mark.asyncio
async def test_akshare_fund_flow_slices_dates_before_row_limit(monkeypatch):
    import pandas as pd

    import app.research_web.datahub.providers_akshare as provider

    package = ModuleType("akshare")

    def reply(**kwargs):
        assert kwargs == {"stock": "600519", "market": "sh"}
        return pd.DataFrame(
            {
                "日期": pd.date_range("2000-01-01", periods=10000).date,
                "主力净流入-净额": [1] * 10000,
            }
        )

    package.stock_individual_fund_flow = reply
    monkeypatch.setitem(sys.modules, "akshare", package)
    result = await provider.fetch(
        BusinessQuery(
            capability="market_activity",
            source="akshare",
            parameters={
                "asset": "600519.SH",
                "dataset": "fund_flow",
                "start_date": "2026-10-13",
                "end_date": "2026-10-13",
            },
        )
    )
    assert result.status == "complete" and len(result.rows) == 1
    assert result.rows[0]["日期"] == "2026-10-13"


def test_akshare_stock_snapshot_keeps_explicit_exchange_identity():
    import app.research_web.datahub.providers_akshare as provider

    query = BusinessQuery(
        capability="market_snapshot",
        source="akshare",
        parameters={"assets": ["000001.SH"], "asset_type": "stock"},
    )
    rows = provider._normalize_snapshot([{"代码": "000001", "最新价": 10}], query)
    assert rows[0]["asset"] == "000001.SH"


@pytest.mark.parametrize(
    "capability,parameters,expected_code",
    [
        ("trading_calendar", {"market": "CN"}, "data_capability_unavailable"),
        ("index_data", {"index": "000300.SH", "dataset": "quotes"}, "data_capability_unavailable"),
        ("factor_macro", {"series": "adjustment_metadata"}, "data_capability_unavailable"),
    ],
)
def test_unavailable_business_source_has_stable_code(
    capability, parameters, expected_code, monkeypatch
):
    from app.research_web.datahub import catalog
    from app.research_web.datahub.broker import resolve
    from app.research_web.store import StoreError

    monkeypatch.setattr(catalog, "find_spec", lambda _name: None)
    with pytest.raises(StoreError) as failure:
        resolve(
            BusinessQuery(capability=capability, parameters=parameters),
            environ={},
            connection_statuses={},
        )
    assert failure.value.code == expected_code and failure.value.status == 503


@pytest.mark.asyncio
@pytest.mark.parametrize("asset,expected", [("000001.SH", "sh000001"), ("000001.SZ", "sz000001")])
async def test_akshare_stock_snapshot_preserves_exchange_in_feed_and_result(
    monkeypatch, asset, expected
):
    import pandas as pd

    import app.research_web.datahub.providers_akshare as provider

    package = ModuleType("akshare")

    def reply(**kwargs):
        assert kwargs["symbol"] == expected
        return pd.DataFrame([{"date": "2026-10-13", "close": 10, "volume": 1}])

    package.stock_zh_a_daily = reply
    monkeypatch.setitem(sys.modules, "akshare", package)
    result = await provider.fetch(
        BusinessQuery(
            capability="market_snapshot",
            source="akshare",
            parameters={"assets": [asset], "asset_type": "stock"},
        )
    )
    assert result.status == "complete" and result.rows[0]["asset"] == asset
    assert result.fields["price"] == {"unit": "CNY", "currency": "CNY"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,reason",
    [
        ([{"unknown_date": "2026-10-13", "flow": 1}], "data_not_equivalent"),
        ([{"日期": "invalid", "flow": 1}], "invalid_provider_date"),
        ([{"日期": "2026-10-13", "flow": 1}] * 5001, "row_limit"),
    ],
)
async def test_akshare_fund_flow_unverifiable_or_excessive_rows_fail_closed(
    monkeypatch, payload, reason
):
    import pandas as pd

    import app.research_web.datahub.providers_akshare as provider

    package = ModuleType("akshare")
    package.stock_individual_fund_flow = lambda **_kwargs: pd.DataFrame(payload)
    monkeypatch.setitem(sys.modules, "akshare", package)
    result = await provider.fetch(
        BusinessQuery(
            capability="market_activity",
            source="akshare",
            parameters={
                "asset": "600519.SH",
                "dataset": "fund_flow",
                "start_date": "2026-10-13",
                "end_date": "2026-10-13",
            },
        )
    )
    assert result.status == "failed" and result.limitations[-1] == reason
    assert result.rows == [] and result.raw == []
