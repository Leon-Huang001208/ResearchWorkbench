"""Resident attachment keeps the existing instance out of the tenant lifecycle."""

import asyncio
import json
import sqlite3
from types import SimpleNamespace
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


@pytest.mark.parametrize("value", [False, True, "missing", 0, 1, None, "false"])
def test_resident_persisted_mcp_switch_precedes_environment_before_runtime(
    tmp_path, monkeypatch, value
):
    import uvicorn

    from app.research_web.multiuser import __main__ as cli
    from app.research_web.multiuser import (
        gateway,
        resident,
        resident_binding,
        resident_boot,
        runtime,
    )

    root = tmp_path / "server"
    root.mkdir(mode=0o700)
    config = {
        "version": 1,
        "revision": "a" * 40,
        "project": str(cli.PROJECT),
        "port": 8089,
        "source": str(tmp_path / "source"),
        "node": "/synthetic/node",
        "origin": "http://localhost",
        "binding": {},
    }
    if value != "missing":
        config["mcp_readonly_enabled"] = value
    path = root / "resident.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    legacy = tmp_path / "legacy/resident"
    legacy.mkdir(parents=True)
    original = legacy / "config.json"
    original.write_text(json.dumps({"node": config["node"]}))
    original.chmod(0o600)
    calls = []

    class Pool:
        def __init__(self, *args, **kwargs):
            calls.append("runtime")

        async def close(self):
            calls.append("closed")

    def gateway_with_real_switch(accounts, pool, **kwargs):
        calls.append(kwargs)
        assert kwargs["mcp_enabled"] is (None if value == "missing" else value)
        return gateway.create_gateway_original(accounts, pool, **kwargs)

    monkeypatch.setenv("RWB_MCP_READONLY_ENABLED", "1")
    monkeypatch.setattr(resident.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(resident.subprocess, "check_output", lambda *args, **kwargs: "a" * 40)
    monkeypatch.setattr(runtime, "RuntimePool", Pool)
    monkeypatch.setattr(
        resident_binding.LegacyBinding, "from_config", lambda _: SimpleNamespace(home=legacy.parent)
    )
    monkeypatch.setattr(resident_boot, "boot_identity", lambda: "synthetic-boot")
    monkeypatch.setattr(resident_binding, "AttachedPool", lambda accounts, pool, *args: pool)
    monkeypatch.setattr(gateway, "create_gateway_original", gateway.create_gateway, raising=False)
    monkeypatch.setattr(gateway, "create_gateway", gateway_with_real_switch)
    apps = []

    def serve(app, **kwargs):
        apps.append(app)
        with TestClient(app, base_url="http://localhost") as client:
            assert client.get("/api/server/health").json()["mcp_readonly_enabled"] is (
                value is not False
            )
            if value is False:
                assert client.get("/.well-known/oauth-authorization-server").status_code == 401

    monkeypatch.setattr(uvicorn, "run", serve)
    if type(value) is not bool and value != "missing":
        with pytest.raises(cli.ServerCommandError, match="server_mcp_configuration_invalid"):
            resident.run(root)
        assert calls == [] and apps == []
        assert not (root / "accounts.sqlite3").exists()
        return
    assert resident.run(root) == 0
    assert calls[1]["mcp_enabled"] is (None if value == "missing" else value)
    assert hasattr(apps[0].state, "mcp_facade") is (value is not False)
    if value is False:
        with sqlite3.connect(root / "accounts.sqlite3") as connection:
            assert not connection.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE 'mcp_%'"
            ).fetchall()


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
    "scenario",
    [
        "previous",
        "external",
        "external_two_pids",
        "same",
        "unknown",
        "invalid",
        "permissions",
        "link",
    ],
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
    if scenario.startswith("external"):
        record.update(generation="b" * 32, execution_mode="external")
    if scenario == "external_two_pids":
        record["pids"] = [123, 456]
    owner.write_text(json.dumps(record))
    owner.chmod(0o600)
    if scenario == "permissions":
        owner.chmod(0o644)
    if scenario == "link":
        state.rename(folder / "outside")
        state.symlink_to(folder / "outside")
    if scenario in {"previous", "external"}:
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


