"""Private server Runtime lifecycle and execution policy contracts."""

import asyncio
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.research_web import tenant_policy
from app.research_web.multiuser import runtime
from app.research_web.store import StoreError


def saved_control(root, port, *, name="datahub.json", **overrides):
    folder = root / ".control"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    value = {"url": f"http://127.0.0.1:{port}", "token": "T" * 43, **overrides}
    if name == "mcp-runtime.json":
        value["version"] = 1
    path = folder / name
    runtime._create_private(path, json.dumps(value).encode())
    return path


def test_resume_reuses_trusted_port_and_never_rewrites_control(tmp_path):
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    path = saved_control(tmp_path, port)
    before = path.read_bytes()
    reserved = runtime._reserve_web_port(tmp_path)
    try:
        assert reserved.getsockname()[1] == port
        with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_port_unavailable"):
            runtime._reserve_web_port(tmp_path)
        assert path.read_bytes() == before
    finally:
        reserved.close()


def test_resume_rebinds_closed_http_connections_without_waiting_for_time_wait(tmp_path):
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    control = saved_control(tmp_path, port)
    before = control.read_bytes()
    with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
        peer, _ = listener.accept()
        peer.close()
        assert client.recv(1) == b""
    listener.close()
    reserved = runtime._reserve_web_port(tmp_path)
    try:
        assert reserved.getsockname()[1] == port
        assert control.read_bytes() == before
    finally:
        reserved.close()


def test_resume_never_reuses_an_existing_reusable_listener(tmp_path):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        saved_control(tmp_path, listener.getsockname()[1])
        with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_port_unavailable"):
            runtime._reserve_web_port(tmp_path)


@pytest.mark.parametrize(
    "case", ["foreign", "token", "permissions", "link", "directory_link", "pending", "mismatch"]
)
def test_resume_rejects_unverified_control_without_modifying_it(tmp_path, case):
    path = saved_control(tmp_path, 23888)
    if case == "foreign":
        path.write_text(json.dumps({"url": "http://192.0.2.1:23888", "token": "T" * 43}))
    elif case == "token":
        path.write_text(json.dumps({"url": "http://127.0.0.1:23888", "token": "bad"}))
    elif case == "permissions":
        path.chmod(0o644)
    elif case == "link":
        target = tmp_path / "outside"
        path.rename(target)
        path.symlink_to(target)
    elif case == "directory_link":
        target = tmp_path / "outside"
        path.parent.rename(target)
        path.parent.symlink_to(target)
    elif case == "pending":
        (path.parent / "origin-transaction.json").write_text("{}")
    elif case == "mismatch":
        saved_control(tmp_path, 23889, name="mcp-runtime.json")
    before = path.read_bytes()
    with pytest.raises(runtime.RuntimeErrorSafe):
        runtime._reserve_web_port(tmp_path)
    assert path.read_bytes() == before


def config(tmp_path):
    return runtime.RuntimeConfig(
        tmp_path / "server", tmp_path, tmp_path, "/venv/bin/python", "/node/bin/node"
    )


@pytest.mark.asyncio
async def test_explicit_four_pair_capacity_retains_existing_users_at_limit(
    tmp_path, fake_processes
):
    from dataclasses import replace

    pool = runtime.RuntimePool(replace(config(tmp_path), max_instances=4))
    users = [str(uuid4()) for _ in range(4)]
    try:
        backends = await asyncio.gather(*(pool.backend_for(user) for user in users))
        assert len({backend.url for backend in backends}) == 4
        with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_capacity_exceeded"):
            await pool.backend_for(str(uuid4()))
        assert await pool.backend_for(users[0]) == backends[0]
        await pool.stop(users[-1])
        assert await pool.backend_for(str(uuid4()))
    finally:
        await pool.close()


class Child:
    serial = 10000

    def __init__(self, command, **kwargs):
        type(self).serial += 1
        self.pid = self.serial
        self.command, self.kwargs, self.code = command, kwargs, None

    def poll(self):
        return self.code


@pytest.fixture
def fake_processes(monkeypatch):
    children = []

    def spawn(*args, **kwargs):
        child = Child(*args, **kwargs)
        children.append(child)
        return child

    async def ready(*args):
        return None

    async def stop(child):
        child.code = 0

    monkeypatch.setattr(runtime.subprocess, "Popen", spawn)
    monkeypatch.setattr(runtime.RuntimePool, "_wait_runtime", ready)
    monkeypatch.setattr(runtime.RuntimePool, "_wait_backend", ready)
    monkeypatch.setattr(runtime.RuntimePool, "_stop_child", staticmethod(stop))
    return children


