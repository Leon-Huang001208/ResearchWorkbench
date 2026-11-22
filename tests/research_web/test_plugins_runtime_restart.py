"""Pool birth-fence concurrency with only bounded, test-owned fixture processes."""

import asyncio
import json
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.research_web import PINNED_DSH_COMMIT
from app.research_web.multiuser import runtime
from app.research_web.plugins import PluginError, PluginService
from app.research_web.plugins.proof import sign
from app.research_web.plugins.runtime_restart import ManagerControl, freeze, unfreeze
from app.research_web.plugins.service import _atomic


def spawn_fixture(root):
    return subprocess.Popen(
        [sys.executable, "-I", "-S", "-c", "import time; time.sleep(30)"],
        cwd=root,
        env={"HOME": str(root), "PATH": "/usr/bin:/bin"},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


@pytest.mark.asyncio
async def test_backend_freeze_tracks_births_and_rejects_cross_generation_or_replay(
    tmp_path, monkeypatch
):
    user, generation, manager = str(uuid4()), uuid4().hex, uuid4().hex
    key = "K" * 43
    keyfile = tmp_path / "gateway.key"
    keyfile.write_text(key)
    keyfile.chmod(0o600)
    for name, value in {
        "RWB_TENANT_MODE": "1",
        "RWB_TENANT_USER": user,
        "RWB_TENANT_GENERATION": generation,
        "RWB_TENANT_MANAGER_INSTANCE": manager,
        "RWB_TENANT_GATEWAY_KEY_FILE": str(keyfile),
    }.items():
        monkeypatch.setenv(name, value)
    plugins = PluginService(tmp_path)
    service = SimpleNamespace(
        plugins=plugins,
        lock=asyncio.Lock(),
        plugin_inflight=0,
        plugin_runtime_frozen=False,
        datahub=SimpleNamespace(tasks={}, probe_tasks={}),
        asset_workspace=SimpleNamespace(history_jobs=SimpleNamespace(tasks={})),
        automations=SimpleNamespace(tasks={}),
        mcp_runtime=SimpleNamespace(runtime=SimpleNamespace(operations=set())),
        model_test_lock=asyncio.Lock(),
    )

    async def idle():
        return True

    service._capability_idle = idle
    body = ManagerControl(
        generation=generation, manager_instance=manager, freeze_id=uuid4().hex, dsh_pid=12345
    )
    _atomic(plugins.root / "guard-state.json", {"pid": body.dsh_pid, "freeze_supported": True})

    def request(action="freeze", selected=body, actor=user):
        raw = json.dumps(selected.model_dump()).encode()
        path = "/api/research/internal/plugin-runtime/" + action
        headers = sign(key, "POST", path, raw, actor, "manager")
        value = Request(
            {
                "type": "http",
                "method": "POST",
                "path": path,
                "headers": [
                    (name.lower().encode(), item.encode()) for name, item in headers.items()
                ],
                "query_string": b"",
                "server": ("127.0.0.1", 8088),
                "scheme": "http",
                "app": SimpleNamespace(state=SimpleNamespace(research=service)),
            }
        )
        value._body = raw
        return value

    service.plugin_inflight = 1
    assert (await freeze(body, request()))["status"] == "deferred"
    service.plugin_inflight = 0
    service.mcp_runtime.runtime.operations.add("SDK fixture")
    assert (await freeze(body, request()))["status"] == "deferred"
    service.mcp_runtime.runtime.operations.clear()
    service.plugins.hook_cancellations["fixture"] = asyncio.Event()
    assert (await freeze(body, request()))["status"] == "deferred"
    service.plugins.hook_cancellations.clear()
    task = asyncio.create_task(asyncio.Event().wait())
    service.datahub.tasks["fixture"] = task
    try:
        assert (await freeze(body, request()))["status"] == "deferred"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        service.datahub.tasks.clear()
    assert not service.plugin_runtime_frozen and not (plugins.root / "runtime-freeze.json").exists()
    stale = body.model_copy(update={"generation": uuid4().hex})
    with pytest.raises(PluginError, match="generation_changed"):
        await freeze(stale, request(selected=stale))
    with pytest.raises(PluginError, match="generation_changed"):
        await freeze(body, request(actor=str(uuid4())))
    signed = request()
    assert (await freeze(body, signed))["status"] == "ready"
    with pytest.raises(PluginError, match="proof_denied"):
        await freeze(body, signed)
    assert service.plugin_runtime_frozen
    assert (await unfreeze(body, request("unfreeze")))["status"] == "ready"
    assert not service.plugin_runtime_frozen and not (plugins.root / "runtime-freeze.json").exists()


def write_auth(entry):
    _atomic(
        entry.state / "auth.json",
        {
            "authority": "127.0.0.1:19998",
            "pid": entry.children[0].pid,
            "source_commit": PINNED_DSH_COMMIT,
            "cwd": str(entry.state.parent / "research-web/runtime/work"),
            "version": "fixture",
            "cookie": "dsh-auth-fixture",
        },
    )
    _atomic(
        entry.state.parent / "research-web/plugins/guard-state.json",
        {"pid": entry.children[0].pid, "freeze_supported": True},
    )


async def fixture_pool(tmp_path, monkeypatch):
    config = runtime.RuntimeConfig(
        tmp_path / "server", tmp_path, tmp_path, str(sys.executable), "/usr/local/bin/node"
    )
    pool = runtime.RuntimePool(config)
    user = str(uuid4())
    parent = config.root / "users" / user
    for path in (
        parent,
        parent / "state",
        parent / "research-web",
        parent / "research-web/runtime",
        parent / "research-web/runtime/work",
        parent / "research-web/plugins",
    ):
        runtime._directory(path)
    children = [spawn_fixture(tmp_path), spawn_fixture(tmp_path)]
    entry = runtime._Instance(
        user, parent / "state", runtime.Backend("http://127.0.0.1:19999", "K" * 43), children
    )
    entry.backend = runtime.Backend(
        entry.backend.url, entry.backend.key, entry.generation, children[0].pid
    )
    pool._instances[user] = entry
    pool._record(entry, create=True)
    runtime._create_private(entry.state / "gateway.key", entry.backend.key.encode())
    write_auth(entry)

    async def ready(current, _port, _root, _deadline):
        assert current.children[0].poll() is None
        write_auth(current)

    monkeypatch.setattr(pool, "_spawn", lambda _command, _environment: spawn_fixture(tmp_path))
    monkeypatch.setattr(pool, "_wait_runtime", ready)
    return pool, user, entry


@pytest.mark.asyncio
@pytest.mark.parametrize("can_recover", [True, False])
async def test_lost_freeze_acknowledgement_never_claims_unverified_rollback(
    tmp_path, monkeypatch, can_recover
):
    pool, user, entry = await fixture_pool(tmp_path, monkeypatch)
    actions, identities = [], []
    backend_frozen = [False]

    async def control(_entry, action, body):
        actions.append(action)
        identities.append(body["freeze_id"])
        if action == "freeze":
            backend_frozen[0] = True
            raise TimeoutError("fixture acknowledgement lost after freeze")
        if not can_recover:
            raise TimeoutError("fixture recovery unavailable")
        if action == "unfreeze":
            backend_frozen[0] = False
        return {"status": "rolled_back" if action == "rollback" else "ready"}

    monkeypatch.setattr(pool, "_plugin_control", control)
    try:
        pids = [child.pid for child in entry.children]
        result = await pool.restart_runtime(user, entry.backend, "d" * 32)
        assert [child.pid for child in entry.children] == pids
        assert all(child.poll() is None for child in entry.children)
        assert len(set(identities)) == 1
        if can_recover:
            assert (
                result["status"] == "deferred" and not backend_frozen[0] and not pool._plugin_frozen
            )
            assert actions == ["freeze", "rollback", "unfreeze"]
        else:
            assert (
                result["status"] == "unknown" and backend_frozen[0] and user in pool._plugin_frozen
            )
            assert (
                json.loads((entry.state / "plugin-restart.json").read_bytes())["state"] == "unknown"
            )
    finally:
        pool._plugin_frozen.clear()  # These are only the test's own fixture processes.
        await pool.close()


@pytest.mark.asyncio
async def test_pool_defers_inflight_and_freezes_new_births_before_replacing_only_owned_dsh(
    tmp_path, monkeypatch
):
    pool, user, entry = await fixture_pool(tmp_path, monkeypatch)
    original, web = entry.children
    expected = entry.backend
    entered, release = asyncio.Event(), asyncio.Event()
    actions = []

    async def control(current, action, body):
        actions.append(action)
        assert body["generation"] == current.generation
        if action == "freeze":
            entered.set()
            await release.wait()
            return {"status": "ready", "freeze_id": body["freeze_id"], "dsh_pid": original.pid}
        if action == "commit":
            assert body["new_dsh_pid"] == entry.children[0].pid
        return {"status": "ready"}

    monkeypatch.setattr(pool, "_plugin_control", control)
    try:
        ticket = await pool.request_started(user, expected)
        assert (await pool.restart_runtime(user, expected, "a" * 32))["status"] == "deferred"
        assert original.poll() is None and actions == []
        await pool.request_finished(user, ticket)
        restarting = asyncio.create_task(pool.restart_runtime(user, expected, "a" * 32))
        await entered.wait()
        with pytest.raises(runtime.RuntimeErrorSafe):
            await pool.request_started(user, expected)
        with pytest.raises(runtime.RuntimeErrorSafe):
            await pool.backend_for(user)
        assert original.poll() is None
        release.set()
        result = await restarting
        assert result["status"] == "ready"
        assert original.poll() is not None
        assert web.poll() is None and entry.children[1] is web
        assert entry.children[0].pid != original.pid
        assert await pool.restart_runtime(user, expected, "a" * 32) == result
        assert actions == ["freeze", "commit", "unfreeze"]
        assert not pool._plugin_frozen
    finally:
        release.set()
        pool._plugin_frozen.clear()
        await pool.close()


@pytest.mark.asyncio
async def test_backend_activity_deferred_and_generation_drift_never_signals(tmp_path, monkeypatch):
    pool, user, entry = await fixture_pool(tmp_path, monkeypatch)
    calls = []

    async def control(_entry, action, _body):
        calls.append(action)
        return {"status": "deferred", "reason": "SDK operation active"}

    monkeypatch.setattr(pool, "_plugin_control", control)
    try:
        wrong = runtime.Backend(
            entry.backend.url, entry.backend.key, "0" * 32, entry.children[0].pid
        )
        assert (await pool.restart_runtime(user, wrong))["status"] == "unknown"
        assert calls == []
        assert (await pool.restart_runtime(user, entry.backend))["status"] == "deferred"
        assert all(child.poll() is None for child in entry.children)
        assert calls == ["freeze"] and not pool._plugin_frozen
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_failed_new_runtime_restores_previous_binding_config_before_unfreezing(
    tmp_path, monkeypatch
):
    pool, user, entry = await fixture_pool(tmp_path, monkeypatch)
    attempts, actions = [], []

    async def wait(current, _port, _root, _deadline):
        attempts.append(current.children[0].pid)
        write_auth(current)
        if len(attempts) == 1:
            raise runtime.RuntimeErrorSafe("fixture_start_failed")

    async def control(_entry, action, body):
        actions.append(action)
        if action == "freeze":
            return {"status": "ready", "freeze_id": body["freeze_id"], "dsh_pid": body["dsh_pid"]}
        return {"status": "rolled_back" if action == "rollback" else "ready"}

    monkeypatch.setattr(pool, "_plugin_control", control)
    monkeypatch.setattr(pool, "_wait_runtime", wait)
    try:
        web_pid = entry.children[1].pid
        result = await pool.restart_runtime(user, entry.backend, "f" * 32)
        assert result == {"status": "deferred", "reason": "restart_rolled_back"}
        assert len(attempts) == 2 and attempts[0] != attempts[1]
        assert actions == ["freeze", "rollback", "unfreeze"]
        assert entry.children[1].pid == web_pid and entry.children[1].poll() is None
        assert (
            json.loads((entry.state / "plugin-restart.json").read_bytes())["state"] == "rolled_back"
        )
        assert not pool._plugin_frozen
    finally:
        pool._plugin_frozen.clear()
        await pool.close()
