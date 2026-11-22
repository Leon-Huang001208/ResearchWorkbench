"""The public stdlib dispatcher passes only a validated operator knowledge origin."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_workbench_entrypoint import bootstrap, server

PERSISTED_ORIGIN = "https://mac-mini-1.tail947973.ts.net:9443"


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


@pytest.fixture
def primary_spawn(tmp_path, monkeypatch):
    from app.research_web import service_manager as module

    manager = module.WebServiceManager(
        project_root=tmp_path,
        data_root=tmp_path / "data/research-web",
        python=sys.executable,
        node="/synthetic/node",
    )
    manager.log_root.mkdir(parents=True)
    process = next(row for row in manager._processes() if row.role == "web")
    calls = []
    monkeypatch.setattr(
        module.subprocess,
        "Popen",
        lambda *args, **kwargs: calls.append(kwargs) or SimpleNamespace(pid=12345),
    )
    monkeypatch.setattr(manager, "_record_attempt_spawn", lambda *args, **kwargs: None)
    monkeypatch.setattr(manager, "_write_state", lambda *args, **kwargs: None)
    return manager, process, calls


@pytest.mark.parametrize("persisted", [True, False])
def test_primary_install_manifest_knowledge_origin_precedes_environment(
    primary_spawn, monkeypatch, persisted
):
    manager, process, calls = primary_spawn
    manifest = {"status": "installed"}
    if persisted:
        manifest["weknora_origin"] = PERSISTED_ORIGIN + "/"
    monkeypatch.setattr(manager, "_read_install_manifest", lambda: manifest)
    monkeypatch.setenv("RESEARCH_WEKNORA_ORIGIN", "http://127.0.0.1:18080/")
    assert manager._spawn_owned_process(process) == 12345
    assert calls[0]["env"]["RESEARCH_WEKNORA_ORIGIN"] == (
        PERSISTED_ORIGIN if persisted else "http://127.0.0.1:18080/"
    )


def test_primary_invalid_persisted_origin_refuses_spawn_without_fallback(
    primary_spawn, monkeypatch, caplog
):
    from app.research_web.service_manager import ServiceManagerError

    manager, process, calls = primary_spawn
    monkeypatch.setenv("RESEARCH_WEKNORA_ORIGIN", PERSISTED_ORIGIN)
    for value in (
        None,
        False,
        42,
        "",
        "https://user:secret@host",
        "https://host/path",
        "http://remote.invalid",
    ):
        monkeypatch.setattr(
            manager,
            "_read_install_manifest",
            lambda value=value: {"status": "installed", "weknora_origin": value},
        )
        with pytest.raises(ServiceManagerError) as failure:
            manager._spawn_owned_process(process)
        assert failure.value.code == "knowledge_origin_invalid"
    assert calls == [] and "secret" not in caplog.text


@pytest.fixture
def gateway_boot(tmp_path, monkeypatch):
    from contextlib import nullcontext

    from app.research_web.multiuser import __main__ as cli
    from app.research_web.multiuser import resident, resident_binding, resident_boot, runtime

    root = tmp_path / "server"
    root.mkdir(mode=0o700)
    legacy = tmp_path / "legacy/resident"
    legacy.mkdir(parents=True)
    original = legacy / "config.json"
    original.write_text(json.dumps({"node": "/synthetic/node"}))
    original.chmod(0o600)
    config = {
        "version": 1,
        "revision": "a" * 40,
        "project": str(cli.PROJECT),
        "port": 8089,
        "source": str(tmp_path / "source"),
        "node": "/synthetic/node",
        "origin": "http://localhost",
        "binding": {},
        "mcp_readonly_enabled": False,
    }
    calls = []

    class ReachedPool(Exception):
        pass

    def pool(*args, **kwargs):
        import os

        calls.append(os.environ.get("RESEARCH_WEKNORA_ORIGIN"))
        raise ReachedPool

    monkeypatch.setattr(cli, "_server_context", lambda root: nullcontext())
    monkeypatch.setattr(resident.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(resident, "verify_local_checkout", lambda *args: None)
    monkeypatch.setattr(resident, "gateway_relocation_pending", lambda root: False)
    monkeypatch.setattr(
        resident_binding.LegacyBinding,
        "from_config",
        lambda value: SimpleNamespace(home=legacy.parent),
    )
    monkeypatch.setattr(resident_boot, "boot_identity", lambda: "synthetic-boot")
    monkeypatch.setattr(runtime, "RuntimePool", pool)

    def save(value):
        path = root / "resident.json"
        path.write_text(json.dumps(value))
        path.chmod(0o600)

    return resident, root, config, save, calls, ReachedPool


@pytest.mark.parametrize("persisted", [True, False])
def test_gateway_persisted_knowledge_origin_is_active_before_runtime_pool(
    gateway_boot, monkeypatch, persisted
):
    resident, root, config, save, calls, reached = gateway_boot
    if persisted:
        config["weknora_origin"] = PERSISTED_ORIGIN + "/"
    save(config)
    monkeypatch.setenv("RESEARCH_WEKNORA_ORIGIN", "http://127.0.0.1:18080/")
    with pytest.raises(reached):
        resident.run(root)
    assert calls == [PERSISTED_ORIGIN if persisted else "http://127.0.0.1:18080/"]


def test_gateway_invalid_persisted_origin_refuses_pool_without_fallback(
    gateway_boot, monkeypatch, caplog
):
    from app.research_web.multiuser.runtime import RuntimeErrorSafe

    resident, root, config, save, calls, _ = gateway_boot
    monkeypatch.setenv("RESEARCH_WEKNORA_ORIGIN", PERSISTED_ORIGIN)
    for value in (
        None,
        False,
        42,
        "",
        "https://user:secret@host",
        "https://host/path",
        "http://remote.invalid",
    ):
        save({**config, "weknora_origin": value})
        with pytest.raises(RuntimeErrorSafe) as failure:
            resident.run(root)
        assert failure.value.code == "server_knowledge_configuration_invalid"
    assert calls == [] and "secret" not in caplog.text
