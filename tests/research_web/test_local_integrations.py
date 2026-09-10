"""Truthful local-integration discovery and API contracts."""

import asyncio
import builtins
import copy
import json
import os
import platform
import queue
import signal
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.research_web.client import RuntimeFailure
from app.research_web.local_integrations import (
    DetectionEnvironment,
    LocalIntegrationError,
    LocalIntegrationManager,
    verifiers,
)
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


class NativeFixture:
    async def rpc(self, method, payload):
        if method == "host.describe":
            return {"version": "fixture", "model": "fixture", "provider": "fixture"}
        if method == "session.list":
            return {"items": []}
        if method == "skill.list":
            return {"skills": []}
        raise RuntimeFailure(f"unexpected method: {method}")

    async def frames(self, _channel):
        yield {"type": "connected"}
        await asyncio.Event().wait()

    async def close(self):
        return None


def environment(
    tmp_path: Path,
    *,
    system: str = "Darwin",
    modules: set[str] | None = None,
    registry_apps: set[str] | None = None,
) -> DetectionEnvironment:
    applications = tmp_path / "Applications"
    addins = tmp_path / "Office Add-Ins"
    applications.mkdir(exist_ok=True)
    addins.mkdir(exist_ok=True)
    return DetectionEnvironment(
        system=system,
        home=tmp_path,
        application_roots=(applications,),
        office_addin_roots=(addins,),
        module_available=lambda name: name in (modules or set()),
        registry_app_exists=lambda name: name in (registry_apps or set()),
        environment_variables={
            "ProgramFiles": str(tmp_path / "Program Files"),
            "ProgramFiles(x86)": str(tmp_path / "Program Files (x86)"),
            "APPDATA": str(tmp_path / "AppData"),
        },
    )


def item(snapshot: dict, item_id: str) -> dict:
    return next(value for value in snapshot["items"] if value["id"] == item_id)


def assert_safe_shape(value: dict) -> None:
    assert set(value) == {
        "id",
        "category",
        "label",
        "discovery",
        "authorization",
        "verification",
        "callable",
        "status",
        "message",
        "detail",
        "capabilities",
        "actions",
        "last_checked_at",
        "last_verified_at",
    }
    assert value["status"] in {
        "可用",
        "待配置",
        "待授权",
        "待验证",
        "未发现",
        "未登录",
        "受限",
        "异常",
        "不适用",
    }


def test_macos_discovers_apps_and_addin_without_conflating_python_bridges(tmp_path):
    env = environment(tmp_path)
    app_root = env.application_roots[0]
    for name in (
        "Microsoft Excel.app",
        "Microsoft Word.app",
        "Microsoft PowerPoint.app",
        "Wind.app",
        "同花顺.app",
        "Google Chrome.app",
    ):
        (app_root / name).mkdir()
    (env.office_addin_roots[0] / "WindAddin").mkdir()

    snapshot = LocalIntegrationManager(tmp_path / "state", environment=env).snapshot()

    assert snapshot["platform"] == "macos"
    assert snapshot["service"] == {"online": True, "label": "本机服务在线"}
    assert item(snapshot, "excel_app")["discovery"] == "已发现"
    assert item(snapshot, "excel_automation_bridge")["status"] == "待配置"
    assert item(snapshot, "excel_automation_bridge")["discovery"] == "未发现"
    assert item(snapshot, "wind_terminal")["discovery"] == "已发现"
    assert item(snapshot, "wind_excel_addin")["discovery"] == "已发现"
    assert item(snapshot, "wind_excel_addin")["callable"] is False
    assert item(snapshot, "wind_terminal")["authorization"] == "待验证"
    assert item(snapshot, "ifind_terminal")["status"] == "不适用"
    assert item(snapshot, "ifind_terminal")["discovery"] == "不适用"
    assert "普通同花顺客户端不是 iFinD 数据接口证据" in item(snapshot, "ifind_terminal")["detail"]
    assert item(snapshot, "ifind_terminal")["actions"] == [
        {
            "id": "configure",
            "label": "配置 iFinD HTTP API",
            "href": "#/settings/data?connection=ifind",
        }
    ]
    assert "ifind_http_api" not in {value["id"] for value in snapshot["items"]}
    assert "wind_data_api" not in {value["id"] for value in snapshot["items"]}
    assert item(snapshot, "wind_terminal")["actions"] == [
        {"id": "configure", "label": "查看 Wind 数据源", "href": "#/settings/data?connection=wind"}
    ]
    assert item(snapshot, "browser_extension")["status"] == "待配置"
    assert item(snapshot, "folder_sync")["status"] == "待配置"
    assert item(snapshot, "local_mcp")["callable"] is False
    assert {category["id"] for category in snapshot["categories"]} == {
        "local_service",
        "folders",
        "office",
        "browsers",
        "mcp",
    }
    assert all(assert_safe_shape(value) is None for value in snapshot["items"])


def test_windows_known_paths_and_registry_are_injectable_but_never_claim_verified(tmp_path):
    env = environment(
        tmp_path,
        system="Windows",
        modules={"xlwings", "iFinDPy"},
        registry_apps={"EXCEL.EXE", "WFT.exe", "iFinD.exe"},
    )
    snapshot = LocalIntegrationManager(tmp_path / "state", environment=env).snapshot()

    assert snapshot["platform"] == "windows"
    assert item(snapshot, "excel_app")["discovery"] == "已发现"
    assert item(snapshot, "excel_app")["verification"] == "待验证"
    assert item(snapshot, "excel_app")["callable"] is False
    assert item(snapshot, "excel_automation_bridge")["discovery"] == "已发现"
    assert item(snapshot, "excel_automation_bridge")["status"] == "待验证"
    assert item(snapshot, "wind_terminal")["authorization"] == "待验证"
    assert item(snapshot, "ifind_terminal")["discovery"] == "已发现"
    assert item(snapshot, "ifind_terminal")["verification"] == "待验证"
    assert item(snapshot, "ifind_terminal")["callable"] is False

    module_only = environment(tmp_path, system="Windows", modules={"iFinDPy"})
    module_snapshot = LocalIntegrationManager(
        tmp_path / "module-only-state", environment=module_only
    ).snapshot()
    assert item(module_snapshot, "ifind_terminal")["discovery"] == "未发现"


