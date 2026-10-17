"""Explicit server commands keep inspection read-only and serving opt-in."""

import importlib
import io
import json
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.research_web.multiuser import __main__ as cli
from app.research_web.multiuser.accounts import AccountStore

PASSWORD = "long private admin password"


@pytest.mark.parametrize("value", [0, 5, True, False, "3", None, 2.5])
def test_resident_capacity_rejects_invalid_or_unbounded_settings(value):
    with pytest.raises(cli.ServerCommandError, match="server_capacity_invalid"):
        cli._configured_capacity({"max_additional_instances": value})


def test_resident_capacity_preserves_default_and_doctor_reports_explicit_limit(tmp_path, output):
    assert cli._configured_capacity({}) == 1
    root = tmp_path / "server"
    root.mkdir(mode=0o700)
    path = root / "resident.json"
    path.write_text(json.dumps({"max_additional_instances": 3}))
    path.chmod(0o600)
    before = path.read_bytes(), path.stat().st_mtime_ns
    assert cli.main(["doctor", "--root", str(root), "--json"]) == 0
    report = json.loads(output.readouterr().out)
    assert report["capacity"] == {
        "status": "configured",
        "additional_instances": 3,
        "total_instances": 4,
    }
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


@pytest.mark.parametrize("case", ["permissions", "link", "large", "invalid", "boolean"])
def test_doctor_capacity_rejects_unsafe_config_without_exposing_contents(tmp_path, output, case):
    root = tmp_path / "server"
    root.mkdir(mode=0o700)
    path = root / "resident.json"
    path.write_text(
        json.dumps({"max_additional_instances": 3, "private_marker": "never-print-this"})
    )
    path.chmod(0o600)
    if case == "permissions":
        path.chmod(0o644)
    elif case == "link":
        target = tmp_path / "target"
        path.rename(target)
        path.symlink_to(target)
    elif case == "large":
        path.write_text("never-print-this" * 5000)
    elif case == "invalid":
        path.write_text("never-print-this")
    else:
        path.write_text(json.dumps({"max_additional_instances": True}))
    before = path.read_bytes()
    assert cli.main(["doctor", "--root", str(root), "--json"]) == 0
    result = output.readouterr()
    assert json.loads(result.out)["capacity"] == {"status": "invalid"}
    assert "never-print-this" not in result.out + result.err
    assert path.read_bytes() == before


@pytest.fixture
def output(monkeypatch):
    """The project intentionally disables pytest's global capture plugin."""
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    def readouterr():
        result = SimpleNamespace(out=stdout.getvalue(), err=stderr.getvalue())
        for stream in (stdout, stderr):
            stream.seek(0)
            stream.truncate()
        return result

    return SimpleNamespace(readouterr=readouterr)


@pytest.fixture
def interactive(monkeypatch):
    prompts = []
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: prompts.append(prompt) or PASSWORD)
    return prompts


def snapshot(root):
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_mode,
            path.stat().st_size,
            path.stat().st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
        for path in root.rglob("*")
    }


def test_help_does_not_import_runtime_or_create_paths(tmp_path, monkeypatch, output):
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(SystemExit) as result:
        cli.main(["--help"])
    assert result.value.code == 0
    assert "doctor" in output.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_init_uses_two_hidden_prompts_and_refuses_reinitialization(tmp_path, interactive, output):
    root = tmp_path / "server"
    assert cli.main(["init", "--root", str(root), "--username", "ADMIN"]) == 0
    assert len(interactive) == 2
    assert AccountStore(root).list_users()[0].public()["role"] == "admin"
    assert cli.main(["init", "--root", str(root), "--username", "other"]) == 1
    assert len(interactive) == 2
    output = output.readouterr()
    assert "server_already_initialized" in output.err
    assert PASSWORD not in output.out + output.err
    assert (root / "logs").stat().st_mode & 0o777 == 0o700
    assert (root / "logs/server.jsonl").stat().st_mode & 0o777 == 0o600


def test_init_mismatch_and_noninteractive_password_fail_safely(tmp_path, monkeypatch, output):
    answers = iter((PASSWORD, "different private password"))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(answers))
    root = tmp_path / "server"
    assert cli.main(["init", "--root", str(root), "--username", "admin"]) == 1
    assert "password_confirmation_mismatch" in output.readouterr().err
    assert not (root / "accounts.sqlite3").exists()
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert cli.main(["init", "--root", str(root), "--username", "admin"]) == 1
    assert "password_tty_required" in output.readouterr().err


