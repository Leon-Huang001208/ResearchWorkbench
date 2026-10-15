"""Actual document files, not chat-text substitutes."""

import builtins
from pathlib import Path

import pytest

from app.research_web.resources.research_helpers import read_pdf, write_deliverables


def test_markdown_only_delivery_avoids_office_imports_and_extra_files(tmp_path, monkeypatch):
    original_import = builtins.__import__

    def deny_office(name, *args, **kwargs):
        if name in {"docx", "openpyxl", "pdfplumber"}:
            raise AssertionError(f"Unrequested format imported: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny_office)
    outputs = write_deliverables(
        tmp_path, "研究", [{"heading": "结论", "text": "正文"}], [], [], formats=["md"]
    )
    assert set(outputs) == {"markdown"}
    assert isinstance(outputs["markdown"], Path)
    assert list(tmp_path.iterdir()) == [outputs["markdown"]]
    assert "正文" in outputs["markdown"].read_text()


@pytest.mark.parametrize("formats", [[], ["csv"], "md", [None], {"md": True}])
def test_invalid_format_selection_fails_before_creating_output(tmp_path, formats):
    output = tmp_path / "outputs"
    with pytest.raises(ValueError, match="formats"):
        write_deliverables(output, "研究", [], [], [], formats=formats)
    assert not output.exists()


def test_pdf_flag_cannot_add_unselected_format(tmp_path):
    with pytest.raises(ValueError, match="pdf=True"):
        write_deliverables(tmp_path / "outputs", "研究", [], [], [], formats=["md"], pdf=True)
    assert not (tmp_path / "outputs").exists()


def test_explicit_pdf_only_is_real_readable_file(tmp_path):
    outputs = write_deliverables(
        tmp_path,
        "Research",
        [{"heading": "Result", "text": "Revenue 123"}],
        [],
        [],
        formats=["pdf"],
    )
    assert set(outputs) == {"pdf"}
    assert list(tmp_path.iterdir()) == [outputs["pdf"]]
    assert "123" in read_pdf(outputs["pdf"])[0]["text"]


@pytest.mark.parametrize("formats", [("html",), ["docx"], ["xlsx"], ["md", "md", "html"]])
def test_explicit_formats_generate_only_selected_readable_outputs(tmp_path, formats):
    outputs = write_deliverables(
        tmp_path,
        "Research",
        [{"heading": "Result", "text": "123"}],
        [{"value": 123}],
        [],
        formats=formats,
    )
    expected = {"markdown" if item == "md" else item for item in formats}
    assert set(outputs) == expected
    assert set(tmp_path.iterdir()) == set(outputs.values())
    if "docx" in outputs:
        from docx import Document

        assert Document(outputs["docx"]).paragraphs[0].text == "Research"
    if "xlsx" in outputs:
        from openpyxl import load_workbook

        book = load_workbook(outputs["xlsx"])
        assert book["analysis"]["A2"].value == 123
        book.close()


def test_legacy_pdf_flag_keeps_all_four_default_formats(tmp_path):
    outputs = write_deliverables(
        tmp_path, "Research", [{"heading": "Result", "text": "123"}], [], [], pdf=True
    )
    assert set(outputs) == {"markdown", "html", "docx", "xlsx", "pdf"}
    assert set(tmp_path.iterdir()) == set(outputs.values())


def test_requested_office_files_are_real_openable_documents(tmp_path):
    from docx import Document
    from openpyxl import load_workbook

    outputs = write_deliverables(
        tmp_path,
        "研究",
        [{"heading": "结论", "text": "缺少行情数据，不做估值结论"}],
        [{"metric": "PE", "value": None}],
        ["https://example.com/source"],
    )
    assert set(outputs) == {"markdown", "html", "docx", "xlsx"}
    assert Document(outputs["docx"]).paragraphs[0].text == "研究"
    workbook = load_workbook(outputs["xlsx"])
    assert workbook["analysis"]["B2"].value is None
    assert "https://example.com/source" in outputs["html"].read_text()


def test_pdf_extraction_includes_real_page_numbers(tmp_path):
    from matplotlib.figure import Figure

    path = tmp_path / "input.pdf"
    figure = Figure()
    figure.text(0.1, 0.8, "Revenue 123")
    figure.savefig(path)
    pages = read_pdf(path)
    assert pages[0]["page"] == 1
    assert "123" in pages[0]["text"]


def test_hot_helper_verifies_raw_but_returns_only_bounded_selected_evidence(tmp_path, monkeypatch):
    import hashlib
    import json
    from uuid import uuid4

    import pytest
    from test_hot_snapshot_publication import bundle

    from app.research_web.resources.research_helpers import read_hot_evidence

    evidence = bundle(str(uuid4()), str(uuid4()))
    did = str(uuid4())
    root = tmp_path / "inputs" / "datasets" / did
    root.mkdir(parents=True)
    (root / "evidence-manifest.json").write_bytes(evidence["manifestBytes"])
    for item in evidence["manifest"]["objects"]:
        (root / item["filename"]).write_bytes(evidence["objects"][item["key"]])
    context = {
        "dataset_id": did,
        "evidence_manifest": f"inputs/datasets/{did}/evidence-manifest.json",
        "evidence_manifest_hash": evidence["manifestHash"],
        "logical_instance_id": evidence["manifest"]["instanceId"],
        "selected_material_ids": evidence["manifest"]["materialIds"],
    }
    path = tmp_path / "inputs/hot-context.json"
    path.write_text(json.dumps(context))
    monkeypatch.chdir(tmp_path)
    result = read_hot_evidence()
    assert result["manifestHash"] == evidence["manifestHash"]
    assert (
        result["materials"][0]["rawHash"]
        == hashlib.sha256(
            evidence["objects"]["raw:" + evidence["manifest"]["materialIds"][0]]
        ).hexdigest()
    )
    assert "complete stored source response" not in json.dumps(result)
    raw = root / evidence["manifest"]["objects"][0]["filename"]
    raw.write_bytes(b"tamper")
    with pytest.raises(ValueError, match="hot_evidence_read_failed"):
        read_hot_evidence()


def test_hot_helper_limits_large_titles_urls_and_limitations(tmp_path, monkeypatch):
    import hashlib
    import json
    from uuid import uuid4

    from test_hot_snapshot_publication import bundle

    from app.research_web.resources.research_helpers import read_hot_evidence

    evidence = bundle(str(uuid4()), str(uuid4()))
    normalized = next(
        x for x in evidence["manifest"]["objects"] if x["format"] == "application/json"
    )
    value = json.loads(evidence["objects"][normalized["key"]])
    value.update(title="大" * 10000, originalUrl="https://example.com/" + "a" * 10000)
    raw = json.dumps(value).encode()
    evidence["objects"][normalized["key"]] = raw
    normalized.update(bytes=len(raw), contentHash=hashlib.sha256(raw).hexdigest())
    evidence["manifest"].update(
        totalBytes=sum(len(v) for v in evidence["objects"].values()), limitations=["缺口" * 10000]
    )
    canonical = json.dumps(evidence["manifest"]).encode()
    did = str(uuid4())
    root = tmp_path / "inputs/datasets" / did
    root.mkdir(parents=True)
    (root / "evidence-manifest.json").write_bytes(canonical)
    for item in evidence["manifest"]["objects"]:
        (root / item["filename"]).write_bytes(evidence["objects"][item["key"]])
    (tmp_path / "inputs/hot-context.json").write_text(
        json.dumps(
            {
                "dataset_id": did,
                "evidence_manifest": f"inputs/datasets/{did}/evidence-manifest.json",
                "evidence_manifest_hash": hashlib.sha256(canonical).hexdigest(),
                "logical_instance_id": evidence["manifest"]["instanceId"],
                "selected_material_ids": evidence["manifest"]["materialIds"],
            }
        )
    )
    monkeypatch.chdir(tmp_path)
    result = read_hot_evidence()
    material = result["materials"][0]
    assert set(material["truncatedFields"]) == {"title", "originalUrl"}
    assert material["originalUrl"] is None and len(material["title"].encode()) <= 256
    assert (
        result["limitationsTruncated"]
        and len(json.dumps(result, ensure_ascii=False).encode()) <= 32768
    )
