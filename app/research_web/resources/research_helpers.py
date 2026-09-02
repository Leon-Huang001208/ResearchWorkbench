"""Deterministic document extraction/delivery helpers for the isolated runner."""

import html
import logging
from pathlib import Path
from uuid import uuid4

log = logging.getLogger("alphafoundry.research.documents")


def read_pdf(path: str | Path, max_pages: int = 150) -> list[dict]:
    import pdfplumber

    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > max_pages:
                raise ValueError(f"PDF 超过 {max_pages} 页；请明确拆分研究范围")
            pages = [
                {"page": index, "text": page.extract_text() or "", "tables": page.extract_tables()}
                for index, page in enumerate(pdf.pages, 1)
            ]
        log.info("pdf_extracted pages=%d", len(pages))
        return pages
    except (OSError, ValueError) as exc:
        log.error("pdf_extraction_failed type=%s", type(exc).__name__)
        raise


def safe_cell(value):
    # Text remains text, never an Excel formula supplied by an external document.
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def write_deliverables(
    output: str | Path, title: str, sections: list[dict], rows: list[dict], sources: list[str]
) -> dict[str, Path]:
    from docx import Document
    from openpyxl import Workbook, load_workbook

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    stem = f"report-{uuid4().hex[:10]}"
    paths = {
        key: output / f"{stem}.{ext}"
        for key, ext in {"markdown": "md", "html": "html", "docx": "docx", "xlsx": "xlsx"}.items()
    }
    try:
        markdown = f"# {title}\n\n" + "\n\n".join(
            f"## {section['heading']}\n\n{section['text']}" for section in sections
        )
        markdown += "\n\n## 来源与缺失项\n\n" + "\n".join(f"- {source}" for source in sources)
        paths["markdown"].write_text(markdown, encoding="utf-8")
        body = "".join(
            f"<section><h2>{html.escape(str(section['heading']))}</h2><p>{html.escape(str(section['text'])).replace(chr(10), '<br>')}</p></section>"
            for section in sections
        )
        paths["html"].write_text(
            f'<!doctype html><html lang="zh"><meta charset="utf-8"><title>{html.escape(title)}</title><style>body{{max-width:900px;margin:40px auto;font:16px/1.8 sans-serif;padding:20px;color:#16304a}}h1,h2{{color:#164e89}}</style><h1>{html.escape(title)}</h1>{body}<h2>来源</h2><pre>{html.escape(chr(10).join(sources))}</pre></html>',
            encoding="utf-8",
        )
        doc = Document()
        doc.add_heading(title, 0)
        for section in sections:
            doc.add_heading(str(section["heading"]), 1)
            doc.add_paragraph(str(section["text"]))
        doc.add_heading("来源与缺失项", 1)
        for source in sources:
            doc.add_paragraph(source)
        doc.save(paths["docx"])
        book = Workbook()
        sheet = book.active
        sheet.title = "analysis"
        columns = list(dict.fromkeys(key for row in rows for key in row))
        if columns:
            sheet.append([safe_cell(column) for column in columns])
            for row in rows:
                sheet.append([safe_cell(row.get(column)) for column in columns])
        references = book.create_sheet("sources")
        for source in sources:
            references.append([safe_cell(source)])
        book.save(paths["xlsx"])
        # Reopen to detect broken containers before reporting delivery.
        Document(paths["docx"])
        check = load_workbook(paths["xlsx"], read_only=True)
        check.close()
        log.info("deliverables_validated count=%d", len(paths))
        return paths
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.error("deliverable_generation_failed type=%s", type(exc).__name__)
        raise
