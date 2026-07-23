"""Switch Huaan ETF Word template chart placeholders from images to native charts."""

from __future__ import annotations

import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from copy import deepcopy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from core.observability import get_logger  # noqa: E402

    logger = get_logger(__name__)
except Exception:  # pragma: no cover - keeps the repair script usable outside app env.
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    logger = logging.getLogger(__name__)

DOCX_PATH = PROJECT_ROOT / "report_projects" / "华安ETF周报" / "templates" / "report_template.docx"
CHART_WORKBOOK_PATH = PROJECT_ROOT / "report_projects" / "华安ETF周报" / "data" / "周报图表.xlsx"
BACKUP_DIR = PROJECT_ROOT / "report_projects" / "华安ETF周报" / "templates" / "backups"

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

ET.register_namespace("w", WORD_NS)
ET.register_namespace("wp", WP_NS)
ET.register_namespace("a", A_NS)
ET.register_namespace("c", C_NS)
ET.register_namespace("r", R_NS)


CHARTS = [
    {
        "label": "industry_weekly_performance",
        "image_target": "media/generated_industry_weekly_performance.png",
        "chart_part": "word/charts/chart1.xml",
        "title": "申万一级行业周涨跌幅",
    },
    {
        "label": "gold_price",
        "image_target": "media/image1.png",
        "chart_part": "word/charts/chart2.xml",
        "source_chart": "xl/charts/chart2.xml",
        "source_rels": "xl/charts/_rels/chart2.xml.rels",
        "related_parts": {
            "xl/charts/style2.xml": "word/charts/style2.xml",
            "xl/charts/colors2.xml": "word/charts/colors2.xml",
        },
        "title": "黄金价格走势",
    },
    {
        "label": "crude_oil_price",
        "image_target": "media/image2.png",
        "chart_part": "word/charts/chart3.xml",
        "source_chart": "xl/charts/chart3.xml",
        "source_rels": "xl/charts/_rels/chart3.xml.rels",
        "related_parts": {
            "xl/charts/style3.xml": "word/charts/style3.xml",
            "xl/charts/colors3.xml": "word/charts/colors3.xml",
            "xl/theme/themeOverride2.xml": "word/theme/themeOverride2.xml",
        },
        "title": "Brent vs WTI 原油期货结算价",
    },
]