@pytest.mark.skipif(platform.system() != "Windows", reason="requires a native Windows runner")
def test_native_windows_runner_uses_real_host_detection_without_claiming_vendor_access(tmp_path):
    manager = LocalIntegrationManager(
        tmp_path / "native-windows-state", environment=DetectionEnvironment.current()
    )
    try:
        snapshot = manager.snapshot(persist=False)
    finally:
        asyncio.run(manager.close())

    assert snapshot["platform"] == "windows"
    assert snapshot["service"] == {"online": True, "label": "本机服务在线"}
    assert item(snapshot, "research_web_service")["callable"] is True
    assert item(snapshot, "wind_terminal")["callable"] is False
    assert item(snapshot, "ifind_terminal")["callable"] is False
    assert all(assert_safe_shape(value) is None for value in snapshot["items"])
    assert str(Path.home()) not in json.dumps(snapshot, ensure_ascii=False)
    assert manager.environment.registry_app_exists("rwb-ci-definitely-missing.exe") is False


def test_windows_ci_runs_native_contracts_and_loopback_probe():
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/research-web-windows-verify.yml"
    ).read_text(encoding="utf-8")

    assert "runs-on: windows-2022" in workflow
    assert 'python-version: "3.11"' in workflow
    assert 'node-version: "20"' in workflow
    assert '- "app/research_web/**"' in workflow
    assert "tests/research_web/test_local_integrations.py" in workflow
    assert "tests/research_web/test_runtime_auth.py" in workflow
    assert "test_windows_runtime_auth_does_not_apply_posix_group_mode_bits" in workflow
    assert "test_windows_runtime_auth_reader_does_not_apply_posix_group_mode_bits" in workflow
    assert "tests/research_web/test_api.py" not in workflow
    assert "tests/research_web/test_connection_center.py" not in workflow
    assert "tests/javascript/research_web_local_integrations_ui.test.mjs" in workflow
    assert "app.research_web.main:app" in workflow
    assert "RESEARCH_RUNTIME_AUTH" in workflow
    assert "dsh-auth-ci-placeholder" in workflow
    assert "os.chmod(os.environ['RESEARCH_RUNTIME_AUTH'], 0o600)" in workflow
    assert "http://127.0.0.1:8088/api/research/local-integrations" in workflow
    assert "local-integrations/probes" in workflow
    assert "snapshot.platform -ne 'windows'" in workflow
    assert "snapshot.service.online -ne $true" in workflow
    assert "probeResult.status -ne 'completed'" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "wind_callable" in workflow
    assert "ifind_callable" in workflow


def test_builtin_capability_bootstrap_preserves_utf8_chinese(tmp_path):
    from app.research_web.capabilities.catalog import CapabilityCatalog

    catalog = CapabilityCatalog(tmp_path)

    instructions = catalog.data["items"]["company-research"]["draft"]["instructions"]
    assert "公司" in instructions


def test_unknown_platform_is_honest_and_never_returns_machine_paths(tmp_path):
    env = environment(tmp_path, system="Haiku")
    snapshot = LocalIntegrationManager(tmp_path / "state", environment=env).snapshot()

    assert snapshot["platform"] == "other"
    assert item(snapshot, "excel_app")["status"] == "不适用"
    assert str(tmp_path) not in str(snapshot)
    assert snapshot["summary"]["available"] == 1
    not_applicable = sum(value["status"] == "不适用" for value in snapshot["items"])
    assert snapshot["summary"]["needs_attention"] == len(snapshot["items"]) - 1 - not_applicable


def test_probe_is_idempotent_and_failure_is_sanitized(tmp_path):
    calls = 0

    def broken_detector():
        nonlocal calls
        calls += 1
        raise OSError("secret path and vendor details")

    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=environment(tmp_path),
        detector=broken_detector,
    )

    async def run():
        first = manager.start_probe("stable-key")
        second = manager.start_probe("stable-key")
        assert first["id"] == second["id"]
        await manager.probe_tasks[first["id"]]
        return manager.probe(first["id"])

    result = asyncio.run(run())
    assert calls == 1
    assert result["status"] == "failed"
    assert result["error"] == {
        "code": "probe_failed",
        "message": "本机能力检测失败，请查看本地日志",
    }
    assert "secret" not in str(result)


def test_snapshot_rejects_extra_fields_and_probe_has_a_server_deadline(tmp_path):
    base_environment = environment(tmp_path)
    valid = LocalIntegrationManager(
        tmp_path / "valid-state", environment=base_environment
    ).snapshot()
    extra = copy.deepcopy(valid)
    extra["unexpected_secret"] = str(tmp_path / "private-token")
    unsafe = LocalIntegrationManager(
        tmp_path / "unsafe-state", environment=base_environment, detector=lambda: extra
    )
    try:
        unsafe.snapshot()
    except LocalIntegrationError as exc:  # The public exception must not echo injected content.
        assert "private-token" not in str(exc)
    else:
        raise AssertionError("unsafe projection was accepted")
    assert not unsafe.state_path.exists()

    secret_environment = environment(tmp_path)
    secret_environment = DetectionEnvironment(
        **{
            **secret_environment.__dict__,
            "environment_variables": {
                **secret_environment.environment_variables,
                "VENDOR_API_TOKEN": "super-secret-token-value",
            },
        }
    )
    leaked = copy.deepcopy(valid)
    leaked["items"][0]["detail"] = "super-secret-token-value"
    secret_projection = LocalIntegrationManager(
        tmp_path / "secret-state", environment=secret_environment, detector=lambda: leaked
    )
    try:
        secret_projection.snapshot()
    except LocalIntegrationError as exc:
        assert "super-secret-token-value" not in str(exc)
    else:
        raise AssertionError("secret in an allowed text field was accepted")

    def slow_detector():
        time.sleep(0.03)
        return valid

    manager = LocalIntegrationManager(
        tmp_path / "timeout-state",
        environment=environment(tmp_path),
        detector=slow_detector,
        probe_timeout_seconds=0.01,
    )

    async def run():
        started = manager.start_probe("timeout-key")
        await manager.probe_tasks[started["id"]]
        result = manager.probe(started["id"])
        for _ in range(20):
            if manager._active_detection is None:
                break
            await asyncio.sleep(0.005)
        await manager.close()
        return result

    result = asyncio.run(run())
    assert result["status"] == "failed"
    assert result["error"] == {
        "code": "probe_timed_out",
        "message": "本机能力检测超时，请稍后重试",
    }
    assert manager._latest is None
    assert not manager.state_path.exists()
    assert manager._active_detection is None


