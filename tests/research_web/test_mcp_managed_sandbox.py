"""Real official SDK canaries use exclusively test-owned files and memory credentials."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

from app.research_web.mcp_runtime.credentials import RuntimeCredentialStore
from app.research_web.mcp_runtime.sdk_host import SDKHost

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="native macOS Seatbelt acceptance")


class MemoryCredentials:
    def get_password(self, *_args):
        raise AssertionError("offline fixture must not read credentials")

    def set_password(self, *_args):
        raise AssertionError("offline fixture must not write credentials")

    def delete_password(self, *_args):
        raise AssertionError("offline fixture must not delete credentials")


@pytest.fixture
def offline_host(monkeypatch):
    import keyring

    def forbidden(*_args, **_kwargs):
        raise AssertionError("real keyring access forbidden")

    for method in ("get_password", "set_password", "delete_password"):
        monkeypatch.setattr(keyring, method, forbidden)
    return SDKHost(credentials=RuntimeCredentialStore(MemoryCredentials()))


SERVER = """import json,sys,os,socket,subprocess
from pathlib import Path
def denied(fn):
 try:
  fn()
  return False
 except (OSError, PermissionError): return True
def check(args):
 if args.get("echo"): return {"content":[{"type":"text","text":"pong"}]}
 if args.get("giant"):
  sys.stdout.write("x"*(2*1024*1024));sys.stdout.flush()
  import time
  time.sleep(60)
 if args.get("oversized"): return {"content":[{"type":"text","text":"x"*(2*1024*1024)}]}
 if args.get("chatty"):
  for i in range(400):
   print(json.dumps({"jsonrpc":"2.0","method":"notifications/message","params":{"level":"info","data":"x"*32768}}),flush=True)
  return {"content":[{"type":"text","text":"too much"}]}
 if args.get("hang"):
  import time
  time.sleep(60)
 sibling=Path(args["sibling"])
 package=Path(__file__).parent
 result={"read":denied(lambda:sibling.read_bytes()),
 "write":denied(lambda:sibling.write_text("changed")),
 "package":denied(lambda:(package/"mutated").write_text("changed")),
 "fork":denied(lambda:os.fork()),
 "spawn":denied(lambda:subprocess.run(["/bin/echo","changed"])),
 "posix_spawn":denied(lambda:os.posix_spawn("/bin/echo",["echo","changed"],{})),
 "exec":denied(lambda:os.execv("/bin/echo",["echo","changed"])),
 "ipv4":denied(lambda:socket.socket().connect(("127.0.0.1",args["port"]))),
 "ipv6":denied(lambda:socket.socket(socket.AF_INET6).connect(("::1",args["port6"]))),
 "unix":denied(lambda:socket.socket(socket.AF_UNIX).connect(args["unix"])),
 "symlink":denied(lambda:(package/"alias").read_bytes()),
 "data_alias":denied(lambda:Path("/System/Volumes/Data"+str(sibling)).read_bytes())}
 scratch=Path(os.environ["HOME"])
 result["hardlink"]=denied(lambda:os.link(sibling,scratch/"escape"))
 result["fd"]=denied(lambda:os.read(args["fd"],64))
 (scratch/"ok").write_text("scratch")
 result["scratch"]=(scratch/"ok").read_text()=="scratch"
 result["env"]=not any(k in os.environ for k in ("AWS_SECRET_ACCESS_KEY","PYTHONPATH","RWB_SECRET"))
 result["site"]=not any("site-packages" in path for path in sys.path)
 result["scratch_path"]=str(scratch)
 result["pid"]=os.getpid()
 return {"content":[{"type":"text","text":json.dumps(result)}]}
for line in sys.stdin:
 request=json.loads(line)
 if "id" not in request: continue
 method=request["method"]
 if method=="initialize": result={"protocolVersion":request["params"]["protocolVersion"],"capabilities":{"tools":{},"resources":{},"prompts":{}},"serverInfo":{"name":"offline-canary","version":"1"}}
 elif method=="tools/list": result={"tools":[{"name":"canary","inputSchema":{"type":"object"}}]}
 elif method=="resources/list": result={"resources":[]}
 elif method=="prompts/list": result={"prompts":[]}
 elif method=="tools/call": result=check(request["params"]["arguments"])
 else: result={}
 print(json.dumps({"jsonrpc":"2.0","id":request["id"],"result":result}),flush=True)
