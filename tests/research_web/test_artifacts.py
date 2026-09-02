"""Actual document files, not chat-text substitutes."""

from app.research_web.resources.research_helpers import read_pdf, write_deliverables


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
