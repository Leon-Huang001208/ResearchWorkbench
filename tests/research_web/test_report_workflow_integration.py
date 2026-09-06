"""Report Workflow API, runtime delegation, scheduling, and migration contracts."""

from __future__ import annotations

import asyncio
import json
import threading
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.research_web.main import create_app
from app.research_web.report_workflows import migration as migration_module
from app.research_web.report_workflows.models import (
    WorkbookRefreshResult,
    WorkflowError,
)
from app.research_web.service import ResearchService
from app.research_web.store import Store


class NativeFixture:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def rpc(self, method, payload):
        self.calls.append((method, payload))
        if method == "host.describe":
            return {"version": "fixture", "provider": "fixture", "cwd": None}
        if method == "credentials.describe":
            return {"credentials": {"RESEARCH_DSH_API_KEY": {"configured": True}}}
        if method == "session.list":
            return {"items": []}
        if method == "subagent.list":
            return {"entries": []}
        if method == "skill.list":
            return {"skills": [{"name": "report-production-workflow"}]}
        return {"accepted": True}

    async def history(self, sid):
        return []

    async def close(self):
        return None

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()


class MissingExcelProvider:
    provider_id = "wind_excel"

    @staticmethod
    def readiness():
        return {"ready": False, "code": "xlwings_missing"}


class AvailableExcelProvider:
    provider_id = "ifind_excel"

    @staticmethod
    def readiness():
        return {"ready": True, "code": None}


def _xlsx(path: Path, formula: str = "WSS(A1)") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData><row><c r="A1"><f>{formula}</f><v>1</v></c></row></sheetData>'
            "</worksheet>",
        )


def _manifest(workflow_id="weekly-report"):
    return {
        "workflow_id": workflow_id,
        "name": "每周报告",
        "description": "使用固定底稿与模板生成报告",
        "version": 1,
        "providers": [{"provider": "wind_excel", "required": True}],
        "workbook_policies": [
            {
                "workbook": "workbooks/source.xlsx",
                "providers": [{"provider": "wind_excel", "required": True}],
                "required_cells": ["Sheet1!A1"],
            }
        ],
        "blocks": [{"id": "summary", "title": "摘要", "kind": "narrative", "required": True}],
        "delivery": {
            "formats": ["docx", "html", "xlsx"],
            "required_artifacts": [],
        },
    }


@pytest.fixture
def api(tmp_path: Path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path / "state"))
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, service, native


def _create_version(client: TestClient, tmp_path: Path, workflow_id="weekly-report"):
    created = client.post("/api/research/report-workflows", json=_manifest(workflow_id))
    assert created.status_code == 201, created.text
    workbook = tmp_path / "source.xlsx"
    _xlsx(workbook)
    response = client.post(
        f"/api/research/report-workflows/{workflow_id}/resources",
        data={"path": "workbooks/source.xlsx"},
        files={"file": ("source.xlsx", workbook.read_bytes())},
    )
    assert response.status_code == 201, response.text
    version = client.post(f"/api/research/report-workflows/{workflow_id}/versions")
    assert version.status_code == 201, version.text
    return version.json()