def _q(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def _read_entries(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _write_entries(path: Path, entries: dict[str, bytes]) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=path.suffix) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _relationship_target_map(rels_root: ET.Element) -> dict[str, ET.Element]:
    return {
        str(rel.attrib.get("Target") or ""): rel
        for rel in rels_root.findall(_q(PKG_REL_NS, "Relationship"))
    }


def _next_relationship_id(rels_root: ET.Element) -> str:
    ids = {
        str(rel.attrib.get("Id") or "") for rel in rels_root.findall(_q(PKG_REL_NS, "Relationship"))
    }
    index = 100
    while f"rId{index}" in ids:
        index += 1
    return f"rId{index}"


def _next_part_relationship_id(rels_root: ET.Element) -> str:
    ids = {
        str(rel.attrib.get("Id") or "") for rel in rels_root.findall(_q(PKG_REL_NS, "Relationship"))
    }
    index = 1
    while f"rId{index}" in ids:
        index += 1
    return f"rId{index}"


def _ensure_chart_relationship(rels_root: ET.Element, chart_part: str) -> str:
    target = chart_part.removeprefix("word/")
    for rel in rels_root.findall(_q(PKG_REL_NS, "Relationship")):
        if rel.attrib.get("Type", "").endswith("/chart") and rel.attrib.get("Target") == target:
            return str(rel.attrib["Id"])
    rel_id = _next_relationship_id(rels_root)
    ET.SubElement(
        rels_root,
        _q(PKG_REL_NS, "Relationship"),
        {
            "Id": rel_id,
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart",
            "Target": target,
        },
    )
    return rel_id


def _ensure_content_type(entries: dict[str, bytes], chart_part: str) -> None:
    root = ET.fromstring(entries["[Content_Types].xml"])
    part_name = "/" + chart_part
    for override in root.findall(_q(CT_NS, "Override")):
        if override.attrib.get("PartName") == part_name:
            return
    ET.SubElement(
        root,
        _q(CT_NS, "Override"),
        {
            "PartName": part_name,
            "ContentType": "application/vnd.openxmlformats-officedocument.drawingml.chart+xml",
        },
    )
    entries["[Content_Types].xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _ensure_external_workbook_link(
    entries: dict[str, bytes], chart_part: str, workbook_path: Path
) -> None:
    """Make a Word chart editable by linking its chart part to the source workbook."""
    rels_part = chart_part.replace("word/charts/", "word/charts/_rels/") + ".rels"
    if rels_part in entries:
        rels_root = ET.fromstring(entries[rels_part])
    else:
        rels_root = ET.Element(_q(PKG_REL_NS, "Relationships"))

    workbook_uri = workbook_path.resolve().as_uri()
    external_rel_id = ""
    for rel in rels_root.findall(_q(PKG_REL_NS, "Relationship")):
        if rel.attrib.get("Type", "").endswith("/oleObject"):
            rel.attrib["Target"] = workbook_uri
            rel.attrib["TargetMode"] = "External"
            external_rel_id = str(rel.attrib["Id"])
            break
    if not external_rel_id:
        external_rel_id = _next_part_relationship_id(rels_root)
        ET.SubElement(
            rels_root,
            _q(PKG_REL_NS, "Relationship"),
            {
                "Id": external_rel_id,
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject",
                "Target": workbook_uri,
                "TargetMode": "External",
            },
        )

    chart_root = ET.fromstring(entries[chart_part])
    external_data = chart_root.find(_q(C_NS, "externalData"))
    if external_data is None:
        external_data = ET.SubElement(
            chart_root,
            _q(C_NS, "externalData"),
            {_q(R_NS, "id"): external_rel_id},
        )
        ET.SubElement(external_data, _q(C_NS, "autoUpdate"), {"val": "0"})
    else:
        external_data.attrib[_q(R_NS, "id")] = external_rel_id
        auto_update = external_data.find(_q(C_NS, "autoUpdate"))
        if auto_update is None:
            ET.SubElement(external_data, _q(C_NS, "autoUpdate"), {"val": "0"})
        else:
            auto_update.attrib["val"] = "0"

    entries[chart_part] = ET.tostring(chart_root, encoding="utf-8", xml_declaration=True)
    entries[rels_part] = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)


def _ensure_override_content_type(
    entries: dict[str, bytes], part_name: str, content_type: str
) -> None:
    root = ET.fromstring(entries["[Content_Types].xml"])
    normalized = "/" + part_name.lstrip("/")
    for override in root.findall(_q(CT_NS, "Override")):
        if override.attrib.get("PartName") == normalized:
            return
    ET.SubElement(
        root,
        _q(CT_NS, "Override"),
        {"PartName": normalized, "ContentType": content_type},
    )
    entries["[Content_Types].xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _ensure_related_part_content_types(
    entries: dict[str, bytes], related_parts: dict[str, str]
) -> None:
    for target in related_parts.values():
        if target.startswith("word/charts/style"):
            _ensure_override_content_type(
                entries,
                target,
                "application/vnd.ms-office.chartstyle+xml",
            )
        elif target.startswith("word/charts/colors"):
            _ensure_override_content_type(
                entries,
                target,
                "application/vnd.ms-office.chartcolorstyle+xml",
            )
        elif target.startswith("word/theme/themeOverride"):
            _ensure_override_content_type(
                entries,
                target,
                "application/vnd.openxmlformats-officedocument.themeOverride+xml",
            )


def _find_image_rel_id(rels_root: ET.Element, image_target: str) -> str:
    target_map = _relationship_target_map(rels_root)
    rel = target_map.get(image_target)
    if rel is None:
        raise RuntimeError(f"Image relationship not found: {image_target}")
    return str(rel.attrib["Id"])


def _replace_image_drawing_with_chart(
    document_root: ET.Element, image_rel_id: str, chart_rel_id: str, title: str
) -> bool:
    for drawing in document_root.iter(_q(WORD_NS, "drawing")):
        blip = drawing.find(f".//{_q(A_NS, 'blip')}")
        if blip is None or blip.attrib.get(_q(R_NS, "embed")) != image_rel_id:
            continue
        replacement = _chart_drawing_from_image_drawing(drawing, chart_rel_id, title)
        _replace_element(document_root, drawing, replacement)
        return True
    return False


