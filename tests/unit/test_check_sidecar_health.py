"""Tests for the isolated desktop sidecar health-check helper."""

from __future__ import annotations

import importlib.util
import logging
import socket
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "desktop" / "check_sidecar_health.py"


def load_helper_module():
    spec = importlib.util.spec_from_file_location("check_sidecar_health", HELPER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HealthHandler(BaseHTTPRequestHandler):
    """Serve a minimal successful health endpoint for the helper."""

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def health_server() -> Iterator[int]:
    """Run a local HTTP health endpoint and yield its ephemeral port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


class FakeProcess:
    """Capture lifecycle calls without starting or stopping a real executable."""

    def __init__(self, command: list[str], **kwargs: object) -> None:
        self.command = command
        self.kwargs = kwargs
        self.pid = 4312
        self.terminated = False
        self.killed = False
        self.wait_calls: list[float | None] = []
        self.time_out_once = False
        output = kwargs.get("stdout")
        if output is not None:
            output.write(b"sidecar stdout\n")
            output.flush()

    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        if self.time_out_once:
            self.time_out_once = False
            raise subprocess.TimeoutExpired(self.command, timeout)
        return 0

    def kill(self) -> None:
        self.killed = True


def test_sidecar_health_check_returns_zero_after_first_http_200(monkeypatch, tmp_path):
    helper = load_helper_module()
    started: list[FakeProcess] = []

    def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
        process = FakeProcess(command, **kwargs)
        started.append(process)
        return process

    monkeypatch.setattr(helper.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(helper, "is_windows", lambda: False, raising=False)
    monkeypatch.setattr(helper.os, "getpgid", lambda pid: pid, raising=False)
    monkeypatch.setattr(helper.os, "killpg", lambda pgid, sig: None, raising=False)
    monkeypatch.setattr(helper, "wait_for_port_release", lambda port, logger: True, raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://desktop_user:secret@127.0.0.1:55432/alphafoundry"
    )
    log_file = tmp_path / "health-smoke.log"

    with health_server() as port:
        result = helper.run_health_check(
            executable="sidecar-under-test",
            port=port,
            timeout_seconds=1,
            log_file=log_file,
        )

    assert result == 0
    assert len(started) == 1
    assert started[0].command == [
        "sidecar-under-test",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    assert started[0].kwargs["env"]["DATABASE_URL"].startswith("postgresql+psycopg://")
    assert started[0].kwargs["stderr"] is subprocess.STDOUT
    assert started[0].kwargs["start_new_session"] is True
    assert "sidecar stdout" in log_file.read_text(encoding="utf-8")


def test_sidecar_health_check_exits_nonzero_and_stops_only_its_child(monkeypatch, tmp_path):
    helper = load_helper_module()
    started: list[FakeProcess] = []

    def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
        process = FakeProcess(command, **kwargs)
        started.append(process)
        return process

    def refused_request(*args: object, **kwargs: object) -> None:
        raise URLError("sidecar is not ready")

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    log_file = tmp_path / "health-smoke.log"
    monkeypatch.setattr(helper.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(helper, "is_windows", lambda: False, raising=False)
    monkeypatch.setattr(helper.LOCAL_HTTP_OPENER, "open", refused_request)
    monkeypatch.setattr(helper.os, "getpgid", lambda pid: pid, raising=False)
    monkeypatch.setattr(helper.os, "killpg", lambda pgid, sig: None, raising=False)
    monkeypatch.setattr(helper, "wait_for_port_release", lambda port, logger: True, raising=False)

    with pytest.raises(SystemExit) as error:
        helper.main(
            [
                "--executable",
                "sidecar-under-test",
                "--port",
                str(port),
                "--timeout-seconds",
                "0.01",
                "--log-file",
                str(log_file),
            ]
        )

    assert error.value.code == 1
    assert len(started) == 1
    assert started[0].kwargs["start_new_session"] is True
    assert "did not become healthy" in log_file.read_text(encoding="utf-8")


def test_posix_cleanup_terminates_only_the_helper_process_group(monkeypatch):
    helper = load_helper_module()
    process = FakeProcess(["sidecar-under-test"])
    process.time_out_once = True
    term_signal = object()
    kill_signal = object()
    signals: list[tuple[int, object]] = []
    monkeypatch.setattr(helper, "is_windows", lambda: False, raising=False)
    monkeypatch.setattr(helper.signal, "SIGTERM", term_signal)
    monkeypatch.setattr(helper.signal, "SIGKILL", kill_signal, raising=False)
    monkeypatch.setattr(helper.os, "getpgid", lambda pid: 9876, raising=False)
    monkeypatch.setattr(
        helper.os,
        "killpg",
        lambda pgid, sig: signals.append((pgid, sig)),
        raising=False,
    )
    monkeypatch.setattr(helper, "wait_for_port_release", lambda port, logger: True, raising=False)

    stopped = helper.stop_child(process, port=8765, logger=logging.getLogger("test.sidecar"))

    assert stopped is True
    assert signals == [(9876, term_signal), (9876, kill_signal)]
    assert process.wait_calls == [helper.CHILD_STOP_TIMEOUT_SECONDS] * 2


def test_windows_cleanup_uses_taskkill_for_only_the_helper_pid(monkeypatch):
    helper = load_helper_module()
    process = FakeProcess(["sidecar-under-test"])
    commands: list[list[str]] = []
    monkeypatch.setattr(helper, "is_windows", lambda: True, raising=False)
    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command) or subprocess.CompletedProcess(command, 0),
    )
    monkeypatch.setattr(helper, "wait_for_port_release", lambda port, logger: True, raising=False)

    stopped = helper.stop_child(process, port=8765, logger=logging.getLogger("test.sidecar"))

    assert stopped is True
    assert commands == [["taskkill", "/PID", "4312", "/T", "/F"]]
    assert process.wait_calls == [helper.CHILD_STOP_TIMEOUT_SECONDS]


def test_port_release_is_confirmed_by_connection_refusal(monkeypatch):
    helper = load_helper_module()

    def refused_connection(*args: object, **kwargs: object) -> None:
        raise ConnectionRefusedError("sidecar port is closed")

    monkeypatch.setattr(helper.socket, "create_connection", refused_connection)

    assert helper.wait_for_port_release(8765, logging.getLogger("test.sidecar")) is True


def test_port_release_timeout_is_not_treated_as_a_closed_port(monkeypatch):
    helper = load_helper_module()

    def timed_out_connection(*args: object, **kwargs: object) -> None:
        raise socket.timeout("connection timed out")

    monkeypatch.setattr(helper, "PORT_RELEASE_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(helper.socket, "create_connection", timed_out_connection)

    assert helper.wait_for_port_release(8765, logging.getLogger("test.sidecar")) is False


def test_posix_process_lookup_still_fails_when_sidecar_port_remains_open(monkeypatch):
    helper = load_helper_module()
    process = FakeProcess(["sidecar-under-test"])
    checked_ports: list[int] = []
    monkeypatch.setattr(
        helper.os,
        "killpg",
        lambda pgid, sig: (_ for _ in ()).throw(ProcessLookupError),
        raising=False,
    )
    monkeypatch.setattr(
        helper,
        "wait_for_port_release",
        lambda port, logger: checked_ports.append(port) or False,
    )

    stopped = helper.stop_posix_process_group(
        process,
        port=8765,
        logger=logging.getLogger("test.sidecar"),
        process_group=9876,
    )

    assert stopped is False
    assert checked_ports == [8765]


def test_posix_permission_error_checks_that_the_sidecar_port_is_released(monkeypatch):
    helper = load_helper_module()
    process = FakeProcess(["sidecar-under-test"])
    checked_ports: list[int] = []
    monkeypatch.setattr(
        helper.os,
        "killpg",
        lambda pgid, sig: (_ for _ in ()).throw(PermissionError),
        raising=False,
    )
    monkeypatch.setattr(
        helper,
        "wait_for_port_release",
        lambda port, logger: checked_ports.append(port) or True,
    )

    stopped = helper.stop_posix_process_group(
        process,
        port=8765,
        logger=logging.getLogger("test.sidecar"),
        process_group=9876,
    )

    assert stopped is True
    assert checked_ports == [8765]