def test_report_workflow_api_coexists_with_capability_workflows(api, tmp_path):
    client, service, _ = api
    assert service.report_studio.scheduler_task is None
    assert service.report_workflows.runtime.scheduler_task is not None
    assert client.get("/api/research/workflows").status_code == 200
    version = _create_version(client, tmp_path)
    assert version["version"] == 1
    assert client.get("/api/research/report-workflows").json()["items"][0]["id"] == "weekly-report"
    assert (
        client.post("/api/research/report-workflows/weekly-report/versions/1/publish").status_code
        == 200
    )
    detail = client.get("/api/research/report-workflows/weekly-report").json()
    assert detail["current_version"] == 1
    assert detail["status"] == "enabled"
    resources = client.get(
        "/api/research/report-workflows/weekly-report/versions/1/resources"
    ).json()["items"]
    resource = next(item for item in resources if item["path"] == "workbooks/source.xlsx")
    downloaded = client.get(
        "/api/research/report-workflows/weekly-report/versions/1/resources/workbooks/source.xlsx"
    )
    assert downloaded.content and resource["sha256"]
    assert (
        client.post("/api/research/report-workflows/weekly-report/disable").json()["status"]
        == "disabled"
    )
    assert (
        client.post("/api/research/report-workflows/weekly-report/versions/1/rollback").status_code
        == 200
    )
    copied = client.post(
        "/api/research/report-workflows/weekly-report/copy",
        json={"id": "weekly-report-copy", "name": "每周报告副本", "version": 1},
    )
    assert copied.status_code == 201 and copied.json()["status"] == "draft"
    changed = _manifest("weekly-report-copy")
    changed["name"] = "每周报告副本二"
    edited = client.patch(
        "/api/research/report-workflows/weekly-report-copy/draft",
        json={
            "manifest": changed,
            "workflow": {
                "steps": [
                    {
                        "id": "refresh",
                        "type": "workbook_refresh",
                        "tool": "workbook_refresh",
                    }
                ]
            },
        },
    )
    assert edited.status_code == 200 and edited.json()["name"] == "每周报告副本二"
    changed["name"] = ""
    invalid = client.patch(
        "/api/research/report-workflows/weekly-report-copy/draft",
        json={"manifest": changed},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_manifest"


def test_provider_probe_is_safe_and_missing_xlwings_blocks_run(api, tmp_path):
    client, service, native = api
    _create_version(client, tmp_path)
    client.post("/api/research/report-workflows/weekly-report/versions/1/publish")
    service.report_workflows.refresh.providers["wind_excel"] = MissingExcelProvider()
    service.report_workflows.refresh.providers["ifind_excel"] = AvailableExcelProvider()
    providers = client.get("/api/research/report-workflows/providers").json()["items"]
    wind = next(item for item in providers if item["id"] == "wind_excel")
    ifind = next(item for item in providers if item["id"] == "ifind_excel")
    assert wind == {
        "id": "wind_excel",
        "ready": False,
        "integration_state": "blocked_dependency",
        "health": "untested",
        "code": "xlwings_missing",
    }
    assert ifind == {
        "id": "ifind_excel",
        "ready": False,
        "integration_state": "ready",
        "health": "untested",
        "code": "needs_probe",
    }
    probe = client.post(
        "/api/research/report-workflows/providers/wind_excel/probe",
        headers={"Idempotency-Key": "probe-one"},
    )
    assert probe.status_code == 200
    assert probe.json()["ready"] is False
    unverified = client.post(
        "/api/research/report-workflows/providers/ifind_excel/probe",
        headers={"Idempotency-Key": "probe-ifind"},
    )
    assert unverified.status_code == 200
    assert unverified.json()["ready"] is False
    assert unverified.json()["health"] == "unverified"
    assert unverified.json()["code"] == "provider_health_unverified"
    run = client.post("/api/research/report-workflows/weekly-report/runs")
    assert run.status_code == 202
    for _ in range(50):
        value = client.get(f"/api/research/report-runs/{run.json()['id']}").json()
        if value["status"] == "blocked_data":
            break
        import time

        time.sleep(0.01)
    assert value["status"] == "blocked_data"
    assert value["failure_code"] in {"provider_not_ready", "xlwings_missing"}
    assert value["session_id"] is None
    assert not any(method == "session.prompt" for method, _ in native.calls)
    assert service.report_workflows.runtime.tasks == {}


def test_refresh_success_delegates_once_to_claw_and_locks_version(api, tmp_path, monkeypatch):
    client, service, _ = api
    _create_version(client, tmp_path)
    client.post("/api/research/report-workflows/weekly-report/versions/1/publish")

    def ready(run_id, workbook, **kwargs):
        run_root = service.report_workflows.runtime.run_path(run_id)
        output = run_root / workbook
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"refreshed")
        manifest = run_root / "refresh-manifests" / ("a" * 64 + ".json")
        manifest.parent.mkdir()
        manifest.write_text(json.dumps({"status": "ready", "output_sha256": "a" * 64}))
        return WorkbookRefreshResult(
            status="ready", manifest_path=f"refresh-manifests/{manifest.name}"
        )

    monkeypatch.setattr(service.report_workflows.catalog, "refresh_workbook", ready)
    sent = []

    async def fake_create(mode="fingpt", title=None):
        row = service.store.create(mode, title or "report")
        row["created"] = True
        service.store.save()
        return service.summary(row)

    async def fake_send(sid, text, key, **kwargs):
        sent.append((sid, text, key, kwargs))
        return {"accepted": True}

    monkeypatch.setattr(service, "create", fake_create)
    monkeypatch.setattr(service, "send", fake_send)
    monkeypatch.setattr(service.report_workflows.runtime, "_wait_for_delivery", lambda run_id: None)
    run = client.post("/api/research/report-workflows/weekly-report/runs").json()
    for _ in range(50):
        value = client.get(f"/api/research/report-runs/{run['id']}").json()
        if value["status"] == "running":
            break
        import time

        time.sleep(0.01)
    assert value["version"] == 1
    assert value["status"] == "running"
    assert value["session_id"]
    assert len(sent) == 1 and sent[0][3]["capability_id"] == "report-production-workflow"
    session = service.store.session(value["session_id"])
    assert session["report_workflow"]["workflow_id"] == "weekly-report"
    assert session["report_workflow"]["version"] == 1
    public = service.report_workflows.runtime.public_run(
        {
            "nested": {
                "items": [
                    {
                        "manifest_path": str(tmp_path / "private" / "manifest.json"),
                        "source_path": str(tmp_path / "private" / "source.xlsx"),
                    }
                ]
            }
        }
    )
    assert public == {"nested": {"items": [{"manifest_path": "private-file"}]}}
    assert str(tmp_path) not in json.dumps(value, ensure_ascii=False)
    assert str(tmp_path) not in service.report_workflows.catalog.index.read_text()


