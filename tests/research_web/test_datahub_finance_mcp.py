"""Finance MCP must retain native values and surface nested vendor failures."""

import json
from types import SimpleNamespace

import httpx
import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.external_sources import EXTERNAL_SOURCES, catalog_entries
from app.research_web.datahub.providers import ProviderError, fetch
from app.research_web.datahub.providers_finance_mcp import SOURCE, projection, tool_payload


def test_gangtise_projection_preserves_missing_and_native_fields():
    value = {
        "ok": True,
        "data": {
            "code": "000000",
            "status": True,
            "data": {
                "fieldList": ["tradeDate", "close", "volume"],
                "list": [["2026-11-16", 1453.9, None]],
            },
        },
    }
    assert projection("gangtise_query", value) == [
        {"tradeDate": "2026-11-16", "close": 1453.9, "volume": None}
    ]


@pytest.mark.parametrize(
    "response",
    [
        {"isError": True},
        {"structuredContent": {"ok": False, "error": "upstream 401"}},
        {"structuredContent": {"ok": True, "data": {"isError": True}}},
    ],
)
def test_nested_error_does_not_become_data(response):
    with pytest.raises(ProviderError):
        tool_payload(response)


def test_gangtise_business_error_does_not_become_data():
    with pytest.raises(ProviderError):
        projection(
            "gangtise_query",
            {"ok": True, "data": {"code": "INSUFFICIENT_CREDITS", "status": False}},
        )


def test_ifind_business_error_inside_successful_gateway_is_rejected():
    response = {
        "structuredContent": {
            "ok": True,
            "data": {"structuredContent": {"code": 0, "msg": "denied"}},
        }
    }
    with pytest.raises(ProviderError, match="finance_mcp_vendor_failed"):
        tool_payload(response, tool="finance_call", arguments={"provider": "ifind"})


def test_finance_catalog_requires_existing_account_credential():
    assert SOURCE in EXTERNAL_SOURCES
    sources, bindings = catalog_entries()
    source = next(item for item in sources if item["id"] == SOURCE)
    assert source["readiness"]["callable"] is False
    assert source["auth_type"] == "api_key"
    assert next(item for item in bindings if item["source_id"] == SOURCE)["implemented"] is True


@pytest.mark.asyncio
async def test_real_mcp_protocol_records_snapshot_without_claiming_units():
    calls = []

    def respond(request):
        assert str(request.url) == "https://www.huaanifd.com/finance-data/mcp"
        assert request.headers["authorization"] == "Bearer test-finance-token"
        if request.method == "GET":
            return httpx.Response(405)
        data = json.loads(request.content)
        calls.append(data["method"])
        if data["method"] == "notifications/initialized":
            return httpx.Response(202)
        result = {
            "protocolVersion": "2025-11-25",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fixture", "version": "1"},
        }
        if data["method"] == "tools/list":
            result = {
                "tools": [
                    {"name": "finance_sources", "inputSchema": {"type": "object", "properties": {}}}
                ]
            }
        if data["method"] == "tools/call":
            assert data["params"]["name"] == "finance_sources"
            assert data["params"]["arguments"] == {}
            result = {
                "content": [],
                "structuredContent": {"ifind": {"status": "windows_worker"}},
                "isError": False,
            }
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": data["id"], "result": result})

    query = BusinessQuery(
        capability="external_data",
        source=SOURCE,
        parameters={"dataset": "finance_sources", "arguments_json": "{}", "limit": 10},
    )
    connections = SimpleNamespace(
        read_source_secret=lambda source: "test-finance-token" if source == SOURCE else None
    )
    result = await fetch(query, transport=httpx.MockTransport(respond), connections=connections)
    assert result.status == "snapshot", result.limitations
    assert result.rows == [{"provider": "ifind", "status": "windows_worker"}]
    assert (
        result.raw
        and json.loads(result.raw[0])["structuredContent"]["ifind"]["status"] == "windows_worker"
    )
    assert "units_not_verified" in result.limitations
    assert result.metadata["historical_point_in_time"] is False
    assert calls.count("tools/call") == 1