def test_probe_rejects_parallel_work_and_reuses_the_same_idempotency_key(tmp_path):
    manager = None

    def slow_detector():
        time.sleep(0.03)
        return manager._detect()

    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=environment(tmp_path),
        detector=slow_detector,
        probe_timeout_seconds=1,
    )

    async def run():
        first = manager.start_probe("same-key")
        assert manager.start_probe("same-key")["id"] == first["id"]
        try:
            manager.start_probe("different-key")
        except LocalIntegrationError as exc:
            assert exc.code == "local_probe_busy"
            assert exc.status == 409
        else:
            raise AssertionError("parallel probe was accepted")
        await manager.probe_tasks[first["id"]]
        await manager.close()

    asyncio.run(run())
    assert len(manager.probes) == 1


def test_local_integration_api_requires_idempotency_and_service_close_cleans_tasks(tmp_path):
    service = ResearchService(NativeFixture(), Store(tmp_path / "store"))
    service.local_integrations = LocalIntegrationManager(
        tmp_path / "local-state", environment=environment(tmp_path)
    )

    with TestClient(create_app(service)) as client:
        snapshot = client.get("/api/research/local-integrations")
        assert snapshot.status_code == 200
        assert item(snapshot.json(), "research_web_service")["callable"] is True

        assert client.post("/api/research/local-integrations/probes").status_code == 422
        headers = {"Idempotency-Key": "local-probe-0001"}
        first = client.post("/api/research/local-integrations/probes", headers=headers)
        second = client.post("/api/research/local-integrations/probes", headers=headers)
        assert first.status_code == 202
        assert first.json()["id"] == second.json()["id"]
        probe_id = first.json()["id"]
        for _ in range(20):
            current = client.get(f"/api/research/local-integrations/probes/{probe_id}")
            if current.json()["status"] not in {"queued", "checking"}:
                break
        assert current.status_code == 200
        assert current.json()["status"] == "completed"
        assert client.get("/api/research/local-integrations/probes/not-a-probe").status_code == 404

    assert service.local_integrations.probe_tasks == {}


def test_verification_is_idempotent_and_success_updates_only_target_items(tmp_path):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    calls = []

    def verifier(target):
        calls.append(target)
        return {"outcome": "available", "code": None}

    manager = LocalIntegrationManager(tmp_path / "state", environment=env, verifier=verifier)

    async def run():
        first = manager.start_verification("excel", "verification-key")
        second = manager.start_verification("excel", "verification-key")
        assert second["id"] == first["id"]
        await manager.verification_tasks[first["id"]]
        return manager.verification(first["id"]), manager.snapshot(persist=False)

    result, snapshot = asyncio.run(run())
    assert calls == ["excel"]
    assert result["status"] == "completed"
    assert result["target"] == "excel"
    assert result["outcome"] == "available"
    assert item(snapshot, "excel_app")["status"] == "可用"
    assert item(snapshot, "excel_automation_bridge")["status"] == "可用"
    assert item(snapshot, "word_app")["callable"] is False
    assert str(tmp_path) not in json.dumps(result, ensure_ascii=False)

    restored = LocalIntegrationManager(tmp_path / "state", environment=env)
    restored_snapshot = restored.snapshot(persist=False)
    assert item(restored_snapshot, "excel_app")["status"] == "可用"
    assert item(restored_snapshot, "excel_app")["last_verified_at"] == result["completed_at"]
    assert item(restored_snapshot, "word_app")["last_verified_at"] is None


def test_verification_evidence_expires_or_changes_context(tmp_path):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    context = {"value": "office-v1"}
    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=env,
        verifier=lambda _target: {"outcome": "available"},
        context_fingerprint=lambda _target: context["value"],
    )

    async def run():
        started = manager.start_verification("excel", "verification-context")
        await manager.verification_tasks[started["id"]]

    asyncio.run(run())
    assert item(manager.snapshot(persist=False), "excel_app")["callable"] is True
    context["value"] = "office-v2"
    assert item(manager.snapshot(persist=False), "excel_app")["callable"] is False

    expired = LocalIntegrationManager(
        tmp_path / "state",
        environment=env,
        context_fingerprint=lambda _target: "office-v1",
        verification_ttl_seconds=0,
    )
    assert item(expired.snapshot(persist=False), "excel_app")["callable"] is False


def test_verification_rejects_future_timestamp_and_stale_wind_session(tmp_path):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    (env.application_roots[0] / "Wind.app").mkdir()
    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=env,
        context_fingerprint=lambda target: target,
        wind_session_ready=lambda: False,
    )
    checked_at = manager.snapshot(persist=False)["last_checked_at"]
    manager.verification_results = {
        "excel": {
            "outcome": "available",
            "completed_at": "2999-01-01T00:00:00Z",
            "context_fingerprint": manager._verification_context_fingerprint("excel"),
        },
        "wind_excel": {
            "outcome": "available",
            "completed_at": checked_at,
            "context_fingerprint": manager._verification_context_fingerprint("wind_excel"),
        },
    }
    snapshot = manager.snapshot(persist=False)
    assert item(snapshot, "excel_app")["callable"] is False
    assert item(snapshot, "wind_terminal")["callable"] is False


