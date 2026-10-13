"""Offline research artifacts sharing one payload and an embedded Chinese font."""

import hashlib
import html
import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

log = logging.getLogger("research_web.report")


def source_id(url):
    return "web:" + hashlib.sha256(url.encode()).hexdigest()[:24]


def validate_payload(value):
    if not isinstance(value, dict) or not re.fullmatch(
        r"[a-f0-9]{24}", str(value.get("task_id", ""))
    ):
        raise ValueError("research_report_task_invalid")
    if not isinstance(value.get("title"), str) or not 1 <= len(value["title"]) <= 200:
        raise ValueError("research_report_title_invalid")
    sections, sources = value.get("sections"), value.get("sources", [])
    if not isinstance(sections, list) or not 1 <= len(sections) <= 50:
        raise ValueError("research_report_sections_invalid")
    if not isinstance(sources, list) or len(sources) > 200:
        raise ValueError("research_report_sources_invalid")
    ids = set()
    for item in sources:
        if not isinstance(item, dict) or not re.fullmatch(
            r"(?:web|file|dataset):[a-zA-Z0-9_-]{1,80}", str(item.get("id", ""))
        ):
            raise ValueError("research_report_source_invalid")
        if item["id"] in ids or not isinstance(item.get("title"), str) or len(item["title"]) > 1000:
            raise ValueError("research_report_source_duplicate_or_title")
        ids.add(item["id"])
        url = item.get("url")
        if url:
            if not isinstance(url, str) or len(url) > 4000 or any(ord(c) < 33 for c in url):
                raise ValueError("research_report_url_invalid")
            parts = urlsplit(url)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or parts.username
                or parts.password
            ):
                raise ValueError("research_report_url_invalid")
    stage_ids = set()
    for item in sections:
        if not isinstance(item, dict) or any(
            not isinstance(item.get(k), str) for k in ("heading", "text")
        ):
            raise ValueError("research_report_section_invalid")
        if not item["heading"].strip() or len(item["heading"]) > 200 or len(item["text"]) > 100000:
            raise ValueError("research_report_section_size")
        stage = item.get("id")
        if stage is not None:
            if (
                not isinstance(stage, str)
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", stage)
                or stage in stage_ids
            ):
                raise ValueError("research_report_stage_invalid")
            stage_ids.add(stage)
        refs = item.get("citations", [])
        if (
            not isinstance(refs, list)
            or len(refs) > 200
            or any(not isinstance(ref, str) or ref not in ids for ref in refs)
        ):
            raise ValueError("research_report_citation_unknown")
    for key in ("required_sections", "missing"):
        values = value.get(key, [])
        if (
            not isinstance(values, list)
            or len(values) > 100
            or any(not isinstance(s, str) or len(s) > 10000 for s in values)
        ):
            raise ValueError("research_report_list_invalid")
    notes = value.get("notes", [])
    if not isinstance(notes, list) or len(notes) > 100:
        raise ValueError("research_report_notes_invalid")
    for note in notes:
        if (
            not isinstance(note, dict)
            or not isinstance(note.get("text"), str)
            or len(note["text"]) > 100000
        ):
            raise ValueError("research_report_note_invalid")
        refs = note.get("citations", [])
        if note.get("stage_id") is not None and note["stage_id"] not in stage_ids:
            raise ValueError("research_report_note_stage_unknown")
        if not isinstance(refs, list) or any(
            not isinstance(ref, str) or ref not in ids for ref in refs
        ):
            raise ValueError("research_report_note_citation_unknown")
    if len(json.dumps(value, ensure_ascii=False).encode()) > 2_000_000:
        raise ValueError("research_report_size")
    return value


def report_blocks(payload):
    """The same text/version is consumed by all three renderers."""
    blocks = [(payload["title"], True)]
    if payload.get("as_of"):
        blocks.append(("研究截止时间：" + str(payload["as_of"]), False))
    for section in payload["sections"]:
        blocks.extend([(section["heading"], True), (section["text"], False)])
        if section.get("citations"):
            blocks.append(("引用：" + ", ".join(section["citations"]), False))
    blocks.append(("来源与证据", True))
    for source in payload.get("sources", []):
        blocks.append(
            (source["id"] + " · " + source["title"] + " " + str(source.get("url", "")), False)
        )
    missing = list(payload.get("missing", []))
    headings = {s["heading"] for s in payload["sections"]}
    missing.extend(
        "未覆盖要求：" + s for s in payload.get("required_sections", []) if s not in headings
    )
    if missing:
        blocks.append(("缺口与限制（研究质量未通过）", True))
        blocks.extend((text, False) for text in missing)
    return blocks


