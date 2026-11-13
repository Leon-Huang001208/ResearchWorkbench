"""Test the FinGPT upload, turn and native report contracts with local fixtures."""

import base64
import json
import sys
import time
from io import BytesIO
from zipfile import ZipFile

import pytest
from docx import Document
from fastapi.testclient import TestClient
from openpyxl import Workbook
from PIL import Image
from test_api import NativeFixture
from test_report_formats import payload

from app.research_web import qa_execution, qa_model
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.main import create_app
from app.research_web.resources.research_report import (
    archive_report_version,
    pdf_bytes,
    required_report_formats,
    verify_rendered_artifact,
    write_research_report,
)
from app.research_web.service import ResearchService
from app.research_web.store import Store

BASE = "/api/research/sessions"


def report_files(tmp_path):
    value = payload()
    value["title"] = "格式验收 report fixture"
    return write_research_report(tmp_path, value, formats=("png", "pptx"))


def test_explicit_report_format_contract_includes_png_and_pptx():
    frozen = {"task_id": "a" * 24, "required_formats": ["md", "png", "pptx"]}
    assert set(required_report_formats(payload(), frozen)) == {"png", "pptx"}
    assert set(required_report_formats("仅生成 PNG、PPTX。")) == {"png", "pptx"}


def test_media_outputs_reopen_and_bind_to_canonical_report(tmp_path):
    paths = report_files(tmp_path)
    with Image.open(paths["png"]) as image:
        assert image.format == "PNG"
        assert image.size[0] > 0
        image.verify()
    with ZipFile(paths["pptx"]) as package:
        assert package.testzip() is None
        assert "ppt/presentation.xml" in package.namelist()
        text = b" ".join(
            package.read(name)
            for name in package.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        ).decode()
        assert "格式验收 report fixture" in text and "1401879" in text
    manifest = json.loads(paths["json"].read_bytes())
    assert archive_report_version(tmp_path)["missing_formats"] == []
    for kind in ("png", "pptx"):
        raw = paths[kind].read_bytes()
        verify_rendered_artifact(manifest, kind, raw)
        with pytest.raises(ValueError, match="research_report_render_binding_changed"):
            verify_rendered_artifact({**manifest, "title": "篡改标题"}, kind, raw)


def _attachment(tmp_path, extension):
    stream = BytesIO()
    if extension == "docx":
        document = Document()
        document.add_paragraph("report fixture")
        document.save(stream)
    elif extension == "xlsx":
        book = Workbook()
        book.active.append(["report fixture", 12.5])
        book.save(stream)
    elif extension == "pdf":
        return pdf_bytes({**payload(), "title": "report fixture"})
    elif extension == "pptx":
        return report_files(tmp_path)["pptx"].read_bytes()
    return stream.getvalue()


def _client(tmp_path, monkeypatch, worker, provider="test", model="test"):
    async def connection(_service, _row):
        endpoint = (
            "https://api.deepseek.com"
            if provider == "deepseek-official"
            else "https://example.invalid"
        )
        return (endpoint + "/chat/completions", model, None, provider)

    monkeypatch.setenv("RWB_ALPHADESK_QA", "1")
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", "0")
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    monkeypatch.setattr(qa_model, "connection", connection)
    monkeypatch.setattr(qa_execution, "run_worker", worker)
    return TestClient(create_app(ResearchService(NativeFixture(), Store(tmp_path / "data"))))


def _submit(client, name, raw):
    sid = client.post(BASE, json={"source_scope": ["uploads"]}).json()["id"]
    uploaded = client.post(f"{BASE}/{sid}/uploads", files=[("files", (name, raw))])
    assert uploaded.status_code == 200, uploaded.text
    fid = uploaded.json()["items"][0]["id"]
    sent = client.post(
        f"{BASE}/{sid}/messages",
        json={"text": "核对资料", "attachment_ids": [fid], "expected_formats": []},
        headers={"Idempotency-Key": "attachment-formats"},
    )
    return sid, sent


def _completed(client, sid):
    for _ in range(120):
        detail = client.get(f"{BASE}/{sid}").json()
        if detail["status"] != "running":
            break
        time.sleep(0.05)
    assert detail["status"] == "completed", detail
    return detail


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native report sandbox")
@pytest.mark.parametrize("extension", ["pdf", "docx", "xlsx", "pptx"])
def test_owned_office_and_pdf_uploads_reach_the_qa_tool(tmp_path, monkeypatch, extension):
    async def worker(_request, callbacks, emit):
        listed = await callbacks["tool"]({"name": "list_research_sources", "arguments": {}}, None)
        source = listed["data"][0]["id"]
        read = await callbacks["tool"](
            {"name": "read_research_source", "arguments": {"id": source}}, None
        )
        assert "report fixture" in read["data"]["content"], read
        assert read["sources"][0]["evidence_id"] == source
        await emit("_qa", {"content": "已核对资料。"})

    raw = _attachment(tmp_path, extension)
    with _client(tmp_path, monkeypatch, worker) as client:
        sid, sent = _submit(client, f"fixture.{extension}", raw)
        assert sent.status_code == 202, sent.text
        _completed(client, sid)


