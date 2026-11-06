"""The public stdlib dispatcher passes only a validated operator knowledge origin."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_workbench_entrypoint import bootstrap, server


@pytest.fixture
def dispatcher(monkeypatch):
    calls = []
    monkeypatch.setattr(bootstrap, "native_python", lambda _root: Path(sys.executable))
    monkeypatch.setattr(
        bootstrap, "native_environment", lambda _root, **_kwargs: {"PATH": "/usr/bin"}
    )
    monkeypatch.setattr(
        server.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or SimpleNamespace(returncode=0),
    )
    monkeypatch.setenv("RESEARCH_WEKNORA_API_KEY", "synthetic-never-forward")
    monkeypatch.setenv("RESEARCH_WEKNORA_JWT", "synthetic-never-forward")
    return calls


def test_origin_passes_canonical_operator_setting_only(dispatcher, monkeypatch, tmp_path):
    monkeypatch.setenv("RESEARCH_WEKNORA_ORIGIN", "https://knowledge.example.test/")
    assert server.dispatch(["serve"], tmp_path) == 0
    environment = dispatcher[-1][1]["env"]
    assert environment["RESEARCH_WEKNORA_ORIGIN"] == "https://knowledge.example.test"
    assert "RESEARCH_WEKNORA_API_KEY" not in environment
    assert "RESEARCH_WEKNORA_JWT" not in environment


def test_invalid_operator_origin_is_not_echoed_or_forwarded(
    dispatcher, monkeypatch, tmp_path, caplog
):
    for value in (
        "https://user:secret@host",
        "https://host?key=secret",
        "http://external.test",
        "https://host/path",
    ):
        monkeypatch.setenv("RESEARCH_WEKNORA_ORIGIN", value)
        assert server.dispatch(["doctor"], tmp_path) == 0
        assert "RESEARCH_WEKNORA_ORIGIN" not in dispatcher[-1][1]["env"]
    assert "secret" not in caplog.text


def test_loopback_origin_is_allowed_without_network(dispatcher, monkeypatch, tmp_path):
    monkeypatch.setenv("RESEARCH_WEKNORA_ORIGIN", "http://127.0.0.1:18080")
    assert server.dispatch(["serve"], tmp_path) == 0
    assert dispatcher[-1][1]["env"]["RESEARCH_WEKNORA_ORIGIN"] == "http://127.0.0.1:18080"


def test_server_doctor_is_cold_and_never_includes_origin_or_secret(tmp_path, monkeypatch):
    import contextlib
    import io

    from app.research_web.multiuser import __main__ as cli

    monkeypatch.setenv("RESEARCH_WEKNORA_ORIGIN", "https://knowledge.example.test")
    missing = tmp_path / "missing-server"
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert cli.main(["doctor", "--root", str(missing), "--json"]) == 0
    report = json.loads(output.getvalue())["knowledge_backend"]
    assert report["enabled"] is True and report["connection"] == "not_checked"
    assert report["runtime_verification"] == "NOT_RUN"
    assert "knowledge.example.test" not in output.getvalue()
    assert not missing.exists()