def test_schedule_is_shanghai_non_reentrant_and_catches_up_once(api, tmp_path):
    client, service, _ = api
    _create_version(client, tmp_path)
    client.post("/api/research/report-workflows/weekly-report/versions/1/publish")
    now = datetime(2026, 9, 6, 4, 0, tzinfo=UTC)
    saved = client.put(
        "/api/research/report-workflows/weekly-report/schedule",
        json={"kind": "weekly", "enabled": True, "weekday": 6, "hour": 11, "minute": 0},
    )
    assert saved.status_code == 200
    service.report_workflows.runtime._set_schedule_due_for_test(
        "weekly-report", now - timedelta(days=14)
    )
    service.report_workflows.runtime._new_run("overlap", "weekly-report", 1, "manual", "running")
    asyncio.run(service.report_workflows.runtime.tick(now))
    runs = service.report_workflows.runtime.runs("weekly-report")
    assert sum(item["trigger"] == "schedule" for item in runs) == 1
    assert (
        next(item for item in runs if item["trigger"] == "schedule")["status"] == "skipped_overlap"
    )
    assert (
        service.report_workflows.runtime.schedule("weekly-report")["next_run_at"] > now.isoformat()
    )


def test_scheduler_isolates_disabled_workflow_and_continues_due_items(api, tmp_path, monkeypatch):
    client, service, _ = api
    for workflow_id in ("disabled-report", "ready-report"):
        _create_version(client, tmp_path, workflow_id)
        client.post(f"/api/research/report-workflows/{workflow_id}/versions/1/publish")
        client.put(
            f"/api/research/report-workflows/{workflow_id}/schedule",
            json={"kind": "weekly", "enabled": True, "weekday": 6, "hour": 11, "minute": 0},
        )
    client.post("/api/research/report-workflows/disabled-report/disable")
    now = datetime(2026, 9, 6, 4, 0, tzinfo=UTC)
    for workflow_id in ("disabled-report", "ready-report"):
        service.report_workflows.runtime._set_schedule_due_for_test(
            workflow_id, now - timedelta(days=7)
        )
    called = []

    async def start_run(workflow_id, **kwargs):
        if workflow_id == "disabled-report":
            raise WorkflowError("Workflow 已停用", "workflow_disabled", 409)
        called.append((workflow_id, kwargs))
        return {"id": "scheduled"}

    monkeypatch.setattr(service.report_workflows.runtime, "start_run", start_run)
    asyncio.run(service.report_workflows.runtime.tick(now))

    assert called == [("ready-report", {"trigger": "schedule"})]
    failed_schedule = service.report_workflows.runtime.schedule("disabled-report")
    assert failed_schedule["last_error_code"] == "workflow_disabled"
    assert failed_schedule["enabled"] is False
    assert service.report_workflows.runtime.schedule("ready-report")["last_error_code"] is None


