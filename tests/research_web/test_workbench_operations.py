"""Research desk handoff and read-only operations regressions."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.research_web.main import create_app
from app.research_web.operations import _managed_state
from app.research_web.service import ResearchService
from app.research_web.store import Store


class NativeFixture:
    def __init__(self):
        self.history_calls = 0

    async def rpc(self, method, payload):
        if method == "host.describe":
            return {
                "version": "fixture",
                "provider": "fixture",
                "cwd": payload.get("cwd"),
            }
        if method == "credentials.describe":
            return {"credentials": {"RESEARCH_DSH_API_KEY": {"configured": True}}}
        if method == "session.list":
            return {"items": []}
        if method == "subagent.list":
            return {"entries": []}
        if method == "skill.list":
            return {"skills": []}
        return {"accepted": True}

    async def history(self, sid):
        self.history_calls += 1
        return []

    async def close(self):
        return None

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()


def nav_payload():
    return {
        "ErrCode": 0,
        "TotalCount": 1,
        "PageSize": 100,
        "PageIndex": 1,
        "Data": {
            "LSJZList": [
                {
                    "FSRQ": "2025-12-31",
                    "DWJZ": "1.2",
                    "LJJZ": "1.3",
                    "JZZZL": "0.1",
                    "FHSP": "",
                }
            ],
            "FundType": "002",
        },
    }


@pytest.fixture
def api(tmp_path):
    service = ResearchService(NativeFixture(), Store(tmp_path))
    service.datahub.transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=nav_payload())
    )
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, service


def test_research_desk_query_is_idempotent_and_exposes_safe_status(api):
    client, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    payload = {
        "session_id": sid,
        "section": "funds",
        "query": {
            "capability": "fund_data",
            "parameters": {"dataset": "nav", "code": "000001", "limit": 20},
        },
    }
    headers = {"Idempotency-Key": "desk-query-0001"}
    first = client.post("/api/research/data/queries", json=payload, headers=headers)
    second = client.post("/api/research/data/queries", json=payload, headers=headers)
    assert first.status_code == 202, first.text
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    query_id = first.json()["id"]
    for _ in range(20):
        status = client.get(f"/api/research/data/queries/{query_id}").json()
        if status["status"] != "running":
            break
    assert status["status"] == "completed"
    assert status["dataset"]["row_count"] == 1
    assert "sample" not in status["dataset"]
    listed = client.get("/api/research/data/queries?section=funds").json()["items"]
    assert listed[0] == status
    assert client.get("/api/research/data/queries?section=market").json()["items"] == []
    assert len(service.datahub.list(sid)) == 1


def test_handoff_copies_only_selected_datasets_and_freezes_page_context(api):
    client, service = api
    source = client.post("/api/research/sessions", json={}).json()["id"]
    query = service.datahub.query
    from app.research_web.datahub import BusinessQuery

    one = asyncio.run(
        query(
            source,
            "one",
            BusinessQuery(
                capability="fund_data",
                parameters={"dataset": "nav", "code": "000001", "limit": 20},
            ),
        )
    )
    two = asyncio.run(
        query(
            source,
            "two",
            BusinessQuery(
                capability="fund_data",
                parameters={"dataset": "profile", "code": "000001"},
                refresh=True,
            ),
        )
    )
    response = client.post(
        "/api/research/handoffs",
        json={
            "source_session_id": source,
            "target_mode": "claw",
            "section": "funds",
            "dataset_ids": [one["dataset_id"]],
            "context": {
                "code": "000001",
                "source": "eastmoney_fund",
                "as_of": "2025-12-31",
            },
        },
        headers={"Idempotency-Key": "handoff-0001"},
    )
    assert response.status_code == 201, response.text
    target = response.json()
    assert target["mode"] == "claw"
    copied = service.datahub.list(target["session_id"])
    assert len(copied) == 1
    assert copied[0]["origin_dataset_id"] == one["dataset_id"]
    assert copied[0]["origin_dataset_id"] != two["dataset_id"]
    context_path = (
        service.store.directory(target["session_id"])
        / response.json()["context_file"]["path"]
    )
    frozen = json.loads(context_path.read_text())
    assert frozen["section"] == "funds"
    assert frozen["context"]["code"] == "000001"
    assert str(service.store.root) not in response.text


def test_artifacts_and_operations_never_return_contents_or_secrets(api, tmp_path):
    client, service = api
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    output = service.store.directory(sid) / "outputs" / "report.html"
    output.write_text("<p>private prompt canary</p>")
    service.store.files(sid)
    service.store.data.setdefault("operation_audit", []).append(
        {"kind": "approval", "outcome": "approve", "at": 1767225600.0}
    )
    service.store.save()

    artifacts = client.get("/api/research/artifacts").json()
    assert artifacts["items"][0]["name"] == "report.html"
    assert "private prompt canary" not in json.dumps(artifacts)

    for endpoint in ("summary", "usage", "tools", "datahub", "services", "storage"):
        response = client.get(f"/api/research/operations/{endpoint}?range=30d")
        assert response.status_code == 200, response.text
        text = response.text
        assert "private prompt canary" not in text
        assert "api_key" not in text.casefold()
    usage = client.get("/api/research/operations/usage?range=30d").json()
    assert usage["cost"]["status"] == "not_configured"
    assert usage["tokens"]["known"] is False
    storage = client.get("/api/research/operations/storage").json()
    assert {item["id"] for item in storage["categories"]} >= {
        "attachments",
        "datasets",
        "artifacts",
        "logs",
        "dsh_source",
        "report_projects",
    }
    assert Path(storage["scope"]).resolve() == tmp_path.resolve()


def test_handoff_rejects_unknown_dataset_before_creating_target(api):
    client, service = api
    source = client.post("/api/research/sessions", json={}).json()["id"]
    before = set(service.store.data["sessions"])
    response = client.post(
        "/api/research/handoffs",
        json={
            "source_session_id": source,
            "target_mode": "fingpt",
            "section": "market",
            "dataset_ids": ["00000000-0000-0000-0000-000000000000"],
            "context": {"market": "CN"},
        },
        headers={"Idempotency-Key": "handoff-invalid-dataset"},
    )
    assert response.status_code == 400
    assert set(service.store.data["sessions"]) == before


def test_handoff_rejects_oversized_page_context_before_creating_target(api):
    client, service = api
    source = client.post("/api/research/sessions", json={}).json()["id"]
    before = set(service.store.data["sessions"])
    response = client.post(
        "/api/research/handoffs",
        json={
            "source_session_id": source,
            "target_mode": "claw",
            "section": "documents",
            "context": {"summary": "x" * (65 * 1024)},
        },
        headers={"Idempotency-Key": "handoff-large-context"},
    )
    assert response.status_code == 400
    assert "64 KiB" in response.text
    assert set(service.store.data["sessions"]) == before


def test_operations_summary_loads_each_session_history_once(api):
    client, service = api
    client.post("/api/research/sessions", json={})
    service.client.history_calls = 0
    response = client.get("/api/research/operations/summary?range=today")
    assert response.status_code == 200, response.text
    assert service.client.history_calls == 1
    assert "reports" in response.json()


def test_managed_process_requires_matching_state_fingerprint_and_command(
    tmp_path, monkeypatch
):
    root = tmp_path / "research-web"
    run = tmp_path / "run"
    root.mkdir()
    run.mkdir()
    command = ["python", "-m", "uvicorn", "app.research_web.main:app"]
    signature = ["app.research_web.main:app", "8088"]
    payload = json.dumps(command, ensure_ascii=False, separators=(",", ":"))
    state = {
        "version": 1,
        "role": "web",
        "pid": os.getpid(),
        "port": 8088,
        "started_at": 1.0,
        "project_root": str(Path(__file__).parents[2].resolve()),
        "data_root": str(root.resolve()),
        "command": command,
        "fingerprint": hashlib.sha256(payload.encode()).hexdigest(),
        "signature": signature,
    }
    (run / "web.json").write_text(json.dumps(state))
    monkeypatch.setattr(
        "app.research_web.operations.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="python -m uvicorn app.research_web.main:app --port 8088",
        ),
    )
    assert _managed_state(root, "web", 8088)["process_running"] is True

    state["command"].append("--tampered")
    (run / "web.json").write_text(json.dumps(state))
    assert _managed_state(root, "web", 8088)["process_running"] is False
