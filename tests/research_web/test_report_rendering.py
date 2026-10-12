"""Reviewed report projection regressions."""

import asyncio
import json
import sys
import zipfile
from pathlib import Path

import pytest
from docx import Document
from openpyxl import Workbook, load_workbook

from app.research_web.report_rendering import render_report_payload
from app.research_web.store import Store


def test_document_business_native_word_generation_routes_to_manager(tmp_path):
    from io import BytesIO

    from app.research_web.report_rendering import execute_document_operation

    store = Store(tmp_path)
    sid = store.create("claw", "Word Native 合同")["id"]
    data = BytesIO()
    Document().save(data)

    class NativeFixture:
        async def run_document(self, selected_session, document):
            assert selected_session == sid and document["format"] == "docx"
            assert document["source"] is None
            assert document["content"]["title"] == "Word 验收报告"
            return {
                "outcome": "available",
                "output_bytes": data.getvalue(),
                "verification_id": "word-fixture",
                "diagnostics": {"cleanup_outcome": "confirmed"},
            }

    result = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "docx",
                "operation": "generate",
                "mode": "native",
                "content": {"title": "Word 验收报告"},
            },
            native_manager=NativeFixture(),
        )
    )
    assert result["status"] == "completed"
    assert result["mode"] == "native" and result["verification_id"] == "word-fixture"