def test_scheduler_isolates_malformed_and_unexpected_failures(api, tmp_path, monkeypatch):
    client, service, _ = api
    for workflow_id in ("malformed-report", "error-report", "later-report"):
        _create_version(client, tmp_path, workflow_id)
        client.post(f"/api/research/report-workflows/{workflow_id}/versions/1/publish")
        client.put(
            f"/api/research/report-workflows/{workflow_id}/schedule",
            json={"kind": "weekly", "enabled": True, "weekday": 6, "hour": 11, "minute": 0},
        )
    now = datetime(2026, 9, 6, 4, 0, tzinfo=UTC)
    for workflow_id in ("error-report", "later-report"):
        service.report_workflows.runtime._set_schedule_due_for_test(
            workflow_id, now - timedelta(days=7)
        )
    with service.report_workflows.catalog._exclusive():
        malformed = service.report_workflows.catalog._row("malformed-report")["schedule"]
        malformed["next_run_at"] = "not-a-date"
        service.report_workflows.catalog._save()
    called = []

    async def start_run(workflow_id, **kwargs):
        if workflow_id == "error-report":
            raise RuntimeError("private provider detail")
        called.append((workflow_id, kwargs))
        return {"id": "scheduled"}

    monkeypatch.setattr(service.report_workflows.runtime, "start_run", start_run)
    asyncio.run(service.report_workflows.runtime.tick(now))

    assert called == [("later-report", {"trigger": "schedule"})]
    malformed = service.report_workflows.runtime.schedule("malformed-report")
    assert malformed["last_error_code"] == "schedule_invalid"
    assert malformed["enabled"] is False
    failed = service.report_workflows.runtime.schedule("error-report")
    assert failed["last_error_code"] == "schedule_trigger_failed"
    assert "private provider detail" not in json.dumps(failed)


