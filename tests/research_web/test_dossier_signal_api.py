"""HTTP wiring uses actual per-user archives and rejects malformed scan input."""

import pytest
from fastapi.testclient import TestClient
from test_api import NativeFixture

from app.research_web.main import create_app
from app.research_web.mcp_runtime.service import MCPRuntimeService
from app.research_web.service import ResearchService
from app.research_web.store import Store


@pytest.fixture
def api(tmp_path, monkeypatch):
    import keyring

    monkeypatch.setattr(keyring, "get_password", lambda *_args: None)
    research = ResearchService(
        NativeFixture(), Store(tmp_path), mcp_runtime=MCPRuntimeService(enabled=False)
    )
    # No lifespan/collectors: this test operates only explicit HTTP requests.
    app = create_app(research)
    app.state.research = research
    client = TestClient(app)
    research.connected = {"host", "mux"}
    yield client, research
    client.close()


def create(client):
    response = client.post(
        "/api/research/dossiers",
        json={
            "title": "主题研究",
            "subject": {"kind": "theme", "key": "energy-transition", "label": "能源转型"},
            "idempotency_key": "create-0001",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_signals_static_route_precedes_dossier_id_and_scan_is_idempotent(api):
    client, research = api
    dossier = create(client)
    assert client.get("/api/research/dossiers/signals").status_code == 200
    response = client.post(
        f"/api/research/dossiers/{dossier['id']}/scan",
        json={"expected_revision": 1, "idempotency_key": "scan-0001"},
    )
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["coverage"]["eligible"] is False
    assert any(row["code"] == "no_frozen_evidence" for row in value["missing"])
    replay = client.post(
        f"/api/research/dossiers/{dossier['id']}/scan",
        json={"expected_revision": 1, "idempotency_key": "scan-0001"},
    )
    assert replay.json() == value
    assert not research.store.data.get("automations", {})


@pytest.mark.parametrize(
    "updates", [{"as_of": "2026-02-30"}, {"expected_revision": 0}, {"owner": "other"}]
)
def test_invalid_scan_input_is_422_and_does_not_write(api, updates):
    client, research = api
    dossier = create(client)
    response = client.post(
        f"/api/research/dossiers/{dossier['id']}/scan",
        json={"expected_revision": 1, "idempotency_key": "scan-0001", **updates},
    )
    assert response.status_code == 422
    assert research.dossiers.get(dossier["id"])["revision"] == 1


def test_tracking_scope_does_not_create_jobs_for_unqualified_material(api):
    client, research = api
    dossier = create(client)
    response = client.patch(
        f"/api/research/dossiers/{dossier['id']}/tracking",
        json={"expected_revision": 1, "idempotency_key": "tracking-0001", "enabled": True},
    )
    assert response.status_code == 409
    assert not research.store.data.get("automations", {})
    assert client.get("/api/research/dossiers/signals?cursor=bad").status_code == 422
