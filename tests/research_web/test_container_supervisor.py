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
print("service fixture ready", flush=True)
if mode != "no-cookie-header":
    print("Cookie: dsh-auth-fixture=private-cookie", flush=True)
print("cookie cache ready", flush=True)
if mode != "no-cookie-header" or role == "web":
    print("retry credential private-cookie", flush=True)
print('{"credential":"structured-credential-value"}', flush=True)
print("retry credential structured-credential-value", flush=True)
print(os.environ["FIXTURE_SECRET"], flush=True)
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
            self.end_headers()
            self.wfile.write(json.dumps({"connected": mode != "unhealthy"}).encode())
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
while True:
    if Path(events + ".exit-" + role).exists():
        record("exit")
        raise SystemExit(9)
    server.handle_request()
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
        ': "${RWB_RUNTIME_STATE:=/state}"',
        'test -d "$RWB_DATA_ROOT" && test -w "$RWB_DATA_ROOT"',
        'test -d "$RWB_RUNTIME_STATE" && test -w "$RWB_RUNTIME_STATE"',
        "exec /opt/rwb/venv/bin/python /opt/rwb/docker/supervisor.py",
    ]
