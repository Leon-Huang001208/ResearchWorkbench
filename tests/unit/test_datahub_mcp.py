"""Exercise the real MCP SDK over stdio without importing the project shim as SDK."""

import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_datahub_stdio_sdk_discovery_query_and_write_rejection():
    try:
        importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("MCP SDK is not installed in this interpreter")
    database_url = os.environ.get("DATAHUB_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Requires an isolated migrated PostgreSQL database")
    # -I keeps the client on the installed SDK; the child exercises the legacy CLI.
    script = r"""
import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def verify():
    server = StdioServerParameters(command=sys.executable, args=["-m", "mcp.server"], cwd=sys.argv[1], env={"DATABASE_URL":sys.argv[2]})
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {"data_catalog", "data_query"} <= {tool.name for tool in tools.tools}
            catalog = await session.call_tool("data_catalog", {})
            assert not catalog.isError
            assert len(json.loads(catalog.content[0].text)["datasets"]) == 17
            result = await session.call_tool("data_query", {"dataset":"factor_data", "limit":1})
            assert not result.isError
            facts = json.loads(result.content[0].text)
            assert "records" in facts and "freshness_status" in facts
            denied = await session.call_tool("data_query", {"dataset":"factor_data", "write":True})
            assert denied.isError
            print(json.dumps({"sdk_roundtrip":True, "write_rejected":True, "records":len(facts["records"])}))

asyncio.run(asyncio.wait_for(verify(), 30))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            script,
            str(Path(__file__).resolve().parents[2]),
            database_url,
        ],
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert completed.returncode == 0, completed.stderr
    assert '"sdk_roundtrip": true' in completed.stdout