def test_migration_is_dry_run_idempotent_and_keeps_ai_blocked(api, tmp_path):
    client, service, _ = api
    source = tmp_path / "report_projects"
    for name in ("华安ETF周报", "创业板50周报", "华安ETF投资风向标"):
        folder = source / name
        (folder / "templates").mkdir(parents=True)
        (folder / "data").mkdir()
        (folder / "project.yaml").write_text(f"name: {name}\n")
        (folder / "config").mkdir()
        (folder / "config" / "report_config.yaml").write_text(
            "placeholders:\n  market_summary:\n    title: 市场概览\n    type: paragraph\n"
            "charts:\n  performance:\n    title: 市场表现图\n"
        )
        (folder / "templates" / ("deck.pptx" if "风向标" in name else "report.docx")).write_bytes(
            b"template"
        )
        _xlsx(folder / "data" / "source.xlsx", formula="1+1")
    ai = source / "AI周报" / "templates"
    ai.mkdir(parents=True)
    (ai / "report.docx").write_bytes(b"draft")
    primary_history = source / "华安ETF周报" / "generated"
    primary_history.mkdir()
    (primary_history / "weekly.pdf").write_bytes(b"historical-weekly")
    duplicate_root = source / "华安ETF周报 2"
    duplicate = duplicate_root / "templates"
    duplicate.mkdir(parents=True)
    (duplicate / "report.docx").write_bytes(b"different")
    (duplicate_root / "data").mkdir()
    (duplicate_root / "data" / "same.xlsx").write_bytes(
        (source / "华安ETF周报" / "data" / "source.xlsx").read_bytes()
    )
    (duplicate_root / "generated").mkdir()
    (duplicate_root / "generated" / "weekly.pdf").write_bytes(b"conflicting-history")
    (duplicate_root / "outputs").mkdir()
    (duplicate_root / "outputs" / "weekly-copy.pdf").write_bytes(b"historical-weekly")
    (duplicate_root / "runs" / "run-001").mkdir(parents=True)
    (duplicate_root / "runs" / "run-001" / "report.docx").write_bytes(b"historical-run")
    (duplicate_root / ".preview-cache").mkdir()
    (duplicate_root / ".preview-cache" / "large-preview.png").write_bytes(b"preview-only")
    preview_cache = source / "华安ETF周报" / ".preview-cache"
    preview_cache.mkdir()
    (preview_cache / "generated.png").write_bytes(b"cache-only")

    dry = service.report_workflows.migration.migrate(source, dry_run=True)
    assert dry["project_count"] == 4
    assert dry["source"] == "legacy-report-projects"
    huaan_dry = next(item for item in dry["projects"] if item["id"] == "huaan-etf-weekly")
    assert huaan_dry["resource_count"] == 4
    assert huaan_dry["history_count"] == 2
    assert dry["resource_count"] == len(dry["accepted"])
    assert dry["history_count"] == 2
    assert not any(
        part in item["path"].split("/")
        for item in dry["accepted"]
        for part in ("generated", "runs", "jobs", "outputs", ".preview-cache")
    )
    assert any(item["reason"] == "historical_path_content_conflict" for item in dry["quarantined"])
    assert str(tmp_path) not in json.dumps(dry, ensure_ascii=False)
    assert not client.get("/api/research/report-workflows").json()["items"]
    applied = service.report_workflows.migration.migrate(source, dry_run=False)
    again = service.report_workflows.migration.migrate(source, dry_run=False)
    assert applied["project_count"] == again["project_count"] == 4
    assert {item["migration_status"] for item in again["projects"]} == {"already_present"}
    items = client.get("/api/research/report-workflows").json()["items"]
    assert {item["id"] for item in items} == {
        "huaan-etf-weekly",
        "chinext-50-weekly",
        "huaan-etf-compass",
        "ai-weekly",
    }
    assert next(item for item in items if item["id"] == "ai-weekly")["status"] == "needs_attention"
    migrated = client.get("/api/research/report-workflows/huaan-etf-weekly").json()
    blocks = migrated["versions"][0]["manifest"]["blocks"]
    assert [(item["title"], item["kind"]) for item in blocks] == [
        ("市场概览", "narrative"),
        ("市场表现图", "chart"),
    ]
    assert any(item["reason"] == "path_content_conflict" for item in applied["quarantined"])
    assert not any(".preview-cache" in item["path"] for item in applied["accepted"])
    assert str(tmp_path) not in json.dumps(applied, ensure_ascii=False)
    assert str(tmp_path) not in json.dumps(migrated, ensure_ascii=False)
    assert str(tmp_path) not in service.report_workflows.catalog.index.read_text()
    assert source.exists()

    new_history = source / "华安ETF周报" / "generated" / "new.pdf"
    new_history.write_bytes(b"new-history")
    history_update = service.report_workflows.migration.migrate(source, dry_run=False)
    history_project = next(
        item for item in history_update["projects"] if item["id"] == "huaan-etf-weekly"
    )
    assert history_project["migration_status"] == "history_updated"
    migrated = client.get("/api/research/report-workflows/huaan-etf-weekly").json()
    assert any(item["path"] == "generated/new.pdf" for item in migrated["historical_artifacts"])
    assert migrated["migration"]["history_sha256"] == history_project["history_sha256"]
    stable = service.report_workflows.migration.migrate(source, dry_run=False)
    stable_project = next(item for item in stable["projects"] if item["id"] == "huaan-etf-weekly")
    assert stable_project["migration_status"] == "already_present"

    (source / "华安ETF周报" / "templates" / "report.docx").write_bytes(b"changed-template")
    conflict = service.report_workflows.migration.migrate(source, dry_run=False)
    project = next(item for item in conflict["projects"] if item["id"] == "huaan-etf-weekly")
    assert project["migration_status"] == "conflict"
    assert project["status"] == "needs_attention"
    assert any(
        item.get("workflow_id") == "huaan-etf-weekly" and item["reason"] == "source_hash_conflict"
        for item in conflict["quarantined"]
    )
    assert not any(item.get("workflow_id") == "huaan-etf-weekly" for item in conflict["accepted"])
    detail = client.get("/api/research/report-workflows/huaan-etf-weekly").json()
    assert detail["status"] == "needs_attention"


