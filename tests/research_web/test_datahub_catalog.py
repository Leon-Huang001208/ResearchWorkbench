"""Static full-source catalog, manual probes and business routing."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from test_api import NativeFixture

from app.research_web.datahub import BusinessQuery, DataHub
from app.research_web.datahub.catalog import build_catalog
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store, StoreError


def test_catalog_contains_all_declared_sources_without_constructing_connectors(monkeypatch):
    import app.research_web.datahub.catalog as module

    monkeypatch.setattr(module.os, "environ", {})
    catalog = build_catalog()
    assert catalog["summary"] == {
        "capabilities": 13,
        "sources": 21,
        "callable_sources": 2,
        "needs_configuration": 9,
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
    }
    assert all(source["readiness"]["code_exists"] for source in catalog["sources"])
    assert {source["id"] for source in catalog["sources"] if source["readiness"]["callable"]} == {
        "cls",
        "eastmoney_fund",
    }
    wind = next(source for source in catalog["sources"] if source["id"] == "wind")
    assert wind["readiness"]["integration_completed"] is False
    assert wind["readiness"]["callable"] is False
    fund = next(cap for cap in catalog["capabilities"] if cap["id"] == "fund_data")
    assert fund["tool_id"] == "datahub_get_fund_data"
    assert fund["source_count"] == 2 and fund["callable_source_count"] == 1


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
            BusinessQuery(capability="market_bars", parameters={"asset": "000001.SZ"}),
        )
    await hub.close()


def test_catalog_api_and_manual_probe_are_idempotent_and_sanitized(tmp_path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path))
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


def test_probe_for_unintegrated_source_never_touches_network(tmp_path):
    calls = []
    hub = DataHub(
        Store(tmp_path), transport=httpx.MockTransport(lambda request: calls.append(request))
    )

    async def run():
        probe = hub.start_probe("wind", "probe-wind-0001")
        await hub.probe_tasks[probe["id"]]
        return hub.probe(probe["id"])

    result = asyncio.run(run())
    assert result["health"] == "unavailable"
    assert result["failure_code"] == "disabled"
    assert calls == []