def test_doctor_missing_root_and_existing_database_never_write(tmp_path, interactive, output):
    root = tmp_path / "server"
    assert cli.main(["doctor", "--root", str(root), "--json"]) == 0
    report = json.loads(output.readouterr().out)
    assert report["status"] == "not_configured"
    assert report["accounts"]["status"] == "not_configured"
    assert not root.exists()
    assert cli.main(["init", "--root", str(root), "--username", "admin"]) == 0
    output.readouterr()
    before = snapshot(root)
    assert cli.main(["doctor", "--root", str(root), "--json"]) == 0
    report = json.loads(output.readouterr().out)
    assert report["accounts"]["active_admins"] == 1
    assert report["source"]["status"] == "not_configured"
    assert report["status"] != "ready"
    assert snapshot(root) == before


def test_doctor_refuses_wal_without_reading_stale_admin_count(tmp_path, output):
    root = tmp_path / "server"
    store = AccountStore(root)
    store.create_user("admin", PASSWORD, "admin")
    with sqlite3.connect(store.path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("INSERT INTO login_failures VALUES ('global', 1000, 1)")
        db.commit()
        before = snapshot(root)
        assert cli.main(["doctor", "--root", str(root), "--json"]) == 0
        report = json.loads(output.readouterr().out.splitlines()[-1])
        assert report["accounts"]["status"] == "unknown"
        assert report["accounts"]["code"] == "database_busy"
        assert report["accounts"]["active_admins"] is None
        assert snapshot(root) == before


def test_doctor_rejects_symlink_and_insecure_roots(tmp_path, output):
    root = tmp_path / "server"
    root.mkdir(mode=0o755)
    assert cli.main(["doctor", "--root", str(root), "--json"]) == 0
    assert json.loads(output.readouterr().out)["accounts"]["status"] == "unsafe"
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    assert cli.main(["doctor", "--root", str(alias), "--json"]) == 0
    assert json.loads(output.readouterr().out)["accounts"]["status"] == "unsafe"


def test_serve_rejects_other_platform_before_creating_state(tmp_path, monkeypatch, output):
    monkeypatch.setattr(cli.platform, "system", lambda: "Linux")
    root = tmp_path / "server"
    assert (
        cli.main(
            [
                "serve",
                "--root",
                str(root),
                "--origin",
                "http://127.0.0.1:8089",
                "--source",
                str(tmp_path / "source"),
                "--node",
                "/usr/bin/node",
            ]
        )
        == 1
    )
    assert "server_platform_unsupported" in output.readouterr().err
    assert not root.exists()


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com",
        "http://0.0.0.0:8089",
        "https://mini.tailabc.ts.net/",
        "https://mini.tailabc.ts.net/path",
        "https://mini.tailabc.ts.net?owner=bob",
    ],
)
def test_serve_rejects_invalid_origin_before_runtime(tmp_path, monkeypatch, origin, output):
    monkeypatch.setattr(cli.platform, "system", lambda: "Darwin")
    root = tmp_path / "server"
    assert (
        cli.main(
            [
                "serve",
                "--root",
                str(root),
                "--origin",
                origin,
                "--source",
                str(tmp_path / "source"),
                "--node",
                "/usr/bin/node",
            ]
        )
        == 1
    )
    assert "server_origin_invalid" in output.readouterr().err
    assert not root.exists()