def test_migration_rejects_project_and_duplicate_directory_symlinks(api, tmp_path):
    _, service, _ = api
    source = tmp_path / "report_projects"
    primary = source / "华安ETF周报"
    (primary / "templates").mkdir(parents=True)
    (primary / "project.yaml").write_text("name: 华安ETF周报\n")
    (primary / "templates" / "report.docx").write_bytes(b"safe-template")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.docx").write_bytes(b"outside-secret")
    (source / "创业板50周报").symlink_to(outside, target_is_directory=True)
    (source / "华安ETF周报 2").symlink_to(outside, target_is_directory=True)
    (primary / "linked-assets").symlink_to(outside, target_is_directory=True)

    report = service.report_workflows.migration.migrate(source, dry_run=True)

    assert report["project_count"] == 1
    assert any(
        item["path"] == "创业板50周报" and item["reason"] == "unsafe_project_directory"
        for item in report["rejected"]
    )
    assert any(item["reason"] == "unsafe_duplicate_directory" for item in report["quarantined"])
    assert not any(
        item["sha256"] == migration_module._sha256(outside / "secret.docx")
        for item in report["accepted"]
    )


def test_migration_fails_closed_when_source_changes_after_scan(api, tmp_path, monkeypatch):
    _, service, _ = api
    source = tmp_path / "report_projects"
    folder = source / "华安ETF周报"
    (folder / "templates").mkdir(parents=True)
    (folder / "project.yaml").write_text("name: 华安ETF周报\n")
    template = folder / "templates" / "report.docx"
    template.write_bytes(b"scanned-content")
    original_sha256 = migration_module._sha256
    changed = False

    def race(path):
        nonlocal changed
        digest = original_sha256(path)
        if path == template and not changed:
            changed = True
            path.write_bytes(b"changed-after-scan")
        return digest

    monkeypatch.setattr(migration_module, "_sha256", race)
    with pytest.raises(WorkflowError) as caught:
        service.report_workflows.migration.migrate(source, dry_run=False)

    assert caught.value.code == "migration_source_changed"
    assert service.report_workflows.list() == []


def test_migration_rejects_symlink_source(api, tmp_path):
    _, service, _ = api
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    with pytest.raises(WorkflowError) as caught:
        service.report_workflows.migration.migrate(linked)
    assert getattr(caught.value, "code", None) == "migration_source_invalid"


