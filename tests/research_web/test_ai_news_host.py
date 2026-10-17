"""Owned AI news configuration, lifecycle fences and zero-call Host contracts."""

import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.research_web.ai_news_service import create_ai_news_service, redact
from app.research_web.aihot_routes import AihotReader
from research_workbench_entrypoint import ai_news_manager as lifecycle
from research_workbench_entrypoint.ai_news import run_ai_news
from research_workbench_entrypoint.ai_news_manager import AiNewsManager, _write
from research_workbench_entrypoint.ai_news_postgres import AiNewsPostgres
from research_workbench_entrypoint.ai_news_transport import AiNewsConnection, AiNewsError


def test_unconfigured_status_doctor_and_factory_have_no_side_effects(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("read-only path attempted mutation or subprocess")

    home = tmp_path / "missing"
    manager = AiNewsManager(tmp_path, home)
    monkeypatch.setattr("subprocess.run", denied)
    monkeypatch.setattr("subprocess.Popen", denied)
    monkeypatch.setattr(Path, "mkdir", denied)
    assert manager.status()["state"] == "not_configured"
    assert manager.doctor()["readOnly"] is True
    service = create_ai_news_service(tmp_path, home, credentials=denied)
    assert asyncio.run(service.status())["configured"] is False
    assert not home.exists()


def test_doctor_checks_complete_pin_and_lock_matched_dependencies_using_files_only(
    tmp_path, monkeypatch
):
    root = tmp_path / "services/ai_news"
    vendor = root / "vendor/aihot"
    vendor.mkdir(parents=True)
    expected = {}
    for index in range(651):
        path = vendor / (str(index) + ".txt")
        path.write_text("pinned source " + str(index))
        expected[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    packages = {
        "node_modules/" + name: {"version": "1.2.3"}
        for name in ("fastify", "postgres", "pg-boss", "zod")
    }
    lock = vendor / "package-lock.json"
    lock.write_text(json.dumps({"lockfileVersion": 3, "packages": packages}))
    expected[lock.name] = hashlib.sha256(lock.read_bytes()).hexdigest()
    (root / "upstream.json").write_text(
        json.dumps(
            {
                "upstream": "https://github.com/KKKKhazix/AIHOT",
                "commit": lifecycle.UPSTREAM_COMMIT,
                "license": "MIT",
                "files": expected,
            }
        )
    )
    for name in ("fastify", "postgres", "pg-boss", "zod"):
        path = vendor / "node_modules" / name / "package.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"name": name, "version": "1.2.3"}))
    (vendor / "node_modules/.package-lock.json").write_text("{}")
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: pytest.fail("subprocess attempted")
    )
    manager = AiNewsManager(tmp_path, tmp_path / "unconfigured")
    facts = manager.doctor()
    assert facts["pinIntegrity"] is True and facts["upstreamFiles"] == 652
    assert facts["dependenciesInstalled"] is True and facts["modelAcceptance"] == "NOT_RUN"
    assert not manager.home.exists()
    (vendor / "node_modules/zod/package.json").write_text('{"name":"zod","version":"old"}')
    facts = manager.doctor()
    assert facts["pinIntegrity"] is True and facts["dependenciesInstalled"] is False
    (vendor / "0.txt").write_text("corrupted")
    assert manager.doctor()["pinIntegrity"] is False


def test_unconfigured_reader_never_calls_any_network(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: pytest.fail("network attempted"))
    with pytest.raises(HTTPException) as failure:
        asyncio.run(AihotReader().read("/site/hot"))
    assert failure.value.status_code == 503
    assert failure.value.detail["code"] == "ai_news_not_configured"


def test_only_pinned_ai_news_dependency_directory_can_be_registered_for_closeout(tmp_path):
    from research_workbench_entrypoint.iteration_resources import ResourceError, register_directory

    owned = tmp_path / "services/ai_news/vendor/aihot/node_modules"
    owned.mkdir(parents=True)
    record = register_directory(tmp_path.resolve(), owned, "dependency")
    assert record["path"] == str(owned)
    unrelated = tmp_path / "services/ai_news/vendor/unrelated/node_modules"
    unrelated.mkdir(parents=True)
    with pytest.raises(ResourceError):
        register_directory(tmp_path.resolve(), unrelated, "dependency")


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://aihot.news",
        "http://localhost:18081",
        "http://127.0.0.1:18081/a",
        "http://127.0.0.1:18081?u=x",
        "http://evil.test:18081",
        "http://u@127.0.0.1:18081",
    ],
)
def test_connection_rejects_public_urls_and_browser_selected_paths(tmp_path, endpoint):
    with pytest.raises(AiNewsError, match="endpoint_invalid"):
        AiNewsConnection(endpoint, tmp_path / "token")