def test_document_business_native_ppt_routes_to_manager_and_publishes_owned_copy(tmp_path):
    import hashlib

    from app.research_web.report_rendering import execute_document_operation

    store = Store(tmp_path)
    sid = store.create("claw", "PPT Native 合同")["id"]
    raw = Path("app/research_web/office-template.pptx").read_bytes()
    source = store.directory(sid) / "inputs" / "native.pptx"
    source.write_bytes(raw)
    file_id = store.files(sid)[0]["id"]

    class NativeFixture:
        async def run_document(self, selected_session, document):
            assert selected_session == sid
            assert document["format"] == "pptx"
            assert document["source"] == raw
            return {
                "outcome": "available",
                "output_bytes": raw,
                "verification_id": "fixture",
                "diagnostics": {"cleanup_outcome": "confirmed"},
                "native_readback": {"targets_verified": 4},
            }

    result = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "pptx",
                "operation": "modify",
                "mode": "native",
                "file_id": file_id,
                "expected_sha256": hashlib.sha256(raw).hexdigest(),
                "changes": [],
            },
            native_manager=NativeFixture(),
        )
    )
    assert result["status"] == "completed"
    assert result["mode"] == "native" and result["verification_id"] == "fixture"
    assert source.read_bytes() == raw
    with store.open_file(sid, result["output"]["id"])[0] as stream:
        assert stream.read() == raw


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS sandbox")
def test_document_business_word_versions_preserve_input_and_reject_stale_fingerprint(tmp_path):
    from app.research_web.report_rendering import execute_document_operation

    store = Store(tmp_path)
    sid = store.create("claw", "文档局部修改")["id"]
    request = {
        "format": "docx",
        "operation": "generate",
        "mode": "file",
        "content": {
            "title": "Word 验收报告",
            "paragraphs": ["这段内容保持不变。", "报告版本 A。"],
            "tables": [[["项目", "数值"], ["样本", "2"]]],
        },
    }
    generated = asyncio.run(execute_document_operation(store, sid, request))
    assert generated["status"] == "completed", generated
    first = generated["output"]
    read = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "docx",
                "operation": "read",
                "mode": "file",
                "file_id": first["id"],
            },
        )
    )
    assert read["document"]["paragraphs"][0]["text"] == "Word 验收报告"
    edits = {
        "format": "docx",
        "operation": "modify",
        "mode": "file",
        "file_id": first["id"],
        "expected_sha256": read["sha256"],
        "changes": [
            {"kind": "paragraph", "index": 2, "text": "报告版本 B。"},
            {"kind": "table_cell", "table": 0, "row": 1, "column": 1, "text": "3"},
        ],
    }
    changed = asyncio.run(execute_document_operation(store, sid, edits))
    assert changed["status"] == "completed", changed
    with store.open_file(sid, changed["output"]["id"])[0] as stream:
        output = Document(stream)
    assert output.paragraphs[0].style.name == "Title"
    assert output.paragraphs[0].runs[0].bold is True
    assert output.paragraphs[1].text == "这段内容保持不变。"
    assert output.paragraphs[2].text == "报告版本 B。"
    assert output.tables[0].cell(1, 1).text == "3"
    original = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "docx",
                "operation": "read",
                "mode": "file",
                "file_id": first["id"],
            },
        )
    )
    assert original["sha256"] == read["sha256"]
    assert original["document"]["paragraphs"][2]["text"] == "报告版本 A。"
    edits["expected_sha256"] = "0" * 64
    conflict = asyncio.run(execute_document_operation(store, sid, edits))
    assert conflict["status"] == "conflict"


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS sandbox")
def test_document_business_excel_does_not_claim_recalculation(tmp_path):
    from app.research_web.report_rendering import execute_document_operation

    store = Store(tmp_path)
    sid = store.create("claw", "Excel 文件模式")["id"]
    result = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "xlsx",
                "mode": "file",
                "operation": "generate",
                "content": {
                    "sheets": [
                        {"name": "Inputs", "rows": [["数值"], [2], [3]]},
                        {"name": "Summary", "rows": [["合计", "=SUM(Inputs!A2:A3)"]]},
                    ]
                },
            },
        )
    )
    assert result["status"] == "completed", result
    source = result["output"]["id"]
    read = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "xlsx",
                "mode": "file",
                "operation": "read",
                "file_id": source,
            },
        )
    )
    updated = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "xlsx",
                "mode": "file",
                "operation": "modify",
                "file_id": source,
                "expected_sha256": read["sha256"],
                "changes": [{"kind": "cell", "sheet": "Inputs", "cell": "A2", "value": 7}],
            },
        )
    )
    assert updated["status"] == "completed", updated
    assert updated["document"]["calculation"] == "not_recalculated"
    with store.open_file(sid, updated["output"]["id"])[0] as stream:
        book = load_workbook(stream)
        assert book["Inputs"]["A2"].value == 7
        assert book["Summary"]["B1"].value == "=SUM(Inputs!A2:A3)"
        book.close()


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS sandbox")
def test_document_business_rejects_embedded_word_object(tmp_path):
    import hashlib

    from docx.oxml import OxmlElement

    from app.research_web.report_rendering import execute_document_operation

    store = Store(tmp_path)
    sid = store.create("claw", "复杂对象")["id"]
    path = store.directory(sid) / "inputs" / "complex.docx"
    document = Document()
    run = document.add_paragraph().add_run("保持对象")
    run._r.append(OxmlElement("w:object"))
    document.save(path)
    original = path.read_bytes()
    fid = store.files(sid)[0]["id"]
    result = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "docx",
                "operation": "modify",
                "mode": "file",
                "file_id": fid,
                "expected_sha256": hashlib.sha256(original).hexdigest(),
                "changes": [{"kind": "paragraph", "index": 0, "text": "不可破坏"}],
            },
        )
    )
    assert result["status"] == "failed"
    assert path.read_bytes() == original
    assert not list((store.directory(sid) / "outputs").iterdir())


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS sandbox")
def test_document_business_failed_receipt_does_not_publish_output(tmp_path, monkeypatch):
    from dataclasses import replace

    from app.research_web import report_rendering

    store = Store(tmp_path)
    sid = store.create("claw", "回执失败")["id"]
    original = report_rendering.sandbox.run_script

    def broken_receipt(*args):
        result = original(*args)
        assert result.status == "completed"
        return replace(result, stdout="invalid JSON")

    monkeypatch.setattr(report_rendering.sandbox, "run_script", broken_receipt)
    result = asyncio.run(
        report_rendering.execute_document_operation(
            store,
            sid,
            {
                "format": "docx",
                "operation": "generate",
                "mode": "file",
                "content": {"title": "回执失败"},
            },
        )
    )
    assert result["status"] == "failed"
    assert store.files(sid) == []
    assert not list((store.directory(sid) / "tmp").glob("document-result-*"))


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS sandbox")
def test_document_business_ppt_uses_visible_order_and_preserves_untouched_part(tmp_path):
    import hashlib

    from app.research_web.report_rendering import execute_document_operation

    store = Store(tmp_path)
    sid = store.create("claw", "PPT页序")["id"]
    source = store.directory(sid) / "inputs" / "deck.pptx"
    p = "http://schemas.openxmlformats.org/presentationml/2006/main"
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    def slide(text):
        return (
            f'<p:sld xmlns:p="{p}" xmlns:a="{a}" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            'xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main" mc:Ignorable="a14">'
            '<p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/></p:nvSpPr>'
            f"<p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody>"
            "</p:sp></p:spTree></p:cSld></p:sld>"
        ).encode()

    untouched = slide("本页保持不变")
    with zipfile.ZipFile(source, "w") as package:
        package.writestr(
            "ppt/presentation.xml",
            f'<p:presentation xmlns:p="{p}" xmlns:r="{r}"><p:sldIdLst>'
            '<p:sldId id="256" r:id="second"/><p:sldId id="257" r:id="first"/>'
            "</p:sldIdLst></p:presentation>",
        )
        package.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="first" Type="{r}/slide" Target="slides/slide1.xml"/>'
            f'<Relationship Id="second" Type="{r}/slide" Target="slides/slide2.xml"/>'
            "</Relationships>",
        )
        package.writestr("ppt/slides/slide1.xml", slide("结论版本 A"))
        package.writestr("ppt/slides/slide2.xml", untouched)
    raw = source.read_bytes()
    result = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "pptx",
                "operation": "modify",
                "mode": "file",
                "file_id": store.files(sid)[0]["id"],
                "expected_sha256": hashlib.sha256(raw).hexdigest(),
                "changes": [
                    {"kind": "shape_text", "slide": 2, "shape_id": "2", "text": "结论版本 B"}
                ],
            },
        )
    )
    assert result["status"] == "completed", result
    with (
        store.open_file(sid, result["output"]["id"])[0] as stream,
        zipfile.ZipFile(stream) as package,
    ):
        assert package.read("ppt/slides/slide2.xml") == untouched
        changed = package.read("ppt/slides/slide1.xml").decode()
        assert "结论版本 B" in changed
        assert "xmlns:a14=" in changed and 'mc:Ignorable="a14"' in changed
    assert source.read_bytes() == raw


