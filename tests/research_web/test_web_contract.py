"""Shared standard-library Research Web runtime contracts."""

from __future__ import annotations

import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from research_workbench_entrypoint.web_contract import (
    HttpFact,
    ProcessFact,
    classify_python_environment,
    command_line,
    http_get,
    node_version_issue,
    pid_exists,
    port_listening,
    probe_process,
    proxy_warnings,
)


@pytest.mark.parametrize(
    ("value", "issue"),
    [
        ("v22.19.0", None),
        ("22.99.1", None),
        ("v24.0.0", None),
        ("v24.999.0", None),
        ("v22.18.9", "node_version_unsupported"),
        ("v23.11.0", "node_version_unsupported"),
        ("v25.0.0", "node_version_unsupported"),
        ("not-a-version", "node_version_invalid"),
        ("", "node_version_invalid"),
        (None, "node_version_invalid"),
    ],
)
def test_node_version_issue_matches_install_contract(value: str | None, issue: str | None) -> None:
    assert node_version_issue(value) == issue


def _write_interpreter(project_root: Path, platform_name: str) -> Path:
    relative = "Scripts/python.exe" if platform_name == "nt" else "bin/python"
    interpreter = project_root / ".venv" / relative
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_text("fixture", encoding="utf-8")
    interpreter.chmod(0o755)
    return interpreter


@pytest.mark.parametrize(
    ("platform_name", "relative"),
    [("posix", "bin/python"), ("nt", "Scripts/python.exe")],
)
def test_python_environment_selects_platform_interpreter_and_accepts_exact_marker(
    tmp_path: Path, platform_name: str, relative: str
) -> None:
    interpreter = _write_interpreter(tmp_path, platform_name)
    marker = tmp_path / ".venv" / ".rwb-web-environment.json"
    marker.write_text(
        json.dumps({"schema_version": 1, "owner": "research-workbench-web-installer"}),
        encoding="utf-8",
    )

    fact = classify_python_environment(tmp_path, platform_name=platform_name)

    assert fact.issue is None
    assert fact.interpreter == tmp_path / ".venv" / relative
    assert fact.interpreter == interpreter
    assert fact.marker_valid is True


def test_python_environment_distinguishes_missing_incomplete_and_unusable(
    tmp_path: Path,
) -> None:
    missing = classify_python_environment(tmp_path, platform_name="posix")
    assert missing.issue == "python_environment_missing"
    assert missing.marker_valid is False

    environment = tmp_path / ".venv"
    environment.mkdir()
    incomplete = classify_python_environment(tmp_path, platform_name="posix")
    assert incomplete.issue == "python_environment_incomplete"

    (environment / ".rwb-web-environment.json").write_text(
        '{"schema_version":1,"owner":"research-workbench-web-installer"}',
        encoding="utf-8",
    )
    binary = environment / "bin" / "python"
    binary.parent.mkdir()
    binary.write_text("not executable", encoding="utf-8")
    binary.chmod(0o644)
    unusable = classify_python_environment(tmp_path, platform_name="posix")
    assert unusable.issue == "python_environment_unusable"
    assert unusable.marker_valid is True


@pytest.mark.parametrize(
    "marker",
    [
        "not-json",
        "[]",
        '"not-an-object"',
        "null",
        '{"owner":"research-workbench-web-installer"}',
        '{"schema_version":1}',
        '{"schema_version":true,"owner":"research-workbench-web-installer"}',
        '{"schema_version":1.0,"owner":"research-workbench-web-installer"}',
        '{"schema_version":"1","owner":"research-workbench-web-installer"}',
        '{"schema_version":2,"owner":"research-workbench-web-installer"}',
        '{"schema_version":1,"owner":true}',
        '{"schema_version":1,"owner":1}',
        '{"schema_version":1,"owner":"someone-else"}',
        ('{"schema_version":1,"owner":"research-workbench-web-installer",' '"unexpected":true}'),
    ],
)
def test_python_environment_rejects_malformed_or_non_exact_marker(
    tmp_path: Path, marker: str
) -> None:
    _write_interpreter(tmp_path, "posix")
    (tmp_path / ".venv" / ".rwb-web-environment.json").write_text(marker, encoding="utf-8")

    fact = classify_python_environment(tmp_path, platform_name="posix")

    assert fact.issue == "python_environment_incomplete"
    assert fact.marker_valid is False


@pytest.mark.parametrize(
    "environment",
    [
        {"HTTP_PROXY": "http://proxy.invalid", "NO_PROXY": "127.0.0.1,localhost"},
        {"https_proxy": "http://proxy.invalid", "no_proxy": "LOCALHOST, 127.0.0.1"},
        {"HTTPS_PROXY": "http://proxy.invalid", "NO_PROXY": "*"},
        {"NO_PROXY": "example.com"},
    ],
)
def test_proxy_warning_accepts_both_loopback_hosts_wildcard_or_no_proxy(
    environment: dict[str, str],
) -> None:
    assert proxy_warnings(environment) == []


@pytest.mark.parametrize(
    "environment",
    [
        {"HTTPS_PROXY": "http://secret:secret@127.0.0.1:7890"},
        {
            "http_proxy": "http://secret:secret@127.0.0.1:7890",
            "no_proxy": "localhost",
        },
        {"HTTP_PROXY": "http://proxy.invalid", "NO_PROXY": "127.0.0.1"},
    ],
)
def test_proxy_warning_is_allowlisted_and_never_contains_proxy_values(
    environment: dict[str, str],
) -> None:
    warnings = proxy_warnings(environment)

    assert warnings == ["loopback_proxy_bypass_missing"]
    assert "secret" not in repr(warnings)
    assert "127.0.0.1:7890" not in repr(warnings)


