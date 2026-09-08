"""Offline capability lifecycle and hostile-package regression tests."""

import hashlib
import io
import json
import stat
import zipfile

import pytest
import yaml
from fastapi.testclient import TestClient
from test_api import NativeFixture

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


@pytest.fixture
def api(tmp_path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path))
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, native, service


def candidate(name="我的研究", slug="my-research"):
    return {
        "metadata": {
            "name": name,
            "slug": slug,
            "description": "基于上传资料开展有来源的研究",
            "category": "资料研究",
            "inputs": [
                {
                    "name": "question",
                    "label": "研究问题",
                    "type": "text",
                    "required": True,
                }
            ],
            "scenarios": ["解读研究资料"],
            "default_formats": ["md"],
            "required_tools": ["research_run_script"],
            "dependencies": [],
        },
        "instructions": f"---\nname: {slug}\ndescription: 有来源的研究\n---\n# 研究\n只读取本会话资料，不编造来源。",
        "files": [{"path": "templates/report.md", "content": "# 研究报告"}],
    }


def create(client, value=None):
    response = client.post("/api/research/capabilities", json=value or candidate())
    assert response.status_code == 201, response.text
    return response.json()


def test_offline_seed_catalog_tools_and_workflows_without_session(api):
    client, native, service = api
    service.connected.clear()
    native.calls.clear()
    result = client.get("/api/research/capabilities")
    assert result.status_code == 200
    rows = result.json()["items"]
    assert len(rows) == 14
    assert {r["name"] for r in rows if r["kind"] == "skill"} == {
        "资料解读",
        "公司研究",
        "行业研究",
        "基金评价",
        "市场解读",
        "金融事件研究",
        "产业链与主题研究",
        "业绩与一致预期",
        "宏观与跨资产",
        "研报增量分析",
    }
    assert all(r["source"] == "builtin" and r["version"] == 1 for r in rows)
    workflows = client.get("/api/research/workflows").json()["items"]
    assert len(workflows) == 4
    assert "report-production-workflow" in {row["id"] for row in workflows}
    tools = client.get("/api/research/tools").json()["items"]
    assert {t["id"] for t in tools if t["selectable"]} == {
        "research_run_script",
        "datahub_get_fund_data",
        "datahub_search_news",
        "datahub_search_assets",
        "datahub_get_market_bars",
        "datahub_get_market_snapshot",
        "datahub_get_financials",
        "datahub_get_market_activity",
        "web_search",
    }
    assert len(tools) == 28
    workflow_tools = {t["id"] for t in tools if t.get("execution_surface") == "workflow_backend"}
    assert workflow_tools == {
        "report_workbook_refresh",
        "report_workbook_extract",
        "report_template_inspect",
        "report_chart_render",
        "report_docx_assemble",
        "report_pptx_assemble",
        "report_delivery_validate",
    }
    assert all(not t["selectable"] for t in tools if t["id"] in workflow_tools)
    assert sum(t["id"] == "datahub_get_fund_data" for t in tools) == 1
    assert all(t["parameters"] and t["source"] and t["conditions"] for t in tools)
    datahub_tools = [t for t in tools if t["source"] == "runtime/public-data.mjs"]
    assert all(t["approval"] == "automatic" for t in datahub_tools)
    assert all(
        t["conditions"]
        == [
            "已配置且可用的 DataHub 来源自动执行，无逐次确认",
            "无可调用来源的能力不会注册到 Runtime",
        ]
        for t in datahub_tools
    )
    assert native.calls == []