@pytest.mark.parametrize("replace_output", [False, True])
@pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS sandbox")
def test_document_business_registration_failure_removes_only_owned_output(
    tmp_path, monkeypatch, replace_output
):
    from app.research_web import report_rendering
    from app.research_web.store import StoreError

    store = Store(tmp_path)
    sid = store.create("claw", "登记失败")["id"]
    root = store.directory(sid)

    def registration_failure(_sid):
        path = root / "outputs" / "failure.docx"
        assert path.is_file()
        if replace_output:
            path.unlink()
            path.write_bytes(b"external replacement")
        raise StoreError("fixture registration failure")

    monkeypatch.setattr(store, "files", registration_failure)
    result = asyncio.run(
        report_rendering.execute_document_operation(
            store,
            sid,
            {
                "format": "docx",
                "operation": "generate",
                "mode": "file",
                "output_name": "failure.docx",
                "content": {"title": "登记失败"},
            },
        )
    )
    assert result["status"] == "failed"
    if replace_output:
        assert (root / "outputs" / "failure.docx").read_bytes() == b"external replacement"
    else:
        assert not (root / "outputs" / "failure.docx").exists()
    assert not list((root / "tmp").glob("document-result-*"))


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS sandbox")
def test_document_business_cancel_waits_for_worker_and_never_publishes(tmp_path, monkeypatch):
    import threading

    from app.research_web import report_rendering

    store = Store(tmp_path)
    sid = store.create("claw", "取消")["id"]
    started, release = threading.Event(), threading.Event()
    original = report_rendering.sandbox.run_script

    def controlled_worker(*args):
        started.set()
        assert release.wait(3)
        return original(*args)

    monkeypatch.setattr(report_rendering.sandbox, "run_script", controlled_worker)

    async def scenario():
        task = asyncio.create_task(
            report_rendering.execute_document_operation(
                store,
                sid,
                {
                    "format": "docx",
                    "operation": "generate",
                    "mode": "file",
                    "content": {"title": "取消"},
                },
            )
        )
        assert await asyncio.to_thread(started.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert store.files(sid) == []
    assert not list((store.directory(sid) / "tmp").glob("document-result-*"))


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS sandbox")
def test_document_business_generates_real_template_ppt_and_precisely_updates_second_slide(tmp_path):
    from app.research_web.report_rendering import execute_document_operation

    store = Store(tmp_path)
    sid = store.create("claw", "PPT文件闭环")["id"]
    result = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "pptx",
                "mode": "file",
                "operation": "generate",
                "content": {
                    "slides": [
                        {"title": "研究概览", "body": "本页保持不变"},
                        {"title": "结论版本 A", "body": "样本数为 2"},
                    ]
                },
            },
        )
    )
    assert result["status"] == "completed", result
    source_id = result["output"]["id"]
    read = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "pptx",
                "mode": "file",
                "operation": "read",
                "file_id": source_id,
            },
        )
    )
    with store.open_file(sid, source_id)[0] as stream:
        original = stream.read()
    changed = asyncio.run(
        execute_document_operation(
            store,
            sid,
            {
                "format": "pptx",
                "mode": "file",
                "operation": "modify",
                "file_id": source_id,
                "expected_sha256": read["sha256"],
                "changes": [
                    {"kind": "shape_text", "slide": 2, "shape_id": "2", "text": "结论版本 B"},
                    {"kind": "shape_text", "slide": 2, "shape_id": "3", "text": "样本数为 3"},
                ],
            },
        )
    )
    assert changed["status"] == "completed", changed
    assert len(changed["document"]["slides"]) == 2
    assert changed["document"]["slides"][1]["objects"][0]["text"] == "结论版本 B"
    with (
        store.open_file(sid, changed["output"]["id"])[0] as stream,
        zipfile.ZipFile(stream) as updated,
    ):
        with zipfile.ZipFile(__import__("io").BytesIO(original)) as initial:
            assert updated.read("ppt/slides/slide1.xml") == initial.read("ppt/slides/slide1.xml")
        assert "样本数为 3" in updated.read("ppt/slides/slide2.xml").decode()
    with store.open_file(sid, source_id)[0] as stream:
        assert stream.read() == original