def test_windows_process_probe_uses_powershell_without_a_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    class Result:
        def __init__(self, returncode: int, stdout: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout

    results = iter(
        [
            Result(0),
            Result(0, "python.exe -m app.research_web.main:app\n"),
            Result(0),
            Result(0, "python.exe -m app.research_web.main:app\n"),
        ]
    )

    def run(command: list[str], **options: object) -> Result:
        calls.append((command, options))
        return next(results)

    monkeypatch.setattr("subprocess.run", run)

    fact = probe_process(4321, platform_name="nt")

    assert fact == ProcessFact(
        state="alive",
        command_line="python.exe -m app.research_web.main:app",
        issue=None,
    )
    assert pid_exists(4321, platform_name="nt") is True
    assert all(
        call[0][:4] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"]
        for call in calls
    )
    assert all(call[1]["shell"] is False for call in calls)
    assert all(int(call[1]["timeout"]) <= 5 for call in calls)


def test_windows_missing_pid_and_probe_failure_are_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        returncode = 1
        stdout = ""

    monkeypatch.setattr("subprocess.run", lambda *_args, **_kwargs: Result())
    assert probe_process(4321, platform_name="nt") == ProcessFact("missing", None, None)
    assert pid_exists(4321, platform_name="nt") is False

    def fail(*_args: object, **_kwargs: object) -> object:
        raise OSError("sensitive operating system detail")

    monkeypatch.setattr("subprocess.run", fail)
    fact = probe_process(4321, platform_name="nt")
    assert fact == ProcessFact("inaccessible", None, "process_probe_failed")
    assert "sensitive" not in repr(fact)
    assert pid_exists(4321, platform_name="nt") is True
    assert command_line(4321, platform_name="nt") == ""


def test_posix_zombie_is_missing_and_access_denied_is_inaccessible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        returncode = 0
        stdout = "Z+\n"

    monkeypatch.setattr(os, "kill", lambda _pid, _signal: None)
    monkeypatch.setattr("subprocess.run", lambda *_args, **_kwargs: Result())
    assert probe_process(4321, platform_name="posix") == ProcessFact("missing", None, None)
    assert pid_exists(4321, platform_name="posix") is False

    def denied(_pid: int, _signal: int) -> None:
        raise PermissionError("private detail")

    monkeypatch.setattr(os, "kill", denied)
    fact = probe_process(4321, platform_name="posix")
    assert fact == ProcessFact("inaccessible", None, "process_access_denied")
    assert "private detail" not in repr(fact)


def test_posix_command_line_uses_bounded_non_shell_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    class Result:
        def __init__(self, stdout: str) -> None:
            self.returncode = 0
            self.stdout = stdout

    results = iter([Result("S+\n"), Result("python -m uvicorn app.research_web.main:app\n")])
    monkeypatch.setattr(os, "kill", lambda _pid, _signal: None)

    def run(command: list[str], **options: object) -> Result:
        calls.append((command, options))
        return next(results)

    monkeypatch.setattr("subprocess.run", run)

    assert command_line(4321, platform_name="posix") == (
        "python -m uvicorn app.research_web.main:app"
    )
    assert calls[0][0] == ["ps", "-p", "4321", "-o", "stat="]
    assert calls[1][0] == ["ps", "-p", "4321", "-o", "command="]
    assert all(call[1]["shell"] is False for call in calls)
    assert all(int(call[1]["timeout"]) <= 5 for call in calls)


def test_port_listening_uses_only_the_requested_ephemeral_loopback_port() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = int(listener.getsockname()[1])
    try:
        assert port_listening(port) is True
    finally:
        listener.close()

    assert port_listening(port) is False


class _HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/large":
            body = b"x" * (2 * 1024 * 1024 + 1)
        else:
            body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


@pytest.fixture
def local_http_server() -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HttpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_get_returns_a_typed_bounded_loopback_fact(
    local_http_server: tuple[ThreadingHTTPServer, int],
) -> None:
    _server, port = local_http_server

    fact = http_get(port, "/health")

    assert fact == HttpFact(200, "application/json; charset=utf-8", b'{"ok":true}', None)


def test_http_get_rejects_responses_larger_than_two_mib(
    local_http_server: tuple[ThreadingHTTPServer, int],
) -> None:
    _server, port = local_http_server

    fact = http_get(port, "/large")

    assert fact.status == 200
    assert fact.body == b""
    assert fact.issue == "http_response_too_large"


def test_http_get_returns_only_a_stable_connection_issue() -> None:
    temporary = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    temporary.bind(("127.0.0.1", 0))
    port = int(temporary.getsockname()[1])
    temporary.close()

    fact = http_get(port, "/health")

    assert fact == HttpFact(None, None, b"", "http_connection_failed")
    assert "refused" not in repr(fact).lower()


def test_http_get_returns_a_stable_protocol_issue_for_malformed_http() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = int(listener.getsockname()[1])

    def serve_malformed_response() -> None:
        connection, _address = listener.accept()
        try:
            connection.recv(4096)
            connection.sendall(b"not-http\r\n\r\n")
        finally:
            connection.close()
            listener.close()

    thread = threading.Thread(target=serve_malformed_response, daemon=True)
    thread.start()
    try:
        fact = http_get(port, "/health")
    finally:
        thread.join(timeout=2)

    assert fact == HttpFact(None, None, b"", "http_protocol_failed")