def _chart_drawing_from_image_drawing(
    image_drawing: ET.Element, chart_rel_id: str, title: str
) -> ET.Element:
    drawing = deepcopy(image_drawing)
    inline = drawing.find(_q(WP_NS, "inline"))
    if inline is None:
        inline = drawing.find(_q(WP_NS, "anchor"))
    if inline is None:
        raise RuntimeError("Image drawing missing wp:inline/wp:anchor")

    doc_pr = inline.find(_q(WP_NS, "docPr"))
    if doc_pr is not None:
        doc_pr.attrib["name"] = title
        doc_pr.attrib["descr"] = title

    graphic = inline.find(_q(A_NS, "graphic"))
    if graphic is None:
        graphic = ET.SubElement(inline, _q(A_NS, "graphic"))
    for child in list(graphic):
        graphic.remove(child)
    graphic_data = ET.SubElement(
        graphic,
        _q(A_NS, "graphicData"),
        {"uri": "http://schemas.openxmlformats.org/drawingml/2006/chart"},
    )
    ET.SubElement(graphic_data, _q(C_NS, "chart"), {_q(R_NS, "id"): chart_rel_id})
    return drawing


def _replace_element(root: ET.Element, target: ET.Element, replacement: ET.Element) -> None:
    for parent in root.iter():
        children = list(parent)
        for index, child in enumerate(children):
            if child is target:
                parent[index] = replacement
                return
    raise RuntimeError("Target drawing not found")


def switch_template_to_native_charts(
    docx_path: Path = DOCX_PATH, workbook_path: Path = CHART_WORKBOOK_PATH
) -> Path:
    """Replace chart images in the Huaan Word template with native chart drawings."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{docx_path.stem}.before_native_charts{docx_path.suffix}"
    if not backup_path.exists():
        shutil.copy2(docx_path, backup_path)
        logger.info("Backed up Word template", backup=str(backup_path))
    else:
        logger.info("Keeping existing Word template backup", backup=str(backup_path))

    entries = _read_entries(docx_path)
    workbook_entries = _read_entries(workbook_path)
    document_root = ET.fromstring(entries["word/document.xml"])
    rels_root = ET.fromstring(entries["word/_rels/document.xml.rels"])

    for chart in CHARTS:
        if chart.get("source_chart"):
            entries[str(chart["chart_part"])] = workbook_entries[str(chart["source_chart"])]
        if chart.get("source_rels"):
            rels_target = (
                str(chart["chart_part"]).replace("word/charts/", "word/charts/_rels/") + ".rels"
            )
            entries[rels_target] = workbook_entries[str(chart["source_rels"])]
        related_parts = (
            chart.get("related_parts") if isinstance(chart.get("related_parts"), dict) else {}
        )
        for source_part, target_part in related_parts.items():
            entries[str(target_part)] = workbook_entries[str(source_part)]
        _ensure_external_workbook_link(entries, str(chart["chart_part"]), workbook_path)
        _ensure_related_part_content_types(entries, related_parts)
        _ensure_content_type(entries, str(chart["chart_part"]))
        image_rel_id = _find_image_rel_id(rels_root, str(chart["image_target"]))
        chart_rel_id = _ensure_chart_relationship(rels_root, str(chart["chart_part"]))
        replaced = _replace_image_drawing_with_chart(
            document_root,
            image_rel_id=image_rel_id,
            chart_rel_id=chart_rel_id,
            title=str(chart["title"]),
        )
        logger.info(
            "Switched image drawing to native chart",
            label=chart["label"],
            image_rel_id=image_rel_id,
            chart_rel_id=chart_rel_id,
            replaced=replaced,
        )
        if not replaced:
            raise RuntimeError(f"Image drawing not found for {chart['label']}: {image_rel_id}")

    entries["word/document.xml"] = ET.tostring(
        document_root, encoding="utf-8", xml_declaration=True
    )
    entries["word/_rels/document.xml.rels"] = ET.tostring(
        rels_root, encoding="utf-8", xml_declaration=True
    )
    _write_entries(docx_path, entries)
    logger.info("Saved Word template with native charts", docx=str(docx_path))
    return backup_path


if __name__ == "__main__":
    backup = switch_template_to_native_charts()
    print(f"updated: {DOCX_PATH}")
    print(f"backup: {backup}")