def test_migration_api_uses_configured_source_not_request_path(api, tmp_path, monkeypatch):
    client, _, _ = api
    configured = tmp_path / "configured" / "report_projects"
    configured.mkdir(parents=True)
    monkeypatch.setenv("RESEARCH_REPORT_MIGRATION_SOURCE", str(configured))
    response = client.post(
        "/api/research/report-workflows/migrations",
        params={"dry_run": "true", "source": str(tmp_path / "private")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "legacy-report-projects"
    assert str(tmp_path) not in response.text


def test_migration_prefers_already_managed_report_projects(api, tmp_path, monkeypatch):
    client, service, _ = api
    monkeypatch.delenv("RESEARCH_REPORT_MIGRATION_SOURCE", raising=False)
    managed = service.store.root / "report-projects"
    assets = managed / "chinext-50-weekly" / "versions" / "1" / "assets"
    (assets / "templates").mkdir(parents=True)
    (assets / "data").mkdir()
    (assets / "project.yaml").write_text("name: 创业板50周报\n")
    (assets / "templates" / "report.docx").write_bytes(b"managed-template")
    _xlsx(assets / "data" / "source.xlsx", formula="1+1")
    history = managed / "chinext-50-weekly" / "history"
    history.mkdir(parents=True)
    (history / "old-report.pdf").write_bytes(b"managed-history")

    dry = client.post("/api/research/report-workflows/migrations?dry_run=true")
    assert dry.status_code == 200, dry.text
    assert dry.json()["source"] == "managed-report-projects"
    assert dry.json()["project_count"] == 1
    assert client.get("/api/research/report-workflows").json()["items"] == []

    applied = client.post("/api/research/report-workflows/migrations?dry_run=false")
    assert applied.status_code == 200, applied.text
    assert applied.json()["source"] == "managed-report-projects"
    detail = client.get("/api/research/report-workflows/chinext-50-weekly").json()
    assert detail["name"] == "创业板50周报"
    assert detail["status"] == "enabled"
    assert any(item["path"].endswith("old-report.pdf") for item in detail["historical_artifacts"])
    assert not list(service.store.root.glob("report-workflow-migration-*"))


def test_operations_include_versioned_report_workflow_runs(api):
    client, service, _ = api
    service.report_workflows.runtime._new_run(
        "versioned-run", "weekly-report", 3, "schedule", "completed"
    )
    response = client.get("/api/research/operations/summary?range=today")
    assert response.status_code == 200, response.text
    reports = response.json()["reports"]
    assert reports["runs"] == 1
    assert reports["outcomes"] == {"completed": 1}
    assert reports["projects"] == [{"project_id": "weekly-report", "runs": 1}]
    storage_ids = {
        item["id"] for item in client.get("/api/research/operations/storage").json()["categories"]
    }
    assert "report_workflows" in storage_ids


def test_refresh_manifest_route_flattens_per_workbook_entries(api, monkeypatch):
    client, service, _ = api
    service.report_workflows.runtime._new_run(
        "multi-workbook-run", "weekly-report", 1, "manual", "blocked_data"
    )
    monkeypatch.setattr(
        service.report_workflows.catalog,
        "read_refresh_manifest",
        lambda run_id: {
            "status": "multiple",
            "workbooks": [
                {"workbook": "workbooks/wind.xlsx", "status": "ready"},
                {"workbook": "workbooks/ifind.xlsx", "status": "blocked"},
            ],
        },
    )

    response = client.get("/api/research/report-runs/multi-workbook-run/refresh-manifests")

    assert response.status_code == 200
    assert [item["workbook"] for item in response.json()["items"]] == [
        "workbooks/wind.xlsx",
        "workbooks/ifind.xlsx",
    ]


def test_refresh_cancellation_waits_for_bounded_worker_cleanup(api, monkeypatch):
    _, service, _ = api
    started = threading.Event()
    stopped = threading.Event()

    def refresh(*args, **kwargs):
        started.set()
        cancellation = kwargs["cancellation_event"]
        assert cancellation.wait(timeout=2)
        stopped.set()
        return WorkbookRefreshResult(status="blocked", code="refresh_cancelled")

    monkeypatch.setattr(service.report_workflows.catalog, "refresh_workbook", refresh)

    async def scenario():
        pending = asyncio.create_task(
            service.report_workflows.runtime._refresh_workbook("run-id", "workbooks/source.xlsx")
        )
        assert await asyncio.to_thread(started.wait, 1)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert stopped.is_set()

    asyncio.run(scenario())
