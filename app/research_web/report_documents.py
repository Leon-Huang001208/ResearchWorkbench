"""Reviewed data-only DOCX projection, shared by report sandbox and Hot exports.

The sandbox embeds this trusted source. No project imports, network or user code.
"""
import logging

log = logging.getLogger("research_web.report_documents")


def build_docx_document(payload, values, template=None):
    from docx import Document
    try:
        document = Document(str(template)) if template else Document()
        replaced = set()
        def replace(paragraph):
            text = paragraph.text
            for key, value in values.items():
                token = "{{" + key + "}}"
                if token in text:
                    text = text.replace(token, value)
                    replaced.add(key)
            if text != paragraph.text:
                paragraph.text = text
        for paragraph in document.paragraphs:
            replace(paragraph)
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        replace(paragraph)
        if not replaced:
            document.add_heading(payload["title"], level=0)
            if payload["as_of"]:
                document.add_paragraph("数据截止时间：" + payload["as_of"])
            if payload["summary"]:
                document.add_paragraph(payload["summary"])
            for item in payload["sections"]:
                document.add_heading(item["title"], level=1)
                for line in item["content"].splitlines():
                    document.add_paragraph(line)
        if payload["missing"]:
            document.add_heading("数据缺失与限制", level=1)
            for item in payload["missing"]:
                document.add_paragraph(str(item), style="List Bullet")
        log.info("report_docx_projected")
        return document
    except Exception:
        log.warning("report_docx_projection_failed")
        raise