"""


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS Seatbelt acceptance")
@pytest.mark.asyncio
async def test_real_sdk_offline_canaries_and_package_revalidation(
    tmp_path, offline_host, monkeypatch
):
    from app.research_web.mcp_runtime.managed_sandbox import build_managed_target
    from app.research_web.mcp_runtime.sdk_host import MCPHostError

    package = tmp_path / "package"
    package.mkdir()
    script = package / "server.py"
    script.write_text(SERVER)
    sibling = tmp_path / "host-credentials-and-db"
    sibling.write_text("owned-canary-secret")
    # Internal alias is later redirected to the sibling; revalidation must reject it.
    (package / "alias").symlink_to(script)
    monkeypatch.setenv("RWB_SECRET", "owned-env-canary")
    target = build_managed_target(package, ["python", "server.py"], "mcpb")
    assert (await offline_host.capabilities(target))["tools"][0]["name"] == "canary"
    import socket

    with (
        tempfile.TemporaryDirectory(dir="/private/tmp") as short,
        socket.socket() as listener,
        socket.socket(socket.AF_INET6) as listener6,
        socket.socket(socket.AF_UNIX) as unix_listener,
        sibling.open("rb") as inherited,
    ):
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener6.bind(("::1", 0))
        listener6.listen()
        unix_path = str(Path(short) / "socket")
        unix_listener.bind(unix_path)
        unix_listener.listen()
        os.set_inheritable(inherited.fileno(), True)
        args = {
            "sibling": str(sibling),
            "port": listener.getsockname()[1],
            "port6": listener6.getsockname()[1],
            "unix": unix_path,
            "fd": inherited.fileno(),
        }
        # Alias inside package is readable; all escapes remain denied.
        result = await offline_host.call_tool(target, "canary", args)
        checks = json.loads(result["content"][0]["text"])
        assert not Path(checks.pop("scratch_path")).exists()
        with pytest.raises(ProcessLookupError):
            os.kill(checks.pop("pid"), 0)
        assert checks.pop("symlink") is False
        assert all(checks.values()), checks
    assert sibling.read_text() == "owned-canary-secret"
    assert not (package / "mutated").exists()
    script.write_text(SERVER + "\n# changed")
    with pytest.raises(MCPHostError, match="mcp_target_invalid"):
        await offline_host.capabilities(target)


def test_hardlink_and_external_symlink_packages_rejected(tmp_path):
    from app.research_web.mcp_runtime.managed_sandbox import build_managed_target

    package = tmp_path / "package"
    package.mkdir()
    outside = tmp_path / "owned-sentinel"
    outside.write_text("fixture")
    script = package / "server.py"
    os.link(outside, script)
    with pytest.raises(ValueError):
        build_managed_target(package, ["python", "server.py"], "mcpb")
    script.unlink()
    script.symlink_to(outside)
    with pytest.raises(ValueError):
        build_managed_target(package, ["python", "server.py"], "mcpb")


@pytest.mark.asyncio
async def test_policy_runtime_and_platform_drift_fail_before_client(
    tmp_path, offline_host, monkeypatch
):
    from app.research_web.mcp_runtime import managed_sandbox as sandbox
    from app.research_web.mcp_runtime.sdk_host import MCPHostError

    package = tmp_path / "package"
    package.mkdir()
    (package / "server.py").write_text(SERVER)
    target = sandbox.build_managed_target(package, ["python", "server.py"], "mcpb")
    with monkeypatch.context() as patch:
        patch.setattr(sandbox, "policy_digest", lambda: "0" * 64)
        with pytest.raises(MCPHostError, match="mcp_target_invalid"):
            await offline_host.capabilities(target)
    runtime, _ = sandbox._runtime_identity()
    with monkeypatch.context() as patch:
        patch.setattr(sandbox, "_runtime_identity", lambda: (runtime, "0" * 64))
        with pytest.raises(MCPHostError, match="mcp_target_invalid"):
            await offline_host.capabilities(target)
    with monkeypatch.context() as patch:
        patch.setattr(sandbox, "available", lambda: False)
        with pytest.raises(MCPHostError, match="mcp_target_invalid"):
            await offline_host.capabilities(target)


@pytest.mark.parametrize(
    "kind,argv,names",
    [
        ("npm", ["node", "server.js"], []),
        ("mcpb", ["/bin/sh", "server.py"], []),
        ("mcpb", ["env", "python", "server.py"], []),
        ("mcpb", ["python", "-c", "pass"], []),
        ("pypi", ["python", "-m", "server"], ["API_KEY"]),
    ],
)
def test_unsupported_runtime_and_secret_environment_rejected(kind, argv, names):
    from app.research_web.mcp_runtime.managed_sandbox import validate_plan

    with pytest.raises(ValueError):
        validate_plan({"package_type": kind, "argv": argv, "environment_names": names})


@pytest.mark.asyncio
async def test_cancelled_sdk_call_retires_owned_scratch(tmp_path, offline_host):
    import anyio

    from app.research_web.mcp_runtime.managed_sandbox import build_managed_target

    package = tmp_path / "package"
    package.mkdir()
    (package / "server.py").write_text(SERVER)
    target = build_managed_target(package, ["python", "server.py"], "mcpb")
    before = set(Path("/private/tmp").glob("rwb-mcp-offline-*"))
    # Structured cancellation lets the real SDK finish its bounded process-tree
    # shutdown; the fixture has no way to fork or write outside owned scratch.
    with anyio.move_on_after(1.0) as cancellation:
        await offline_host.call_tool(target, "canary", {"hang": True})
    assert cancellation.cancelled_caught
    assert set(Path("/private/tmp").glob("rwb-mcp-offline-*")) == before


@pytest.mark.asyncio
async def test_pypi_package_dependencies_load_without_host_site_startup(tmp_path, offline_host):
    from app.research_web.mcp_runtime.managed_sandbox import build_managed_target

    package = tmp_path / "package"
    module = package / "fixture"
    module.mkdir(parents=True)
    (module / "__init__.py").write_text("")
    (package / "fixture_dependency.py").write_text("VALUE = 'local-dependency'\n")
    (module / "__main__.py").write_text(
        "import fixture_dependency\nassert fixture_dependency.VALUE=='local-dependency'\n" + SERVER
    )
    target = build_managed_target(package, ["python", "-m", "fixture"], "pypi")
    assert (await offline_host.capabilities(target))["tools"][0]["name"] == "canary"
    assert (await offline_host.call_tool(target, "canary", {"echo": True}))["content"][0][
        "text"
    ] == "pong"


@pytest.mark.asyncio
async def test_official_sdk_timeout_retires_owned_scratch(tmp_path, offline_host):
    from app.research_web.mcp_runtime.managed_sandbox import build_managed_target
    from app.research_web.mcp_runtime.sdk_host import MCPHostError

    package = tmp_path / "package"
    package.mkdir()
    (package / "server.py").write_text(SERVER)
    target = build_managed_target(package, ["python", "server.py"], "mcpb")
    before = set(Path("/private/tmp").glob("rwb-mcp-offline-*"))

    def short_real_client(target, **options):
        options["read_timeout_seconds"] = 0.25
        return SDKHost._official_client(target, **options)

    offline_host.client_factory = short_real_client
    with pytest.raises(MCPHostError, match="mcp_operation_failed"):
        await offline_host.call_tool(target, "canary", {"hang": True})
    assert set(Path("/private/tmp").glob("rwb-mcp-offline-*")) == before


@pytest.mark.asyncio
async def test_asyncio_cancel_retires_owned_scratch(tmp_path, offline_host):
    import asyncio

    from app.research_web.mcp_runtime.managed_sandbox import build_managed_target

    package = tmp_path / "package"
    package.mkdir()
    (package / "server.py").write_text(SERVER)
    target = build_managed_target(package, ["python", "server.py"], "mcpb")
    before = set(Path("/private/tmp").glob("rwb-mcp-offline-*"))
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(offline_host.call_tool(target, "canary", {"hang": True}), 1.0)
    assert set(Path("/private/tmp").glob("rwb-mcp-offline-*")) == before


@pytest.mark.parametrize("mode", ["giant", "oversized", "chatty"])
@pytest.mark.asyncio
async def test_managed_stdout_is_bounded_before_json_parse_and_reaped(
    tmp_path, offline_host, monkeypatch, mode
):
    import mcp_types

    from app.research_web.mcp_runtime import managed_sandbox as sandbox
    from app.research_web.mcp_runtime.sdk_host import MCPHostError

    package = tmp_path / "package"
    package.mkdir()
    (package / "server.py").write_text(SERVER)
    target = sandbox.build_managed_target(package, ["python", "server.py"], "mcpb")
    processes = []
    real_open = sandbox.anyio.open_process

    async def observe_owned_child(*args, **kwargs):
        process = await real_open(*args, **kwargs)
        processes.append((process, Path(kwargs["cwd"])))
        return process

    adapter = mcp_types.jsonrpc_message_adapter
    parsed_lengths = []

    class BoundedParserEvidence:
        def validate_json(self, raw, **options):
            parsed_lengths.append(len(raw))
            assert len(raw) <= sandbox.MAX_STDIO_LINE_BYTES
            return adapter.validate_json(raw, **options)

    monkeypatch.setattr(sandbox.anyio, "open_process", observe_owned_child)
    monkeypatch.setattr(mcp_types, "jsonrpc_message_adapter", BoundedParserEvidence())
    # A permissive post-parse result cap cannot be the reason this test passes.
    offline_host.max_result_bytes = 4 * 1024 * 1024
    with pytest.raises(MCPHostError, match="mcp_operation_failed"):
        await offline_host.call_tool(target, "canary", {mode: True})
    assert parsed_lengths and max(parsed_lengths) <= sandbox.MAX_STDIO_LINE_BYTES
    assert len(processes) == 1
    for process, scratch in processes:
        assert process.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.kill(process.pid, 0)
        assert not scratch.exists()


@pytest.mark.asyncio
async def test_repeated_native_cancel_during_owned_birth_still_reaps(
    tmp_path, offline_host, monkeypatch
):
    import asyncio

    from app.research_web.mcp_runtime import managed_sandbox as sandbox

    package = tmp_path / "package"
    package.mkdir()
    (package / "server.py").write_text(SERVER)
    target = sandbox.build_managed_target(package, ["python", "server.py"], "mcpb")
    real_open = sandbox.anyio.open_process
    born = asyncio.Event()
    processes = []

    async def delayed_owned_birth(*args, **kwargs):
        process = await real_open(*args, **kwargs)
        processes.append((process, Path(kwargs["cwd"])))
        born.set()
        await asyncio.sleep(0.4)
        return process

    monkeypatch.setattr(sandbox.anyio, "open_process", delayed_owned_birth)
    task = asyncio.create_task(offline_host.call_tool(target, "canary", {"hang": True}))
    await asyncio.wait_for(born.wait(), 5)
    task.cancel()
    await asyncio.sleep(0.03)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    assert len(processes) == 1
    for process, scratch in processes:
        assert process.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.kill(process.pid, 0)
        assert not scratch.exists()
    assert offline_host.managed_cleanup_blocked is False


@pytest.mark.asyncio
async def test_repeated_native_cancel_during_owned_cleanup_still_reaps(
    tmp_path, offline_host, monkeypatch
):
    import asyncio

    from app.research_web.mcp_runtime import managed_sandbox as sandbox

    package = tmp_path / "package"
    package.mkdir()
    (package / "server.py").write_text(SERVER)
    target = sandbox.build_managed_target(package, ["python", "server.py"], "mcpb")
    real_stop = sandbox._stop_owned_process
    real_open = sandbox.anyio.open_process
    stopping = asyncio.Event()
    processes = []

    async def delayed_owned_cleanup(process, lifecycle):
        stopping.set()
        await asyncio.sleep(0.4)
        await real_stop(process, lifecycle)

    async def observed_owned_birth(*args, **kwargs):
        process = await real_open(*args, **kwargs)
        processes.append((process, Path(kwargs["cwd"])))
        return process

    monkeypatch.setattr(sandbox, "_stop_owned_process", delayed_owned_cleanup)
    monkeypatch.setattr(sandbox.anyio, "open_process", observed_owned_birth)
    task = asyncio.create_task(offline_host.call_tool(target, "canary", {"echo": True}))
    await asyncio.wait_for(stopping.wait(), 5)
    task.cancel()
    await asyncio.sleep(0.03)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    for process, scratch in processes:
        assert process.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.kill(process.pid, 0)
        assert not scratch.exists()
    assert offline_host.managed_cleanup_blocked is False


@pytest.mark.asyncio
async def test_cleanup_failure_retains_owned_scratch_and_runtime_admission(
    tmp_path, offline_host, monkeypatch
):
    from types import SimpleNamespace

    from app.research_web.mcp_runtime import managed_sandbox as sandbox
    from app.research_web.mcp_runtime.sdk_host import MCPHostError
    from app.research_web.mcp_runtime.service import sdk_operation

    package = tmp_path / "package"
    package.mkdir()
    (package / "server.py").write_text(SERVER)
    target = sandbox.build_managed_target(package, ["python", "server.py"], "mcpb")
    scratch_paths = []
    real_remove = sandbox.shutil.rmtree

    def blocked_owned_cleanup(path):
        scratch_paths.append(Path(path))
        raise OSError("owned cleanup failure")

    @sdk_operation
    async def operation(runtime):
        return await runtime.host.call_tool(target, "canary", {"echo": True})

    runtime = SimpleNamespace(host=offline_host, operations=set())
    monkeypatch.setattr(sandbox.shutil, "rmtree", blocked_owned_cleanup)
    try:
        with pytest.raises(MCPHostError, match="mcp_operation_failed"):
            await operation(runtime)
        assert offline_host.managed_cleanup_blocked is True
        assert len(runtime.operations) == 1
        assert scratch_paths and all(path.is_dir() for path in scratch_paths)
    finally:
        for path in scratch_paths:
            if path.exists():
                real_remove(path)


@pytest.mark.asyncio
async def test_reviewed_runtime_real_probe_call_cache_and_recovery(tmp_path, offline_host):
    from types import SimpleNamespace

    from test_plugins import Catalog, bundle

    from app.research_web.mcp_runtime.package_installer import PackageInstaller
    from app.research_web.mcp_runtime.service import MCPRuntimeError, MCPRuntimeService
    from app.research_web.mcp_runtime.transport import StdioTarget
    from app.research_web.plugins.mcp_policy import native_fingerprint, register_managed
    from app.research_web.plugins.service import PluginService

    root = tmp_path / "tenant"
    iid = "mcp-installation-" + "a" * 32
    package = root / "mcp-runtime/packages" / iid
    package.mkdir(parents=True, mode=0o700)
    package.parent.chmod(0o700)
    package.parent.parent.chmod(0o700)
    (package / "server.py").write_text(SERVER)
    staging = root / "staging"
    staging.mkdir(mode=0o700)
    selection = {
        "registry_id": "official",
        "server_name": "example/server",
        "server_version": "1.0.0",
        "package_index": 0,
    }
    plan = {
        **selection,
        "package_type": "mcpb",
        "argv": ["python", "server.py"],
        "environment_names": [],
        "target_kind": "local",
    }
    native = {"id": iid, "plan": plan}
    manifest = SimpleNamespace(
        id=iid,
        plan=SimpleNamespace(**plan, assert_integrity=lambda: None),
        model_dump=lambda **_: native,
    )
    plugins = PluginService(root, Catalog(), idle_gate=lambda: True)
    raw = bundle(
        "plugin.json",
        extra={
            "plugin.json": json.dumps(
                {
                    "name": "fixture",
                    "version": "1.0.0",
                    "extensions": {"research_workbench": {"mcp": {"server": selection}}},
                }
            )
        },
    )
    item = plugins.preview(raw)
    assert any(permission.startswith("mcp:offline-sandbox:") for permission in item["permissions"])
    plugins.review(item["digest"], item["permissions"], "admin")
    await plugins.enable(item["digest"])
    row = plugins._row(item["digest"])
    row["mcp_bindings"]["server"] = iid
    row["mcp_reviews"] = {"server": native_fingerprint(root, native)}
    plugins.save()
    register_managed(root, iid)
    installer = PackageInstaller(
        staging, package.parent, credentials=RuntimeCredentialStore(MemoryCredentials())
    )
    runtime = MCPRuntimeService(
        root,
        enabled=True,
        managed_only=True,
        host=offline_host,
        store=SimpleNamespace(get=lambda _: manifest),
        installer=installer,
        idle_gate=lambda: True,
        restart_callback=lambda _: None,
    )
    plugins.mcp = runtime
    probe = await runtime.probe(iid)
    snapshot = plugins.mcp_review_snapshot(item["digest"], "server")
    plugins.mcp_review(item["digest"], "server", snapshot["fingerprint"])
    await runtime.enable(iid)
    runtime.classify_tool(iid, "canary", risk_tier="read_only", allow_unattended=False)
    schema = probe["tools"][0]["schema_sha256"]
    runtime.authorize_session(
        "session-fixture",
        installation_id=iid,
        version="1.0.0",
        tool_name="canary",
        schema_sha256=schema,
    )
    result = await runtime.call_tool(
        installation_id=iid,
        version="1.0.0",
        session_id="session-fixture",
        call_id="call-fixture",
        tool_name="canary",
        schema_sha256=schema,
        arguments={"echo": True},
    )
    assert result["result"]["content"][0]["text"] == "pong"
    # An ordinary pre-sandbox cached target is not allowed to reach the Host.
    runtime._targets[iid] = StdioTarget(("/bin/echo",), package, {})
    with pytest.raises(MCPRuntimeError) as cached:
        await runtime._target(manifest)
    assert cached.value.code == "mcp_managed_approval_required"
    # Fresh recovery builds the confined target only after current reviews pass.
    runtime._targets.clear()
    await runtime.start()
    assert runtime._targets[iid].package == package
    (package / "server.py").write_text(SERVER + "\n# changed")
    with pytest.raises(MCPRuntimeError) as changed:
        await runtime._target(manifest)
    assert changed.value.code == "mcp_managed_approval_required"


@pytest.mark.asyncio
async def test_old_policy_requires_explicit_reimport_and_new_review(tmp_path, monkeypatch):
    from test_plugins import Catalog, bundle

    from app.research_web.mcp_runtime import managed_sandbox
    from app.research_web.plugins.service import PluginService

    selection = {
        "registry_id": "official",
        "server_name": "example/server",
        "server_version": "1.0.0",
        "package_index": 0,
    }
    raw = bundle(
        "plugin.json",
        extra={
            "plugin.json": json.dumps(
                {
                    "name": "fixture",
                    "version": "1.0.0",
                    "extensions": {"research_workbench": {"mcp": {"server": selection}}},
                }
            )
        },
    )
    plugins = PluginService(tmp_path, Catalog(), idle_gate=lambda: True)
    item = plugins.preview(raw)
    plugins.review(item["digest"], item["permissions"], "admin")
    await plugins.enable(item["digest"])
    assert plugins.version_authorized(item["digest"])
    monkeypatch.setattr(managed_sandbox, "policy_digest", lambda: "0" * 64)
    assert not plugins.version_authorized(item["digest"])
    assert plugins.detail(item["digest"])["approved_for_sessions"] is False
    refreshed = plugins.preview(raw)
    assert refreshed["review"] is None
    assert refreshed["permissions"] != item["permissions"]
    assert not plugins.version_authorized(item["digest"])
    plugins.review(item["digest"], refreshed["permissions"], "admin")
    assert plugins.version_authorized(item["digest"])
    assert plugins._row(item["digest"])["mcp_reviews"] == {}