def test_specialist_seed_metadata_boundaries_and_existing_contracts(api):
    client, _, _ = api
    rows = {row["id"]: row for row in client.get("/api/research/capabilities").json()["items"]}
    existing = {
        "document-reading": (
            "资料解读",
            "资料研究",
            [],
            ["research_run_script", "datahub_search_news"],
        ),
        "company-research": (
            "公司研究",
            "公司",
            ["docx", "html", "xlsx"],
            ["research_run_script", "datahub_search_news"],
        ),
        "industry-research": (
            "行业研究",
            "行业",
            ["docx", "html", "xlsx"],
            ["research_run_script", "datahub_search_news"],
        ),
        "fund-evaluation": (
            "基金评价",
            "基金",
            ["docx", "html", "xlsx"],
            ["research_run_script", "datahub_get_fund_data"],
        ),
        "market-commentary": (
            "市场解读",
            "市场",
            ["docx", "html", "xlsx"],
            ["research_run_script", "datahub_search_news"],
        ),
    }
    for slug, (name, category, formats, tools) in existing.items():
        metadata = rows[slug]["metadata"]
        assert rows[slug]["version"] == 1
        assert metadata == {
            "slug": slug,
            "name": name,
            "description": f"基于实际材料开展{name}，保留来源、口径及数据缺失，按需交付真实文件。",
            "category": category,
            "inputs": [
                {
                    "name": "question",
                    "label": "研究问题与资料",
                    "type": "text",
                    "required": True,
                }
            ],
            "scenarios": [name],
            "default_formats": formats,
            "required_tools": tools,
            "dependencies": [],
        }

    workflows = {
        "market-commentary-workflow": "市场资料筛选与解读交付",
        "fund-research-workflow": "基金资料准备与受限评价",
        "company-research-workflow": "公司资料研究与报告交付",
        "report-production-workflow": "报告项目资料准备与文件交付",
    }
    for slug, name in workflows.items():
        row = rows[slug]
        assert row["version"] == 1
        assert row["metadata"] == {
            "slug": slug,
            "name": name,
            "description": "有序研究步骤模板；并不表示任何步骤已经执行。",
            "category": "研究流程",
            "inputs": [
                {
                    "name": "question",
                    "label": "对象、期间与资料",
                    "type": "text",
                    "required": True,
                }
            ],
            "scenarios": [name],
            "default_formats": ["docx", "html", "xlsx"],
            "required_tools": ["research_run_script"],
            "dependencies": [],
        }

    specialists = {
        "finance-news-event-research": ("金融事件研究", "事件与政策"),
        "industry-chain-research": ("产业链与主题研究", "行业与主题"),
        "earnings-consensus-research": ("业绩与一致预期", "公司与业绩"),
        "macro-asset-research": ("宏观与跨资产", "宏观与资产"),
        "sell-side-report-reader": ("研报增量分析", "研报与资料"),
    }
    for slug, (name, category) in specialists.items():
        row = rows[slug]
        metadata = row["metadata"]
        detail = client.get(f"/api/research/capabilities/{slug}").json()
        header = yaml.safe_load(detail["draft"]["instructions"].split("---", 2)[1])
        assert row["kind"] == "skill" and row["source"] == "builtin"
        assert row["version"] == 1 and row["enabled"] is True
        assert metadata["slug"] == header["name"] == slug
        assert metadata["name"] == name and metadata["category"] == category
        assert metadata["default_formats"] == []
        assert metadata["required_tools"] == (
            ["research_run_script", "web_search"]
            if slug == "sell-side-report-reader"
            else ["web_search"]
        )
        assert metadata["dependencies"] == []
        assert "不" in metadata["description"]
    assert not any("router" in capability_id for capability_id in rows)


def test_specialist_exports_bundle_one_evidence_protocol_snapshot_and_reimports(
    api, monkeypatch, tmp_path
):
    client, _, _ = api
    slugs = (
        "finance-news-event-research",
        "industry-chain-research",
        "earnings-consensus-research",
        "macro-asset-research",
        "sell-side-report-reader",
    )
    protocol_hashes = set()
    exported = None
    for slug in slugs:
        response = client.get(f"/api/research/capabilities/{slug}/versions/1/export")
        assert response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = archive.namelist()
            assert names.count("references/evidence-protocol.md") == 1
            protocol = archive.read("references/evidence-protocol.md")
            protocol_hashes.add(hashlib.sha256(protocol).hexdigest())
            assert b"DataHub" in protocol
            visible_package = b"\n".join(
                archive.read(name) for name in names if name.endswith((".md", ".json"))
            )
            assert b"ZhengYan" not in visible_package and b"OpenAI" not in visible_package
        exported = response.content
    assert len(protocol_hashes) == 1

    monkeypatch.setattr("app.research_web.capabilities.catalog.seed_packages", list)
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path / "reimport"))
    with TestClient(create_app(service)) as import_client:
        imported = import_client.post(
            "/api/research/capabilities/import",
            files={"file": ("specialist.zip", exported, "application/zip")},
        )
        assert imported.status_code == 201, imported.text
        draft = imported.json()["draft"]
        bundled = next(
            item for item in draft["files"] if item["path"] == "references/evidence-protocol.md"
        )
        assert bundled["sha256"] in protocol_hashes
        assert bundled["content"].encode() == protocol