def test_document_business_refuses_paths_and_explicit_native_fallback(tmp_path):
    from app.research_web.report_rendering import execute_document_operation
    from app.research_web.store import StoreError

    store = Store(tmp_path)
    sid = store.create("claw", "边界")["id"]
    request = {"format": "docx", "operation": "generate", "mode": "native"}
    result = asyncio.run(execute_document_operation(store, sid, request))
    assert result["status"] == "unavailable"
    assert result["mode"] == "native"
    assert store.files(sid) == []
    request.update(mode="file", output_name="../escape.docx")
    with pytest.raises(StoreError):
        asyncio.run(execute_document_operation(store, sid, request))
    request.update(output_name="owned.docx", script="arbitrary code")
    with pytest.raises(StoreError):
        asyncio.run(execute_document_operation(store, sid, request))


@pytest.mark.skipif(sys.platform != "darwin", reason="renderer requires native macOS sandbox")
def test_report_payload_projects_to_real_office_and_html_files(tmp_path: Path):
    store = Store(tmp_path)
    session = store.create("claw", "report projection")
    root = store.directory(session["id"])
    (root / "outputs" / "report_payload.json").write_text(
        json.dumps(
            {
                "title": "真实周报",
                "as_of": "2026-09-04",
                "summary": "基于锁定资料形成。",
                "sections": [
                    {
                        "id": "market",
                        "title": "市场回顾",
                        "content": "市场数据存在部分缺失。",
                    },
                    {
                        "id": "risk",
                        "title": "风险提示",
                        "content": "历史数据不代表未来。",
                    },
                ],
                "sources": [{"title": "DataHub 快照", "as_of": "2026-09-04"}],
                "missing": ["行业数据尚未更新"],
            },
            ensure_ascii=False,
        )
    )

    result = asyncio.run(render_report_payload(store, session["id"], ["docx", "html", "xlsx"]))

    assert result["status"] == "completed"
    for name in ("report.docx", "report.html", "report.xlsx"):
        assert (root / "outputs" / name).stat().st_size > 0


@pytest.mark.skipif(sys.platform != "darwin", reason="renderer requires native macOS sandbox")
def test_report_projection_requires_structured_payload(tmp_path: Path):
    store = Store(tmp_path)
    session = store.create("claw", "missing payload")
    result = asyncio.run(render_report_payload(store, session["id"], ["html"]))
    assert result["status"] == "missing_payload"