def render_pdf(path, payload):
    path = Path(path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    try:
        previous_directory = os.getcwd()
    except PermissionError:
        previous_directory = str(Path(__file__).resolve().parent.parent)
    try:
        # ReportLab initializes paths from CWD. Only the already writable output
        # directory is readable under Seatbelt; session-root grants stay closed.
        os.chdir(path.parent)
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        font = Path(__file__).with_name("fonts") / "NotoSansSC-Regular.ttf"
        if font.is_symlink() or not font.is_file():
            raise ValueError("research_pdf_font_missing")
        pdfmetrics.registerFont(TTFont("ResearchCJK", str(font)))
        styles = {
            True: ParagraphStyle(
                "heading",
                fontName="ResearchCJK",
                fontSize=15,
                leading=22,
                wordWrap="CJK",
                spaceBefore=12,
                keepWithNext=True,
            ),
            False: ParagraphStyle(
                "body",
                fontName="ResearchCJK",
                fontSize=10,
                leading=17,
                wordWrap="CJK",
                splitLongWords=True,
            ),
        }
        story = []
        for text, heading in report_blocks(payload):
            if any(
                ord(char) not in pdfmetrics.getFont("ResearchCJK").face.charToGlyph
                for char in text
                if char not in "\n\r\t"
            ):
                raise ValueError("research_pdf_glyph_missing")
            story.extend(
                [Paragraph(html.escape(text).replace("\n", "<br/>"), styles[heading]), Spacer(1, 6)]
            )
        SimpleDocTemplate(
            str(path),
            pagesize=A4,
            title=payload["title"],
            leftMargin=42,
            rightMargin=42,
            topMargin=42,
            bottomMargin=42,
        ).build(story)
        log.info("research_pdf_rendered")
        return Path(path)
    except Exception as exc:
        log.error("research_pdf_render_failed type=%s", type(exc).__name__)
        raise
    finally:
        os.chdir(previous_directory)


def write_research_report(output, payload):
    import pdfplumber
    from docx import Document

    try:
        validate_payload(payload)
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        stem = "research-report-" + uuid4().hex[:12]
        paths = {kind: output / (stem + "." + kind) for kind in ("html", "docx", "pdf")}
        paths["json"] = output / "research-report.json"
        if any(p.is_symlink() for p in paths.values()):
            raise ValueError("research_report_output_alias")
        blocks = report_blocks(payload)
        doc = Document()
        for text, heading in blocks:
            doc.add_heading(text, level=1) if heading else doc.add_paragraph(text)
        doc.save(paths["docx"])
        body = "".join(
            f'<{"h2" if heading else "p"}>{html.escape(text)}</{"h2" if heading else "p"}>'
            for text, heading in blocks
        )
        paths["html"].write_text(
            '<!doctype html><html lang="zh"><meta charset="utf-8"><title>'
            + html.escape(payload["title"])
            + "</title><body>"
            + body
            + "</body></html>",
            encoding="utf-8",
        )
        render_pdf(paths["pdf"], payload)
        Document(paths["docx"])
        with pdfplumber.open(paths["pdf"]) as pdf:
            if not pdf.pages or not any((p.extract_text() or "").strip() for p in pdf.pages):
                raise ValueError("research_pdf_empty")
        published = {
            **payload,
            "artifacts": [
                {"name": paths[k].name, "sha256": hashlib.sha256(paths[k].read_bytes()).hexdigest()}
                for k in ("html", "docx", "pdf")
            ],
        }
        manifest = output / (stem + ".json")
        manifest.write_text(json.dumps(published, ensure_ascii=False), encoding="utf-8")
        manifest.replace(paths["json"])
        log.info("research_report_rendered formats=3")
        return paths
    except Exception as exc:
        log.error("research_report_failed type=%s", type(exc).__name__)
        raise
