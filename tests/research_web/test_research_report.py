"""Research report bytes and evidence acceptance, independent of live inference."""

import json

import pdfplumber
import pytest
from docx import Document

from app.research_web.resources.research_report import write_research_report


def payload():
    return {
        "task_id": "a" * 24,
        "title": "黄金与美元研究",
        "as_of": "2026-10-13",
        "required_sections": ["风险"],
        "sections": [
            {"heading": "风险", "text": "黄金价格存在不确定性。", "citations": ["file:abc"]}
        ],
        "sources": [{"id": "file:abc", "title": "本会话上传资料"}],
        "notes": [],
        "missing": ["没有完整历史序列"],
    }


def test_chinese_pdf_word_and_page_share_content_and_missing(tmp_path):
    result = write_research_report(tmp_path, payload())
    assert set(result) == {"json", "html", "docx", "pdf"}
    with pdfplumber.open(result["pdf"]) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        assert len(pdf.pages) >= 1
        assert "黄金价格存在不确定性" in text
        assert "没有完整历史序列" in text
        assert "本会话上传资料" in text
    assert b"/FontFile2" in result["pdf"].read_bytes()
    assert "黄金价格存在不确定性" in "\n".join(p.text for p in Document(result["docx"]).paragraphs)
    assert "本会话上传资料" in result["html"].read_text()
    assert json.loads(result["json"].read_text())["task_id"] == "a" * 24


def test_report_refuses_undefined_citations_and_executable_source_urls(tmp_path):
    value = payload()
    value["sections"][0]["citations"] = ["other-session:unknown"]
    with pytest.raises(ValueError):
        write_research_report(tmp_path, value)
    value = payload()
    value["sources"][0]["url"] = "javascript:alert(1)"
    with pytest.raises(ValueError):
        write_research_report(tmp_path, value)


def test_report_quality_cannot_pass_without_observed_sources(tmp_path):
    from app.research_web.research_evidence import report_projection
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "研究")["id"]
    value = payload()
    value["sections"][0]["citations"] = []
    value["sources"] = []
    value["missing"] = []
    write_research_report(store.directory(sid) / "outputs", value)
    report = report_projection(store, sid, store.files(sid), [], "a" * 24)
    assert report["quality"] == "incomplete"
    assert "sources_missing" in report["issues"]


def test_report_rejects_duplicate_artifacts_and_missing_note_lineage(tmp_path):
    from app.research_web.research_evidence import report_projection
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "研究")["id"]
    value = payload()
    value["missing"] = []
    result = write_research_report(store.directory(sid) / "outputs", value)
    report = json.loads(result["json"].read_text())
    report["artifacts"] = [report["artifacts"][0]] * 3
    result["json"].write_text(json.dumps(report))
    projected = report_projection(store, sid, store.files(sid), value["sources"], value["task_id"])
    assert projected["quality"] == "incomplete"
    assert "report_artifact_formats_invalid" in projected["issues"]
    assert "section_note_lineage_missing:风险" in projected["issues"]


def test_complete_lineage_requires_independent_delivery_and_current_hashes(tmp_path):
    from app.research_web.research_evidence import report_projection
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "研究")["id"]
    value = payload()
    value["missing"] = []
    value["sections"][0]["id"] = "risk"
    value["notes"] = [{"stage_id": "risk", "text": "资料中的风险说明。", "citations": ["file:abc"]}]
    result = write_research_report(store.directory(sid) / "outputs", value)
    manifest = json.loads(result["json"].read_text())
    delivery = {"files": [{**a, "valid": True} for a in manifest["artifacts"]]}

    def project(task=value["task_id"], verified=delivery):
        return report_projection(store, sid, store.files(sid), value["sources"], task, verified)

    assert project()["quality"] == "checked"
    assert project(verified=None)["quality"] == "incomplete"
    result["html"].write_text("<html>替换内容</html>")
    assert project()["quality"] == "incomplete"
    assert any(issue.startswith("report_artifact_changed:") for issue in project()["issues"])
    assert project(task="b" * 24)["quality"] == "stale"
    assert "notes" not in project(task="b" * 24)


