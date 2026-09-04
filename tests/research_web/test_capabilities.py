"""Offline capability lifecycle and hostile-package regression tests."""

import io
import json
import stat
import zipfile

import pytest
from fastapi.testclient import TestClient
from test_api import NativeFixture

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
            "inputs": [{"name": "question", "label": "研究问题", "type": "text", "required": True}],
            "scenarios": ["解读研究资料"],
            "default_formats": ["md"],
            "required_tools": ["af_run_script"],
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
    assert len(rows) == 6
    assert {r["name"] for r in rows if r["kind"] == "skill"} == {
        "资料解读",
        "公司研究",
        "行业研究",
        "基金评价",
    }
    assert all(r["source"] == "builtin" and r["version"] == 1 for r in rows)
    assert len(client.get("/api/research/workflows").json()["items"]) == 2
    tools = client.get("/api/research/tools").json()["items"]
    assert {t["id"] for t in tools if t["selectable"]} == {
        "af_run_script",
        "datahub_get_fund_data",
        "datahub_search_news",
        "web_search",
    }
    assert next(t for t in tools if t["id"] == "af_public_data")["selectable"] is False
    assert all(t["parameters"] and t["source"] and t["conditions"] for t in tools)
    assert native.calls == []


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
    value["metadata"]["dependencies"] = ["af-nonexistent-distribution-987==1.0"]
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
    assert {c["code"] for c in checks["issues"]} >= {"tool_unavailable", "metadata_invalid"}
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
    assert not list(service.capabilities.native_root.glob("af-*"))


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
            "tools": ["af_run_script"],
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
        {"path": "scripts/research.py", "content": "raise RuntimeError('never execute')"}
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
