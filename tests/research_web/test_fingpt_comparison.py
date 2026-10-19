"""Offline admission tests; no provider calls or real credential resolution."""

import json

import pytest

from research_workbench_entrypoint.fingpt_compare import ComparisonError, Experiment


def test_settings_only_store_nonsecret_metadata(tmp_path):
    calls = []

    def credential(home, request):
        calls.append((home, request))
        return {"configured": bool(calls)} if request["op"] == "describe" else {}

    exp = Experiment.initialize(tmp_path / "case", credential=credential)
    exp.configure_lite("mimo-test", "fixture-secret")
    raw = (exp.root / "experiment.json").read_text()
    assert "fixture-secret" not in raw
    assert calls[-1][1]["op"] == "set"
    assert calls[-1][0] == exp.root / "credentials/lite"
    assert exp.status()["lite"]["configured"]
    assert "fixture-secret" not in json.dumps(exp.status())


def test_all_groups_ready_and_review_bound_before_any_submission(tmp_path):
    exp = Experiment.initialize(tmp_path / "case", credential=lambda *_: {"configured": False})
    with pytest.raises(ComparisonError, match="not_ready"):
        exp.admit_sequence()
    assert not (exp.root / "sequence.json").exists()


def test_attempt_is_durable_and_never_automatically_reissued(tmp_path):
    exp = Experiment.initialize(tmp_path / "case", credential=lambda *_: {"configured": True})
    attempt = exp.reserve("A")
    assert attempt["status"] == "submission_intent"
    assert attempt["idempotency_key"]
    with pytest.raises(ComparisonError, match="already_reserved"):
        exp.reserve("A")


def test_settings_only_approval_never_admits_real_research(tmp_path):
    from research_workbench_entrypoint.fingpt_compare import atomic, code_binding, review_valid

    exp = Experiment.initialize(tmp_path / "case", credential=lambda *_: {"configured": True})
    config = json.loads((exp.root / "experiment.json").read_text())
    config["lite"]["model"] = "fixture-model"
    atomic(exp.root / "experiment.json", config)
    atomic(exp.root / "prepared.json", {"fixture": True})
    atomic(
        exp.root / "review.json",
        {"status": "APPROVE", "scopes": ["settings"], "code_binding": code_binding()},
    )
    assert review_valid(exp.root, "settings")
    assert not review_valid(exp.root, "execution")
    with pytest.raises(ComparisonError, match="not_ready"):
        exp.admit_sequence()