@pytest.mark.parametrize("old_writer", ["none", "native", "docker", "unguarded"])
def test_primary_storage_requires_exclusive_lifecycle_and_quiescence(
    tmp_path, monkeypatch, old_writer
):
    import subprocess
    from contextlib import contextmanager

    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    for path in (home / "resident", home / "research-web", tmp_path / "release"):
        path.mkdir(mode=0o700)
    project = tmp_path / "release"
    data = home / "research-web"

    def identity(path):
        item = path.stat()
        return item.st_dev, item.st_ino

    binding = LegacyBinding(
        str(uuid4()), home, "a" * 40, 8088, 3081, project, identity(project), identity(data)
    )
    events = []

    @contextmanager
    def lifecycle_lock():
        events.append("locked")
        try:
            yield SimpleNamespace(assert_held=lambda: events.append("verified"))
        finally:
            events.append("released")

    manager = SimpleNamespace(
        _lifecycle_lock=lifecycle_lock,
        _native_quiescent=lambda: old_writer != "native",
        _other_runtime_quiescent=lambda: old_writer != "docker",
    )
    monkeypatch.setattr(LegacyBinding, "_verified_manager", lambda _: manager)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1 if old_writer == "unguarded" else 0),
    )
    if old_writer == "unguarded":
        with (
            pytest.raises(RuntimeErrorSafe, match="legacy_lifecycle_guard_unverified"),
            binding.service_only_storage(),
        ):
            pytest.fail("unverified legacy guard protocol was admitted")
        assert not events
    elif old_writer == "none":
        with binding.service_only_storage() as storage:
            assert storage.data_root == data and storage.user_id == binding.primary_user_id
            storage.assert_held()
        with pytest.raises(RuntimeErrorSafe, match="primary_storage_lease_unverified"):
            storage.assert_held()
        assert events == ["locked", "verified", "released"]
    else:
        code = (
            "legacy_other_runtime_must_be_stopped"
            if old_writer == "docker"
            else "legacy_services_must_be_stopped"
        )
        with (
            pytest.raises(RuntimeErrorSafe, match=code),
            binding.service_only_storage(),
        ):
            pytest.fail("live legacy service was admitted")
        assert events == ["locked", "released"]


def test_service_only_resident_serves_original_primary_and_releases_lifecycle(
    tmp_path, monkeypatch
):
    import subprocess
    from pathlib import Path

    import uvicorn

    from app.research_web.multiuser import __main__ as cli
    from app.research_web.multiuser import resident, resident_boot
    from app.research_web.multiuser.runtime import _reserve_port
    from app.research_web.service_manager import WebServiceManager
    from app.research_web.store import Store

    home = tmp_path / "legacy"
    root = tmp_path / "server"
    for directory in (
        home,
        home / "resident",
        home / "install",
        home / "run",
        home / "research-web",
    ):
        directory.mkdir(mode=0o700)
    project = Path(cli.PROJECT).resolve()
    sha = subprocess.check_output(
        ["/usr/bin/git", "-C", str(project), "rev-parse", "HEAD"], text=True
    ).strip()
    accounts = AccountStore(root)
    admin = accounts.create_user("primary-pilot", "synthetic primary password", "admin")
    token, _ = accounts.login(admin.username, "synthetic primary password")
    with _reserve_port() as listener:
        web = listener.getsockname()[1]
    with _reserve_port() as listener:
        dsh = listener.getsockname()[1]
    data = home / "research-web"
    store = Store(data)
    sid = store.create("fingpt", "Originally attached research")["id"]
    original = store.directory(sid) / "inputs" / "archive.txt"
    raw = b"approved original primary evidence"
    original.write_bytes(raw)
    store.files(sid)
    control = data / ".control"
    control.mkdir(mode=0o700)

    def save(path, value):
        path.write_text(json.dumps(value))
        path.chmod(0o600)

    save(control / "datahub.json", {"url": f"http://127.0.0.1:{web}", "token": "S" * 43})
    save(
        home / "resident/config.json",
        {"project": str(project), "web_port": web, "runtime_port": dsh, "node": "/synthetic/node"},
    )
    save(home / "install/manifest.json", {"status": "installed", "code_commit": sha})
    binding = LegacyBinding.discover(home, admin.id)
    origin = "https://research.tail123.ts.net"
    save(
        root / "resident.json",
        {
            "version": 1,
            "revision": sha,
            "project": str(project),
            "port": 8089,
            "source": str(project),
            "node": "/synthetic/node",
            "origin": origin,
            "binding": binding.public_config(),
            "service_only": True,
            "mcp_readonly_enabled": True,
            "weknora_oauth_origin": "https://weknora.tail123.ts.net",
        },
    )
    monkeypatch.setattr(resident.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(resident_boot, "boot_identity", lambda: str(uuid4()))
    monkeypatch.setattr(WebServiceManager, "_native_quiescent", lambda self: True)

    def serve(app, **options):
        with TestClient(app, base_url=origin) as client:
            health = client.get("/api/server/health").json()
            assert (
                health["execution_mode"] == "external" and health["primary_last_verified"] is True
            )
            headers = {"Cookie": "rwb_session=" + token}
            history = client.get("/api/research/sessions", headers=headers).json()
            assert any(item["id"] == sid for item in history["items"])
            record = json.loads((root / "users" / admin.id / "state/owner.json").read_bytes())
            assert len(record["pids"]) == 1 and record["execution_mode"] == "external"
            assert not (root / "users" / admin.id / "research-web").exists()
            assert app.state.mcp_facade.store.client_enabled("rwb-weknora")

    monkeypatch.setattr(uvicorn, "run", serve)
    assert resident.run(root) == 0
    assert original.read_bytes() == raw
    assert not (root / "users" / admin.id / "state/owner.json").exists()
    with _reserve_port(web):
        pass
    manager = binding._verified_manager()
    with manager._lifecycle_lock() as lease:
        lease.assert_held()