def test_wind_vendor_session_error_does_not_fail_snapshot(tmp_path, monkeypatch):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    (env.application_roots[0] / "Wind.app").mkdir()
    (env.office_addin_roots[0] / "WindAddin.xlam").write_bytes(b"addin")

    class BrokenWindSession:
        @staticmethod
        def isconnected():
            raise RuntimeError("vendor session failed with private details")

    monkeypatch.setitem(sys.modules, "WindPy", SimpleNamespace(w=BrokenWindSession()))
    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=env,
        context_fingerprint=lambda target: target,
    )
    checked_at = manager.snapshot(persist=False)["last_checked_at"]
    manager.verification_results = {
        "excel": {
            "outcome": "available",
            "completed_at": checked_at,
            "context_fingerprint": manager._verification_context_fingerprint("excel"),
        },
        "wind_excel": {
            "outcome": "available",
            "completed_at": checked_at,
            "context_fingerprint": manager._verification_context_fingerprint("wind_excel"),
        },
    }

    snapshot = manager.snapshot(persist=False)

    assert item(snapshot, "excel_app")["callable"] is True
    assert item(snapshot, "wind_terminal")["discovery"] == "已发现"
    assert item(snapshot, "wind_terminal")["callable"] is False


def test_wind_vendor_import_error_does_not_fail_snapshot(tmp_path, monkeypatch):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    (env.application_roots[0] / "Wind.app").mkdir()
    (env.office_addin_roots[0] / "WindAddin.xlam").write_bytes(b"addin")
    original_import = builtins.__import__

    def fail_wind_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "WindPy":
            raise RuntimeError("vendor import failed with private details")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fail_wind_import)
    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=env,
        context_fingerprint=lambda target: target,
    )
    checked_at = manager.snapshot(persist=False)["last_checked_at"]
    manager.verification_results = {
        "wind_excel": {
            "outcome": "available",
            "completed_at": checked_at,
            "context_fingerprint": manager._verification_context_fingerprint("wind_excel"),
        }
    }

    snapshot = manager.snapshot(persist=False)

    assert item(snapshot, "wind_terminal")["discovery"] == "已发现"
    assert item(snapshot, "wind_terminal")["callable"] is False


def test_wind_excel_verification_does_not_require_windpy(tmp_path, monkeypatch):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    (env.application_roots[0] / "Wind.app").mkdir()
    (env.office_addin_roots[0] / "WindAddin.xlam").write_bytes(b"addin")
    original_import = builtins.__import__

    def omit_windpy(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "WindPy":
            raise ModuleNotFoundError("No module named 'WindPy'", name="WindPy")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", omit_windpy)
    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=env,
        context_fingerprint=lambda target: target,
    )
    checked_at = manager.snapshot(persist=False)["last_checked_at"]
    manager.verification_results = {
        "wind_excel": {
            "outcome": "available",
            "completed_at": checked_at,
            "context_fingerprint": manager._verification_context_fingerprint("wind_excel"),
        }
    }

    snapshot = manager.snapshot(persist=False)

    assert item(snapshot, "wind_terminal")["callable"] is True
    assert item(snapshot, "wind_excel_addin")["callable"] is True


def test_windpy_internal_dependency_error_invalidates_wind_evidence(tmp_path, monkeypatch):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    (env.application_roots[0] / "Wind.app").mkdir()
    (env.office_addin_roots[0] / "WindAddin.xlam").write_bytes(b"addin")
    original_import = builtins.__import__

    def fail_windpy_dependency(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "WindPy":
            raise ModuleNotFoundError(
                "No module named 'vendor_dependency'", name="vendor_dependency"
            )
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fail_windpy_dependency)
    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=env,
        context_fingerprint=lambda target: target,
    )
    checked_at = manager.snapshot(persist=False)["last_checked_at"]
    manager.verification_results = {
        "wind_excel": {
            "outcome": "available",
            "completed_at": checked_at,
            "context_fingerprint": manager._verification_context_fingerprint("wind_excel"),
        }
    }

    snapshot = manager.snapshot(persist=False)

    assert item(snapshot, "wind_terminal")["callable"] is False
    assert item(snapshot, "wind_excel_addin")["callable"] is False


def test_verification_persistence_failure_does_not_publish_callable(tmp_path, monkeypatch):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=env,
        verifier=lambda _target: {"outcome": "available"},
        context_fingerprint=lambda _target: "office-v1",
    )
    monkeypatch.setattr(
        manager,
        "_persist",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk failed")),
    )

    async def run():
        started = manager.start_verification("excel", "verification-persist-failure")
        await manager.verification_tasks[started["id"]]
        return manager.verification(started["id"])

    result = asyncio.run(run())
    assert result["status"] == "failed"
    assert manager.verification_results == {}
    assert item(manager.snapshot(persist=False), "excel_app")["callable"] is False


def test_probe_publish_cannot_overwrite_newer_verification_evidence(tmp_path, monkeypatch):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=env,
        verifier=lambda _target: {"outcome": "available"},
        context_fingerprint=lambda _target: "office-v1",
    )
    stale_persist_entered = threading.Event()
    release_stale_persist = threading.Event()
    persisted = []

    def controlled_persist(snapshot, **_kwargs):
        if not item(snapshot, "excel_app")["callable"] and not stale_persist_entered.is_set():
            stale_persist_entered.set()
            assert release_stale_persist.wait(2)
        persisted.append(copy.deepcopy(snapshot))

    monkeypatch.setattr(manager, "_persist", controlled_persist)

    async def run():
        stale_reader = asyncio.create_task(asyncio.to_thread(manager.snapshot))
        assert await asyncio.to_thread(stale_persist_entered.wait, 1)
        started = manager.start_verification("excel", "verification-order")
        verification_task = manager.verification_tasks[started["id"]]
        await asyncio.sleep(0.02)
        release_stale_persist.set()
        await stale_reader
        await verification_task

    asyncio.run(run())
    assert item(manager._latest, "excel_app")["callable"] is True
    assert item(persisted[-1], "excel_app")["callable"] is True