def test_serve_builds_lazy_pool_with_loopback_and_no_access_logs(
    tmp_path, monkeypatch, interactive, output
):
    root = tmp_path / "server"
    assert cli.main(["init", "--root", str(root), "--username", "admin"]) == 0
    source = tmp_path / "source"
    entry = source / "apps/cli/lib/bin.js"
    entry.parent.mkdir(parents=True)
    entry.write_text("// built CLI")
    node = tmp_path / "node"
    node.write_text("#!/bin/sh\n")
    node.chmod(0o700)
    calls = {}

    class FakePool:
        def __init__(self, config):
            calls["config"] = config

        async def close(self):
            calls["close_count"] = calls.get("close_count", 0) + 1

    runtime = importlib.import_module("app.research_web.multiuser.runtime")
    gateway = importlib.import_module("app.research_web.multiuser.gateway")
    monkeypatch.setattr(cli.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(runtime, "RuntimePool", FakePool)
    monkeypatch.setattr(
        gateway,
        "create_gateway",
        lambda accounts, pool, **kwargs: calls.setdefault("app", object()),
    )
    monkeypatch.setitem(
        sys.modules, "uvicorn", SimpleNamespace(run=lambda app, **kwargs: calls.update(kwargs))
    )
    assert (
        cli.main(
            [
                "serve",
                "--root",
                str(root),
                "--origin",
                "http://127.0.0.1:8089",
                "--source",
                str(source),
                "--node",
                str(node),
            ]
        )
        == 0
    )
    assert calls["host"] == "127.0.0.1" and calls["port"] == 8089
    assert calls["access_log"] is False
    assert calls["proxy_headers"] is False
    assert calls["config"].max_instances == 2
    assert calls["config"].root == root
    assert calls["config"].python == sys.executable
    assert calls["close_count"] == 1
    output.readouterr()

    def failed_start(*args, **kwargs):
        raise OSError("private-cookie-and-path-must-not-escape")

    sys.modules["uvicorn"].run = failed_start
    assert (
        cli.main(
            [
                "serve",
                "--root",
                str(root),
                "--origin",
                "http://127.0.0.1:8089",
                "--source",
                str(source),
                "--node",
                str(node),
            ]
        )
        == 1
    )
    assert calls["close_count"] == 2
    captured = output.readouterr()
    assert captured.err == "server_command_failed\n"
    assert "private-cookie" not in captured.out + captured.err


def test_reset_admin_revokes_existing_cookie_and_refuses_user_accounts(
    tmp_path, interactive, output
):
    root = tmp_path / "server"
    assert cli.main(["init", "--root", str(root), "--username", "admin"]) == 0
    store = AccountStore(root)
    token, _ = store.login("admin", PASSWORD)
    store.create_user("alice", PASSWORD)
    assert cli.main(["reset-admin", "--root", str(root), "--username", "admin"]) == 0
    assert store.authenticate(token) is None
    assert cli.main(["reset-admin", "--root", str(root), "--username", "alice"]) == 1
    assert "admin_account_required" in output.readouterr().err


def test_cli_module_import_and_doctor_do_not_load_legacy_settings(tmp_path):
    import subprocess

    project = Path(__file__).resolve().parents[2]
    root = tmp_path / "missing"
    environment = dict(
        os.environ, PYTHONPATH=str(project), RESEARCH_CONFIG_FILE=str(tmp_path / "secret.env")
    )
    script = (
        "import sys; from app.research_web.multiuser.__main__ import main; "
        f"assert main(['doctor','--root',{str(root)!r},'--json']) == 0; "
        "assert 'core.settings' not in sys.modules; assert 'core.observability' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert not root.exists()


def test_init_does_not_load_dotenv_or_create_legacy_project_directories(tmp_path):
    import subprocess

    project = Path(__file__).resolve().parents[2]
    root = tmp_path / "server"
    fake_env = tmp_path / "private.env"
    fake_env.write_text("LOG_DIR=must-not-be-loaded\n")
    environment = dict(os.environ, PYTHONPATH=str(project), RESEARCH_CONFIG_FILE=str(fake_env))
    script = (
        "import sys,getpass,dotenv; "
        "dotenv.load_dotenv=lambda *a,**k: (_ for _ in ()).throw(AssertionError('dotenv_read')); "
        "sys.stdin.isatty=lambda: True; "
        f"getpass.getpass=lambda prompt: {PASSWORD!r}; "
        "from app.research_web.multiuser.__main__ import main; "
        f"assert main(['init','--root',{str(root)!r},'--username','admin']) == 0"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert {path.name for path in tmp_path.iterdir()} == {"server", "private.env"}
    assert PASSWORD not in result.stdout + result.stderr
    assert PASSWORD not in (root / "logs/server.jsonl").read_text()


def test_initialization_lock_and_log_symlinks_fail_closed(tmp_path, interactive, output):
    import fcntl

    root = tmp_path / "server"
    root.mkdir(mode=0o700)
    lock = root / "admin.lock"
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert cli.main(["init", "--root", str(root), "--username", "admin"]) == 1
        assert "server_admin_busy" in output.readouterr().err
        assert not (root / "accounts.sqlite3").exists()
    finally:
        os.close(descriptor)
    (root / "logs/server.jsonl").unlink()
    outside = tmp_path / "outside.log"
    (root / "logs/server.jsonl").symlink_to(outside)
    assert cli.main(["init", "--root", str(root), "--username", "admin"]) == 1
    assert not outside.exists()
