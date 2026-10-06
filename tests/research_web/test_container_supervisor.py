"""Real-process acceptance for the container lifecycle and authenticated probes."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SECRET = "fixture-private-secret-value"


@pytest.mark.parametrize("existing", ["datahub", "mcp"])
def test_guest_prepare_controls_fills_missing_without_rotating_token(tmp_path, existing):
    from docker import supervisor
    from app.research_web.datahub.security import load_control
    from app.research_web.mcp_runtime.control import load_control as load_mcp
    root = tmp_path / "data"
    root.mkdir(mode=0o700)
    origin = "http://127.0.0.1:48240"
    original = (load_control if existing == "datahub" else load_mcp)(root, origin)
    prepare = getattr(supervisor, "prepare_controls", None)
    assert callable(prepare), "trusted guest preparation entry is missing"
    prepare(root, origin)
    values = {"datahub": load_control(root, origin), "mcp": load_mcp(root, origin)}
    assert values[existing]["token"] == original["token"]
    assert values["datahub"]["url"] == values["mcp"]["url"] == origin


def test_guest_prepare_controls_rejects_existing_origin_mismatch(tmp_path):
    from docker import supervisor
    from app.research_web.datahub.security import load_control
    root = tmp_path / "data"
    root.mkdir(mode=0o700)
    load_control(root, "http://127.0.0.1:48240")
    prepare = getattr(supervisor, "prepare_controls", None)
    assert callable(prepare), "trusted guest preparation entry is missing"
    with pytest.raises(RuntimeError):
        prepare(root, "http://127.0.0.1:8088")
    assert not (root / ".control/mcp-runtime.json").exists()

CHILD = r'''
import http.server, json, os, signal, sys, time
from pathlib import Path
role, port, events, mode = sys.argv[1:]
def record(event):
    with open(events, "a") as f:
        f.write(json.dumps([role, event, time.monotonic(), os.getpid()]) + "\n")
def stop(signum, frame):
    record("term")
    if mode != "stubborn" and not (mode == "detached-stubborn" and role == "worker"):
        raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
record("start")
Path(events + ".staged-" + role).write_text(os.environ.get("RWB_DSH_STAGED", "absent"))
print("service fixture ready", flush=True)
if mode != "no-cookie-header":
    print("Cookie: dsh-auth-fixture=private-cookie", flush=True)
print("cookie cache ready", flush=True)
if mode != "no-cookie-header" or role == "web":
    print("retry credential private-cookie", flush=True)
print('{"credential":"structured-credential-value"}', flush=True)
print("retry credential structured-credential-value", flush=True)
print(os.environ["FIXTURE_SECRET"], flush=True)
print("RWB_SUPERVISOR_ROLE=" + os.environ.get("RWB_SUPERVISOR_ROLE", "missing"), flush=True)
def spawn_adopted():
    intermediate = os.fork()
    if intermediate == 0:
        if os.fork() != 0:
            os._exit(0)
        os.setsid()
        environment = dict(os.environ)
        if mode == "adopted-missing": environment.pop("RWB_SUPERVISOR_ROLE", None)
        if mode == "adopted-invalid": environment["RWB_SUPERVISOR_ROLE"] = "invalid-role-marker"
        worker = str(Path(events).parent / "worker.py")
        os.execve(sys.executable, [sys.executable, worker, role + "-worker", events], environment)
    os.waitpid(intermediate, 0)
if mode == "descendant" and os.fork() == 0:
    role = "worker"
    record("start")
    while True: time.sleep(.01)
if mode.startswith("detached") and os.fork() == 0:
    os.setsid()
    role = "worker"
    record("start")
    while True: time.sleep(.01)
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if role == "runtime":
            self.send_response(303)
            self.send_header("Set-Cookie", "dsh-auth-fixture=private-cookie; HttpOnly")
            self.end_headers()
        else:
            self.send_response(200)
            content_type = "application/json"
            body = json.dumps({"connected": mode != "unhealthy",
                               "health_check_passed": mode != "unhealthy"}).encode()
            if self.path == "/":
                content_type = "text/html"
                body = "Research Workbench · Research".encode()
            elif self.path == "/static/app.mjs":
                content_type = "text/javascript"
                body = b"const defaultCatalogNames = [];"
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(body)
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        record("probe")
        if Path(events + ".stall").exists():
            time.sleep(2)
            return
        ok = self.headers.get("Cookie") == "dsh-auth-fixture=private-cookie"
        self.send_response(200 if ok and mode != "unhealthy" else 503)
        self.end_headers()
        self.wfile.write(json.dumps({"type": "server-response", "rpcId": "wrong" if Path(events + ".bad-rpc").exists() else request["rpcId"],
            "result": {"ok": True, "value": {"items": []}}}).encode())
server = http.server.HTTPServer(("127.0.0.1", int(port)), Handler)
server.timeout = .03
if role == "runtime":
    print("dsh web: http://127.0.0.1:" + port + "/?token=" + "x" * 43, flush=True)
    print("retry credential " + "x" * 43, flush=True)
    print("dsh web: http://127.0.0.1:" + port + "/?token=" + "y" * 43, flush=True)
    print("old credential " + "x" * 43 + " new credential " + "y" * 43, flush=True)
spawned = False
while True:
    if mode.startswith("adopted") and not spawned and Path(events + ".spawn").exists():
        spawn_adopted()
        spawned = True
    if Path(events + ".exit-" + role).exists():
        record("exit")
        raise SystemExit(9)
    server.handle_request()
'''

WORKER = r'''
import json, os, signal, sys, time
from pathlib import Path
role, events = sys.argv[1:]
def record(event):
    with open(events, "a") as stream:
        stream.write(json.dumps([role, event, time.monotonic(), os.getpid()]) + "\n")
def stop(signum, frame):
    record("term")
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
marker = os.environ.get("RWB_SUPERVISOR_ROLE")
raw = b"FIXTURE_ENV=never-disclose-process-environment\0"
if marker is not None: raw += b"RWB_SUPERVISOR_ROLE=" + marker.encode() + b"\0"
Path(events + ".role-" + str(os.getpid())).write_bytes(raw)
record("start")
print("RWB_SUPERVISOR_ROLE=" + str(marker), flush=True)
while True: time.sleep(.01)
'''

RUNNER = r'''
import json, sys
from pathlib import Path
from docker import supervisor
from app.research_web.process_spec import ProcessSpec, WebProcessSpecs
root, runtime_port, web_port, runtime_mode, web_mode = sys.argv[1:]
root = Path(root)
config = supervisor.SupervisorConfig(data_root=root/"data", state_root=root/"state",
    project_root=Path.cwd(), runtime_source=root/"source", python=sys.executable,
    node="unused", runtime_port=int(runtime_port), web_port=int(web_port),
    startup_timeout=.9, shutdown_timeout=.35)
def specs(**kwargs):
    assert kwargs["web_host"] == "0.0.0.0"
    def spec(role, port, mode):
        command = (sys.executable, str(root/"child.py"), role, str(port), str(root/"events"), mode)
        if mode == "missing": command = (str(root/"missing-executable"),)
        return ProcessSpec(role, port, command, ())
    return WebProcessSpecs(spec("runtime", config.runtime_port, runtime_mode),
        spec("web", config.web_port, web_mode), config.state_root)
supervisor.build_process_specs = specs
if sys.platform == "darwin" and (runtime_mode.startswith("adopted") or web_mode.startswith("adopted")):
    # macOS cannot adopt these orphans. Model only Linux's PPID observation;
    # keep real child PIDs, sessions, signals and birth identities for cleanup.
    from dataclasses import replace
    import os
    original_snapshot = supervisor._process_snapshot
    original_init = supervisor._OwnedProcesses.__init__
    def snapshot():
        values = original_snapshot()
        records = [json.loads(line) for line in (root/"events").read_text().splitlines()] if (root/"events").exists() else []
        started = {row[3]: row[0] for row in records if row[1] == "start"}
        family = {pid for pid, info in values.items() if info.parent == os.getpid()}
        while True:
            added = {pid for pid, info in values.items() if info.parent in family} - family
            if not added: break
            family.update(added)
        for pid, info in list(values.items()):
            if pid in family and pid not in started:
                del values[pid]  # Hide intermediate/pre-exec ancestry and ps helper.
            elif started.get(pid, "").endswith("-worker"):
                if info.parent == 1:
                    values[pid] = replace(info, parent=os.getpid())
                else:
                    del values[pid]  # Never expose its pre-adoption ancestry.
        return values
    def init(self):
        original_init(self)
        self.adopts = True
    supervisor._process_snapshot = snapshot
    supervisor._OwnedProcesses.__init__ = init
    supervisor._read_role_environment = lambda pid: (root/("events.role-" + str(pid))).read_bytes()
raise SystemExit(supervisor.run(config))
'''


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def events(root):
    path = root / "events"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def wait_for(check, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.02)
    pytest.fail("fixture readiness timed out")


@pytest.fixture
def launch(tmp_path):
    # Resolve macOS /var alias before the production private-state validator.
    root = tmp_path.resolve()
    (root / "data").mkdir(mode=0o700)
    (root / "state").mkdir(mode=0o700)
    (root / "source").mkdir()
    (root / "source/package.json").write_text('{"version":"fixture"}')
    (root / "child.py").write_text(CHILD)
    (root / "worker.py").write_text(WORKER)
    processes = []

    def start(runtime="normal", web="normal", state_mode=0o700):
        (root / "state").chmod(state_mode)
        runtime_port, web_port = free_port(), free_port()
        proc = subprocess.Popen(
            [sys.executable, "-c", RUNNER, str(root), str(runtime_port), str(web_port), runtime, web],
            cwd=ROOT, env={**os.environ, "FIXTURE_SECRET": SECRET},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        processes.append(proc)
        return proc, root, runtime_port, web_port

    yield start
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
    for role, event, _, pid in events(root):
        if event == "start":
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def started(root, role):
    return any(item[:2] == [role, "start"] for item in events(root))


@pytest.mark.parametrize("flag", [None, "", "0", "invalid", "1", "1 "])
def test_staged_flag_is_exact_and_reaches_only_runtime_child(launch, monkeypatch, flag):
    if flag is None:
        monkeypatch.delenv("RWB_DSH_STAGED", raising=False)
    else:
        monkeypatch.setenv("RWB_DSH_STAGED", flag)
    proc, root, _, _ = launch()
    wait_for(lambda: (root / "events.staged-web").exists() or proc.poll() is not None)
    assert proc.poll() is None, proc.communicate()[0]
    proc.terminate()
    output = proc.communicate(timeout=5)[0]
    assert proc.returncode == 0, output
    assert (root / "events.staged-runtime").read_text() == ("1" if flag == "1" else "absent")
    assert (root / "events.staged-web").read_text() == "absent"


@pytest.mark.parametrize("stop_signal", [signal.SIGTERM, signal.SIGINT])
def test_start_order_signal_cleanup_and_redacted_forwarding(launch, stop_signal):
    proc, root, _, _ = launch()
    wait_for(lambda: started(root, "web") or proc.poll() is not None)
    assert proc.poll() is None, proc.communicate()[0]
    proc.send_signal(stop_signal)
    output = proc.communicate(timeout=5)[0]
    assert proc.returncode == 0, output
    sequence = [item[:2] for item in events(root)]
    assert sequence.index(["runtime", "probe"]) < sequence.index(["web", "start"])
    assert sequence.index(["web", "term"]) < sequence.index(["runtime", "term"])
    assert "service fixture ready" in output
    assert "cookie cache ready" in output
    assert "retry credential [redacted]" in output
    assert "role" in output and "state" in output and "code" in output
    assert all(value not in output for value in (
        SECRET, "private-cookie", "x" * 43, "y" * 43, "structured-credential-value"
    ))
    assert "kill" not in output
    assert not (root / "state/auth.json").exists()
    persisted = "".join(path.read_text() for path in (root / "data/logs").glob("*.log"))
    assert "service fixture ready" in persisted and "health_ready" in persisted
    assert "cookie cache ready" in persisted
    assert all(value not in persisted for value in (
        SECRET, "private-cookie", "x" * 43, "y" * 43, "structured-credential-value"
    ))


def test_auth_record_cookie_redacted_without_prior_cookie_output(launch):
    proc, root, _, _ = launch(runtime="no-cookie-header", web="no-cookie-header")
    wait_for(lambda: started(root, "web") or proc.poll() is not None)
    proc.terminate()
    output = proc.communicate(timeout=5)[0]
    assert proc.returncode == 0, output
    persisted = "".join(path.read_text() for path in (root / "data/logs").glob("*.log"))
    assert "private-cookie" not in output + persisted
    assert "cookie cache ready" in output and "retry credential [redacted]" in output


@pytest.mark.parametrize("runtime_mode", ["adopted", "adopted-missing", "adopted-invalid"])
def test_unobserved_adopted_workers_keep_proven_roles_or_cleanup_last(launch, runtime_mode):
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        proc, root, _, _ = launch(runtime=runtime_mode, web="adopted")
        wait_for(lambda: started(root, "web") or proc.poll() is not None)
        (root / "events.spawn").touch()
        wait_for(lambda: started(root, "web-worker") or proc.poll() is not None)
        wait_for(lambda: started(root, "runtime-worker") or proc.poll() is not None)
        assert proc.poll() is None, proc.communicate()[0]
        time.sleep(.2)
        proc.terminate()
        output = proc.communicate(timeout=6)[0]
        unknown = runtime_mode != "adopted"
        assert proc.returncode == (1 if unknown else 0), output
        terms = {row[0]: row[2] for row in events(root) if row[1] == "term"}
        assert terms["web-worker"] < terms["runtime"]
        assert terms["web"] < terms["runtime-worker"]
        assert terms["web-worker"] < terms["runtime-worker"]
        if unknown:
            assert terms["runtime"] < terms["runtime-worker"]
            assert "unknown_owned_role" in output
        persisted = "".join(path.read_text() for path in (root / "data/logs").glob("*.log"))
        for path in root.glob("events.role-*"):
            for entry in path.read_bytes().split(b"\0"):
                if entry.startswith(b"RWB_SUPERVISOR_ROLE="):
                    assert entry.decode() not in output + persisted
        assert "never-disclose-process-environment" not in output + persisted
        assert unrelated.poll() is None
        for row in events(root):
            if row[0].endswith("-worker") and row[1] == "start":
                with pytest.raises(ProcessLookupError):
                    os.kill(row[3], 0)
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=3)


@pytest.mark.parametrize("raw,expected", [
    (b"RWB_SUPERVISOR_ROLE=runtime\0", "runtime"),
    (b"RWB_SUPERVISOR_ROLE=web\0", "web"),
    (b"OTHER_ROLE=runtime\0", "unknown"),
    (b"RWB_SUPERVISOR_ROLE=runtime-extra\0", "unknown"),
    (b"RWB_SUPERVISOR_ROLE=web\0RWB_SUPERVISOR_ROLE=runtime\0", "unknown"),
    (b"RWB_SUPERVISOR_ROLE=runtime\0" + b"x" * 65536, "unknown"),
])
def test_adopted_role_uses_only_one_exact_bounded_marker(monkeypatch, raw, expected):
    from docker import supervisor

    identity = supervisor._ProcessIdentity(os.getpid(), os.getpid(), "birth", False)
    monkeypatch.setattr(supervisor, "_read_role_environment", lambda pid: raw)
    monkeypatch.setattr(supervisor, "_process_snapshot", lambda: {42: identity})
    assert supervisor._adopted_role(42, identity) == expected
    monkeypatch.setattr(supervisor, "_process_snapshot", lambda: {})
    assert supervisor._adopted_role(42, identity) == "unknown"


def test_baseline_direct_child_is_not_adopted_or_signalled(monkeypatch):
    from docker import supervisor

    baseline = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    ownership = supervisor._OwnedProcesses()
    ownership.adopts = True
    try:
        actual_snapshot = supervisor._process_snapshot
        def snapshot():
            # Exclude the transient ps helper used on macOS, retain the real baseline.
            return {pid: info for pid, info in actual_snapshot().items()
                    if info.parent != os.getpid() or pid == baseline.pid}
        monkeypatch.setattr(supervisor, "_process_snapshot", snapshot)
        assert baseline.pid not in ownership.refresh({})
        assert baseline.pid not in ownership.owned
        assert not ownership.unknown_roles_seen
        assert baseline.poll() is None
    finally:
        ownership.close()
        baseline.terminate()
        baseline.wait(timeout=3)


@pytest.mark.parametrize("unexpected", [False, True])
@pytest.mark.parametrize("worker_mode", ["detached", "detached-stubborn"])
def test_cleans_setsid_descendant_even_after_direct_parent_exit(launch, unexpected, worker_mode):
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        proc, root, _, _ = launch(web=worker_mode)
        wait_for(lambda: started(root, "worker") or proc.poll() is not None)
        assert proc.poll() is None, proc.communicate()[0]
        worker_pid = next(row[3] for row in events(root) if row[:2] == ["worker", "start"])
        assert os.getpgid(worker_pid) == worker_pid
        time.sleep(.2)  # Allow the non-PID-1 macOS fixture to observe ancestry before orphaning.
        before = time.monotonic()
        if unexpected:
            (root / "events.exit-web").touch()
        else:
            proc.terminate()
        output = proc.communicate(timeout=6)[0]
        assert proc.returncode == (1 if unexpected else 0), output
        assert ["worker", "term"] in [row[:2] for row in events(root)], output
        if worker_mode == "detached-stubborn":
            assert time.monotonic() - before >= .35
            assert "signal_kill" in output
        def worker_gone():
            try:
                os.kill(worker_pid, 0)
                return False
            except ProcessLookupError:
                return True
        wait_for(worker_gone, timeout=2)
        assert unrelated.poll() is None
        worker_term = next(row[2] for row in events(root) if row[:2] == ["worker", "term"])
        runtime_term = next(row[2] for row in events(root) if row[:2] == ["runtime", "term"])
        assert worker_term < runtime_term
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=3)


@pytest.mark.parametrize("runtime,web", [("unhealthy", "normal"), ("normal", "missing"), ("normal", "unhealthy")])
def test_start_failure_cleans_runtime(launch, runtime, web):
    proc, root, _, _ = launch(runtime, web)
    output = proc.communicate(timeout=6)[0]
    assert proc.returncode != 0
    assert ["runtime", "term"] in [item[:2] for item in events(root)], output
    if runtime == "unhealthy":
        assert not started(root, "web")


@pytest.mark.parametrize("role", ["runtime", "web"])
def test_unexpected_exit_cleans_sibling(launch, role):
    proc, root, _, _ = launch()
    wait_for(lambda: started(root, "web") or proc.poll() is not None)
    (root / ("events.exit-" + role)).touch()
    output = proc.communicate(timeout=5)[0]
    assert proc.returncode != 0, output
    sibling = "web" if role == "runtime" else "runtime"
    assert [sibling, "term"] in [item[:2] for item in events(root)]


def test_kill_only_after_grace_period(launch):
    proc, root, _, _ = launch(web="stubborn")
    wait_for(lambda: started(root, "web") or proc.poll() is not None)
    started_at = time.monotonic()
    proc.terminate()
    output = proc.communicate(timeout=5)[0]
    assert proc.returncode == 0, output
    assert time.monotonic() - started_at >= .35
    assert "kill" in output


def test_healthcheck_real_authenticated_services_and_read_only_state(launch):
    from docker.healthcheck import check

    proc, root, runtime_port, web_port = launch()
    wait_for(lambda: started(root, "web") or proc.poll() is not None)
    assert proc.poll() is None, proc.communicate()[0]
    auth = root / "state/auth.json"
    before = auth.read_bytes()
    assert check(root / "state", root / "data", runtime_port, web_port, timeout=.5) == 0
    assert auth.read_bytes() == before
    auth.write_text("{}")
    assert check(root / "state", root / "data", runtime_port, web_port, timeout=.5) != 0
    assert auth.read_text() == "{}"
    auth.write_bytes(before)
    (root / "state").chmod(0o755)
    assert check(root / "state", root / "data", runtime_port, web_port, timeout=.5) != 0
    (root / "state").chmod(0o700)


def test_healthcheck_import_exists():
    from docker.healthcheck import check
    from docker.supervisor import SupervisorConfig, run

    assert callable(check) and callable(run) and SupervisorConfig.__dataclass_params__.frozen


def test_container_full_page_probe_uses_shared_total_deadline(tmp_path, monkeypatch):
    from docker.healthcheck import ContainerHealth

    probe = ContainerHealth(timeout=.1, data_root=tmp_path / "data")
    calls = []

    def request(port, method, path, *args):
        calls.append((port, method, path))
        return 200, {"Content-Type": "text/html"}, b"Research Workbench"

    monkeypatch.setattr(probe, "_request", request)
    assert probe._text_request(18088, "/", max_bytes=100) == (
        200, "text/html", "Research Workbench"
    )
    assert calls == [(18088, "GET", "/")]


def test_healthcheck_rejects_bad_rpc_and_bounds_slow_response(launch):
    from docker.healthcheck import check

    proc, root, runtime_port, web_port = launch()
    wait_for(lambda: started(root, "web") or proc.poll() is not None)
    (root / "events.bad-rpc").touch()
    assert check(root / "state", root / "data", runtime_port, web_port, timeout=.3) == 1
    (root / "events.bad-rpc").unlink()
    (root / "events.stall").touch()
    before = time.monotonic()
    assert check(root / "state", root / "data", runtime_port, web_port, timeout=.15) == 1
    assert time.monotonic() - before < .5


def test_unsafe_state_never_starts_a_child(launch):
    proc, root, _, _ = launch(state_mode=0o755)
    output = proc.communicate(timeout=5)[0]
    assert proc.returncode != 0, output
    assert events(root) == []


def test_shutdown_reaches_process_group_descendants(launch):
    proc, root, _, _ = launch(web="descendant")
    wait_for(lambda: started(root, "worker") or proc.poll() is not None)
    proc.terminate()
    output = proc.communicate(timeout=5)[0]
    assert proc.returncode == 0, output
    assert ["worker", "term"] in [item[:2] for item in events(root)]


def test_reaps_untracked_children_and_preserves_owned_exit_status():
    from docker.supervisor import _reap_children

    first = subprocess.Popen([sys.executable, "-c", "raise SystemExit(9)"])
    second = subprocess.Popen([sys.executable, "-c", "raise SystemExit(0)"])
    try:
        reaped = set()
        def both_reaped():
            reaped.update(_reap_children({"runtime": first}))
            return reaped == {first.pid, second.pid}
        wait_for(both_reaped)
        assert first.returncode == 9
        with pytest.raises(ChildProcessError):
            os.waitpid(second.pid, os.WNOHANG)
    finally:
        first.wait(timeout=3)
        second.wait(timeout=3)


def test_shutdown_cleanup_failure_returns_nonzero(launch):
    proc, root, _, _ = launch(web="unhealthy")
    wait_for(lambda: started(root, "web") or proc.poll() is not None)
    (root / "state").chmod(0o755)
    proc.terminate()
    output = proc.communicate(timeout=5)[0]
    assert "auth_cleanup_failed" in output
    assert proc.returncode != 0, output
    (root / "state").chmod(0o700)


def test_entrypoint_is_only_validation_and_exec():
    script = (ROOT / "docker/entrypoint.sh").read_text()
    assert script.splitlines() == [
        "#!/bin/sh", "set -eu", ': "${RWB_DATA_ROOT:=/data/research-web}"',
        ': "${RWB_RUNTIME_STATE:=/state/runtime}"',
        ': "${RESEARCH_CREDENTIAL_HOME:=/run/rwb-secrets/private}"',
        'test -d "$RWB_DATA_ROOT" && test -w "$RWB_DATA_ROOT"',
        'test -d "${RWB_RUNTIME_STATE%/*}" && test -w "${RWB_RUNTIME_STATE%/*}"',
        'test -d "${RESEARCH_CREDENTIAL_HOME%/*}" && test -w "${RESEARCH_CREDENTIAL_HOME%/*}"',
        'export RWB_DATA_ROOT RWB_RUNTIME_STATE RESEARCH_CREDENTIAL_HOME',
        "exec /opt/rwb/venv/bin/python /opt/rwb/docker/supervisor.py",
    ]


def test_private_mount_leaves_are_prepared_before_ownership_and_reused(tmp_path, monkeypatch):
    from docker import supervisor
    import stat

    root = tmp_path.resolve()
    state_mount, secret_mount = root / "state", root / "secrets"
    state_mount.mkdir(mode=0o700)
    secret_mount.mkdir(mode=0o700)
    config = supervisor.SupervisorConfig(
        data_root=root / "data", state_root=state_mount / "runtime",
        credential_root=secret_mount / "private", project_root=ROOT,
        runtime_source=root / "source", python=sys.executable, node="unused",
    )
    observed = []

    def stop_after_preparation():
        observed.append(tuple((path.stat().st_ino, path.stat().st_uid,
                               stat.S_IMODE(path.stat().st_mode))
                              for path in (config.state_root, config.credential_root)))
        raise RuntimeError("fixture_stop_before_children")

    monkeypatch.setattr(supervisor, "_OwnedProcesses", stop_after_preparation)
    monkeypatch.setattr(supervisor, "setup_logging", lambda: None)
    monkeypatch.setattr(supervisor.settings, "LOG_DIR", supervisor.settings.LOG_DIR)
    assert supervisor.run(config) == 1
    assert supervisor.run(config) == 1
    assert observed[0] == observed[1]
    assert all(owner == os.getuid() and mode == 0o700 for _, owner, mode in observed[0])


@pytest.mark.parametrize("bad_leaf", ["state", "credential"])
@pytest.mark.parametrize("kind", ["alias", "mode"])
def test_unsafe_private_mount_leaf_fails_before_children(tmp_path, monkeypatch, bad_leaf, kind):
    from docker import supervisor

    root = tmp_path.resolve()
    state, credential = root / "state/runtime", root / "secrets/private"
    state.parent.mkdir(mode=0o700)
    credential.parent.mkdir(mode=0o700)
    path = state if bad_leaf == "state" else credential
    if kind == "alias":
        target = root / "foreign"
        target.mkdir(mode=0o700)
        path.symlink_to(target, target_is_directory=True)
    else:
        path.mkdir(mode=0o755)
    config = supervisor.SupervisorConfig(
        data_root=root / "data", state_root=state, credential_root=credential,
        project_root=ROOT, runtime_source=root / "source", python=sys.executable, node="unused",
    )
    monkeypatch.setattr(supervisor, "_OwnedProcesses", lambda: pytest.fail("unsafe mount reached child ownership"))
    assert supervisor.run(config) == 1


def test_supervisor_and_health_defaults_share_private_state_leaf(monkeypatch):
    from docker import healthcheck, supervisor

    for name in ("RWB_DATA_ROOT", "RWB_RUNTIME_STATE", "RESEARCH_CREDENTIAL_HOME"):
        monkeypatch.delenv(name, raising=False)
    configs = []
    monkeypatch.setattr(supervisor, "run", lambda config: configs.append(config) or 0)
    assert supervisor.main() == 0
    assert configs[0].state_root == Path("/state/runtime")
    assert configs[0].credential_root == Path("/run/rwb-secrets/private")
    checks = []
    monkeypatch.setattr(healthcheck, "check", lambda *args: checks.append(args) or 0)
    assert healthcheck.main() == 0
    assert checks[0][0] == configs[0].state_root


@pytest.mark.parametrize("name", ["runtime", "private", "logs"])
@pytest.mark.parametrize("transition", ["mapped", "foreign_uid", "foreign_gid", "mode", "inode", "custom"])
def test_docker_first_mkdir_owner_mapping_then_strict_repin(tmp_path, monkeypatch, name, transition):
    from docker import supervisor
    from app.research_web.runtime_state import RuntimeStateError, runtime_state_directory

    mount = tmp_path.resolve() / "mount"
    mount.mkdir(mode=0o700)
    leaf = mount / name
    real_stat, real_fstat, real_mkdir = os.stat, os.fstat, os.mkdir
    mount_node = (real_stat(mount).st_dev, real_stat(mount).st_ino)
    mapped = []

    def project(info):
        if (info.st_dev, info.st_ino) == mount_node:
            values = list(info)
            if not mapped:
                values[4:6] = [0, 0]
            elif transition == "foreign_uid":
                values[4] = os.getuid() + 9876
            elif transition == "foreign_gid":
                values[5] = os.getgid() + 9876
            elif transition == "mode":
                values[0] |= 0o055
            elif transition == "inode":
                values[1] += 99999
            return os.stat_result(values)
        return info

    def mkdir(path, mode=0o777, *, dir_fd=None):
        result = real_mkdir(path, mode, dir_fd=dir_fd)
        if str(path) == name and dir_fd is not None:
            mapped.append(True)
        return result

    monkeypatch.setattr(os, "stat", lambda *args, **kwargs: project(real_stat(*args, **kwargs)))
    monkeypatch.setattr(os, "fstat", lambda descriptor: project(real_fstat(descriptor)))
    monkeypatch.setattr(os, "mkdir", mkdir)
    # Preserve a direct reproducer of why creation inside the strict guard fails.
    with pytest.raises(RuntimeStateError):
        with runtime_state_directory(leaf, create=True):
            pass
    leaf.rmdir()
    mapped.clear()
    monkeypatch.setattr(supervisor, "_DOCKER_PRIVATE_LEAVES", set() if transition == "custom" else {leaf}, raising=False)
    if transition != "mapped":
        with pytest.raises((RuntimeStateError, OSError)):
            supervisor._prepare_private_leaf(leaf)
        return
    supervisor._prepare_private_leaf(leaf)
    assert mapped == [True]
    with runtime_state_directory(leaf):
        identity = leaf.stat().st_ino
    supervisor._prepare_private_leaf(leaf)
    assert leaf.stat().st_ino == identity


@pytest.mark.parametrize("bad", ["parent_alias", "parent_mode", "foreign_owner", "parent_replace", "leaf_replace"])
def test_docker_two_phase_creation_rejects_unsafe_or_replaced_nodes(tmp_path, monkeypatch, bad):
    from docker import supervisor
    from app.research_web.runtime_state import RuntimeStateError

    mount = tmp_path.resolve() / "mount"
    mount.mkdir(mode=0o700)
    leaf = mount / "private"
    monkeypatch.setattr(supervisor, "_DOCKER_PRIVATE_LEAVES", {leaf}, raising=False)
    if bad == "parent_alias":
        other = mount.with_name("other")
        mount.rename(other)
        mount.symlink_to(other, target_is_directory=True)
    elif bad == "parent_mode":
        mount.chmod(0o755)
    elif bad == "foreign_owner":
        real_stat = os.stat
        inode = mount.stat().st_ino
        def foreign_stat(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if info.st_ino == inode:
                values = list(info)
                values[4] = os.getuid() + 9876
                return os.stat_result(values)
            return info
        monkeypatch.setattr(os, "stat", foreign_stat)
    else:
        original = supervisor.runtime_state_directory
        from contextlib import contextmanager
        @contextmanager
        def replace_before_repin(path, **kwargs):
            if path == leaf and leaf.exists():
                if bad == "parent_replace":
                    mount.rename(mount.with_name("old"))
                    mount.mkdir(mode=0o700)
                    leaf.mkdir(mode=0o700)
                else:
                    leaf.rename(mount / "old")
                    leaf.mkdir(mode=0o700)
            with original(path, **kwargs) as value:
                yield value
        monkeypatch.setattr(supervisor, "runtime_state_directory", replace_before_repin)
    with pytest.raises((RuntimeStateError, OSError)):
        supervisor._prepare_private_leaf(leaf)


@pytest.mark.parametrize(("error", "kind", "number"), [
    (PermissionError(13, "fixture-private-path"), "PermissionError", 13),
    (ValueError("fixture-private-value"), "ValueError", None),
    (RuntimeError("fixture-private-command"), "RuntimeError", None),
])
def test_failure_diagnostics_only_include_fixed_fields(error, kind, number):
    from docker import supervisor

    class Child:
        returncode = 7

    report = supervisor._failure_diagnostics("logging_setup", error, {"runtime": Child()})
    assert report == {
        "stage": "logging_setup", "exception_class": kind, "errno": number,
        "runtime_returncode": 7, "web_returncode": None,
    }
    assert "fixture-private" not in json.dumps(report)


def test_directory_failure_records_stage_before_starting_children(tmp_path, monkeypatch):
    from docker import supervisor

    root = tmp_path.resolve()
    state = root / "state"
    state.mkdir(mode=0o700)
    config = supervisor.SupervisorConfig(
        data_root=root / "data", state_root=state, project_root=ROOT,
        runtime_source=root / "source", python=sys.executable, node="unused",
    )
    captured = []
    monkeypatch.setattr(supervisor, "_event", lambda *args: None)
    monkeypatch.setattr(supervisor, "_emit_failure_diagnostics", lambda value: captured.append(value))
    def fail(_path):
        raise PermissionError(13, "fixture-private-path")
    monkeypatch.setattr(supervisor, "_prepare_private_leaf", fail)
    assert supervisor.run(config) == 1
    assert captured == [{
        "stage": "private_directories", "exception_class": "PermissionError", "errno": 13,
        "runtime_returncode": None, "web_returncode": None,
    }]


def test_existing_state_leaf_initializes_mapping_before_strict_access(tmp_path, monkeypatch):
    from docker import supervisor
    from app.research_web.runtime_state import RuntimeStateError, runtime_state_directory

    mount = tmp_path.resolve() / "state"
    mount.mkdir(mode=0o700)
    leaf = mount / "runtime"
    leaf.mkdir(mode=0o700)
    real_stat, real_fstat, real_open = os.stat, os.fstat, os.open
    node = (mount.stat().st_dev, mount.stat().st_ino)
    mapped = []

    def project(info):
        if (info.st_dev, info.st_ino) == node and not mapped:
            values = list(info)
            values[4:6] = [0, 0]
            return os.stat_result(values)
        return info

    def open_file(name, flags, mode=0o777, *, dir_fd=None):
        descriptor = real_open(name, flags, mode, dir_fd=dir_fd)
        if flags & os.O_CREAT and dir_fd is not None:
            mapped.append(True)
        return descriptor

    monkeypatch.setattr(os, "stat", lambda *args, **kwargs: project(real_stat(*args, **kwargs)))
    monkeypatch.setattr(os, "fstat", lambda descriptor: project(real_fstat(descriptor)))
    monkeypatch.setattr(os, "open", open_file)
    # The unchanged global guard rejects first-write parent mapping.
    leaf_descriptor = real_open(leaf, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(RuntimeStateError):
            with runtime_state_directory(leaf):
                descriptor = os.open("reproducer", os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                                     0o600, dir_fd=leaf_descriptor)
                os.close(descriptor)
    finally:
        os.close(leaf_descriptor)
    (leaf / "reproducer").unlink()
    mapped.clear()
    monkeypatch.setattr(supervisor, "_DOCKER_PRIVATE_LEAVES", {leaf})
    monkeypatch.setattr(supervisor, "_DOCKER_STATE_LEAF", leaf, raising=False)
    supervisor._prepare_private_leaf(leaf, initialize_state=True)
    with runtime_state_directory(leaf):
        leaf_descriptor = real_open(leaf, os.O_RDONLY | os.O_DIRECTORY)
        try:
            descriptor = os.open("strict-access", os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                                 0o600, dir_fd=leaf_descriptor)
            os.close(descriptor)
        finally:
            os.close(leaf_descriptor)
    (leaf / "strict-access").unlink()
    assert mapped
    assert list(leaf.iterdir()) == []


@pytest.mark.parametrize("change", [
    "stable", "mapped", "dev", "inode", "mode", "reverse", "foreign_uid", "foreign_gid",
    "mixed", "named_mismatch", "ancestor", "leaf", "leaf_gid", "root_overlap",
    "parent_replace", "leaf_replace", "temp_replace", "temp_hardlink", "temp_mode",
    "temp_content", "create_failure", "cleanup_failure", "after_init",
])
def test_state_initialization_identity_and_cleanup_boundary(tmp_path, monkeypatch, change):
    from docker import supervisor
    from app.research_web.runtime_state import RuntimeStateError, runtime_state_directory

    root = tmp_path.resolve()
    mount = root / "state"
    mount.mkdir(mode=0o700)
    leaf = mount / "runtime"
    leaf.mkdir(mode=0o700)
    real_stat, real_fstat, real_open, real_unlink = os.stat, os.fstat, os.open, os.unlink
    mount_node = (mount.stat().st_dev, mount.stat().st_ino)
    leaf_node = (leaf.stat().st_dev, leaf.stat().st_ino)
    ancestor_node = (root.stat().st_dev, root.stat().st_ino)
    runtime_pair = (os.getuid(), os.getgid())
    created = []
    post_init = []
    removed = []
    temporary_names = []

    def project(info, *, named=False):
        values = list(info)
        node = (info.st_dev, info.st_ino)
        if change == "root_overlap":
            if info.st_uid == runtime_pair[0]:
                values[4:6] = [0, 0]
            if node == mount_node and created:
                values[4:6] = [1, 1]
        elif node == mount_node:
            if change == "stable":
                pass
            elif not created:
                values[4:6] = list(runtime_pair) if change == "reverse" else [0, 0]
            elif change == "reverse":
                values[4:6] = [0, 0]
            elif change == "foreign_uid":
                values[4] += 9981
            elif change == "foreign_gid":
                values[5] += 9981
            elif change == "mixed":
                values[4] = 0
            elif change == "dev":
                values[2] += 1
            elif change == "inode":
                values[1] += 1
            elif change == "mode":
                values[0] |= 0o055
            elif change == "named_mismatch" and named:
                values[1] += 1
            elif change == "after_init" and post_init:
                values[4:6] = [0, 0]
        elif node == ancestor_node and change == "ancestor" and created:
            values[1] += 1
        elif node == leaf_node:
            if change == "leaf" and created:
                values[1] += 1
            elif change == "leaf_gid":
                values[5] += 9981
        return os.stat_result(values)

    def open_file(name, flags, mode=0o777, *, dir_fd=None):
        if not flags & os.O_CREAT:
            return real_open(name, flags, mode, dir_fd=dir_fd)
        assert dir_fd is not None
        assert flags & os.O_EXCL and flags & os.O_NOFOLLOW and flags & os.O_CLOEXEC
        assert mode == 0o600
        if change == "create_failure":
            raise PermissionError("fixture_create_failure")
        descriptor = real_open(name, flags, mode, dir_fd=dir_fd)
        created.append(True)
        temporary_names.append(name)
        if change == "parent_replace":
            mount.rename(root / "old-state")
            mount.mkdir(mode=0o700)
        elif change == "leaf_replace":
            leaf.rename(mount / "old-runtime")
            leaf.mkdir(mode=0o700)
        elif change == "temp_replace":
            os.rename(name, "held-original", src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
            replacement = real_open(name, flags, mode, dir_fd=dir_fd)
            os.close(replacement)
        elif change == "temp_hardlink":
            os.link(name, "extra-link", src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        elif change == "temp_mode":
            os.fchmod(descriptor, 0o644)
        elif change == "temp_content":
            os.write(descriptor, b"foreign-content")
        return descriptor

    def unlink(name, *, dir_fd=None):
        if change == "cleanup_failure":
            raise PermissionError("fixture_cleanup_failure")
        removed.append(name)
        return real_unlink(name, dir_fd=dir_fd)

    monkeypatch.setattr(os, "stat", lambda *args, **kwargs: project(real_stat(*args, **kwargs), named=True))
    monkeypatch.setattr(os, "fstat", lambda descriptor: project(real_fstat(descriptor)))
    monkeypatch.setattr(os, "open", open_file)
    monkeypatch.setattr(os, "unlink", unlink)
    monkeypatch.setattr(supervisor, "_DOCKER_PRIVATE_LEAVES", {leaf})
    monkeypatch.setattr(supervisor, "_DOCKER_STATE_LEAF", leaf)
    if change == "root_overlap":
        monkeypatch.setattr(os, "getuid", lambda: 0)
        monkeypatch.setattr(os, "getgid", lambda: 0)
    if change in {"stable", "mapped", "after_init"}:
        supervisor._prepare_private_leaf(leaf, initialize_state=True)
        assert created == [True] and removed == temporary_names
        assert list(leaf.iterdir()) == []
        assert not (leaf / "auth.json").exists()
        if change == "after_init":
            with pytest.raises(RuntimeStateError):
                with runtime_state_directory(leaf):
                    post_init.append(True)
        else:
            with runtime_state_directory(leaf):
                pass
    else:
        with pytest.raises((RuntimeStateError, OSError)):
            supervisor._prepare_private_leaf(leaf, initialize_state=True)
        if change in {"temp_replace", "temp_hardlink", "temp_mode", "temp_content", "cleanup_failure"}:
            assert removed == []
            assert (leaf / temporary_names[0]).exists()


@pytest.mark.parametrize("scope", ["custom", "credential", "logs", "default_readonly"])
def test_state_initialization_does_not_write_other_existing_leaves(tmp_path, monkeypatch, scope):
    from docker import supervisor
    leaf = tmp_path.resolve() / scope
    leaf.mkdir(mode=0o700)
    monkeypatch.setattr(supervisor, "_DOCKER_PRIVATE_LEAVES", {leaf})
    if scope == "default_readonly":
        monkeypatch.setattr(supervisor, "_DOCKER_STATE_LEAF", leaf)
    real_open = os.open

    def no_create(name, flags, mode=0o777, *, dir_fd=None):
        assert not flags & os.O_CREAT, "existing non-state/read-only leaf wrote a file"
        return real_open(name, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", no_create)
    supervisor._prepare_private_leaf(leaf, initialize_state=scope != "default_readonly")
    assert list(leaf.iterdir()) == []


@pytest.mark.parametrize("layout", ["managed", "custom", "invalid_timeout"])
def test_run_initializes_only_valid_managed_layout_before_controls(tmp_path, monkeypatch, layout):
    from contextlib import contextmanager
    from docker import supervisor

    calls = []
    config = supervisor.SupervisorConfig(
        data_root=Path("/data/research-web"), state_root=Path("/state/runtime"),
        credential_root=Path("/run/rwb-secrets/private"), project_root=Path("/opt/rwb"),
        runtime_source=Path("/opt/dsh"), python=sys.executable, node="unused",
        startup_timeout=0 if layout == "invalid_timeout" else 1,
    )
    if layout == "custom":
        from dataclasses import replace
        config = replace(config, state_root=tmp_path / "custom")

    @contextmanager
    def guard(*args, **kwargs):
        yield tmp_path

    def prepare(path, *, initialize_state=False):
        calls.append(("prepare", path, initialize_state))

    def stop():
        calls.append(("ownership",))
        raise RuntimeError("fixture_stop_before_children")

    monkeypatch.setattr(supervisor, "runtime_state_directory", guard)
    monkeypatch.setattr(supervisor, "_prepare_private_leaf", prepare)
    monkeypatch.setattr(supervisor, "prepare_controls", lambda *args: calls.append(("controls",)))
    monkeypatch.setattr(supervisor, "_OwnedProcesses", stop)
    monkeypatch.setattr(supervisor, "setup_logging", lambda: calls.append(("logging",)))
    monkeypatch.setattr(supervisor.settings, "LOG_DIR", supervisor.settings.LOG_DIR)
    monkeypatch.setattr(Path, "unlink", lambda *args, **kwargs: None)
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("spawned"))
    assert supervisor.run(config) == 1
    initializations = [i for i, item in enumerate(calls) if item[0] == "prepare" and item[2]]
    if layout == "managed":
        assert len(initializations) == 1
        position = initializations[0]
        assert calls[position][1] == config.state_root
        assert position > calls.index(("logging",))
        assert position < calls.index(("controls",)) < calls.index(("ownership",))
    else:
        assert initializations == []
        if layout == "invalid_timeout":
            assert ("controls",) not in calls


def test_readonly_probe_and_prepare_only_never_initialize(tmp_path, monkeypatch):
    from docker import supervisor

    leaf = tmp_path.resolve() / "runtime"
    leaf.mkdir(mode=0o700)
    config = supervisor.SupervisorConfig(
        data_root=tmp_path, state_root=leaf, project_root=ROOT, runtime_source=tmp_path,
        python=sys.executable, node="unused",
    )
    monkeypatch.setattr(supervisor, "_prepare_private_leaf", lambda *args, **kwargs: pytest.fail("initialized"))
    real_open = os.open

    def no_create(name, flags, mode=0o777, *, dir_fd=None):
        assert not flags & os.O_CREAT
        return real_open(name, flags, mode, dir_fd=dir_fd)

    class ReadonlyHealth:
        def __init__(self, **kwargs):
            pass

        def _runtime_healthy(self):
            return True

        _web_healthy = _runtime_healthy

    monkeypatch.setattr(os, "open", no_create)
    monkeypatch.setattr(supervisor, "ContainerHealth", ReadonlyHealth)
    assert supervisor.real_probe(config, "runtime", 1)
    assert supervisor.real_probe(config, "web", 1)
    monkeypatch.setattr(supervisor, "prepare_controls", lambda *args: None)
    assert supervisor.main(["--prepare-controls-only", "--previous-origin", "http://127.0.0.1:8088"]) == 0
    assert list(leaf.iterdir()) == []
