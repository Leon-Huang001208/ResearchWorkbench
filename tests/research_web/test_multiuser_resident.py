"""Resident attachment keeps the existing instance out of the tenant lifecycle."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.research_web.multiuser.accounts import AccountError, AccountStore
from app.research_web.multiuser.gateway import create_gateway
from app.research_web.multiuser.preservation import compare_snapshot, snapshot
from app.research_web.multiuser.resident_binding import AttachedPool, LegacyBinding
from app.research_web.multiuser.resident_boot import retire_previous_boot
from app.research_web.multiuser.runtime import Backend, RuntimeErrorSafe


class PrivatePool:
    def __init__(self):
        self.calls = []
        self.stopped = []
        self.closed = False

    async def backend_for(self, uid):
        self.calls.append(uid)
        return Backend("http://127.0.0.1:19998", "test-private-key")

    async def stop(self, uid):
        self.stopped.append(uid)

    async def close(self):
        self.closed = True


@pytest.fixture
def attached(tmp_path, monkeypatch):
    accounts = AccountStore(tmp_path / "server")
    admin = accounts.create_user("admin", "a private test password", "admin")
    user = accounts.create_user("userone", "a private user password")
    binding = LegacyBinding(
        admin.id, tmp_path / "legacy", "a" * 40, 8088, 3081, tmp_path / "production", (1, 2), (3, 4)
    )
    legacy_ui = binding.project / "app/research_web/ui"
    legacy_ui.mkdir(parents=True)
    (legacy_ui / "index.html").write_text(
        '<p>original UI</p><script src="/static/app.mjs"></script>'
    )
    (legacy_ui / "original-only.mjs").write_text("original asset")
    monkeypatch.setattr(
        LegacyBinding, "verify", lambda self: {"revision": self.revision, "active": False}
    )
    private = PrivatePool()
    return AttachedPool(accounts, private, binding, "b" * 40), private, admin, user


@pytest.mark.asyncio
async def test_primary_routes_to_existing_backend_without_starting_or_stopping_it(attached):
    pool, private, admin, user = attached
    primary = await pool.backend_for(admin.id)
    assert primary.url == "http://127.0.0.1:8088"
    assert private.calls == []
    assert (await pool.backend_for(user.id)).url != primary.url
    assert private.calls == [user.id]
    with pytest.raises(AccountError, match="primary_account_protected"):
        await pool.stop(admin.id)
    await pool.close()
    assert private.closed and private.stopped == []


@pytest.mark.asyncio
async def test_primary_binding_never_falls_back_to_another_users_root(attached, monkeypatch):
    pool, private, admin, user = attached

    def unavailable(self):
        raise RuntimeErrorSafe("legacy_instance_unverified")

    monkeypatch.setattr(LegacyBinding, "verify", unavailable)
    with pytest.raises(RuntimeErrorSafe, match="legacy_instance_unverified"):
        await pool.backend_for(admin.id)
    assert private.calls == []
    assert (await pool.backend_for(user.id)).url == "http://127.0.0.1:19998"


def test_snapshot_detects_old_data_or_model_changes_but_allows_new_sessions(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    sid = str(uuid4())
    folder = root / "sessions" / sid / "inputs"
    folder.mkdir(parents=True)
    (folder / "original.md").write_text("original bytes")
    index = {
        "sessions": {sid: {"id": sid, "title": "old", "mode": "claw"}},
        "model": {"provider": "deepseek-official", "model": "deepseek-flash"},
    }
    (root / "index.json").write_text(json.dumps(index))
    before = snapshot(root)
    index["sessions"][str(uuid4())] = {"mode": "fingpt"}
    (root / "index.json").write_text(json.dumps(index))
    assert compare_snapshot(before, snapshot(root))["preserved"] is True
    (folder / "original.md").write_text("changed")
    assert compare_snapshot(before, snapshot(root))["preserved"] is False
    (folder / "original.md").write_text("original bytes")
    index["model"]["model"] = "other"
    (root / "index.json").write_text(json.dumps(index))
    assert compare_snapshot(before, snapshot(root))["preserved"] is False


def test_deployment_gate_blocks_get_birth_and_login_but_reports_fenced_health(attached, tmp_path):
    pool, private, _admin, _user = attached
    pool.deployment_path = tmp_path / "gateway-upgrade.json"
    pool.deployment_path.write_text("{}")
    with TestClient(
        create_gateway(pool.accounts, pool, origin="http://localhost"), base_url="http://localhost"
    ) as client:
        assert client.get("/api/research/sessions").status_code == 503
        assert client.post("/api/server/login").status_code == 503
        health = client.get("/api/server/health")
        assert health.status_code == 200 and health.json()["deployment_fenced"] is True
        assert private.calls == []


@pytest.mark.asyncio
async def test_anonymous_health_is_cheap_and_primary_probes_single_flight(attached, monkeypatch):
    pool, _private, admin, _user = attached
    calls = []
    monkeypatch.setattr(LegacyBinding, "verify", lambda self: calls.append(1))
    await asyncio.gather(*(pool.health() for _ in range(50)))
    assert calls == []
    await asyncio.gather(*(pool.backend_for(admin.id) for _ in range(20)))
    assert calls == [1]


def test_primary_protection_and_cutover_fence_are_enforced_by_http(attached, tmp_path):
    pool, _private, admin, _user = attached
    pool.maintenance_path = tmp_path / "cutover.json"
    with TestClient(
        create_gateway(pool.accounts, pool, origin="http://localhost"), base_url="http://localhost"
    ) as client:
        assert client.get("/api/server/health").json()["status"] == "ready"
        login = client.post(
            "/api/server/login",
            headers={"Origin": "http://localhost"},
            json={"username": "admin", "password": "a private test password"},
        )
        assert login.status_code == 200
        for method, suffix, body in (("PATCH", "", {"enabled": False}), ("POST", "/stop", None)):
            result = client.request(
                method,
                f"/api/server/users/{admin.id}{suffix}",
                headers={"Origin": "http://localhost"},
                json=body,
            )
            assert result.status_code == 409
        pool.maintenance_path.write_text("{}")
        result = client.post(
            "/api/research/sessions", headers={"Origin": "http://localhost"}, json={}
        )
        assert result.status_code == 503
        assert pool.accounts.get_user(admin.id).enabled is True


def test_primary_keeps_original_ui_assets_and_ai_reading_backend(attached):
    pool, _private, _admin, _user = attached
    forwarded = []

    async def upstream(request):
        forwarded.append(request)
        return httpx.Response(200, json={"original_backend": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_gateway(pool.accounts, pool, origin="http://localhost", upstream=client)
    with TestClient(app, base_url="http://localhost") as browser:
        assert browser.get("/static/original-only.mjs").status_code == 404
        assert (
            browser.post(
                "/api/server/login",
                headers={"Origin": "http://localhost"},
                json={"username": "admin", "password": "a private test password"},
            ).status_code
            == 200
        )
        page = browser.get("/").text
        assert "original UI" in page and "/server-static/session.mjs" in page
        assert browser.get("/static/original-only.mjs").text == "original asset"
        response = browser.get("/api/research/aihot/featured")
        assert response.status_code == 200 and response.json() == {"original_backend": True}
        assert forwarded[-1].url.port == 8088
        assert "x-rwb-tenant-gateway-key" not in forwarded[-1].headers
        browser.post("/api/server/logout", headers={"Origin": "http://localhost"})
        browser.post(
            "/api/server/login",
            headers={"Origin": "http://localhost"},
            json={"username": "userone", "password": "a private user password"},
        )
        assert browser.get("/static/original-only.mjs").status_code == 404
        assert "original UI" not in browser.get("/").text


@pytest.mark.parametrize("name", ["outputs/tmp/report.md", "outputs/report.lock"])
@pytest.mark.parametrize("change", ["modify", "delete", "symlink"])
def test_preservation_includes_business_tmp_and_lock_files(tmp_path, name, change):
    root = tmp_path / "data"
    root.mkdir()
    (root / "index.json").write_text(json.dumps({"sessions": {}}))
    file = root / "sessions" / str(uuid4()) / name
    file.parent.mkdir(parents=True)
    file.write_text("business")
    before = snapshot(root)
    if change == "modify":
        file.write_text("modified")
    else:
        file.unlink()
    if change == "symlink":
        file.symlink_to(tmp_path / "outside")
        with pytest.raises(RuntimeError, match="preservation_snapshot_failed"):
            snapshot(root)
    else:
        assert compare_snapshot(before, snapshot(root))["preserved"] is False


@pytest.mark.parametrize(
    "scenario", ["previous", "same", "unknown", "invalid", "permissions", "link"]
)
def test_boot_recovery_only_retires_proven_previous_boot(tmp_path, scenario):
    store = AccountStore(tmp_path / "server")
    user = store.create_user("admin", "private test password", "admin")
    current, previous = str(uuid4()), str(uuid4())
    folder = tmp_path / "server/users" / (str(uuid4()) if scenario == "unknown" else user.id)
    folder.mkdir(parents=True, mode=0o700)
    state = folder / "state"
    state.mkdir(mode=0o700)
    owner = state / "owner.json"
    record = {
        "version": 1,
        "user": folder.name,
        "instance": "a" * 32,
        "pids": [123],
        "boot_id": current if scenario == "same" else previous,
    }
    if scenario == "invalid":
        record.pop("boot_id")
    owner.write_text(json.dumps(record))
    owner.chmod(0o600)
    if scenario == "permissions":
        owner.chmod(0o644)
    if scenario == "link":
        state.rename(folder / "outside")
        state.symlink_to(folder / "outside")
    if scenario == "previous":
        retire_previous_boot(
            folder, current_boot=current, accounts=store, archive=tmp_path / "archive"
        )
        assert not owner.exists()
        assert len(list((tmp_path / "archive").glob("*/owner.json"))) == 1
    else:
        with pytest.raises((RuntimeErrorSafe, AccountError)):
            retire_previous_boot(
                folder, current_boot=current, accounts=store, archive=tmp_path / "archive"
            )
        assert owner.exists()


@pytest.mark.parametrize(
    "target", ["sessions", "runtime", "runtime/home", "runtime/home/sessions", "index.json"]
)
@pytest.mark.parametrize("dangling", [False, True])
def test_preservation_rejects_links_at_scan_roots_and_index(tmp_path, target, dangling):
    root = tmp_path / "data"
    root.mkdir()
    (root / "index.json").write_text(json.dumps({"sessions": {}}))
    outside = tmp_path / "outside"
    if not dangling:
        if target == "index.json":
            outside.write_text(json.dumps({"sessions": {}}))
        else:
            outside.mkdir()
    link = root / target
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists():
        link.unlink()
    link.symlink_to(outside)
    with pytest.raises(RuntimeError, match="preservation_snapshot_failed"):
        snapshot(root)