@pytest.mark.skipif(sys.platform != "darwin", reason="renderer requires native macOS sandbox")
def test_report_workflow_projection_uses_locked_template_and_refreshed_workbook(
    tmp_path: Path,
):
    store = Store(tmp_path)
    session = store.create("claw", "locked workflow projection")
    root = store.directory(session["id"])
    templates = root / "inputs" / "report-workflow" / "templates"
    workbooks = root / "inputs" / "report-workflow" / "workbooks"
    templates.mkdir(parents=True)
    workbooks.mkdir(parents=True)

    document = Document()
    document.add_paragraph("{{market}}")
    document.save(templates / "report.docx")
    workbook = Workbook()
    workbook.active["A1"] = "locked-refreshed-data"
    workbook.save(workbooks / "source.xlsx")
    (root / "inputs" / "report-workflow" / "run-context.json").write_text(
        json.dumps({"primary_workbook": "workbooks/source.xlsx"})
    )
    (root / "outputs" / "report_payload.json").write_text(
        json.dumps(
            {
                "title": "锁定周报",
                "as_of": "2026-09-07",
                "sections": [{"id": "market", "title": "市场", "content": "真实正文"}],
            },
            ensure_ascii=False,
        )
    )

    result = asyncio.run(render_report_payload(store, session["id"], ["docx", "html", "xlsx"]))

    assert result["status"] == "completed"
    rendered = Document(root / "outputs" / "report.docx")
    assert "真实正文" in "\n".join(item.text for item in rendered.paragraphs)
    delivered = load_workbook(root / "outputs" / "report.xlsx", data_only=False)
    assert delivered.active["A1"].value == "locked-refreshed-data"


@pytest.mark.skipif(sys.platform != "darwin", reason="renderer requires native macOS sandbox")
def test_report_projection_normalizes_block_families_and_reports_missing_blocks(
    tmp_path: Path,
):
    store = Store(tmp_path)
    session = store.create("claw", "block-family report projection")
    root = store.directory(session["id"])
    workflow = root / "inputs" / "report-workflow"
    workflow.mkdir(parents=True)
    (workflow / "run-context.json").write_text(
        json.dumps(
            {
                "name": "华安ETF周报",
                "primary_workbook": None,
                "blocks": [
                    {"id": "block_001", "title": "市场回顾", "required": True},
                    {"id": "block_002", "title": "行业观察", "required": True},
                    {"id": "block_003", "title": "数据表", "required": True},
                ],
            },
            ensure_ascii=False,
        )
    )
    (root / "outputs" / "report_payload.json").write_text(
        json.dumps(
            {
                "workflow_id": "huaan-etf-weekly",
                "report_period": {"end_date_trading": "2026-09-04"},
                "blocks": {"block_001": {"title": "市场回顾", "text": "市场真实正文。"}},
                "date_blocks": {
                    "block_002": {
                        "title": "行业观察",
                        "status": "missing_unresolved",
                        "text": "模型提供了缺失解释，但没有可交付正文。",
                    }
                },
                "table_blocks": {"block_003": {"title": "数据表", "content": "表格口径说明。"}},
                "missing": [
                    {
                        "block": "block_002",
                        "title": "行业观察",
                        "reason": "缺少新闻证据",
                    }
                ],
                "sources": ["锁定的数据快照"],
            },
            ensure_ascii=False,
        )
    )

    result = asyncio.run(render_report_payload(store, session["id"], ["docx", "html"]))

    assert result["status"] == "completed"
    assert result["missing_blocks"] == ["block_002"]
    rendered = Document(root / "outputs" / "report.docx")
    text = "\n".join(item.text for item in rendered.paragraphs)
    assert "华安ETF周报" in text
    assert "市场真实正文" in text
    assert "缺少新闻证据" in text


@pytest.mark.skipif(sys.platform != "darwin", reason="renderer requires native macOS sandbox")
def test_report_projection_replaces_pptx_placeholder_split_across_text_runs(
    tmp_path: Path,
):
    store = Store(tmp_path)
    session = store.create("claw", "split PPTX placeholder")
    root = store.directory(session["id"])
    templates = root / "inputs" / "report-workflow" / "templates"
    templates.mkdir(parents=True)
    with zipfile.ZipFile(templates / "deck.pptx", "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr(
            "ppt/slides/slide1.xml",
            (
                '<p:sld xmlns:p="urn:p" xmlns:a="urn:a"><p:cSld><a:p>'
                "<a:r><a:t>前缀 {{市</a:t></a:r>"
                "<a:r><a:t>场概览}}</a:t></a:r>"
                "<a:r><a:t> 后缀</a:t></a:r>"
                "</a:p></p:cSld></p:sld>"
            ),
        )
    (root / "outputs" / "report_payload.json").write_text(
        json.dumps(
            {
                "title": "投资风向标",
                "sections": [{"id": "market", "title": "市场概览", "content": "真实市场正文"}],
            },
            ensure_ascii=False,
        )
    )

    result = asyncio.run(render_report_payload(store, session["id"], ["pptx"]))

    assert result["status"] == "completed"
    with zipfile.ZipFile(root / "outputs" / "report.pptx") as package:
        slide = package.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "{{市场概览}}" not in slide
    assert "真实市场正文" in slide