def test_token_permissions_symlinks_and_changed_config_fail_closed(tmp_path):
    token = tmp_path / "token"
    token.write_text("a" * 64)
    connection = AiNewsConnection("http://127.0.0.1:18081", token)
    token.chmod(0o644)
    with pytest.raises(AiNewsError, match="storage_unsafe"):
        connection.headers()
    token.chmod(0o600)
    assert connection.headers() == {"x-rwb-ai-news-token": "a" * 64}
    alias = tmp_path / "alias"
    alias.symlink_to(token)
    with pytest.raises(AiNewsError, match="storage_unsafe"):
        AiNewsConnection("http://127.0.0.1:18081", alias).headers()


def test_setup_and_restore_require_explicit_authorization_before_io(tmp_path):
    manager = AiNewsManager(tmp_path, tmp_path / "home")
    with pytest.raises(AiNewsError, match="authorization_required"):
        manager.setup()
    with pytest.raises(AiNewsError, match="authorization_required"):
        manager.restore(tmp_path / "archive")
    assert not manager.directory.exists()


def test_cli_returns_specific_safe_authorization_code_without_side_effects(tmp_path, monkeypatch):
    output = []
    monkeypatch.setattr("builtins.print", output.append)
    assert run_ai_news(["setup", "--json"], tmp_path, tmp_path) == 1
    assert json.loads(output[0])["code"] == "ai_news_setup_authorization_required"
    assert not (tmp_path / "ai-news").exists()