def test_wind_context_fingerprint_tracks_actual_matching_addin(tmp_path):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    (env.application_roots[0] / "Wind.app").mkdir()
    addin = env.office_addin_roots[0] / "WindAddin-custom.xlam"
    addin.write_bytes(b"version-one")
    manager = LocalIntegrationManager(tmp_path / "state", environment=env)

    before = manager._verification_context_fingerprint("wind_excel")
    addin.write_bytes(b"version-two")
    after = manager._verification_context_fingerprint("wind_excel")

    assert before != after


def test_wind_context_fingerprint_tracks_matching_addin_directory_contents(tmp_path):
    env = environment(tmp_path, modules={"xlwings"})
    (env.application_roots[0] / "Microsoft Excel.app").mkdir()
    (env.application_roots[0] / "Wind.app").mkdir()
    addin = env.office_addin_roots[0] / "WindAddin.bundle"
    addin.mkdir()
    payload = addin / "Contents" / "plugin.bin"
    payload.parent.mkdir()
    payload.write_bytes(b"version-one")
    manager = LocalIntegrationManager(tmp_path / "state", environment=env)

    before = manager._verification_context_fingerprint("wind_excel")
    payload.write_bytes(b"version-two")
    after = manager._verification_context_fingerprint("wind_excel")

    assert before != after


@pytest.mark.parametrize(
    ("outcome", "status", "authorization", "verification"),
    [
        ("authorization_required", "待授权", "待授权", "待验证"),
        ("login_required", "未登录", "未登录", "待验证"),
        ("timeout", "异常", "待验证", "异常"),
        ("formula_error", "待验证", "待验证", "未通过"),
        ("failed", "异常", "待验证", "异常"),
    ],
)
def test_verification_failure_outcomes_are_safely_mapped(
    tmp_path, outcome, status, authorization, verification
):
    env = environment(tmp_path)
    (env.application_roots[0] / "Microsoft Word.app").mkdir()
    manager = LocalIntegrationManager(
        tmp_path / "state",
        environment=env,
        verifier=lambda target: {
            "outcome": outcome,
            "code": "vendor-private-detail",
            "unsafe": str(tmp_path / "secret"),
        },
    )

    async def run():
        started = manager.start_verification("word", f"key-{outcome}")
        await manager.verification_tasks[started["id"]]
        return manager.verification(started["id"]), manager.snapshot(persist=False)

    result, snapshot = asyncio.run(run())
    word = item(snapshot, "word_app")
    assert word["status"] == status
    assert word["authorization"] == authorization
    assert word["verification"] == verification
    assert word["callable"] is False
    assert "vendor-private-detail" not in json.dumps(result, ensure_ascii=False)
    assert str(tmp_path) not in json.dumps(result, ensure_ascii=False)


def test_verification_api_rejects_unknown_targets_and_requires_idempotency(tmp_path):
    service = ResearchService(NativeFixture(), Store(tmp_path / "store"))
    service.local_integrations = LocalIntegrationManager(
        tmp_path / "local-state",
        environment=environment(tmp_path),
        verifier=lambda target: {"outcome": "available", "code": None},
    )

    with TestClient(create_app(service)) as client:
        endpoint = "/api/research/local-integrations/verifications"
        assert client.post(endpoint, json={"target": "excel"}).status_code == 422
        assert (
            client.post(
                endpoint,
                json={"target": "arbitrary/path"},
                headers={"Idempotency-Key": "verification-bad"},
            ).status_code
            == 422
        )
        accepted = client.post(
            endpoint,
            json={"target": "excel"},
            headers={"Idempotency-Key": "verification-excel"},
        )
        assert accepted.status_code == 202
        verification_id = accepted.json()["id"]
        for _ in range(20):
            current = client.get(
                f"/api/research/local-integrations/verifications/{verification_id}"
            )
            if current.json()["status"] not in {"queued", "checking"}:
                break
        assert current.json()["status"] == "completed"
        assert current.json()["outcome"] == "available"
        assert (
            client.get("/api/research/local-integrations/verifications/not-found").status_code
            == 404
        )


def test_macos_excel_verifier_uses_sandbox_file_and_owned_app(tmp_path, monkeypatch):
    from app.research_web.report_workflows.workbook import XlwingsExcelProvider

    documents = tmp_path / "Documents"
    documents.mkdir()
    run_root = tmp_path / ("a" * 32)
    run_root.mkdir()
    values = {"A3": 42}
    events = []

    class Range:
        def __init__(self, reference):
            self.reference = reference
            self.formula = None

        @property
        def value(self):
            return values.get(self.reference)

        @value.setter
        def value(self, value):
            values[self.reference] = value

    class Book:
        sheets = [SimpleNamespace(range=lambda reference: Range(reference))]

        def save(self):
            return None

        def close(self):
            return None

    class Books:
        def __init__(self):
            self.paths = []

        def open(self, path, **_kwargs):
            self.paths.append(Path(path))
            assert self.paths[-1].is_file()
            return Book()

    class App:
        def __init__(self):
            self.books = Books()
            self.api = SimpleNamespace(calculate_full_rebuild=lambda: None)
            self.quit_called = False

        def quit(self):
            self.quit_called = True

    app = App()

    monkeypatch.setattr(verifiers, "_office_documents_root", lambda _target: documents)
    monkeypatch.setattr(
        XlwingsExcelProvider,
        "_activate_macos_appscript_compat",
        staticmethod(lambda: events.append("appscript-compat")),
    )
    monkeypatch.setitem(sys.modules, "xlwings", SimpleNamespace(App=lambda **_kwargs: app))

    result = verifiers._verify_excel_macos(run_root)

    assert result == {"outcome": "available", "code": None}
    assert events == ["appscript-compat"]
    assert app.quit_called is True
    assert len(app.books.paths) == 2
    artifact = app.books.paths[0]
    assert artifact.parent == documents
    assert artifact.name == f"research-workbench-{'a' * 32}.xlsx"
    assert not artifact.exists()


