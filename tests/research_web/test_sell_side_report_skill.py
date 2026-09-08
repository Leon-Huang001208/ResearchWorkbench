"""Product contract and sandbox evidence for the sell-side report specialist."""

import hashlib
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from test_capabilities import api as api_fixture

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.sandbox import SandboxConfig, run_script

api = api_fixture
SLUG = "sell-side-report-reader"
PROJECT = Path(__file__).resolve().parents[2]
SKILL_ROOT = PROJECT / "app/research_web/skills" / SLUG


def load_script(name):
    path = SKILL_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(f"sell_side_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = previous


def valid_digest():
    citation = {"locator": "p.12", "source": "用户上传研报"}
    return {
        "schemaVersion": 1,
        "source": {
            "title": "样例研报",
            "publishedAt": "2026-09-01",
            "accessStatus": "full_text",
            "locatorScheme": "page",
        },
        "baseline": {
            "type": "prior_public_information",
            "asOf": "2026-08-31",
            "description": "事件发生前已公开信息",
        },
        "claimLayers": {
            "facts": [{"text": "披露产量数据", "citations": [citation]}],
            "sourceOpinions": [{"text": "研报认为需求回升", "citations": [citation]}],
            "newEvidence": [{"text": "相对基线新增了产量指引", "citations": [citation]}],
            "inferences": [
                {
                    "text": "利用率或在条件满足时回升",
                    "premises": ["披露产量数据"],
                    "citations": [citation],
                }
            ],
        },
        "counterEvidence": [
            {"text": "终端库存仍高", "effect": "削弱需求判断", "citations": [citation]}
        ],
        "scenarios": [
            {
                "name": "基准",
                "conditions": ["库存继续回落"],
                "window": "未来3个月",
                "signals": ["利用率"],
                "invalidationSignals": ["库存重新上升"],
            }
        ],
        "actionAssessment": {
            "label": "等待验证",
            "attribution": "研报隐含",
            "audience": "跟踪该产业链的研究者",
            "horizon": "未来3个月",
            "conditions": ["库存继续回落"],
            "citations": [citation],
            "invalidationSignals": ["库存重新上升"],
        },
        "limitations": ["无法验证样本外推性"],
        "knowledgeFramework": {
            "scope": "样例产业链",
            "nodes": [
                {"id": "demand", "label": "需求 <修复>"},
                {"id": "util", "label": "利用率 & 利润"},
            ],
            "edges": [
                {
                    "from": "demand",
                    "to": "util",
                    "relation": "条件性驱动 <&>",
                    "citations": [citation],
                }
            ],
        },
    }


def test_builtin_metadata_text_boundaries_and_reviewed_resources(api):
    client, _, _ = api
    rows = client.get("/api/research/capabilities").json()["items"]
    assert len([row for row in rows if row["kind"] == "skill"]) == 10
    assert len([row for row in rows if row["kind"] == "workflow"]) == 4
    assert not any("router" in row["id"] for row in rows)
    row = next(row for row in rows if row["id"] == SLUG)
    assert row["metadata"] == {
        "slug": SLUG,
        "name": "研报增量分析",
        "description": "聚焦卖方研报或研究文章的增量、公开时序、可信度与证伪；不用于一般资料提取或个人买卖建议。",
        "category": "研报与资料",
        "inputs": [
            {
                "name": "question",
                "label": "研究问题与资料",
                "type": "text",
                "required": True,
            }
        ],
        "scenarios": ["研报增量与公开时序研究"],
        "default_formats": [],
        "required_tools": ["research_run_script", "web_search"],
        "dependencies": [],
    }
    detail = client.get(f"/api/research/capabilities/{SLUG}").json()
    header = yaml.safe_load(detail["draft"]["instructions"].split("---", 2)[1])
    assert header["name"] == SLUG
    text = "\n".join(
        [detail["draft"]["instructions"]]
        + [item.get("content", "") for item in detail["draft"]["files"]]
    )
    for required in (
        "document-reading",
        "research_helpers.read_pdf",
        "搜索摘要",
        "证据不足",
        "无法判断",
        "微信",
        "视觉证据受限",
        "研报明示",
        "研报隐含",
        "失效信号",
    ):
        assert required in text
    lowered = text.lower()
    for forbidden in (
        "zhengyan",
        "openai",
        "skill_dir",
        "poppler",
        "subprocess",
        "brew install",
        "apt install",
        "pip install",
    ):
        assert forbidden not in lowered

    scripts = [item for item in detail["draft"]["files"] if item["path"].endswith(".py")]
    assert {item["path"] for item in scripts} == {
        "scripts/render_knowledge_graph.py",
        "scripts/validate_digest.py",
    }
    assert {item["sha256"] for item in scripts} == set(detail["draft"]["reviewed_scripts"])
    check = client.post(f"/api/research/capabilities/{SLUG}/check").json()
    assert check["valid"] is True and check["issues"] == []


def test_export_has_stable_hashes_and_reimports(api, monkeypatch, tmp_path):
    client, _, _ = api
    response = client.get(f"/api/research/capabilities/{SLUG}/versions/1/export")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert {
            "SKILL.md",
            "capability.json",
            "references/evidence-protocol.md",
            "scripts/validate_digest.py",
            "scripts/render_knowledge_graph.py",
        } <= names
        expected = {
            name: hashlib.sha256(archive.read(name)).hexdigest()
            for name in names
            if name not in {"SKILL.md", "capability.json"}
        }

    monkeypatch.setattr("app.research_web.capabilities.catalog.seed_packages", list)
    imported = CapabilityCatalog(tmp_path / "reimport").import_bytes(
        "sell-side.zip", response.content
    )
    assert imported["status"] == "invalid"
    assert {item["path"]: item["sha256"] for item in imported["draft"]["files"]} == expected
    assert {
        item["path"]
        for item in imported["checks"]["issues"]
        if item["code"] == "script_review_required"
    } == {"scripts/validate_digest.py", "scripts/render_knowledge_graph.py"}


def test_validator_accepts_complete_structure_and_rejects_evidence_gaps(caplog):
    module = load_script("validate_digest.py")
    result = module.validate_digest(valid_digest())
    assert result == {"valid": True, "errors": [], "warnings": []}

    incomplete = valid_digest()
    incomplete["source"]["accessStatus"] = "search_snippet"
    incomplete["baseline"] = {}
    incomplete["claimLayers"]["facts"][0]["citations"] = []
    incomplete["counterEvidence"] = []
    incomplete["scenarios"][0]["invalidationSignals"] = []
    incomplete["actionAssessment"].pop("audience")
    result = module.validate_digest(incomplete)
    assert result["valid"] is False
    assert any("accessStatus" in item for item in result["errors"])
    assert any("baseline" in item for item in result["errors"])
    assert any("citations" in item for item in result["errors"])
    assert any("counterEvidence" in item for item in result["errors"])
    assert any("invalidationSignals" in item for item in result["errors"])
    assert any("audience" in item for item in result["errors"])
    assert any(record.name.startswith("research.skill") for record in caplog.records)


def test_svg_is_deterministic_escaped_and_rejects_unsupported_relationship(caplog):
    module = load_script("render_knowledge_graph.py")
    digest = valid_digest()
    first = module.build_svg(digest)
    second = module.build_svg(digest)
    assert first == second
    assert "<script>" not in first and "&lt;修复&gt;" in first
    assert "&amp;" in first and "p.12" in first

    digest["knowledgeFramework"]["edges"][0]["citations"] = []
    with pytest.raises(ValueError, match="source locator"):
        module.build_svg(digest)
    assert any(record.name.startswith("research.skill") for record in caplog.records)


@pytest.mark.skipif(
    sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file(),
    reason="native macOS Seatbelt evidence only",
)
def test_packaged_scripts_run_inside_research_sandbox(tmp_path):
    catalog = CapabilityCatalog(tmp_path / "catalog")
    root = tmp_path / "research"
    session = root / "sessions" / str(uuid4())
    for name in ("inputs", "outputs", "tmp", "resources"):
        (session / name).mkdir(parents=True)
    catalog.snapshot(catalog.selection(SLUG), session)
    (session / "inputs/digest.json").write_text(
        json.dumps(valid_digest(), ensure_ascii=False), encoding="utf-8"
    )
    resource = f"resources/capabilities/{SLUG}/1/scripts"
    code = f"""
import json
from pathlib import Path
digest=json.loads(Path('inputs/digest.json').read_text(encoding='utf-8'))
def load(path):
    namespace={{'__name__':'reviewed_skill_resource'}}
    source=Path(path).read_text(encoding='utf-8')
    exec(compile(source,path,'exec'),namespace)
    return namespace
validator=load('{resource}/validate_digest.py')
result=validator['validate_digest'](digest)
assert result['valid'], result
renderer=load('{resource}/render_knowledge_graph.py')
svg=renderer['build_svg'](digest)
Path('outputs/graph.svg').write_text(svg, encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
"""
    result = run_script(
        SandboxConfig(research_root=root, python=Path(sys.executable)), session, code
    )
    assert result.status == "completed", result
    assert json.loads(result.stdout)["valid"] is True
    assert (session / "outputs/graph.svg").read_text(encoding="utf-8").startswith("<svg")
