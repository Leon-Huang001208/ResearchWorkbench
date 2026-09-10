"""Truthful local-integration discovery and API contracts."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app.research_web.client import RuntimeFailure
from app.research_web.local_integrations import (
    DetectionEnvironment,
    LocalIntegrationManager,
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
    assert item(snapshot, "ifind_local_sdk")["status"] == "不适用"
    assert item(snapshot, "ifind_local_sdk")["discovery"] == "不适用"
    assert "同花顺" not in item(snapshot, "ifind_local_sdk")["message"]
    assert item(snapshot, "ifind_local_sdk")["actions"] == [
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
        registry_apps={"EXCEL.EXE", "WFT.exe"},
    )
    snapshot = LocalIntegrationManager(tmp_path / "state", environment=env).snapshot()

    assert snapshot["platform"] == "windows"
    assert item(snapshot, "excel_app")["discovery"] == "已发现"
    assert item(snapshot, "excel_app")["verification"] == "待验证"
    assert item(snapshot, "excel_app")["callable"] is False
    assert item(snapshot, "excel_automation_bridge")["discovery"] == "已发现"
    assert item(snapshot, "excel_automation_bridge")["status"] == "待验证"
    assert item(snapshot, "ifind_local_sdk")["discovery"] == "已发现"
    assert item(snapshot, "ifind_local_sdk")["verification"] == "待验证"
    assert item(snapshot, "ifind_local_sdk")["callable"] is False


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
    assert result["error"] == {"code": "probe_failed", "message": "本机能力检测失败，请查看本地日志"}
    assert "secret" not in str(result)


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
