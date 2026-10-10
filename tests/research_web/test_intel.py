"""Fixed-origin, bounded, credential-free intelligence adapter contracts."""

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_web import intel_routes


@pytest.fixture
def adapter(monkeypatch):
    app = FastAPI()
    app.include_router(intel_routes.router)
    calls = []
    handler = {"response": httpx.Response(200, json={"data": {"items": []}})}
    real_client = httpx.AsyncClient

    def respond(request):
        calls.append(request)
        response = handler["response"]
        if isinstance(response, Exception):
            raise response
        return response

    def create_client(**kwargs):
        assert kwargs == {"timeout": 20, "follow_redirects": False, "trust_env": False}
        return real_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(intel_routes.httpx, "AsyncClient", create_client)
    return TestClient(app), calls, handler


@pytest.mark.parametrize(
    ("local", "remote"),
    [
        ("overview?impact=high", "/intelligence?impact=high&view=compact"),
        ("story-focus", "/intelligence/story-focus"),
        ("breakfast-focus", "/intelligence/breakfast-focus"),
        ("events/evt_123", "/intelligence/events/evt_123"),
        ("reports?limit=20&offset=40", "/report-records?limit=20&offset=40"),
        ("reports/report-123", "/report-records/report-123"),
        ("radar", "/radar"),
        ("wsc?cursor=a%2Bb%3D", "/wsc/live?cursor=a%2Bb%3D"),
        ("social", "/social/accounts"),
        ("news?code=600519", "/news?code=600519"),
        ("announcements?code=600519", "/announcements?code=600519"),
    ],
)
def test_only_fixed_get_endpoints_without_credentials(adapter, local, remote):
    client, calls, _ = adapter
    response = client.get(
        "/api/research/intel/" + local,
        headers={"Authorization": "Bearer local-secret", "Cookie": "session=private"},
    )
    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert str(calls[0].url) == intel_routes.UPSTREAM + remote
    assert calls[0].method == "GET"
    assert "authorization" not in calls[0].headers
    assert "cookie" not in calls[0].headers


@pytest.mark.parametrize(
    "path",
    [
        "overview?impact=arbitrary",
        "reports?limit=51",
        "reports?offset=-1",
        "events/a.b",
        "events/evil%3Furl=http",
        "news?code=60051",
        "news?code=abc123",
        "announcements?code=0000010",
        "wsc?cursor=" + "x" * 257,
    ],
)
def test_parameters_fail_before_network(adapter, path):
    client, calls, _ = adapter
    assert client.get("/api/research/intel/" + path).status_code == 422
    assert not calls


def test_no_remote_mutations_or_arbitrary_proxy(adapter):
    client, calls, _ = adapter
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/research/intel/radar").status_code == 405
    assert client.get("/api/research/intel/proxy?url=http://example.com").status_code == 404
    client.get("/api/research/intel/radar?url=http://example.com")
    assert str(calls[0].url) == intel_routes.UPSTREAM + "/radar"


@pytest.mark.parametrize(
    ("upstream", "status", "code"),
    [
        (httpx.Response(401, json={"secret": "not exposed"}), 502, "intel_upstream_unavailable"),
        (
            httpx.Response(302, headers={"location": "http://elsewhere"}),
            502,
            "intel_upstream_unavailable",
        ),
        (httpx.Response(404, json={}), 404, "intel_not_found"),
        (httpx.Response(200, text="<html>not JSON</html>"), 502, "intel_invalid_response"),
        (
            httpx.Response(200, content=b"invalid", headers={"content-type": "application/json"}),
            502,
            "intel_invalid_response",
        ),
        (httpx.Response(200, json={"data": None}), 502, "intel_invalid_response"),
        (httpx.ReadTimeout("private upstream detail"), 504, "intel_upstream_timeout"),
        (httpx.ConnectError("private address"), 502, "intel_upstream_unavailable"),
    ],
)
def test_safe_upstream_errors(adapter, upstream, status, code):
    client, calls, handler = adapter
    handler["response"] = upstream
    response = client.get("/api/research/intel/radar")
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert "private" not in response.text and "secret" not in response.text
    assert len(calls) == 1


def test_bounded_response_and_array_payload(adapter, monkeypatch):
    client, _, handler = adapter
    handler["response"] = httpx.Response(200, json={"data": [{"title": "公开新闻"}]})
    assert client.get("/api/research/intel/radar").json() == [{"title": "公开新闻"}]
    monkeypatch.setattr(intel_routes, "RESPONSE_LIMIT", 4)
    response = client.get("/api/research/intel/radar")
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "intel_response_too_large"
