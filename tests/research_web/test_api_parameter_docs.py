"""The OpenAPI parameter glossary must cover every real operation parameter."""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from typing import Any

from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from app.research_web.api_parameter_docs import (
    DEFAULTS,
    HTTP_METHODS,
    PREFIX_OVERRIDES,
    install_openapi_parameter_docs,
)
from app.research_web.main import create_app


def _parameters(schema: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for path, item in schema["paths"].items():
        if path.startswith("/static/"):
            continue
        for method, operation in item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            for parameter in operation.get("parameters") or []:
                yield method.upper(), path, parameter


def test_every_operation_parameter_has_a_reviewed_description():
    schema = TestClient(create_app()).get("/openapi.json").json()
    missing = [
        (method, path, parameter.get("in"), parameter.get("name"))
        for method, path, parameter in _parameters(schema)
        if not parameter.get("description")
    ]
    assert missing == []


def test_glossary_entries_all_match_live_parameters():
    schema = TestClient(create_app()).get("/openapi.json").json()
    parameters = list(_parameters(schema))
    used = {
        f"{parameter.get('in')}:{parameter.get('name')}" for _method, _path, parameter in parameters
    }
    assert set(DEFAULTS) - used == set()
    for location, name, prefix, description in PREFIX_OVERRIDES:
        assert description.strip()
        assert any(
            parameter.get("in") == location
            and parameter.get("name") == name
            and path.startswith(prefix)
            for _method, path, parameter in parameters
        ), (location, name, prefix)


def test_existing_parameter_descriptions_are_not_overwritten():
    app = FastAPI()

    @app.get("/demo")
    async def demo(limit: int = Query(default=1, description="原有说明")):
        return {"limit": limit}

    install_openapi_parameter_docs(app)
    schema = app.openapi()
    parameter = schema["paths"]["/demo"]["get"]["parameters"][0]
    assert parameter["description"] == "原有说明"


def test_openapi_enrichment_is_idempotent():
    app = create_app()
    install_openapi_parameter_docs(app)
    first = app.openapi()
    second = app.openapi()
    assert first is second
    assert all(parameter.get("description") for _method, _path, parameter in _parameters(first))


def test_parameter_docs_preserve_constraints_and_request_behavior():
    app = FastAPI()

    @app.get("/demo")
    async def demo(limit: int = Query(default=1, ge=1, le=5)):
        return {"limit": limit, "extra": "retained"}

    client = TestClient(app)
    original_schema = deepcopy(app.openapi())
    original_responses = [client.get(url) for url in ("/demo", "/demo?limit=3", "/demo?limit=0")]
    install_openapi_parameter_docs(app)
    enriched_schema = deepcopy(client.get("/openapi.json").json())
    for _method, _path, parameter in _parameters(enriched_schema):
        assert parameter.pop("description") == DEFAULTS["query:limit"]
    assert enriched_schema == original_schema
    for url, original in zip(("/demo", "/demo?limit=3", "/demo?limit=0"), original_responses):
        response = client.get(url)
        assert (response.status_code, response.json()) == (original.status_code, original.json())


def test_ambiguous_parameter_names_use_their_route_semantics():
    schema = create_app().openapi()
    parameters = {
        (path, parameter["name"]): parameter["description"]
        for _method, path, parameter in _parameters(schema)
    }
    assert "运行 ID" in parameters[("/api/research/research-bots/{bot_id}/runs", "before")]
    assert "含时区" in parameters[("/api/research/market-scores", "as_of")]
    assert "OAuth" in parameters[("/api/research/mcp/oauth/callback", "code")]
    assert "证券" in parameters[("/api/research/intel/news", "code")]
    assert "档案" in parameters[("/api/research/dossiers/{did}", "did")]
    assert "CN、US、HK" in parameters[("/api/research/events", "market")]
    assert "YYYY-Www" in parameters[("/api/research/aihot/reports/{kind}/{key}", "key")]
