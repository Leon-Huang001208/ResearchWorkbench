"""Report-project migration, version and schedule regressions."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


class NativeFixture:
    async def rpc(self, method, payload):
        if method == "host.describe":
            return {
                "version": "fixture",
                "provider": "fixture",
                "cwd": payload.get("cwd"),
            }
        if method == "credentials.describe":
            return {"credentials": {"RESEARCH_DSH_API_KEY": {"configured": True}}}
        if method == "session.list":
            return {"items": []}
        if method == "subagent.list":
            return {"entries": []}
        if method == "skill.list":
            return {"skills": []}
        return {"accepted": True}

    async def history(self, sid):
        return []

    async def close(self):
        return None

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()


@pytest.fixture
def api(tmp_path: Path):
    service = ResearchService(NativeFixture(), Store(tmp_path / "state"))
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, service


def _migration_source(root: Path) -> Path:
    source = root / "report_projects"
    specs = {
        "华安ETF周报": "name: 华安ETF周报\ndisplay_order: 0\n",
        "创业板50周报": "name: 创业板50周报\ndisplay_order: 2\n",
        "华安ETF投资风向标": "name: 华安ETF投资风向标\nproject_type: ppt\n",
    }
    for name, content in specs.items():
        folder = source / name
        (folder / "templates").mkdir(parents=True)
        (folder / "data").mkdir()
        (folder / "project.yaml").write_text(content)
        extension = "pptx" if "风向标" in name else "docx"
        (folder / "templates" / f"report_template.{extension}").write_bytes(
            b"template-" + name.encode()
        )
        (folder / "data" / "base.xlsx").write_bytes(b"workbook-" + name.encode())
    ai = source / "AI周报"
    (ai / "templates").mkdir(parents=True)
    (ai / "templates" / "report_template.docx").write_bytes(b"ai-template")
    duplicate = source / "华安ETF周报 2"
    (duplicate / "templates").mkdir(parents=True)
    (duplicate / "data").mkdir()
    (duplicate / "templates" / "report_template.docx").write_bytes(
        (source / "华安ETF周报" / "templates" / "report_template.docx").read_bytes()
    )
    (duplicate / "data" / "base.xlsx").write_bytes(b"conflicting-workbook")
    return source


def test_migration_dry_run_then_apply_deduplicates_and_quarantines(api, tmp_path):
    client, service = api
    source = _migration_source(tmp_path)
    dry = service.report_studio.migration(source, dry_run=True)
    assert dry["project_count"] == 4
    assert not service.store.data["report_projects"]
    assert any(item["reason"] == "path_content_conflict" for item in dry["quarantined"])

    applied = service.report_studio.migration(source, dry_run=False)
    assert applied["project_count"] == 4
    rows = client.get("/api/research/report-projects").json()["items"]
    assert {item["id"] for item in rows} == {
        "huaan-etf-weekly",
        "chinext-50-weekly",
        "huaan-etf-compass",
        "ai-weekly",
    }
    assert (
        next(item for item in rows if item["id"] == "ai-weekly")["status"]
        == "needs_attention"
    )
    project = client.get("/api/research/report-projects/huaan-etf-weekly").json()
    assert project["status"] == "ready"
    assert all(
        "source_path" not in item and "stored_path" not in item
        for item in project["versions"][0]["files"]
    )
    internal = service.store.data["report_projects"]["huaan-etf-weekly"]["versions"][
        "1"
    ]
    assert all(Path(item["stored_path"]).exists() for item in internal["files"])


def test_version_is_immutable_and_active_run_locks_version(api):
    client, service = api
    created = client.post(
        "/api/research/report-projects",
        json={"id": "weekly-demo", "name": "每周报告", "project_type": "weekly"},
    )
    assert created.status_code == 201
    uploaded = client.post(
        "/api/research/report-projects/weekly-demo/files",
        files={"file": ("template.docx", b"reviewed-template")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["sha256"]
    assert "stored_path" not in uploaded.json()
    first = client.post(
        "/api/research/report-projects/weekly-demo/versions",
        json={"output_formats": ["docx", "html", "xlsx"], "instructions": "第一版"},
    )
    assert first.status_code == 201
    original = first.json()
    row = service.store.data["report_projects"]["weekly-demo"]
    row["status"] = "enabled"
    run = service.report_studio._new_run("run-one", row, "manual", "running")
    service.store.data["report_runs"]["run-one"] = run
    service.store.save()
    blocked = client.post(
        "/api/research/report-projects/weekly-demo/versions",
        json={"output_formats": ["docx"], "instructions": "第二版"},
    )
    assert blocked.status_code == 409
    assert (
        client.get("/api/research/report-projects/weekly-demo/versions").json()[
            "items"
        ][0]
        == original
    )
    assert (
        client.post(
            "/api/research/report-projects/weekly-demo/files",
            files={"file": ("setup.sh", b"echo unsafe")},
        ).status_code
        == 422
    )


def test_version_rejects_unfixed_data_source_and_prepares_shared_snapshot(api):
    client, service = api
    client.post(
        "/api/research/report-projects",
        json={"id": "data-weekly", "name": "数据周报", "project_type": "weekly"},
    )
    rejected = client.post(
        "/api/research/report-projects/data-weekly/versions",
        json={
            "output_formats": ["html"],
            "data_recipe": [
                {
                    "capability": "search_news",
                    "source": "auto",
                    "parameters": {"query": "ETF", "limit": 10},
                }
            ],
        },
    )
    assert rejected.status_code == 422

    published = client.post(
        "/api/research/report-projects/data-weekly/versions",
        json={
            "output_formats": ["html"],
            "data_recipe": [
                {
                    "id": "weekly-news",
                    "capability": "search_news",
                    "source": "cls",
                    "parameters": {"query": "ETF", "limit": 10},
                }
            ],
        },
    )
    assert published.status_code == 201
    recipe = published.json()["data_recipe"]
    assert recipe[0]["source"] == "cls"
    assert recipe[0]["allow_fallback"] is False

    sid = service.store.create("claw", "data preparation")["id"]
    project = service.store.data["report_projects"]["data-weekly"]
    run = service.report_studio._new_run(
        "prepared", project, "manual", "preparing_data"
    )
    service.report_studio._preauthorization = lambda item: ("allowed", None)
    service.datahub.query = AsyncMock(
        return_value={
            "dataset_id": "00000000-0000-0000-0000-000000000001",
            "status": "complete",
        }
    )
    assert asyncio.run(service.report_studio._prepare_data(run, sid, recipe)) is True
    assert run["dataset_ids"] == ["00000000-0000-0000-0000-000000000001"]
    service.datahub.query.assert_awaited_once()


def test_paid_project_source_waits_for_approval_without_query(api):
    _, service = api
    sid = service.store.create("claw", "approval")["id"]
    run = {
        "id": "approval-run",
        "dataset_ids": [],
        "status": "preparing_data",
        "updated_at": 0,
    }
    recipe = [
        {
            "id": "paid-data",
            "capability": "market_bars",
            "source": "wind",
            "allow_fallback": False,
            "parameters": {"asset": "600000.SH"},
            "refresh": True,
            "required": True,
            "allow_partial": False,
        }
    ]
    service.report_studio._preauthorization = lambda item: (
        "blocked_approval",
        "source_requires_approval",
    )
    service.datahub.query = AsyncMock()
    assert asyncio.run(service.report_studio._prepare_data(run, sid, recipe)) is False
    assert run["status"] == "blocked_approval"
    service.datahub.query.assert_not_awaited()


def test_weekly_schedule_and_overlap_are_persistent(api):
    client, service = api
    client.post(
        "/api/research/report-projects",
        json={"id": "scheduled-weekly", "name": "日程周报", "project_type": "weekly"},
    )
    client.post(
        "/api/research/report-projects/scheduled-weekly/versions",
        json={"output_formats": ["docx"]},
    )
    configured = service.report_studio.put_schedule(
        "scheduled-weekly",
        {"kind": "weekly", "enabled": True, "weekday": 0, "hour": 9, "minute": 30},
        now=datetime(2026, 9, 6, 1, 0, tzinfo=UTC),
    )
    assert configured["timezone"] == "Asia/Shanghai"
    assert configured["next_run_at"] == "2026-09-07T01:30:00+00:00"
    project = service.store.data["report_projects"]["scheduled-weekly"]
    active = service.report_studio._new_run("active", project, "manual", "running")
    service.store.data["report_runs"]["active"] = active
    service.store.save()
    skipped = asyncio.run(service.report_studio.start_run("scheduled-weekly"))
    assert skipped["status"] == "skipped_overlap"
    reloaded = Store(service.store.root)
    assert (
        reloaded.data["report_projects"]["scheduled-weekly"]["schedule"]["next_run_at"]
        == configured["next_run_at"]
    )


def test_scheduler_catches_up_only_the_latest_due_run(api):
    client, service = api
    client.post(
        "/api/research/report-projects",
        json={"id": "catchup-weekly", "name": "补跑周报", "project_type": "weekly"},
    )
    client.post(
        "/api/research/report-projects/catchup-weekly/versions",
        json={"output_formats": ["docx"]},
    )
    service.report_studio.put_schedule(
        "catchup-weekly",
        {"kind": "weekly", "enabled": True, "weekday": 0, "hour": 9, "minute": 30},
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )
    service.report_studio.start_run = AsyncMock(return_value={"status": "queued"})
    now = datetime(2026, 9, 6, 2, 0, tzinfo=UTC)

    asyncio.run(service.report_studio.tick(now))
    asyncio.run(service.report_studio.tick(now))

    service.report_studio.start_run.assert_awaited_once_with(
        "catchup-weekly", trigger="schedule"
    )
    schedule = service.report_studio.schedule("catchup-weekly")
    assert schedule["last_triggered_at"] == now.isoformat()
    assert datetime.fromisoformat(schedule["next_run_at"]) > now


def test_report_artifacts_hide_preview_cache_and_paginate(api):
    client, service = api
    client.post(
        "/api/research/report-projects",
        json={"id": "artifact-weekly", "name": "产物周报", "project_type": "weekly"},
    )
    project = service.store.data["report_projects"]["artifact-weekly"]
    project["historical_artifacts"] = []
    for index, path in enumerate(
        [
            "generated/.preview-cache/page-001.png",
            "generated/jobs/job.json",
            "generated/weekly.docx",
            "generated/analysis.xlsx",
            "generated/report.html",
        ]
    ):
        stored = service.report_studio.root / "artifact-weekly" / path
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_bytes(f"artifact-{index}".encode())
        project["historical_artifacts"].append(
            {
                "path": path,
                "stored_path": str(stored),
                "sha256": f"{index + 1:064x}",
                "size": stored.stat().st_size,
                "historical": True,
            }
        )
    service.store.save()

    first = client.get(
        "/api/research/report-projects/artifact-weekly/artifacts?offset=0&limit=2"
    )
    assert first.status_code == 200
    body = first.json()
    assert body["total"] == 3
    assert body["offset"] == 0
    assert body["limit"] == 2
    assert [item["path"] for item in body["items"]] == [
        "generated/weekly.docx",
        "generated/analysis.xlsx",
    ]
    assert all(item["name"] for item in body["items"])

    second = client.get(
        "/api/research/report-projects/artifact-weekly/artifacts?offset=2&limit=2"
    ).json()
    assert second["total"] == 3
    assert [item["path"] for item in second["items"]] == [
        "generated/report.html"
    ]
