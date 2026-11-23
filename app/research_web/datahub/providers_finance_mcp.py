"""Fixed finance MCP upstream using the account's existing credential store."""

import asyncio
import json

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from core.observability import get_logger

from .connections import CredentialStoreError
from .external_sources import inventory_rows
from .providers import MAX_RESPONSE_BYTES, MAX_ROWS, ProviderError, Result

log = get_logger(__name__)
SOURCE = "ext_finance_mcp"
ENDPOINT = "https://www.huaanifd.com/finance-data/mcp"
TOOLS = frozenset(
    {"finance_sources", "finance_list_tools", "finance_call", "alpha_query", "gangtise_query"}
)


def tool_payload(result, *, tool=None, arguments=None):
    """Keep the original structured object or JSON text, including vendor status."""
    if result.get("isError"):
        raise ProviderError("finance_mcp_tool_failed")
    value = result.get("structuredContent")
    if value is None:
        texts = [item["text"] for item in result.get("content", []) if item.get("type") == "text"]
        if len(texts) != 1:
            raise ProviderError("finance_mcp_payload_invalid")
        value = json.loads(texts[0])
    if not isinstance(value, dict):
        raise ProviderError("finance_mcp_payload_invalid")
    if value.get("ok") is False:
        raise ProviderError("finance_mcp_upstream_failed")
    nested = value.get("data")
    if isinstance(nested, dict) and nested.get("isError"):
        raise ProviderError("finance_mcp_vendor_failed")
    if tool == "finance_call" and (arguments or {}).get("provider") == "ifind":
        if not isinstance(nested, dict):
            raise ProviderError("finance_mcp_payload_invalid")
        business = nested.get("structuredContent")
        if business is None:
            blocks = nested.get("content", [])
            if len(blocks) == 1 and blocks[0].get("type") == "text":
                business = json.loads(blocks[0]["text"])
        if (
            not isinstance(business, dict)
            or type(business.get("code")) is not int
            or business["code"] != 1
        ):
            raise ProviderError("finance_mcp_vendor_failed")
    return value


def projection(tool, value):
    if tool == "finance_sources":
        return [
            {"provider": provider, **item}
            for provider, item in value.items()
            if isinstance(item, dict)
        ]
    if tool == "gangtise_query":
        business = value.get("data", {})
        if business.get("code") != "000000" or business.get("status") is not True:
            raise ProviderError("finance_mcp_vendor_failed")
        data = business.get("data", {})
        fields, values = data.get("fieldList"), data.get("list")
        if isinstance(fields, list) and isinstance(values, list):
            if len(fields) != len(set(fields)) or any(not isinstance(key, str) for key in fields):
                raise ProviderError("finance_mcp_fields_invalid")
            if any(not isinstance(row, list) or len(row) != len(fields) for row in values):
                raise ProviderError("finance_mcp_rows_invalid")
            return [dict(zip(fields, row, strict=True)) for row in values]
    # Heterogeneous vendor output stays an envelope until its numeric semantics
    # have been verified. Never turn a vendor error into accepted numeric rows.
    return [{"provider_payload": value}]


async def fetch(query, *, transport=None, connections=None):
    result = Result(provider_id=SOURCE, source_url=ENDPOINT)
    tool = query.parameters.get("dataset", "catalog")
    if tool == "catalog":
        result.rows = inventory_rows(SOURCE)
        result.status = "snapshot"
        result.limitations = ["catalog_not_live_data"]
        return result
    try:
        if tool not in TOOLS:
            raise ProviderError("finance_mcp_tool_unknown")
        if query.as_of is not None or query.purpose == "backtest" or query.required_semantics:
            raise ProviderError("finance_mcp_historical_semantics_unverified")
        arguments = json.loads(query.parameters.get("arguments_json") or "{}")
        if not isinstance(arguments, dict):
            raise ProviderError("finance_mcp_arguments_invalid")
        limit = query.parameters.get("limit", 500)
        if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
            raise ProviderError("finance_mcp_limit_invalid")
        if connections is None:
            raise ProviderError("finance_mcp_credential_missing")
        token = await asyncio.to_thread(connections.read_source_secret, SOURCE)
        async with (
            asyncio.timeout(130),
            httpx.AsyncClient(
                transport=transport,
                timeout=130,
                trust_env=False,
                follow_redirects=False,
                headers={"Authorization": "Bearer " + token},
            ) as http,
            streamable_http_client(ENDPOINT, http_client=http) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            called = await session.call_tool(tool, arguments)
            response = called.model_dump(mode="json", by_alias=True)
        raw = json.dumps(response, ensure_ascii=False).encode()
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderError("finance_mcp_response_too_large")
        result.raw = [raw]
        result.raw_bytes = len(raw)
        result.pages_fetched = 1
        value = tool_payload(response, tool=tool, arguments=arguments)
        rows = projection(tool, value)
        result.rows = rows[:limit]
        result.provider_total = len(rows)
        result.status = "snapshot"
        if rows and "provider_payload" in rows[0] and tool != "finance_list_tools":
            result.status = "partial"
        result.limitations = [
            "provider_native_fields",
            "units_not_verified",
            "historical_pit_not_verified",
            "single_response_not_complete_history",
        ]
        if len(rows) > limit:
            result.limitations.append("row_limit")
        if result.status == "partial":
            result.limitations.append("vendor_business_semantics_unverified")
        result.metadata = {
            "schema_version": "finance-mcp-envelope-v1",
            "upstream_tool": tool,
            "raw_format": "mcp_tool_result_json",
            "historical_point_in_time": False,
            "formal_backtest_eligible": False,
            "quality_accepted": tool in {"finance_sources", "finance_list_tools"}
            or (tool == "gangtise_query" and bool(rows) and "provider_payload" not in rows[0]),
        }
    except asyncio.CancelledError:
        log.info("finance_mcp_query_cancelled", tool=tool)
        raise
    except (
        ProviderError,
        CredentialStoreError,
        httpx.HTTPError,
        TimeoutError,
        ValueError,
        TypeError,
        ExceptionGroup,
    ) as exc:
        code = str(exc) if isinstance(exc, ProviderError) else "finance_mcp_request_failed"
        result.status = "failed"
        result.limitations.append(code)
        log.warning("finance_mcp_query_failed", tool=tool, code=code, error_type=type(exc).__name__)
    return result