def test_model_environment_is_never_inherited(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sensitive")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sensitive")
    monkeypatch.setenv("HTTP_PROXY", "http://private")
    assert (
        not {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HTTP_PROXY"}
        & AiNewsManager._environment().keys()
    )


def test_private_writes_reject_hardlinks_and_public_files(tmp_path):
    target = tmp_path / "state"
    target.write_text("preserve")
    with pytest.raises(AiNewsError, match="storage_unsafe"):
        _write(target, b"changed")
    assert target.read_text() == "preserve"
    target.chmod(0o600)
    alias = tmp_path / "hardlink"
    alias.hardlink_to(target)
    with pytest.raises(AiNewsError, match="storage_unsafe"):
        _write(target, b"changed")
    assert target.read_text() == "preserve"


def test_status_never_signals_reused_pid(tmp_path, monkeypatch):
    manager = AiNewsManager(tmp_path, tmp_path)
    manager._directories()
    instance = "12a9f89e-e0c2-4411-9c60-88e4f037d58f"
    _write(
        manager.identity_path,
        json.dumps(
            {
                "instanceId": instance,
                "projectRoot": str(tmp_path),
                "home": str(tmp_path),
                "databaseName": "rwb_ai_news",
            }
        ).encode(),
    )
    token = manager.directory / "secrets/token"
    _write(token, b"a" * 64)
    _write(
        manager.config_path,
        json.dumps(
            {
                "port": 18081,
                "tokenFile": str(token),
                "dataDir": str(manager.directory),
                "adminPasswordFile": str(manager.directory / "secrets/admin"),
                "sessionSecretFile": str(manager.directory / "secrets/session"),
                "imageSecretFile": str(manager.directory / "secrets/image"),
                "database": {
                    "host": "127.0.0.1",
                    "port": 15432,
                    "name": "rwb_ai_news",
                    "user": "postgres",
                    "passwordFile": str(manager.directory / "secrets/database"),
                },
            }
        ).encode(),
    )
    _write(
        manager.state_path,
        json.dumps(
            {
                "instanceId": instance,
                "processes": [{"pid": 12345, "fingerprint": "old", "role": "api"}],
            }
        ).encode(),
    )
    monkeypatch.setattr(
        "research_workbench_entrypoint.ai_news_manager._fingerprint", lambda pid: "new"
    )
    monkeypatch.setattr("os.kill", lambda *args: pytest.fail("signal attempted"))
    assert manager.status()["state"] == "invalid"
    with pytest.raises(AiNewsError, match="foreign"):
        manager._stop_processes([{"pid": 12345, "fingerprint": "old", "role": "api"}])


def test_management_whitelist_and_redaction(tmp_path):
    service = create_ai_news_service(tmp_path, tmp_path)
    for action in ("model.enable", "settings.update", "source.fetch", "start", "restore"):
        with pytest.raises(HTTPException) as failure:
            asyncio.run(service.control(action, {}))
        assert failure.value.status_code == 403
    assert redact(
        {"password": "s", "nested": {"api_key": "s", "tokenFile": "path"}, "title": "safe"}
    ) == {
        "password": "[redacted]",
        "nested": {"api_key": "[redacted]", "tokenFile": "[redacted]"},
        "title": "safe",
    }


def test_nested_diagnostic_strings_hide_local_paths_and_keep_publisher_urls():
    publisher = "https://publisher.example/home/report?source=public"
    value = {
        "engine": {
            "runs": {
                "failedJobs": [
                    {
                        "last_output": "Error at file:///Users/example/project/engine/reports/compose.ts:1:2 "
                        "and /home/example/project/task.py:3 and " + publisher,
                        "error": [
                            "at /private/tmp/task/file.py:1",
                            "at /var/run/work/file.ts:2",
                            "at /tmp/work/file.ts:2",
                            "at /Volumes/Work/engine.py:4",
                            r"at C:\Users\example\project\engine.ts:1",
                            "at D:/work/engine.ts:2",
                        ],
                    }
                ]
            }
        }
    }
    safe = redact(value)
    output = safe["engine"]["runs"]["failedJobs"][0]
    assert publisher in output["last_output"]
    assert "file:///Users/" not in output["last_output"]
    assert "/home/example" not in output["last_output"]
    assert output["error"] == ["at [private path]"] * 6


def test_management_no_browser_credentials_forwarded(tmp_path, monkeypatch):
    token = tmp_path / "token"
    _write(token, b"a" * 64)
    service = create_ai_news_service(tmp_path, tmp_path)
    monkeypatch.setattr(
        service.manager, "connection", lambda: AiNewsConnection("http://127.0.0.1:18081", token)
    )
    calls = []
    real_client = httpx.AsyncClient

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True, "data": {"password": "never"}})

    def client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return real_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    assert asyncio.run(service.control("settings", {}))["data"]["password"] == "[redacted]"
    assert calls[0].headers["x-rwb-ai-news-token"] == "a" * 64
    assert "cookie" not in calls[0].headers
    assert calls[0].url.path == "/internal/rwb/control"


class MemoryCredentials:
    def __init__(self):
        self.values = {}

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, value):
        self.values[service, account] = value