@pytest.mark.asyncio
async def test_resume_across_pool_recreation_preserves_callback_and_rotates_gateway_key(
    tmp_path, fake_processes
):
    settings = config(tmp_path)
    user = str(uuid4())
    first_pool = runtime.RuntimePool(settings)
    first = await first_pool.backend_for(user)
    data = settings.root / "users" / user / "research-web"
    control = saved_control(data, urlsplit(first.url).port)
    before = control.read_bytes()
    await first_pool.close()
    second_pool = runtime.RuntimePool(settings)
    try:
        second = await second_pool.backend_for(user)
        assert second.url == first.url
        assert second.key != first.key
        assert control.read_bytes() == before
    finally:
        await second_pool.close()


@pytest.mark.asyncio
async def test_two_users_isolate_processes_secrets_paths_capacity(
    tmp_path, fake_processes, monkeypatch
):
    monkeypatch.setenv("RESEARCH_WEB_PRIVATE_ORIGIN", "https://personal.tail123.ts.net")
    monkeypatch.setenv("OPENAI_API_KEY", "never-inherit")
    pool = runtime.RuntimePool(config(tmp_path))
    first, second = str(uuid4()), str(uuid4())
    try:
        a, b = await pool.backend_for(first), await pool.backend_for(second)
        assert a.url != b.url and a.key != b.key
        assert await pool.backend_for(first) == a
        with pytest.raises(runtime.RuntimeErrorSafe) as full:
            await pool.backend_for(str(uuid4()))
        assert full.value.code == "runtime_capacity_exceeded" and full.value.status == 503
        assert len(fake_processes) == 4
        for child in fake_processes:
            env = child.kwargs["env"]
            assert "OPENAI_API_KEY" not in env and "RESEARCH_WEB_PRIVATE_ORIGIN" not in env
            assert env["RWB_TENANT_MODE"] == "1"
            assert env["RESEARCH_AUTOMATIONS_ENABLED"] == "0"
            assert env["RESEARCH_MCP_RUNTIME_ENABLED"] == "0"
            assert env["RESEARCH_RUN_MODE"] == "web-prod"
            assert env["HOME"].startswith(str(tmp_path / "server/users"))
            assert child.kwargs["stdout"] == runtime.subprocess.DEVNULL
            assert child.kwargs["stderr"] == runtime.subprocess.DEVNULL
            assert child.kwargs["start_new_session"] is True
        assert all(
            "never-inherit" not in item.read_text() for item in (tmp_path / "server/logs").iterdir()
        )
        await pool.stop(first)
        assert all(child.code == 0 for child in fake_processes[:2])
        assert all(child.code is None for child in fake_processes[2:])
    finally:
        await pool.close()
    assert all(child.code == 0 for child in fake_processes)


@pytest.mark.asyncio
async def test_invalid_uuid_unsafe_dirs_stale_and_duplicate_fail_closed(tmp_path, fake_processes):
    cfg = config(tmp_path)
    pool = runtime.RuntimePool(cfg)
    try:
        with pytest.raises(runtime.RuntimeErrorSafe, match="user_id_invalid"):
            await pool.backend_for("../../other")
        with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_pool_locked"):
            runtime.RuntimePool(cfg)
        uid = str(uuid4())
        (cfg.root / "users" / uid).symlink_to(tmp_path, target_is_directory=True)
        with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_path_unsafe"):
            await pool.backend_for(uid)
        uid = str(uuid4())
        state = cfg.root / "users" / uid / "state"
        state.parent.mkdir(mode=0o700)
        state.mkdir(mode=0o700)
        (state / "owner.json").write_text("{}")
        with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_stale_owner"):
            await pool.backend_for(uid)
        assert not fake_processes
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_start_failure_cleans_only_created_children_and_can_retry(
    tmp_path, fake_processes, monkeypatch
):
    pool = runtime.RuntimePool(config(tmp_path))
    uid = str(uuid4())

    async def fail(*args):
        raise runtime.RuntimeErrorSafe("runtime_start_failed", 503)

    monkeypatch.setattr(pool, "_wait_backend", fail)
    try:
        with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_start_failed"):
            await pool.backend_for(uid)
        assert len(fake_processes) == 2 and all(child.code == 0 for child in fake_processes)
        assert not (pool.config.root / "users" / uid / "state/owner.json").exists()
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_health_probe_requires_authenticated_owned_connected_runtime():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            valid = self.headers.get(tenant_policy.GATEWAY_HEADER) == "health-secret"
            self.send_response(200 if valid else 403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"health_check_passed": True, "owned_runtime": True, "connected": True}
                ).encode()
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        assert await runtime._probe_backend(runtime.Backend(url, "health-secret"))
        assert not await runtime._probe_backend(runtime.Backend(url, "wrong"))
    finally:
        server.shutdown()
        thread.join(2)
        server.server_close()


