from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.research_web.automation.models import AutomationError
from app.research_web.automation.routes import router
from app.research_web.automation.service import automation_feature_enabled


def test_automation_feature_is_enabled_by_default_and_can_be_disabled(monkeypatch):
    monkeypatch.delenv("RESEARCH_AUTOMATIONS_ENABLED", raising=False)
    assert automation_feature_enabled() is True
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", "0")
    assert automation_feature_enabled() is False


class FakeAutomations:
    def __init__(self):
        self.calls = []
        self.channels = SimpleNamespace(
            list=lambda: {"items": []},
            put=lambda body: {"id": "delivery-1", "name": body.name},
        )

    def list(self):
        return {"items": []}

    def get(self, automation_id):
        return {"id": automation_id}

    def create(self, body):
        self.calls.append(("create", body.name))
        return {"id": "automation-1", "name": body.name}

    def update(self, automation_id, body):
        return {"id": automation_id, "name": body.name}

    def delete(self, automation_id):
        return {"deleted": True, "id": automation_id}

    def enable(self, automation_id):
        return {"id": automation_id, "enabled": True}

    def disable(self, automation_id):
        return {"id": automation_id, "enabled": False}

    async def run(self, automation_id):
        return {"id": "run-1", "automation_id": automation_id}

    async def retry(self, run_id):
        return {"id": "run-2", "retry_of": run_id}

    def list_runs(self, automation_id=None):
        return {"items": [], "automation_id": automation_id}

    def preview_report_schedule_migrations(self):
        return {"items": []}

    def apply_report_schedule_migrations(self, workflow_ids):
        return {"migrated": workflow_ids}


def client(monkeypatch, enabled="1"):
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", enabled)
    app = FastAPI()
    service = FakeAutomations()
    app.state.research = SimpleNamespace(automations=service)

    @app.exception_handler(AutomationError)
    async def automation_error(_request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}},
            status_code=exc.status,
        )

    app.include_router(router)
    return TestClient(app), service


def valid_body():
    return {
        "name": "研究任务",
        "target_kind": "skill",
        "target_id": "company-research",
        "target_version": 2,
        "target_sha256": "a" * 64,
        "input_template": "研究公司",
        "workspace_id": "research",
        "output_formats": ["md"],
        "mcp_tools": [],
        "schedule": {
            "kind": "daily",
            "timezone": "Asia/Shanghai",
            "hour": 9,
            "minute": 0,
        },
        "delivery": {"channel_ids": [], "include_attachments": False},
    }


def test_automation_crud_run_retry_and_migration_routes(monkeypatch):
    web, service = client(monkeypatch)
    assert web.post("/api/research/automations", json=valid_body()).status_code == 201
    assert web.get("/api/research/automations").json() == {"items": []}
    assert web.get("/api/research/automations/automation-1").status_code == 200
    assert (
        web.patch("/api/research/automations/automation-1", json={"name": "更新任务"}).json()[
            "name"
        ]
        == "更新任务"
    )
    assert web.post("/api/research/automations/automation-1/enable").json()["enabled"]
    assert web.post("/api/research/automations/automation-1/disable").json()["enabled"] is False
    assert web.post("/api/research/automations/automation-1/run").status_code == 202
    assert web.post("/api/research/automation-runs/run-1/retry").status_code == 202
    assert web.get("/api/research/automation-runs?automation_id=automation-1").status_code == 200
    assert (
        web.post("/api/research/automations/migrations/report-schedules/preview").status_code == 200
    )
    assert web.post(
        "/api/research/automations/migrations/report-schedules/apply",
        json={"workflow_ids": ["report-1"]},
    ).json() == {"migrated": ["report-1"]}
    assert web.delete("/api/research/automations/automation-1").status_code == 200
    assert service.calls == [("create", "研究任务")]


def test_delivery_channel_routes_and_feature_flag(monkeypatch):
    web, _ = client(monkeypatch)
    assert web.get("/api/research/delivery-channels").json() == {"items": []}
    response = web.put(
        "/api/research/delivery-channels",
        json={
            "name": "通知",
            "kind": "webhook",
            "endpoint": "https://example.test/hook",
            "secret": "secret",
        },
    )
    assert response.status_code == 200
    disabled, _ = client(monkeypatch, "0")
    assert disabled.get("/api/research/automations").status_code == 404