@pytest.mark.parametrize("failure_phase", ["credentials", "database", "migrate", "seed"])
def test_setup_resumes_exact_identity_after_each_failure(tmp_path, monkeypatch, failure_phase):
    credentials = MemoryCredentials()
    manager = AiNewsManager(tmp_path, tmp_path, credentials)
    failed = False
    commands = []
    original_get = credentials.get_password

    def get(service, account):
        nonlocal failed
        if failure_phase == "credentials" and account == "database" and not failed:
            failed = True
            raise RuntimeError("backend temporarily unavailable")
        return original_get(service, account)

    def database_start():
        nonlocal failed
        if failure_phase == "database" and not failed:
            failed = True
            raise AiNewsError("ai_news_resource_admission_denied")
        return {"host": "127.0.0.1", "port": 15432, "name": "rwb_ai_news", "user": "postgres"}

    def run(action):
        nonlocal failed
        commands.append(action)
        if action == failure_phase and not failed:
            failed = True
            raise AiNewsError("ai_news_" + action + "_failed")

    monkeypatch.setattr(credentials, "get_password", get)
    monkeypatch.setattr(manager, "_database", lambda: SimpleNamespace(start=database_start))
    monkeypatch.setattr(manager, "_run", run)
    with pytest.raises(AiNewsError):
        manager.setup(authorized=True)
    original_identity = manager._identity()
    assert manager.status()["state"] == "setup_incomplete"
    assert manager.setup(authorized=True)["state"] == "stopped"
    assert manager._identity() == original_identity
    assert json.loads(manager.setup_path.read_text())["phase"] == "complete"
    assert commands[-2:] == ["migrate", "seed"]
    assert len(credentials.values) == 5
    for path in (manager.directory / "secrets").iterdir():
        assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(AiNewsError, match="already_configured"):
        manager.setup(authorized=True)


def test_setup_refuses_foreign_resume_journal(tmp_path):
    manager = AiNewsManager(tmp_path, tmp_path, MemoryCredentials())
    manager._directories()
    _write(
        manager.setup_path,
        json.dumps(
            {
                "version": 1,
                "phase": "secrets",
                "identity": {
                    "projectRoot": str(tmp_path),
                    "home": "/other",
                    "databaseName": "rwb_ai_news",
                    "instanceId": "12a9f89e-e0c2-4411-9c60-88e4f037d58f",
                },
            }
        ).encode(),
    )
    with pytest.raises(AiNewsError, match="setup_foreign"):
        manager.setup(authorized=True)
    assert not manager.identity_path.exists()


def test_process_fingerprint_ignores_scheduling_state_but_binds_start_and_command(monkeypatch):
    values = iter(
        [
            "Ss   Sat Oct 17 12:00:00 2026 node runtime.mjs worker",
            "Rs   Sat Oct 17 12:00:00 2026 node runtime.mjs worker",
            "Rs   Sat Oct 17 12:00:01 2026 node runtime.mjs worker",
            "Z    Sat Oct 17 12:00:00 2026 node runtime.mjs worker",
        ]
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=next(values)),
    )
    first = lifecycle._fingerprint(12345)
    assert lifecycle._fingerprint(12345) == first
    assert lifecycle._fingerprint(12345) != first
    assert lifecycle._fingerprint(12345) is None