def test_macos_excel_cleanup_failure_is_not_available(tmp_path, monkeypatch):
    documents = tmp_path / "Documents"
    documents.mkdir()
    run_root = tmp_path / ("d" * 32)
    run_root.mkdir()
    artifact = documents / f"research-workbench-{'d' * 32}.xlsx"

    class Range:
        value = 42
        formula = None

    class Book:
        sheets = [SimpleNamespace(range=lambda _reference: Range())]

        def save(self):
            return None

        def close(self):
            return None

    class App:
        books = SimpleNamespace(open=lambda *_args, **_kwargs: Book())
        api = SimpleNamespace(calculate_full_rebuild=lambda: None)

        def quit(self):
            return None

    monkeypatch.setattr(verifiers, "_office_documents_root", lambda _target: documents)
    monkeypatch.setitem(sys.modules, "xlwings", SimpleNamespace(App=lambda **_kwargs: App()))
    monkeypatch.setattr(verifiers, "_remove_office_artifact", lambda *_args: False)

    result = verifiers._verify_excel_macos(run_root)

    assert result == {"outcome": "failed", "code": "cleanup_failed"}
    artifact.unlink()


@pytest.mark.parametrize(
    ("target", "verifier", "suffix"),
    [
        ("word", verifiers._verify_word, ".docx"),
        ("powerpoint", verifiers._verify_powerpoint, ".pptx"),
    ],
)
def test_macos_document_verifiers_use_office_sandbox(
    tmp_path, monkeypatch, target, verifier, suffix
):
    documents = tmp_path / "Documents"
    documents.mkdir()
    run_root = tmp_path / ("e" * 32)
    run_root.mkdir()
    observed = {}

    def run_script(_script, *arguments):
        observed["artifact"] = Path(arguments[0])
        observed["target_name"] = arguments[1]
        observed["script"] = _script
        observed["artifact"].write_bytes(b"office")
        return {"outcome": "available", "code": None}

    monkeypatch.setattr(verifiers, "_office_documents_root", lambda _target: documents)
    monkeypatch.setattr(verifiers, "_run_osascript", run_script)
    if target == "powerpoint":
        original_import = builtins.__import__

        def reject_undeclared_pptx(name, *args, **kwargs):
            if name == "pptx" or name.startswith("pptx."):
                raise AssertionError("PowerPoint verification must not require python-pptx")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", reject_undeclared_pptx)

    assert verifier(run_root) == {"outcome": "available", "code": None}
    artifact = observed["artifact"]
    assert artifact.parent == documents
    assert artifact.name == f"research-workbench-{'e' * 32}{suffix}"
    assert observed["target_name"] == artifact.name
    assert "active document" not in observed["script"]
    assert "active presentation" not in observed["script"]
    if target == "powerpoint":
        script = observed["script"]
        assert (
            script.index("save smokePresentation in targetFile")
            < script.index("set smokePresentation to presentation targetName")
            < script.index("close smokePresentation")
        )
    assert not artifact.exists()


def test_windows_excel_verifier_uses_app_api_full_rebuild_and_reopens_saved_value(
    tmp_path, monkeypatch
):
    events = []

    class Range:
        value = None
        formula = None

    class Sheet:
        def __init__(self):
            self.values = {"A3": 42}

        def range(self, reference):
            value = Range()
            value.value = self.values.get(reference)
            return value

    class Book:
        sheets = [Sheet()]

        def save(self, path):
            Path(path).write_bytes(b"xlsx")

        def close(self):
            events.append("book-close")

    class Books:
        active = Book()

        def open(self, *_args, **_kwargs):
            events.append("reopen")
            return Book()

    class API:
        def calculate_full_rebuild(self):
            events.append("mac-full-rebuild")

        def CalculateFullRebuild(self):
            events.append("windows-full-rebuild")

    class App:
        books = Books()
        api = API()

        def calculate_full_rebuild(self):
            raise AssertionError("xlwings wrapper method must not be used")

        def CalculateFullRebuild(self):
            raise AssertionError("xlwings wrapper method must not be used")

        def calculate(self):
            raise AssertionError("full rebuild must be preferred")

        def quit(self):
            events.append("quit")

    monkeypatch.setitem(sys.modules, "xlwings", SimpleNamespace(App=lambda **_kwargs: App()))
    monkeypatch.setattr(verifiers.sys, "platform", "win32")

    assert verifiers._verify_excel(tmp_path)["outcome"] == "available"
    assert "windows-full-rebuild" in events
    assert "reopen" in events
    assert "quit" in events


def test_excel_verifier_does_not_accept_wrapper_only_full_rebuild(tmp_path, monkeypatch):
    class Range:
        value = None
        formula = None

    class Sheet:
        def range(self, _reference):
            return Range()

    class Book:
        sheets = [Sheet()]

        def close(self):
            return None

    class App:
        books = SimpleNamespace(active=Book())
        api = object()

        def calculate_full_rebuild(self):
            raise AssertionError("wrapper method must never satisfy the native API contract")

        def quit(self):
            return None

    monkeypatch.setitem(sys.modules, "xlwings", SimpleNamespace(App=lambda **_kwargs: App()))
    monkeypatch.setattr(verifiers.sys, "platform", "win32")

    assert verifiers._verify_excel(tmp_path) == {
        "outcome": "formula_error",
        "code": "excel_full_rebuild_unavailable",
    }