def request(path, method="GET", headers=(), body=b""):
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": list(headers),
            "query_string": b"",
            "app": SimpleNamespace(
                state=SimpleNamespace(
                    research=SimpleNamespace(
                        datahub=SimpleNamespace(authenticate=lambda token: token == "data-secret")
                    )
                )
            ),
        },
        receive,
    )


@pytest.mark.asyncio
async def test_tenant_requires_gateway_key_and_rejects_native_and_ssrf(tmp_path, monkeypatch):
    monkeypatch.setenv("RWB_TENANT_MODE", "1")
    token = tmp_path / "gateway.key"
    token.write_text("g" * 43)
    token.chmod(0o600)
    monkeypatch.setenv("RWB_TENANT_GATEWAY_KEY_FILE", str(token))
    headers = [(tenant_policy.GATEWAY_HEADER.lower().encode(), b"g" * 43)]
    assert (await tenant_policy.check_request(request("/api/research/sessions"))).status_code == 403
    assert (
        await tenant_policy.check_request(request("/api/research/sessions", headers=headers))
        is None
    )
    assert (
        await tenant_policy.check_request(
            request("/api/research/internal/data/skill-preflight", headers=headers)
        )
    ).status_code == 403
    data = [(b"x-research-data-key", b"data-secret")]
    assert (
        await tenant_policy.check_request(
            request(
                "/api/research/internal/data/skill-preflight",
                "POST",
                data,
                b'{"tool_name":"agent_step"}',
            )
        )
        is None
    )
    assert (
        await tenant_policy.check_request(
            request(
                "/api/research/internal/data/skill-preflight",
                "POST",
                data,
                b'{"native_name":"unreviewed"}',
            )
        )
    ).status_code == 403
    assert (
        await tenant_policy.check_request(
            request("/api/research/internal/data/automation-action", headers=data)
        )
    ).status_code == 403
    for path in [
        "/api/research/runtime/tabbit",
        "/api/research/local-integrations",
        "/api/research/mcp",
        "/api/research/hot",
        "/api/research/report-projects",
        "/api/research/automation-runs",
        "/api/research/automation-runs/fixture/retry",
        "/api/research/data/sources/wind/configuration",
    ]:
        assert (
            await tenant_policy.check_request(request(path, headers=headers))
        ).status_code == 403
    bad = json.dumps({"provider": "openai-compatible", "base_url": "http://127.0.0.1"}).encode()
    assert (
        await tenant_policy.check_request(
            request("/api/research/runtime/model", "PUT", headers, bad)
        )
    ).status_code == 403
    good = json.dumps(
        {"provider": "deepseek-official", "model": "deepseek-flash", "api_key": "not-logged"}
    ).encode()
    assert (
        await tenant_policy.check_request(
            request("/api/research/runtime/model", "PUT", headers, good)
        )
        is None
    )
    with pytest.raises(StoreError) as denied:
        tenant_policy.enforce_document_mode("native")
    assert denied.value.status == 403
    tenant_policy.enforce_document_mode("file")


@pytest.mark.asyncio
async def test_cancelled_start_retires_created_children(tmp_path, fake_processes, monkeypatch):
    pool = runtime.RuntimePool(config(tmp_path))
    reached = asyncio.Event()

    async def wait_forever(*_args):
        reached.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(pool, "_wait_backend", wait_forever)
    task = asyncio.create_task(pool.backend_for(str(uuid4())))
    await reached.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(fake_processes) == 2 and all(child.code == 0 for child in fake_processes)
    assert not pool._instances
    await pool.close()


@pytest.mark.asyncio
async def test_reaped_leader_with_live_group_retains_ownership(tmp_path, monkeypatch):
    child = Child(("fixture",))
    child.code = 0
    monkeypatch.setattr(os, "killpg", lambda *_: None)
    with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_stop_unverified"):
        await runtime.RuntimePool._stop_child(child)


@pytest.mark.asyncio
async def test_failed_stop_preserves_owner_and_lock_for_retry(
    tmp_path, fake_processes, monkeypatch
):
    pool = runtime.RuntimePool(config(tmp_path))
    uid = str(uuid4())
    await pool.backend_for(uid)
    original = pool._stop_child

    async def uncertain(_child):
        raise runtime.RuntimeErrorSafe("runtime_stop_unverified")

    monkeypatch.setattr(pool, "_stop_child", uncertain)
    with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_shutdown_incomplete"):
        await pool.close()
    state = pool.config.root / "users" / uid / "state"
    assert (state / "owner.json").exists() and (state / "gateway.key").exists()
    with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_pool_locked"):
        runtime.RuntimePool(pool.config)
    monkeypatch.setattr(pool, "_stop_child", original)
    await pool.close()


