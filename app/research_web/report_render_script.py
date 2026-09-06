"""Trusted sandbox program for report-project file projection.

This file is read by ``report_rendering.py`` and executed with network and host
filesystem access denied.  It never performs research or model calls.
"""

import html
import json
import re
import shutil
import zipfile
from pathlib import Path


def clean_text(value, limit=100_000):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    return value.strip()[:limit]


def load_payload():
    path = Path("outputs/report_payload.json")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("invalid report payload")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("payload must be an object")
    title = clean_text(value.get("title"), 500)
    if not title:
        raise ValueError("payload title is required")
    sections = value.get("sections")
    if isinstance(sections, dict):
        sections = [
            {"id": key, "title": key, "content": content}
            for key, content in sections.items()
        ]
    if not isinstance(sections, list) or not sections:
        raise ValueError("payload sections are required")
    normalized = []
    for index, item in enumerate(sections[:80]):
        if not isinstance(item, dict):
            continue
        content = clean_text(item.get("content"))
        if not content:
            continue
        normalized.append(
            {
                "id": clean_text(item.get("id") or f"section-{index + 1}", 200),
                "title": clean_text(item.get("title") or item.get("id") or f"章节 {index + 1}", 500),
                "content": content,
            }
        )
    if not normalized:
        raise ValueError("payload has no report content")
    value["title"] = title
    value["summary"] = clean_text(value.get("summary"))
    value["as_of"] = clean_text(value.get("as_of"), 200)
    value["sections"] = normalized
    value["sources"] = value.get("sources") if isinstance(value.get("sources"), list) else []
    value["missing"] = value.get("missing") if isinstance(value.get("missing"), list) else []
    return value


def replacements(payload):
    rows = {
        "标题": payload["title"],
        "报告标题": payload["title"],
        "数据截止时间": payload["as_of"],
        "摘要": payload["summary"],
    }
    for item in payload["sections"]:
        rows[item["id"]] = item["content"]
        rows[item["title"]] = item["content"]
    return rows


def replace_paragraph(paragraph, values, replaced):
    text = paragraph.text
    if "{{" not in text:
        return
    updated = text
    for key, value in values.items():
        token = "{{" + key + "}}"
        if token in updated:
            updated = updated.replace(token, value)
            replaced.add(key)
    if updated != text:
        paragraph.text = updated


def render_docx(payload, values):
    from docx import Document

    templates = sorted(Path("inputs/report-project").rglob("*.docx"))
    document = Document(str(templates[0])) if templates else Document()
    replaced = set()
    for paragraph in document.paragraphs:
        replace_paragraph(paragraph, values, replaced)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    replace_paragraph(paragraph, values, replaced)
    if not replaced:
        document.add_heading(payload["title"], level=0)
        if payload["as_of"]:
            document.add_paragraph("数据截止时间：" + payload["as_of"])
        if payload["summary"]:
            document.add_paragraph(payload["summary"])
        for item in payload["sections"]:
            document.add_heading(item["title"], level=1)
            document.add_paragraph(item["content"])
    if payload["missing"]:
        document.add_heading("数据缺失与限制", level=1)
        for item in payload["missing"]:
            document.add_paragraph(clean_text(item), style="List Bullet")
    output = Path("outputs/report.docx")
    document.save(output)
    return output


def render_xlsx(payload):
    from openpyxl import Workbook

    book = Workbook()
    overview = book.active
    overview.title = "报告摘要"
    overview.append(["字段", "内容"])
    overview.append(["标题", payload["title"]])
    overview.append(["数据截止时间", payload["as_of"]])
    overview.append(["摘要", payload["summary"]])
    sections = book.create_sheet("章节底稿")
    sections.append(["章节ID", "章节", "正文"])
    for item in payload["sections"]:
        sections.append([item["id"], item["title"], item["content"]])
    sources = book.create_sheet("来源")
    sources.append(["来源", "链接", "截止时间"])
    for item in payload["sources"]:
        if isinstance(item, dict):
            sources.append(
                [clean_text(item.get("title") or item.get("source")), clean_text(item.get("url")), clean_text(item.get("as_of"))]
            )
        else:
            sources.append([clean_text(item), "", ""])
    missing = book.create_sheet("缺失项")
    missing.append(["缺失或限制"])
    for item in payload["missing"]:
        missing.append([clean_text(item)])
    output = Path("outputs/report.xlsx")
    book.save(output)
    return output


def render_html(payload):
    sections = "".join(
        f"<section><h2>{html.escape(item['title'])}</h2><p>{html.escape(item['content']).replace(chr(10), '<br>')}</p></section>"
        for item in payload["sections"]
    )
    sources = "".join(
        f"<li>{html.escape(clean_text(item.get('title') or item.get('source'))) if isinstance(item, dict) else html.escape(clean_text(item))}</li>"
        for item in payload["sources"]
    )
    missing = "".join(f"<li>{html.escape(clean_text(item))}</li>" for item in payload["missing"])
    text = f"""<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>{html.escape(payload['title'])}</title><style>body{{max-width:920px;margin:40px auto;padding:0 24px;font:16px/1.75 system-ui;color:#202124}}h1,h2{{line-height:1.3}}.meta{{color:#666}}section{{margin:32px 0}}@media print{{body{{margin:0}}}}</style><body><h1>{html.escape(payload['title'])}</h1><p class=\"meta\">数据截止时间：{html.escape(payload['as_of'] or '未提供')}</p><p>{html.escape(payload['summary'])}</p>{sections}<section><h2>来源</h2><ul>{sources or '<li>未提供</li>'}</ul></section><section><h2>数据缺失与限制</h2><ul>{missing or '<li>无已声明缺失项</li>'}</ul></section></body></html>"""
    output = Path("outputs/report.html")
    output.write_text(text, encoding="utf-8")
    return output


def render_pptx(payload, values):
    templates = sorted(Path("inputs/report-project").rglob("*.pptx"))
    if not templates:
        raise ValueError("PPTX template is required")
    source = templates[0]
    output = Path("outputs/report.pptx")
    with zipfile.ZipFile(source) as package, zipfile.ZipFile(output, "w") as target:
        for info in package.infolist():
            raw = package.read(info.filename)
            if info.filename.startswith("ppt/slides/slide") and info.filename.endswith(".xml"):
                text = raw.decode("utf-8")
                for key, value in values.items():
                    token = "{{" + key + "}}"
                    text = text.replace(token, html.escape(value))
                raw = text.encode("utf-8")
            target.writestr(info, raw)
    return output


payload = load_payload()
values = replacements(payload)
writers = {
    "docx": lambda: render_docx(payload, values),
    "html": lambda: render_html(payload),
    "xlsx": lambda: render_xlsx(payload),
    "pptx": lambda: render_pptx(payload, values),
}
created = []
for requested in FORMATS:
    output = writers[requested]()
    if output.is_symlink() or not output.is_file() or output.stat().st_size == 0:
        raise ValueError("renderer did not produce a regular file")
    created.append(output.as_posix())
print(json.dumps({"status": "completed", "files": created}, ensure_ascii=False))
