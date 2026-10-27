"""Fixed native compatibility ingress uses real provider/parser/snapshot paths."""

import asyncio
import json
import os
import select
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import httpx
import pytest
import test_owned_method_execution as fixtures

api = fixtures.api


@pytest.mark.parametrize(
    "arguments",
    [
        {"limit": True},
        {"limit": 1.5},
        {"limit": 101},
        {"date": "2026-01-01"},
        {"source": "auto"},
        {"stock": "MSFT"},
        {"sentiment": "positive"},
        {"importance": 1},
        {"query": "https://example.com"},
    ],
)
def test_host_owned_news_strict_arguments_cannot_use_original_broad_schema(api, arguments):
    client, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    response = client.post(
        "/api/research/internal/data/business-query",
        headers={"X-Research-Data-Key": service.datahub.control["token"]},
        json={
            "request_kind": "owned-latest-cls-news-v1",
            "session_id": sid,
            "call_id": "bad-owned-arguments",
            "arguments": arguments,
        },
    )
    assert response.status_code == 422
    assert not service.datahub.snapshots.ids(sid)


def test_wrapper_rechecks_scope_source_and_actual_cancel_before_snapshot(api, monkeypatch):
    from app.research_web.datahub import catalog

    client, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    monkeypatch.setattr(service, "_model_tools_verified", lambda _sid=None: True)
    headers = {"X-Research-Data-Key": service.datahub.control["token"]}
    body = {
        "request_kind": "owned-latest-cls-news-v1",
        "session_id": sid,
        "call_id": "owned-cancel",
        "arguments": {"limit": 2},
    }
    service.store.session(sid)["source_scope"] = ["web", "uploads"]
    assert (
        client.post(
            "/api/research/internal/data/business-query", json=body, headers=headers
        ).status_code
        == 409
    )
    service.store.session(sid)["source_scope"] = ["datahub", "web", "uploads"]
    disabled = catalog.DISABLED
    monkeypatch.setattr(catalog, "DISABLED", {*disabled, "cls"})
    assert (
        client.post(
            "/api/research/internal/data/business-query", json=body, headers=headers
        ).status_code
        == 409
    )
    monkeypatch.setattr(catalog, "DISABLED", disabled)
    entered, cancelled = Event(), Event()

    async def respond(request):
        assert request.url.host == "www.cls.cn"
        entered.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        raise AssertionError("expected cancellation")

    service.datahub.transport = httpx.MockTransport(respond)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.post, "/api/research/internal/data/business-query", json=body, headers=headers
        )
        assert entered.wait(3)
        cancel = client.post(
            "/api/research/internal/data/cancel",
            json={"session_id": sid, "call_id": "owned-cancel"},
            headers=headers,
        )
        assert cancel.status_code == 200, cancel.text
        assert future.result(timeout=5).status_code == 409
    assert cancelled.is_set()
    assert not service.datahub.snapshots.ids(sid)


def test_native_news_wrapper_real_host_provider_and_bounded_snapshot(api, monkeypatch, tmp_path):
    client, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    calls = []

    def respond(request):
        assert request.url.host == "www.cls.cn"
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "errno": 0,
                "data": {
                    "roll_data": [
                        {"id": 123, "ctime": 1788326831, "content": "No matching headline"},
                        {"id": 124, "ctime": 1788326830, "content": "ABC acquired event body"},
                    ]
                },
            },
        )

    service.datahub.transport = httpx.MockTransport(respond)
    monkeypatch.setattr(service, "_model_tools_verified", lambda _sid=None: True)
    path = tmp_path / "native-owned-news.json"
    path.write_text(
        json.dumps(
            {
                "researchRoot": str(service.store.root),
                "sid": sid,
                "cases": [
                    {"query": "abc", "limit": 1},
                    {"query": "abc", "limit": 2},
                    {"query": "", "limit": 2},
                    {"limit": True},
                    {"limit": 1.5},
                    {"days": 3},
                    {"query": "https://example.com"},
                ],
            }
        )
    )
    node = os.environ["RWB_TEST_NODE"]
    process = subprocess.Popen(
        [
            node,
            str(
                Path(__file__).parents[2] / "tests/javascript/helpers/owned-news-native-driver.mjs"
            ),
            str(path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    headers = {"X-Research-Data-Key": service.datahub.control["token"]}
    final, queries = None, []
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            ready, _, _ = select.select([process.stdout], [], [], 0.5)
            if not ready:
                if process.poll() is not None:
                    break
                continue
            line = process.stdout.readline()
            if not line:
                break
            value = json.loads(line)
            if value["kind"] == "result":
                final = value
                break
            assert value["authorizationPresent"]
            assert value["path"] in {
                "/api/research/internal/data/business-query",
                "/api/research/internal/data/skill-preflight",
                "/api/research/internal/data/cancel",
            }
            response = client.post(value["path"], json=value["body"], headers=headers)
            if value["path"].endswith("business-query"):
                queries.append(response.json())
                assert value["body"]["request_kind"] == "owned-latest-cls-news-v1"
            process.stdin.write(
                json.dumps(
                    {"id": value["id"], "status": response.status_code, "body": response.json()}
                )
                + "\n"
            )
            process.stdin.flush()
        process.stdin.close()
        process.wait(timeout=5)
        assert process.returncode == 0 and final is not None, process.stderr.read()
        assert all(item["isError"] is False for item in final["results"][:3])
        assert all(item["isError"] is True for item in final["results"][3:])
        assert [item["row_count"] for item in queries] == [0, 1, 2]
        assert [int(request.url.params["rn"]) for request in calls] == [1, 2, 2]
        assert {"start_date", "end_date", "source"} <= set(final["original"]["properties"])
        for item in queries:
            manifest = service.datahub.detail(sid, item["dataset_id"])
            assert manifest["provider"] == "cls"
            assert manifest["query"]["allow_fallback"] is False
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