def test_tenant_launcher_forces_private_home_and_disables_host_plugins(tmp_path, monkeypatch):
    from app.research_web import launch_runtime

    source = tmp_path / "source"
    (source / "apps/cli/lib").mkdir(parents=True)
    (source / "apps/cli/lib/bin.js").write_text("// fixture")
    data = tmp_path / "data"
    monkeypatch.setenv("RWB_TENANT_MODE", "1")
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "1")
    monkeypatch.setattr(
        launch_runtime.subprocess, "check_output", lambda *_a, **_k: launch_runtime.PINNED_COMMIT
    )
    _, env, _ = launch_runtime.prepare(source, data, "/node", 13081)
    overlay = (data / "runtime/overlay.yml").read_text()
    assert env["HOME"] == str(data / "runtime/home")
    assert "tenantMode: true" in overlay and "tabbitBrowserEnabled: false" in overlay
    assert "tabbitWebFetchEnabled: false" in overlay
    assert launch_runtime.load_mcp_runtime_bindings(data) == []


@pytest.mark.asyncio
async def test_owned_bootstrap_auth_exchange_replaces_token_without_logging(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(303 if self.path == "/?token=" + "t" * 43 else 403)
            self.send_header("Set-Cookie", "dsh-auth-fixture=secret; HttpOnly")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    pool = runtime.RuntimePool(config(tmp_path))
    try:
        state = pool.config.root / "state"
        state.mkdir(mode=0o700)
        root = pool.config.root / "data"
        child = Child(("fixture",))
        port = server.server_address[1]
        record = {
            "authority": f"127.0.0.1:{port}",
            "cwd": str(root / "runtime/work"),
            "source_commit": runtime.PINNED_DSH_COMMIT,
            "pid": child.pid,
            "version": "fixture",
            "bootstrap_token": "t" * 43,
        }
        runtime._create_private(state / "auth.json", json.dumps(record).encode())
        entry = runtime._Instance(
            str(uuid4()), state, runtime.Backend("http://unused", "g" * 43), [child]
        )
        await pool._wait_runtime(entry, port, root, runtime.time.monotonic() + 3)
        final = json.loads((state / "auth.json").read_text())
        assert final["cookie"] == "dsh-auth-fixture=secret" and "bootstrap_token" not in final
        assert (state / "auth.json").stat().st_mode & 0o777 == 0o600
    finally:
        await pool.close()
        server.shutdown()
        thread.join(2)
        server.server_close()


@pytest.mark.asyncio
async def test_native_document_execution_denied_before_store_lookup(monkeypatch):
    from app.research_web.report_rendering import execute_document_operation

    monkeypatch.setenv("RWB_TENANT_MODE", "1")
    with pytest.raises(StoreError) as denied:
        await execute_document_operation(
            None, "unowned", {"format": "docx", "operation": "generate", "mode": "native"}
        )
    assert denied.value.status == 403


@pytest.mark.asyncio
async def test_leader_exit_during_stop_does_not_hide_live_descendants(monkeypatch):
    child = Child(("fixture",))
    states = iter([None, 0])
    child.poll = lambda: next(states)

    def vanished(_pid):
        raise ProcessLookupError

    monkeypatch.setattr(os, "getpgid", vanished)
    monkeypatch.setattr(os, "killpg", lambda *_: None)
    with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_stop_unverified"):
        await runtime.RuntimePool._stop_child(child)


@pytest.mark.asyncio
async def test_deployment_slot_wins_after_native_exists_check_without_spawn_or_dispose(
    tmp_path, fake_processes, monkeypatch
):
    pool = runtime.RuntimePool(config(tmp_path))
    uid = str(uuid4())
    original = pool._record
    owner = pool.config.root / "users" / uid / "state/owner.json"

    def publish_before_record(entry, *, create=False):
        if create:
            owner.mkdir(mode=0o700)
            (owner / "reservation").write_text("operator-owned test slot")
        return original(entry, create=create)

    async def forbidden_dispose(*_):
        pytest.fail("native must not dispose an operator-owned slot")

    monkeypatch.setattr(pool, "_record", publish_before_record)
    monkeypatch.setattr(pool, "_dispose", forbidden_dispose)
    try:
        with pytest.raises(runtime.RuntimeErrorSafe, match="runtime_start_failed"):
            await pool.backend_for(uid)
        assert fake_processes == [] and not pool._instances
        assert (owner / "reservation").read_text() == "operator-owned test slot"
        assert not (owner.parent / "gateway.key").exists()
    finally:
        await pool.close()