@pytest.mark.skipif(__import__("sys").platform != "darwin", reason="native macOS sandbox")
def test_chinese_pdf_generation_in_real_research_sandbox(tmp_path):
    import shutil
    import sys
    from pathlib import Path

    from app.research_web.sandbox import SandboxConfig, run_script
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "沙箱中文报告")["id"]
    session = store.directory(sid)
    shutil.copytree(Path("app/research_web/resources"), session / "resources", dirs_exist_ok=True)
    code = (
        "import sys, json, pdfplumber\n"
        "from research_report import write_research_report\n"
        f"paths = write_research_report('outputs', {payload()!r})\n"
        "with pdfplumber.open(paths['pdf']) as pdf:\n"
        "    assert '黄金价格存在不确定性' in ''.join(page.extract_text() or '' for page in pdf.pages)\n"
        "print('sandbox-pdf-reopened')\n"
    )
    result = run_script(
        SandboxConfig(research_root=store.root, python=Path(sys.executable), timeout_seconds=30),
        session,
        code,
    )
    assert result.status == "completed", result.stderr
    assert "sandbox-pdf-reopened" in result.stdout
    assert len([f for f in store.files(sid) if f["name"].endswith(".pdf")]) == 1


@pytest.mark.parametrize("bad_name", [None, 42])
def test_invalid_artifact_name_returns_quality_gap_instead_of_raising(tmp_path, bad_name):
    from app.research_web.research_evidence import report_projection
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "无效产物")["id"]
    result = write_research_report(store.directory(sid) / "outputs", payload())
    manifest = json.loads(result["json"].read_text())
    manifest["artifacts"][0]["name"] = bad_name
    result["json"].write_text(json.dumps(manifest))
    view = report_projection(store, sid, store.files(sid), [], "a" * 24)
    assert view["quality"] == "incomplete"
    assert "report_artifact_invalid" in view["issues"]


@pytest.mark.skipif(__import__("sys").platform != "darwin", reason="native macOS sandbox")
def test_bundled_font_absolute_helper_avoids_cwd_without_expanding_sandbox(tmp_path):
    import shutil
    import sys
    from pathlib import Path

    from app.research_web.sandbox import SandboxConfig, run_script
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    session = store.directory(store.create("fingpt", "字体路径夹具")["id"])
    shutil.copytree(Path("app/research_web/resources"), session / "resources", dirs_exist_ok=True)
    private = session / "resources/capabilities/not-admitted/1"
    private.mkdir(parents=True)
    (private / "canary.txt").write_text("private-synthetic-canary")
    config = SandboxConfig(
        research_root=store.root, python=Path(sys.executable), timeout_seconds=30
    )
    relative = run_script(
        config,
        session,
        "from matplotlib.font_manager import FontProperties\n"
        "print(FontProperties(fname='resources/fonts/NotoSansSC-Regular.ttf').get_name())\n",
    )
    assert relative.status == "failed"
    assert "PermissionError" in relative.stderr
    fixed = run_script(
        config,
        session,
        "import os, socket, errno\n"
        "from pathlib import Path\n"
        "from matplotlib.font_manager import FontProperties\n"
        "from research_helpers import chinese_font_path\n"
        "font = chinese_font_path()\n"
        "assert font.is_absolute()\n"
        "assert FontProperties(fname=str(font)).get_name()\n"
        "def denied(operation):\n"
        "    try: operation()\n"
        "    except OSError as error: assert error.errno in (errno.EPERM, errno.EACCES)\n"
        "    else: raise AssertionError('sandbox restriction lost')\n"
        "denied(os.getcwd)\n"
        "denied(lambda: socket.create_connection(('127.0.0.1', 9), timeout=1))\n"
        "denied(lambda: Path('resources/capabilities/not-admitted/1/canary.txt').read_text())\n"
        "print('font-ready-guards-preserved')\n",
    )
    assert fixed.status == "completed", fixed.stderr
    assert "font-ready-guards-preserved" in fixed.stdout


@pytest.mark.parametrize("unsafe", ["missing", "symlink"])
def test_chinese_font_helper_fails_with_path_free_error(tmp_path, monkeypatch, caplog, unsafe):
    from app.research_web.resources import research_helpers

    module_file = tmp_path / "research_helpers.py"
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    if unsafe == "symlink":
        target = tmp_path / "synthetic.ttf"
        target.write_bytes(b"not-a-font")
        (fonts / "NotoSansSC-Regular.ttf").symlink_to(target)
    monkeypatch.setattr(research_helpers, "__file__", str(module_file))
    with pytest.raises(ValueError, match="^research_chinese_font_unavailable$") as caught:
        research_helpers.chinese_font_path()
    assert caught.value.__cause__ is None
    assert str(tmp_path) not in caplog.text