@pytest.mark.parametrize(
    "provider,model", [("openai-compatible", "gpt-4o"), ("deepseek-official", "deepseek-flash")]
)
def test_image_bytes_stay_on_host_and_reach_eligible_model(tmp_path, monkeypatch, provider, model):
    stream = BytesIO()
    Image.new("RGB", (20, 20), "red").save(stream, format="PNG")
    raw = stream.getvalue()
    data_uri = "data:image/png;base64," + base64.b64encode(raw).decode()

    async def stream_model(_client, _connection, params, _emit):
        assert params["messages"][-1]["content"][1] == {
            "type": "image_url",
            "image_url": {"url": data_uri},
        }
        return {"content": "已解读图片。", "toolCalls": []}

    async def worker(request, callbacks, emit):
        assert data_uri not in json.dumps(request)
        params = {"messages": [{"role": "user", "content": "核对资料"}]}
        result = await callbacks["model"](params, emit)
        await emit("_qa", {"content": result["content"]})

    monkeypatch.setattr(qa_model, "stream_model", stream_model)
    with _client(tmp_path, monkeypatch, worker, provider, model) as client:
        sid, sent = _submit(client, "fixture.png", raw)
        assert sent.status_code == 202, sent.text
        assert data_uri not in json.dumps(_completed(client, sid))


def test_text_only_model_does_not_receive_image_bytes(tmp_path, monkeypatch):
    async def worker(*_args):
        pytest.fail("a text-only model must never run with image attachments")

    stream = BytesIO()
    Image.new("RGB", (20, 20), "red").save(stream, format="PNG")
    with _client(tmp_path, monkeypatch, worker, "openai-compatible", "text-only") as client:
        _sid, sent = _submit(client, "fixture.png", stream.getvalue())
        assert sent.status_code == 422, sent.text
        assert "qa_image_model_unsupported" in sent.text


@pytest.mark.skipif(sys.platform != "darwin", reason="requires native report sandbox")
def test_media_reports_reach_checked_downloads(tmp_path, monkeypatch):
    async def worker(_request, callbacks, emit):
        async def tool(name, arguments):
            return await callbacks["tool"]({"name": name, "arguments": arguments}, None)

        await tool("read_frozen_dataset", {"dataset_id": snapshot["dataset_id"]})
        index = (await tool("list_research_observations", {}))["data"]
        plan = {
            "title": "收盘价报告",
            "missing": [],
            "sections": [
                {
                    "id": "price",
                    "heading": "收盘价",
                    "evidence_ids": [index["observations"][0]["id"]],
                    "requirement_ids": [item["id"] for item in index["requirements"]],
                }
            ],
        }
        written = await tool("write_research_report", {"plan": plan})
        assert written["data"]["status"] == "generated", written
        await emit("_qa", {"content": "已生成报告。"})

    with _client(tmp_path, monkeypatch, worker) as client:
        service = client.app.state.research
        sid = client.post(BASE, json={"source_scope": ["datahub"], "research_mode": "deep"}).json()[
            "id"
        ]
        snapshot = service.datahub.snapshots.publish(
            sid,
            BusinessQuery(capability="market_bars"),
            Result(
                rows=[{"date": "2026-11-10", "close": 12.5}],
                status="complete",
                fields={"close": {"unit": "元"}},
                as_of="2026-11-10",
                provider_id="eastmoney",
            ),
        )
        sent = client.post(
            f"{BASE}/{sid}/messages",
            json={"text": "核对收盘价。", "expected_formats": ["png", "pptx"]},
            headers={"Idempotency-Key": "report-formats"},
        )
        assert sent.status_code == 202, sent.text
        detail = _completed(client, sid)
        assert detail["research_quality"]["status"] == "passed", detail["research_quality"]
        delivery = detail["research_report_delivery"]
        assert delivery["status"] == "bound", delivery
        urls = {item["name"].rsplit(".", 1)[-1]: item["url"] for item in delivery["files"]}
        for kind, magic in [("png", b"\x89PNG\r\n\x1a\n"), ("pptx", b"PK\x03\x04")]:
            download = client.get(urls[kind])
            assert download.status_code == 200, download.text
            assert download.content.startswith(magic)