def test_catalog_migrates_persisted_legacy_tool_ids_as_new_versions(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    custom = catalog.create(candidate())
    catalog.publish(custom["id"])

    for cid in ("document-reading", custom["id"]):
        row = catalog.row(cid)
        row["draft"]["metadata"]["required_tools"] = ["af_run_script"]
        row["draft"]["instructions"] = row["draft"]["instructions"].replace(
            "research_run_script", "af_run_script"
        )
        active = row["versions"][str(row["version"])]
        active["metadata"]["required_tools"] = ["af_run_script"]
        active["instructions"] = active["instructions"].replace(
            "research_run_script", "af_run_script"
        )

    workflow = catalog.row("fund-research-workflow")
    for record in (workflow["draft"], workflow["versions"]["1"]):
        record["metadata"]["required_tools"] = ["af_run_script"]
        record["steps"][0]["tools"] = ["af_public_data"]
        record["steps"][1]["tools"] = ["af_run_script"]
        record["steps"][2]["tools"] = ["af_run_script"]
    catalog.save()

    migrated = CapabilityCatalog(tmp_path)
    for cid in (
        "document-reading",
        "fund-research-workflow",
        "market-commentary-workflow",
        custom["id"],
    ):
        row = migrated.row(cid)
        assert row["version"] == 2
        active = row["versions"]["2"]
        assert "af_run_script" not in json.dumps(active, ensure_ascii=False)
        assert "af_public_data" not in json.dumps(active, ensure_ascii=False)
        assert migrated.selection(cid)["version"] == 2
    assert migrated.row("document-reading")["versions"]["1"]["metadata"]["required_tools"] == [
        "af_run_script"
    ]
    assert migrated.row("fund-research-workflow")["versions"]["2"]["steps"][0]["tools"] == [
        "datahub_get_fund_data"
    ]

    reloaded = CapabilityCatalog(tmp_path)
    assert reloaded.row("document-reading")["version"] == 2
    assert reloaded.row("market-commentary-workflow")["version"] == 2
    assert reloaded.row(custom["id"])["version"] == 2


def test_draft_check_publish_copy_versions_disable_rollback_export(api):
    client, _, service = api
    row = create(client)
    cid = row["id"]
    base = f"/api/research/capabilities/{cid}"
    assert row["status"] == "draft"
    assert client.post(base + "/check").json()["valid"] is True
    first = client.post(base + "/publish").json()
    assert first["status"] == "enabled" and first["version"] == 1
    version_path = service.capabilities.version_path(cid, 1)
    first_raw = (version_path / "SKILL.md").read_bytes()
    assert not (version_path / "SKILL.md").stat().st_mode & 0o222
    changed = candidate()
    changed["instructions"] += "\n新增研究要求。"
    assert client.patch(base + "/draft", json=changed).status_code == 200
    assert client.post(base + "/publish").json()["version"] == 2
    assert (version_path / "SKILL.md").read_bytes() == first_raw
    assert client.post(base + "/disable").json()["status"] == "disabled"
    assert client.post(base + "/enable").json()["status"] == "enabled"
    assert client.post(base + "/rollback", json={"version": 1}).json()["version"] == 1
    assert len(client.get(base + "/versions").json()["items"]) == 2
    exported = client.get(base + "/versions/1/export")
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        assert archive.read("SKILL.md").decode() == candidate()["instructions"]
        assert json.loads(archive.read("capability.json"))["name"] == "我的研究"
    assert client.post("/api/research/capabilities", json=candidate()).status_code == 409
    assert (
        client.patch("/api/research/capabilities/company-research/draft", json=changed).status_code
        == 409
    )
    copied = client.post(
        "/api/research/capabilities/company-research/copy",
        json={"name": "公司研究副本", "slug": "company-copy"},
    )
    assert copied.status_code == 201 and copied.json()["source"] == "copy"
    assert copied.json()["status"] == "draft"


def test_metadata_dependencies_tools_invalid_preserved(api):
    client, _, _ = api
    value = candidate()
    value["metadata"]["dependencies"] = ["rwb-nonexistent-distribution-987==1.0"]
    row = create(client, value)
    base = f"/api/research/capabilities/{row['id']}"
    checks = client.post(base + "/check").json()
    assert checks["status"] == "blocked_dependencies"
    assert any(c["code"] == "dependency_missing" for c in checks["issues"])
    assert client.post(base + "/publish").status_code == 422
    value["metadata"]["dependencies"] = []
    value["metadata"]["required_tools"] = ["shell"]
    value["metadata"]["inputs"] = []
    client.patch(base + "/draft", json=value)
    checks = client.post(base + "/check").json()
    assert {c["code"] for c in checks["issues"]} >= {
        "tool_unavailable",
        "metadata_invalid",
    }
    assert client.get(base).json()["draft"]["metadata"]["required_tools"] == ["shell"]


@pytest.mark.parametrize(
    "filename",
    [
        "../escape.md",
        "/absolute.md",
        "a/../../escape.md",
        "a\\evil.md",
        "nested.zip",
        "install.py",
        "payload.exe",
        ".git/config",
        "C:/evil.md",
    ],
)
def test_import_unsafe_zip_keeps_report_without_extraction(api, filename):
    client, _, service = api
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("SKILL.md", candidate()["instructions"])
        zf.writestr(filename, "malicious input")
    response = client.post(
        "/api/research/capabilities/import",
        files={"file": ("research.zip", archive.getvalue(), "application/zip")},
    )
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["status"] == "invalid"
    assert row["checks"]["issues"]
    assert not (service.store.root.parent / "escape.md").exists()
    assert not list(service.capabilities.native_root.glob("rwb-*"))


def test_zip_link_duplicate_limits_and_missing_metadata(api):
    client, _, _ = api
    for kind in ("symlink", "duplicate", "count", "expanded"):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SKILL.md", candidate()["instructions"])
            if kind == "symlink":
                info = zipfile.ZipInfo("templates/link.md")
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                zf.writestr(info, "/etc/passwd")
            elif kind == "duplicate":
                zf.writestr("skill.MD", "ambiguous")
            elif kind == "count":
                for i in range(128):
                    zf.writestr(f"t{i}.md", "text")
            else:
                zf.writestr("huge.md", b"a" * (10 * 1024 * 1024 + 1))
        response = client.post(
            "/api/research/capabilities/import",
            files={"file": ("research.zip", archive.getvalue())},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "invalid"
    response = client.post(
        "/api/research/capabilities/import",
        files={"file": ("SKILL.md", candidate()["instructions"].encode())},
    )
    assert response.json()["status"] == "invalid"
    assert any(i["code"] == "metadata_invalid" for i in response.json()["checks"]["issues"])


def test_workflow_compiles_native_skill_template_not_execution(api):
    client, _, service = api
    value = candidate()
    value["kind"] = "workflow"
    value["instructions"] = ""
    value["steps"] = [
        {
            "title": "资料核对",
            "instruction": "核对来源和缺失",
            "skill_id": "document-reading",
            "tools": ["research_run_script"],
        },
        {"title": "交付", "instruction": "仅生成实际文件", "tools": []},
    ]
    row = create(client, value)
    result = client.post(f"/api/research/capabilities/{row['id']}/publish")
    assert result.status_code == 200, result.text
    compiled = (
        service.capabilities.native_root / result.json()["native_name"] / "SKILL.md"
    ).read_text()
    assert "步骤模板" in compiled and "未执行" in compiled and "document-reading" in compiled
    assert "1. 资料核对" in compiled and "2. 交付" in compiled


def test_research_script_requires_explicit_review_and_never_executes(api):
    client, _, _ = api
    value = candidate()
    value["files"].append(
        {
            "path": "scripts/research.py",
            "content": "raise RuntimeError('never execute')",
        }
    )
    row = create(client, value)
    base = f"/api/research/capabilities/{row['id']}"
    check = client.post(base + "/check").json()
    assert any(i["code"] == "script_review_required" for i in check["issues"])
    assert client.post(base + "/publish").status_code == 422
    reviewed = next(
        f["sha256"] for f in client.get(base).json()["draft"]["files"] if f["path"].endswith(".py")
    )
    value["reviewed_scripts"] = [reviewed]
    assert client.patch(base + "/draft", json=value).status_code == 200
    assert client.post(base + "/publish").status_code == 200