@pytest.mark.skipif(os.name != "posix", reason="native POSIX process-tree evidence")
def test_finite_command_timeout_kills_owned_launcher_and_grandchild_then_allows_retry(
    tmp_path, monkeypatch
):
    manager = AiNewsManager(tmp_path, tmp_path)
    manager._directories()
    child_pid = tmp_path / "grandchild.pid"
    script = tmp_path / "owned-launcher.py"
    child_code = (
        "import os,signal,time;from pathlib import Path;"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        f"Path({str(child_pid)!r}).write_text(str(os.getpid()));time.sleep(60)"
    )
    script.write_text(
        "import signal,subprocess,sys,time\n"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
        f"subprocess.Popen([sys.executable,'-c',{child_code!r}])\n"
        "time.sleep(60)\n"
    )
    monkeypatch.setattr(manager, "_command", lambda action: [sys.executable, str(script)])
    spawned = []
    original_popen = subprocess.Popen

    def popen(*args, **kwargs):
        proc = original_popen(*args, **kwargs)
        if kwargs.get("start_new_session"):
            spawned.append(proc)
        return proc

    monkeypatch.setattr(subprocess, "Popen", popen)
    started = time.monotonic()
    try:
        with pytest.raises(AiNewsError, match="command_timeout$"):
            manager._run("migrate", timeout=0.5)
        assert time.monotonic() - started < 8
        assert child_pid.exists()
        assert spawned[0].returncode is not None
        assert lifecycle._fingerprint(int(child_pid.read_text())) is None
        assert not (manager.directory / "command-recovery.json").exists()
        monkeypatch.setattr(manager, "_command", lambda action: [sys.executable, "-c", "pass"])
        manager._run("migrate", timeout=2)
        assert spawned[-1].returncode == 0
    finally:
        for proc in spawned:
            if proc.returncode is None:
                if os.getpgid(proc.pid) == proc.pid and os.getsid(proc.pid) == proc.pid:
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=3)


def test_finite_command_refuses_unknown_process_group_without_signaling(monkeypatch):
    proc = SimpleNamespace(pid=12345, returncode=None)
    monkeypatch.setattr(os, "getpgid", lambda pid: 98765)
    monkeypatch.setattr(os, "killpg", lambda *args: pytest.fail("unknown group signaled"))
    with pytest.raises(AiNewsError, match="group_unverified"):
        lifecycle._terminate_command_tree(proc, proc.pid)


def test_uncertain_command_cleanup_blocks_retry_before_new_subprocess(tmp_path, monkeypatch):
    manager = AiNewsManager(tmp_path, tmp_path)
    manager._directories()
    calls = []

    class Child:
        pid = 12345

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("owned", timeout)

    def popen(*args, **kwargs):
        calls.append(kwargs)
        return Child()

    def cleanup(proc, group):
        raise AiNewsError("ai_news_command_group_unverified")

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(lifecycle, "_terminate_command_tree", cleanup)
    with pytest.raises(AiNewsError, match="command_recovery_required"):
        manager._run("seed", timeout=0.01)
    with pytest.raises(AiNewsError, match="command_recovery_required"):
        manager._run("seed", timeout=0.01)
    assert len(calls) == 1 and calls[0]["start_new_session"] is True
    assert (
        json.loads((manager.directory / "command-recovery.json").read_text())["state"]
        == "cleanup_blocked"
    )


def test_future_test_postgres_has_temporary_lifetime_and_requires_task_owner(tmp_path, monkeypatch):
    database = AiNewsPostgres(tmp_path, "12a9f89e-e0c2-4411-9c60-88e4f037d58f", "rwb_ai_news_test")
    monkeypatch.delenv("RWB_DELIVERY_TASK_ID", raising=False)
    with pytest.raises(AiNewsError, match="delivery_task_required"):
        database._labels()
    monkeypatch.setenv("RWB_DELIVERY_TASK_ID", "ai-news-autonomous-20261017")
    flags = database._labels()
    assert "io.research-workbench.lifetime=temporary" in flags
    assert "io.research-workbench.delivery-task=ai-news-autonomous-20261017" in flags


