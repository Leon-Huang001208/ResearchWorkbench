"""Legacy FinGPT observes the same installed state as the managed Research Web."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from research_workbench_entrypoint.resident.admission import MaintenanceBusy, file_lock

from app.api.routes import fingpt

ORIGIN = "https://research.tail123.ts.net"
SHA = "a" * 40
BASE = "/api/v2/fingpt"


def _write(path, value):
    path.parent.mkdir(mode=0o700, exist_ok=True, parents=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def _state(home, enabled=True, origin=ORIGIN, gateway_sha=SHA, flag=None):
    flags = {"alphadesk_qa": enabled if flag is None else flag} if enabled else {}
    _write(home / "resident/config.json", {"baseline": SHA, "private_origin": origin})
    _write(
        home / "install/manifest.json",
        {"schema_version": 1, "status": "installed", "code_commit": SHA, **flags},
    )
    _write(
        home / "server/resident.json",
        {
            "version": 1,
            "origin": origin,
            "revision": gateway_sha,
            "binding": {"revision": gateway_sha, "home": str(home)},
            **flags,
        },
    )
    _write(
        home / "resident/accepted.json",
        {
            "target": SHA,
            "compatibility_review": {"profile": "reviewed-fingpt-alphadesk-v1"} if enabled else {},
        },
    )


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    home = tmp_path.resolve() / "research-home"
    home.mkdir(mode=0o700)
    monkeypatch.setenv("RESEARCH_RESIDENT_HOME", str(home / "resident"))
    monkeypatch.setenv("ALPHAFOUNDRY_DSH_TOOL_TOKEN", "fixture-token")
    calls = []

    class Service:
        def health(self):
            calls.append("legacy-health")
            return {"available": False}

        def create_task(self, preset_id):
            calls.append(preset_id)
            with (
                pytest.raises(MaintenanceBusy),
                file_lock(home / "resident", "admission.lock", exclusive=True),
            ):
                pytest.fail("legacy write ran outside resident admission")
            return {"created": True}

        def accept_dsh_event(self, event):
            calls.append(event["event_type"])
            return True

    def db():
        calls.append("db")
        yield None
        if "fail-db" in calls:
            raise ValueError("legacy database error")

    def service(_db=None):
        return Service()

    app = FastAPI()
    app.include_router(fingpt.router)
    app.dependency_overrides[fingpt.get_fingpt_service] = service
    monkeypatch.setattr(fingpt, "get_db", db)
    monkeypatch.setattr(fingpt, "get_fingpt_service", service)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        yield home, client, calls


def test_active_uses_configured_origin_without_touching_legacy_service(legacy):
    home, client, calls = legacy
    _state(home)
    health = client.get(BASE + "/health", headers={"host": "hostile.example"})
    assert health.json() == {"retired": True, "research_web_url": ORIGIN + "/#/qa"}
    assert health.headers["cache-control"] == "no-store"
    for endpoint, body in [
        ("/tasks", {"preset_id": "theme-research"}),
        ("/tasks/old/execute", {}),
        ("/launches/old/consume", {}),
    ]:
        assert (
            client.post(
                BASE + endpoint,
                json=body,
                headers={"authorization": "Bearer fixture-token"},
            ).status_code
            == 410
        )
    assert not calls
    event = client.post(
        BASE + "/dsh-events",
        json={"session_id": "old", "event_key": "old", "event_type": "turn/end"},
        headers={"authorization": "Bearer fixture-token"},
    )
    assert event.status_code == 202
    assert calls == ["turn/end"]


def test_rollback_refreshes_existing_legacy_process_and_locks_old_writes(legacy):
    home, client, calls = legacy
    _state(home)
    assert client.get(BASE + "/health").json()["retired"] is True
    _state(home, enabled=False)
    assert client.get(BASE + "/health").json() == {"available": False}
    assert client.post(BASE + "/tasks", json={"preset_id": "theme-research"}).status_code == 201
    assert calls == ["db", "legacy-health", "theme-research"]


@pytest.mark.parametrize(
    "cause", ["transaction", "gateway-journal", "mixed", "origin", "integer", "symlink"]
)
def test_partial_or_unsafe_managed_cutover_blocks_writes(legacy, cause):
    home, client, calls = legacy
    _state(
        home,
        origin="https://other.example" if cause == "origin" else ORIGIN,
        gateway_sha="b" * 40 if cause == "mixed" else SHA,
        flag=1 if cause == "integer" else None,
    )
    if cause == "transaction":
        _write(home / "resident/transaction.json", {})
    elif cause == "gateway-journal":
        _write(home / "server/run/gateway-upgrade.json", {})
    elif cause == "symlink":
        manifest = home / "install/manifest.json"
        manifest.rename(home / "copied-manifest.json")
        manifest.symlink_to(home / "copied-manifest.json")
    assert client.get(BASE + "/health").status_code == 503
    assert client.post(BASE + "/tasks", json={"preset_id": "theme-research"}).status_code == 503
    assert not calls


def test_missing_default_install_keeps_legacy_without_creating_state(legacy, monkeypatch):
    home, client, calls = legacy
    monkeypatch.delenv("RESEARCH_RESIDENT_HOME")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RWB_ALPHADESK_QA", "1")
    assert client.get(BASE + "/health").json() == {"available": False}
    assert calls == ["db", "legacy-health"]
    assert not (home / ".research-workbench").exists()


def test_legacy_health_does_not_mislabel_database_error(legacy):
    home, client, calls = legacy
    _state(home, enabled=False)
    calls.append("fail-db")
    response = client.get(BASE + "/health")
    assert response.status_code == 409
    assert response.json() == {"detail": "legacy database error"}