def test_no_symlink_or_unknown_group(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    (tmp_path / "alias").symlink_to(target)
    with pytest.raises(ComparisonError):
        Experiment.initialize(tmp_path / "alias")
    exp = Experiment.initialize(tmp_path / "case")
    with pytest.raises(ComparisonError):
        exp.reserve("production")


def test_production_credential_seam_is_read_only(tmp_path):
    from research_workbench_entrypoint.fingpt_compare_worker import flash_credential

    calls = []
    backend = lambda home, req: calls.append(req) or {"configured": True}
    for op in ("set", "unset"):
        with pytest.raises(ComparisonError):
            flash_credential(tmp_path, {"op": op, "ref": "RESEARCH_DSH_API_KEY"}, backend)
    assert flash_credential(tmp_path, {"op": "describe", "ref": "RESEARCH_DSH_API_KEY"}, backend)[
        "configured"
    ]
    assert len(calls) == 1


def test_flash_preflight_requires_actual_credentials_and_exact_model():
    from research_workbench_entrypoint.fingpt_compare_worker import assert_flash_ready

    valid = {
        "connected": True,
        "owned_runtime": True,
        "health_check_passed": True,
        "credential_configured": True,
        "credential_code": None,
        "provider": "deepseek-official",
        "model": "deepseek-flash",
    }
    assert_flash_ready(valid)
    for key, value in [
        ("credential_configured", False),
        ("credential_configured", None),
        ("credential_code", "unavailable"),
        ("model", "other-model"),
        ("health_check_passed", False),
    ]:
        with pytest.raises(ComparisonError, match="flash_not_ready"):
            assert_flash_ready({**valid, key: value})


def test_isolated_bootstrap_cookie_exchange_binds_owned_pid_and_original_record(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from research_workbench_entrypoint.fingpt_compare import atomic
    from research_workbench_entrypoint.fingpt_compare_worker import complete_auth

    root = tmp_path / "case"
    data = root / "groups/A/research-data"
    auth = data / "runtime/auth.json"
    auth.parent.mkdir(parents=True, mode=0o700)
    pin = root / "sources/current/runtimes/research_web.json"
    pin.parent.mkdir(parents=True, mode=0o700)
    atomic(pin, {"dsh": {"commit": "a" * 40}})
    record = {
        "authority": "127.0.0.1:13081",
        "cwd": str(data / "runtime/work"),
        "source_commit": "a" * 40,
        "pid": 1234,
        "version": "test",
        "bootstrap_token": "b" * 43,
    }
    atomic(auth, record)
    monkeypatch.setattr(
        "research_workbench_entrypoint.fingpt_compare_worker.assert_owned_listener", lambda *_: None
    )
    child = SimpleNamespace(pid=1234, poll=lambda: None)
    complete_auth(root, "A", child, exchange=lambda *_: "dsh-auth-fixture=fixture")
    final = json.loads(auth.read_text())
    assert "bootstrap_token" not in final and final["cookie"].startswith("dsh-auth-")
    atomic(auth, record)

    def raced(*_):
        atomic(auth, {**record, "pid": 9999})
        return "dsh-auth-fixture=fixture"

    with pytest.raises(ComparisonError, match="identity_changed"):
        complete_auth(root, "A", child, exchange=raced)


def test_loopback_auth_origin_redaction_and_one_use_grant(tmp_path):
    import http.client
    import socket
    import threading

    from research_workbench_entrypoint.fingpt_compare import build_server

    exp = Experiment.initialize(tmp_path / "case", credential=lambda *_: {"configured": False})
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = build_server(exp, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{port}"

    def request(path, body=None, headers=None):
        con = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            con.request("POST" if body is not None else "GET", path, body, headers or {})
            response = con.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            con.close()

    try:
        assert request("/api/status")[0] == 403
        grant = json.loads((exp.root / "browser-grant.json").read_text())["bootstrap"]
        assert (
            request(
                "/bootstrap", b"", {"Origin": "https://evil.test", "X-Comparison-Bootstrap": grant}
            )[0]
            == 409
        )
        status, headers, _ = request(
            "/bootstrap", b"", {"Origin": origin, "X-Comparison-Bootstrap": grant}
        )
        assert status == 200
        cookie = headers["Set-Cookie"].split(";")[0]
        assert "HttpOnly" in headers["Set-Cookie"]
        assert request("/api/status", headers={"Cookie": cookie})[0] == 200
        assert (
            request("/bootstrap", b"", {"Origin": origin, "X-Comparison-Bootstrap": grant})[0]
            == 409
        )
        status, _, body = request(
            "/api/lite",
            b'{"model":"bad value","api_key":"fixture-secret"}',
            {"Cookie": cookie, "Origin": origin, "Content-Type": "application/json"},
        )
        assert status == 409 and b"fixture-secret" not in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_creation_handle_returned_before_fallible_identity_probe(monkeypatch):
    import subprocess
    import sys

    from research_workbench_entrypoint import fingpt_compare_worker as worker

    children = []
    try:
        with monkeypatch.context() as patch:

            def unavailable(_child):
                raise OSError("fixture_process_table_unavailable")

            patch.setattr(worker, "owned_members", unavailable)
            children.append(
                worker.start_owned(
                    [sys.executable, "-c", "import time;time.sleep(30)"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
            assert children[0].poll() is None
        worker.stop_owned(children)
        assert children[0].poll() is not None
    finally:
        worker.stop_owned(children)


def test_owned_group_retirement_includes_orphan_child_ignoring_term():
    import subprocess
    import sys

    from research_workbench_entrypoint.fingpt_compare_worker import (
        owned_members,
        start_owned,
        stop_owned,
    )

    child_code = "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)"
    code = f'import subprocess,sys,os;p=subprocess.Popen([sys.executable,"-c",{child_code!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);print(p.pid,flush=True);os._exit(0)'
    leader = start_owned(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    try:
        assert leader.stdout.readline().strip().isdigit()
        leader.wait(timeout=3)
        assert owned_members(leader)
        stop_owned([leader])
        assert not owned_members(leader)
    finally:
        stop_owned([leader])
        leader.stdout.close()


def test_deadline_escalation_does_not_wait_for_blocked_cancel_http():
    import subprocess
    import sys
    import threading

    from research_workbench_entrypoint.fingpt_compare_worker import (
        arm_deadline,
        start_owned,
        stop_owned,
    )

    ready = threading.Event()
    blocked = threading.Event()
    child = start_owned(
        [
            sys.executable,
            "-c",
            "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    timer = arm_deadline([child], lambda: blocked.wait(10), ready, seconds=0.1)
    try:
        assert ready.wait(timeout=2)
        timer.join(timeout=6)
        assert not timer.is_alive()
        assert child.poll() is not None
    finally:
        blocked.set()
        timer.cancel()
        stop_owned([child])