@pytest.mark.parametrize("failure_kind", ["fingerprint", "state-write"])
@pytest.mark.parametrize("failed_child", [1, 2])
def test_start_reaps_every_owned_popen_on_fingerprint_or_journal_failure(
    tmp_path, monkeypatch, failure_kind, failed_child
):
    manager = AiNewsManager(tmp_path, tmp_path)
    manager._directories()
    _write(manager.config_path, b'{"database": {}}')
    monkeypatch.setattr(manager, "connection", lambda: SimpleNamespace(headers=dict))
    monkeypatch.setattr(manager, "_lock", nullcontext)
    monkeypatch.setattr(manager, "_states", list)
    monkeypatch.setattr(manager, "_identity", lambda: {"instanceId": "owned"})
    monkeypatch.setattr(manager, "_database", lambda: SimpleNamespace(start=dict))
    monkeypatch.setattr(manager, "_command", lambda role: ["node", role])
    events = []
    monkeypatch.setattr(manager, "_run", lambda action: events.append(action))
    children = []

    class Child:
        def __init__(self, *args, **kwargs):
            assert events == ["stage"]
            self.pid = 12340 + len(children) + 1
            self.terminated = False
            self.waited = False
            children.append(self)

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            assert timeout == 15
            self.waited = True
            return 0

    def fingerprint(pid):
        if failure_kind == "fingerprint" and pid == 12340 + failed_child:
            raise AiNewsError("ai_news_process_check_failed")
        return "owned-fingerprint"

    original_json = lifecycle._json
    writes = 0

    def persist(path, value, **kwargs):
        nonlocal writes
        if path == manager.state_path:
            writes += 1
            if failure_kind == "state-write" and writes == failed_child:
                raise AiNewsError("ai_news_storage_write_failed")
        return original_json(path, value, **kwargs)

    monkeypatch.setattr(lifecycle, "_json", persist)
    monkeypatch.setattr(lifecycle, "_fingerprint", fingerprint)
    monkeypatch.setattr(subprocess, "Popen", Child)
    with pytest.raises(AiNewsError, match="start_failed"):
        manager.start()
    assert len(children) == failed_child
    assert all(child.terminated and child.waited for child in children)


def test_database_admission_unknown_memory_fails_before_any_create(tmp_path, monkeypatch):
    database = AiNewsPostgres(tmp_path, "12a9f89e-e0c2-4411-9c60-88e4f037d58f")
    calls = []

    def call(args, timeout=30):
        calls.append(args)
        if args[:1] == ["image"]:
            return "{}"
        if args[:1] == ["info"]:
            return str(8 * 1024**3)
        if args == ["ps", "-q"]:
            return "unknown-container"
        if args == ["inspect", "unknown-container"]:
            return json.dumps([{"Name": "/unrelated", "HostConfig": {"Memory": 0}}])
        pytest.fail("mutation attempted")

    monkeypatch.setattr(database, "call", call)
    with pytest.raises(AiNewsError, match="admission_unknown"):
        database._start()
    assert not any(args[0] in {"create", "start", "stop"} for args in calls)


def test_backup_failure_preserves_partial_and_does_not_publish_manifest(tmp_path, monkeypatch):
    manager = AiNewsManager(tmp_path, tmp_path)
    monkeypatch.setattr(manager, "_identity", dict)
    monkeypatch.setattr(manager, "_lock", nullcontext)
    monkeypatch.setattr(
        manager, "_database", lambda: SimpleNamespace(inspect=lambda: {"Id": "owned"})
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1))
    archive = tmp_path / "backup.dump"
    with pytest.raises(AiNewsError, match="backup_failed"):
        manager.backup(archive)
    assert archive.exists()
    assert not archive.with_suffix(".dump.json").exists()


def test_restore_requires_stopped_processes_and_valid_archive_before_database_start(
    tmp_path, monkeypatch
):
    manager = AiNewsManager(tmp_path, tmp_path)
    monkeypatch.setattr(manager, "_identity", dict)
    monkeypatch.setattr(manager, "_lock", nullcontext)
    monkeypatch.setattr(manager, "_states", lambda: [{"pid": 12345}])
    monkeypatch.setattr(lifecycle, "_fingerprint", lambda pid: "running")
    monkeypatch.setattr(manager, "_database", lambda: pytest.fail("database touched"))
    with pytest.raises(AiNewsError, match="requires_stopped"):
        manager.restore(tmp_path / "missing", authorized=True)
    monkeypatch.setattr(manager, "_states", list)
    archive = tmp_path / "archive.dump"
    _write(archive, b"tampered")
    _write(
        archive.with_suffix(".dump.json"),
        json.dumps({"kind": "rwb-ai-news-pg-dump/v1", "sha256": "0" * 64}).encode(),
    )
    with pytest.raises(AiNewsError, match="backup_invalid"):
        manager.restore(archive, authorized=True)