@pytest.mark.parametrize("mutate_source", [False, True])
def test_wind_verifier_runs_bounded_smoke_then_full_and_guards_published_source(
    tmp_path, monkeypatch, mutate_source
):
    from app.research_web.report_workflows import catalog as catalog_module
    from app.research_web.report_workflows import workbook as workbook_module
    from app.research_web.report_workflows.models import (
        RefreshStatus,
        WorkbookFormulaProvider,
    )

    source = tmp_path / "published" / "workbooks" / "wind.xlsx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"immutable-published-workbook")
    original = source.read_bytes()
    calls = []

    class Policy:
        workbook = "workbooks/wind.xlsx"
        required_cells = []
        timeout_seconds = 900.0

        def model_copy(self, *, update):
            return SimpleNamespace(
                workbook=self.workbook,
                required_cells=self.required_cells,
                timeout_seconds=update["timeout_seconds"],
            )

    policy = Policy()

    class Catalog:
        def __init__(self, root):
            assert root == tmp_path

        def _row(self, workflow_id):
            assert workflow_id == "huaan-etf-weekly"
            return {"current_version": 7}

        def manifest(self, workflow_id, version):
            assert (workflow_id, version) == ("huaan-etf-weekly", 7)
            return SimpleNamespace(workbook_policies=[policy])

        def resource_path(self, workflow_id, version, workbook):
            assert (workflow_id, version, workbook) == (
                "huaan-etf-weekly",
                7,
                "workbooks/wind.xlsx",
            )
            return source

    class Refresh:
        def refresh(self, selected_source, stage, selected_policy):
            calls.append(
                (
                    selected_source,
                    stage.name,
                    selected_policy.workbook,
                    selected_policy.timeout_seconds,
                )
            )
            if mutate_source:
                selected_source.write_bytes(b"malicious-provider-mutation")
            return SimpleNamespace(status=RefreshStatus.READY, code=None)

    monkeypatch.setattr(catalog_module, "ReportWorkflowService", Catalog)
    monkeypatch.setattr(workbook_module, "WorkbookRefreshService", Refresh)
    monkeypatch.setattr(
        workbook_module,
        "scan_workbook_formulas",
        lambda _path: SimpleNamespace(provider=WorkbookFormulaProvider.WIND),
    )

    result = verifiers._verify_wind(tmp_path, tmp_path / "verification")

    if mutate_source:
        assert result == {"outcome": "failed", "code": "source_hash_changed"}
        assert [call[1] for call in calls] == ["smoke"]
        assert source.read_bytes() != original
    else:
        assert result == {"outcome": "available", "code": None}
        assert [(call[0], call[1], call[2]) for call in calls] == [
            (source, "smoke", "workbooks/wind.xlsx"),
            (source, "full", "workbooks/wind.xlsx"),
        ]
        assert source.read_bytes() == original
    assert all(
        0
        < call[3]
        <= verifiers.VERIFICATION_TIMEOUT_SECONDS - verifiers.PROCESS_COORDINATION_GRACE_SECONDS
        for call in calls
    )
    if len(calls) == 2:
        assert calls[1][3] <= calls[0][3]


def test_wind_verifier_stops_before_refresh_when_global_budget_is_exhausted(tmp_path, monkeypatch):
    from app.research_web.report_workflows import catalog as catalog_module
    from app.research_web.report_workflows import workbook as workbook_module
    from app.research_web.report_workflows.models import WorkbookFormulaProvider

    source = tmp_path / "published" / "workbooks" / "wind.xlsx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"immutable-published-workbook")
    policy = SimpleNamespace(
        workbook="workbooks/wind.xlsx",
        required_cells=[],
        timeout_seconds=30.0,
    )
    policy.model_copy = lambda **_kwargs: policy

    class Catalog:
        def __init__(self, _root):
            return None

        def _row(self, _workflow_id):
            return {"current_version": 1}

        def manifest(self, _workflow_id, _version):
            return SimpleNamespace(workbook_policies=[policy])

        def resource_path(self, _workflow_id, _version, _workbook):
            return source

    class Refresh:
        def refresh(self, *_args):
            raise AssertionError("refresh must not start after the global deadline")

    times = iter((100.0, 281.0))
    monkeypatch.setattr(catalog_module, "ReportWorkflowService", Catalog)
    monkeypatch.setattr(workbook_module, "WorkbookRefreshService", Refresh)
    monkeypatch.setattr(
        workbook_module,
        "scan_workbook_formulas",
        lambda _path: SimpleNamespace(provider=WorkbookFormulaProvider.WIND),
    )
    monkeypatch.setattr(verifiers.time, "monotonic", lambda: next(times))

    assert verifiers._verify_wind(tmp_path, tmp_path / "verification") == {
        "outcome": "timeout",
        "code": "verification_timed_out",
    }