def test_restore_failure_keeps_original_database_and_records_failed_staging(tmp_path, monkeypatch):
    manager = AiNewsManager(tmp_path, tmp_path)
    manager._directories()
    monkeypatch.setattr(manager, "_identity", lambda: {"instanceId": "owned"})
    monkeypatch.setattr(manager, "_lock", nullcontext)
    monkeypatch.setattr(manager, "_states", list)
    database_calls = []
    database = SimpleNamespace(
        start=dict, inspect=lambda: {"Id": "owned"}, call=lambda args: database_calls.append(args)
    )
    monkeypatch.setattr(manager, "_database", lambda: database)
    archive = tmp_path / "archive.dump"
    _write(archive, b"archive-bytes")
    _write(
        archive.with_suffix(".dump.json"),
        json.dumps(
            {
                "kind": "rwb-ai-news-pg-dump/v1",
                "sha256": hashlib.sha256(b"archive-bytes").hexdigest(),
            }
        ).encode(),
    )

    def restore_command(args, **kwargs):
        assert args[:4] == ["docker", "exec", "-i", "owned"]
        assert "--single-transaction" in args and "--clean" not in args
        assert args[args.index("-d") + 1].startswith("rwb_ai_news_restore_")
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(subprocess, "run", restore_command)
    with pytest.raises(AiNewsError, match="restore_failed"):
        manager.restore(archive, authorized=True)
    assert len(database_calls) == 1 and "createdb" in database_calls[0]
    assert json.loads(manager.restore_path.read_text())["phase"] == "failed"
    assert archive.read_bytes() == b"archive-bytes"


def test_rss_is_bounded_fixed_authenticated_and_rewrites_private_origin(tmp_path, monkeypatch):
    token = tmp_path / "token"
    _write(token, b"a" * 64)
    service = create_ai_news_service(tmp_path, tmp_path)
    monkeypatch.setattr(
        service.manager, "connection", lambda: AiNewsConnection("http://127.0.0.1:18081", token)
    )
    calls = []
    real_client = httpx.AsyncClient
    replies = [
        b'<?xml version="1.0"?><rss><link>http://127.0.0.1:18081/items/abc</link></rss>',
        b'<!DOCTYPE rss SYSTEM "http://evil.test"><rss/>',
    ]

    def respond(request):
        calls.append(request)
        return httpx.Response(
            200, content=replies.pop(0), headers={"content-type": "application/rss+xml"}
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    content = asyncio.run(service.feed("daily", "http://127.0.0.1:18088"))
    assert b"18081" not in content
    assert b"http://127.0.0.1:18088/#/aihot/item/abc" in content
    assert calls[0].url.path == "/feed/daily.xml"
    assert calls[0].headers["x-rwb-ai-news-token"] == "a" * 64
    with pytest.raises(HTTPException) as failure:
        asyncio.run(service.feed("daily", "http://127.0.0.1:18088"))
    assert failure.value.status_code == 503


def test_recovery_actions_use_finite_bridge_and_do_not_enable_paid_calls(tmp_path, monkeypatch):
    service = create_ai_news_service(tmp_path, tmp_path)
    calls = []

    async def request(path, body):
        calls.append((path, body))
        return {"ok": True}

    monkeypatch.setattr(service, "_request", request)
    assert asyncio.run(
        service.control("receipt.release", {"id": 1, "billed": False, "note": "checked"})
    ) == {"ok": True}
    assert asyncio.run(
        service.control("processing.requeue", {"group": None, "reason": "checked"})
    ) == {"ok": True}
    assert all(path == "/internal/rwb/control" for path, body in calls)