def test_posix_timeout_cleanup_terminates_the_worker_process_group(monkeypatch):
    events = []

    class Process:
        pid = 24680

        def is_alive(self):
            return False

        def join(self, timeout):
            events.append(("join", timeout))

        def terminate(self):
            raise AssertionError("POSIX cleanup must target the process group")

    monkeypatch.setattr(verifiers.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(
        verifiers.os, "killpg", lambda pgid, sig: events.append(("killpg", pgid, sig))
    )

    verifiers._terminate_process_tree(Process(), platform_name="posix")

    assert ("killpg", 24680, signal.SIGTERM) in events
    assert ("killpg", 24680, signal.SIGKILL) in events


def test_verify_target_timeout_uses_process_tree_cleanup_and_closes_queue(tmp_path, monkeypatch):
    from app.research_web.report_workflows import workbook as workbook_module

    events = []
    documents = tmp_path / "Documents"
    documents.mkdir()
    run_root = tmp_path / "state" / "verification-runs" / ("b" * 32)
    run_root.mkdir(parents=True)
    artifact = documents / f"research-workbench-{'b' * 32}.xlsx"
    unrelated = documents / "existing-user-workbook.xlsx"
    artifact.write_bytes(b"verification")
    unrelated.write_bytes(b"user")

    class ResultQueue:
        sent = False

        def get(self, timeout):
            if not self.sent:
                self.sent = True
                return {
                    "status": "started",
                    "child_processes": [{"pid": 54321, "token": "a" * 64}],
                }
            raise queue.Empty

        def close(self):
            events.append("queue-close")

        def join_thread(self):
            events.append("queue-join")

    class Process:
        pid = 13579

        def start(self):
            events.append("start")

        def join(self, timeout):
            events.append(("join", timeout))

        def is_alive(self):
            return True

    class Context:
        def Queue(self, maxsize):
            assert maxsize == 4
            return ResultQueue()

        def Process(self, **kwargs):
            assert kwargs["name"] == "local-verification-excel"
            return Process()

    monkeypatch.setattr(verifiers.sys, "platform", "darwin")
    monkeypatch.setattr(verifiers, "_office_documents_root", lambda _target: documents)
    monkeypatch.setattr(verifiers, "_prepare_run_directory", lambda _state_root: (run_root, None))
    monkeypatch.setattr(verifiers, "VERIFICATION_TIMEOUT_SECONDS", 0.0)
    monkeypatch.setattr(verifiers, "PROCESS_COORDINATION_GRACE_SECONDS", 0.0)
    monkeypatch.setattr(verifiers.multiprocessing, "get_context", lambda _name: Context())
    monkeypatch.setattr(
        verifiers,
        "_terminate_process_tree",
        lambda process: events.append(("tree-cleanup", process.pid)) or True,
    )
    monkeypatch.setattr(
        workbook_module,
        "_terminate_managed_excel_processes",
        lambda identities: events.append(("excel-cleanup", identities)) or True,
    )

    result = verifiers.verify_target("excel", tmp_path / "state")

    assert result == {"outcome": "timeout", "code": "verification_timed_out"}
    assert ("tree-cleanup", 13579) in events
    assert (
        "excel-cleanup",
        [{"pid": 54321, "token": "a" * 64}],
    ) in events
    assert events[-2:] == ["queue-close", "queue-join"]
    assert not artifact.exists()
    assert unrelated.read_bytes() == b"user"


def test_excel_artifact_cleanup_rejects_symlink(tmp_path, monkeypatch):
    documents = tmp_path / "Documents"
    documents.mkdir()
    run_root = tmp_path / ("c" * 32)
    run_root.mkdir()
    outside = tmp_path / "outside.xlsx"
    outside.write_bytes(b"keep")
    artifact = documents / f"research-workbench-{'c' * 32}.xlsx"
    artifact.symlink_to(outside)
    monkeypatch.setattr(verifiers, "_office_documents_root", lambda _target: documents)

    assert verifiers._remove_office_artifact("excel", run_root) is False
    assert artifact.is_symlink()
    assert outside.read_bytes() == b"keep"


def test_wind_verification_prepares_run_inside_excel_sandbox(tmp_path, monkeypatch):
    state_root = tmp_path / "state"
    excel_documents = tmp_path / "Excel Documents"
    excel_documents.mkdir()
    observed = []

    monkeypatch.setattr(verifiers.sys, "platform", "darwin")
    monkeypatch.setattr(
        verifiers,
        "_office_documents_root",
        lambda target: excel_documents if target == "excel" else tmp_path,
    )
    monkeypatch.setattr(
        verifiers,
        "_prepare_run_directory",
        lambda root: observed.append(root) or (None, "verification_storage_unsafe"),
    )

    assert verifiers.verify_target("wind_excel", state_root) == {
        "outcome": "failed",
        "code": "verification_storage_unsafe",
    }
    assert observed == [excel_documents]


def test_verification_run_storage_rejects_symlink(tmp_path):
    state_root = tmp_path / "state"
    state_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (state_root / "verification-runs").symlink_to(outside, target_is_directory=True)

    run_root, error = verifiers._prepare_run_directory(state_root)

    assert run_root is None
    assert error == "verification_storage_unsafe"
    assert outside.exists()


def test_verification_run_storage_prunes_by_age_count_and_size(tmp_path, monkeypatch):
    state_root = tmp_path / "state"
    runs = state_root / "verification-runs"
    runs.mkdir(parents=True)
    old = runs / ("a" * 32)
    first = runs / ("b" * 32)
    second = runs / ("c" * 32)
    for path, payload in ((old, b"old"), (first, b"1234"), (second, b"5678")):
        path.mkdir()
        (path / "artifact").write_bytes(payload)
    old_time = time.time() - 120
    first_time = time.time() - 20
    second_time = time.time() - 10
    for path, timestamp in ((old, old_time), (first, first_time), (second, second_time)):
        # Directory mtime changes when its artifact is written, so set it last.
        os.utime(path, (timestamp, timestamp))
    monkeypatch.setattr(verifiers, "VERIFICATION_RUN_RETENTION_SECONDS", 60)
    monkeypatch.setattr(verifiers, "MAX_VERIFICATION_RUNS", 2)
    monkeypatch.setattr(verifiers, "MAX_VERIFICATION_STORAGE_BYTES", 4)

    run_root, error = verifiers._prepare_run_directory(state_root)

    assert error is None
    assert run_root is not None
    assert run_root.parent == runs
    assert not run_root.exists()
    assert not old.exists()
    assert not first.exists()
    assert second.exists()


def test_verification_run_storage_rejects_nested_symlink(tmp_path):
    state_root = tmp_path / "state"
    run = state_root / "verification-runs" / ("d" * 32)
    run.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_text("keep", encoding="utf-8")
    (run / "escape").symlink_to(outside)

    run_root, error = verifiers._prepare_run_directory(state_root)

    assert run_root is None
    assert error == "verification_storage_unsafe"
    assert outside.read_text(encoding="utf-8") == "keep"
