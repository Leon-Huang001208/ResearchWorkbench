"""Merge Huaan Word original layout with native Office chart objects.

The Office copy/paste workflow can create valid native chart parts, but using a
rebuilt Word document as the target loses the original header/footer and layout.
This repair script keeps the original template package as the base and only
transplants the native chart drawings and chart parts from a known-good chart
template.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAYOUT_TEMPLATE = (
    PROJECT_ROOT
    / "report_projects"
    / "华安ETF周报"
    / "templates"
    / "backups"
    / "report_template.before_native_charts.docx"
)
DEFAULT_CHART_TEMPLATE = (
    PROJECT_ROOT / "report_projects" / "华安ETF周报" / "templates" / "report_template.docx"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "report_projects"
    / "华安ETF周报"
    / "generated"
    / "layout_preserved_native_charts.docx"
)

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

logger = logging.getLogger(__name__)


def _read_xml(zip_file: ZipFile, name: str) -> etree._Element:
    return etree.fromstring(zip_file.read(name))


def _write_xml(root: etree._Element) -> bytes:
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def _replace_zip_entries(source: Path, replacements: dict[str, bytes], output: Path) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        with ZipFile(source, "r") as zin, ZipFile(tmp_path, "w", ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename in replacements:
                    zout.writestr(item, replacements[item.filename])
                else:
                    zout.writestr(item, zin.read(item.filename))

            existing = set(zin.namelist())
            for name, data in replacements.items():
                if name not in existing:
                    zout.writestr(name, data)

        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_path), output)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def merge_layout_with_native_charts(
    layout_template: Path = DEFAULT_LAYOUT_TEMPLATE,
    chart_template: Path = DEFAULT_CHART_TEMPLATE,
    output: Path = DEFAULT_OUTPUT,
) -> Path:
    """Create a docx preserving layout_template and replacing chart images."""
    layout_template = layout_template.resolve()
    chart_template = chart_template.resolve()
    output = output.resolve()
    if not layout_template.exists():
        raise FileNotFoundError(layout_template)
    if not chart_template.exists():
        raise FileNotFoundError(chart_template)

    replacements: dict[str, bytes] = {}
    with ZipFile(layout_template, "r") as layout_zip, ZipFile(chart_template, "r") as chart_zip:
        layout_doc = _read_xml(layout_zip, "word/document.xml")
        chart_doc = _read_xml(chart_zip, "word/document.xml")
        layout_rels = _read_xml(layout_zip, "word/_rels/document.xml.rels")
        chart_rels = _read_xml(chart_zip, "word/_rels/document.xml.rels")
        layout_types = _read_xml(layout_zip, "[Content_Types].xml")
        chart_types = _read_xml(chart_zip, "[Content_Types].xml")

        layout_drawings = layout_doc.xpath("//w:drawing", namespaces=NS)
        chart_drawings = chart_doc.xpath("//w:drawing", namespaces=NS)
        if len(layout_drawings) != 3 or len(chart_drawings) != 3:
            raise ValueError(
                f"Expected 3 drawings in both docs, got layout={len(layout_drawings)} "
                f"chart={len(chart_drawings)}"
            )

        chart_rel_by_id = {rel.get("Id"): rel for rel in chart_rels}
        new_chart_rids = ["rId101", "rId102", "rId103"]

        for index, (layout_drawing, chart_drawing, new_rid) in enumerate(
            zip(layout_drawings, chart_drawings, new_chart_rids),
            start=1,
        ):
            cloned = etree.fromstring(etree.tostring(chart_drawing))
            chart_ids = cloned.xpath(".//c:chart/@r:id", namespaces=NS)
            if len(chart_ids) != 1:
                raise ValueError(f"Chart drawing {index} does not contain one chart reference")

            original_extent = layout_drawing.xpath(".//wp:extent", namespaces=NS)
            chart_extent = cloned.xpath(".//wp:extent", namespaces=NS)
            graphic_extent = cloned.xpath(".//a:ext", namespaces=NS)
            if original_extent:
                cx = original_extent[0].get("cx")
                cy = original_extent[0].get("cy")
                for node in chart_extent + graphic_extent:
                    node.set("cx", cx)
                    node.set("cy", cy)

            chart_ref = cloned.xpath(".//c:chart", namespaces=NS)[0]
            old_rid = chart_ref.get(f"{{{NS['r']}}}id")
            chart_ref.set(f"{{{NS['r']}}}id", new_rid)

            old_rel = chart_rel_by_id[old_rid]
            new_rel = etree.Element(f"{{{REL_NS}}}Relationship")
            new_rel.set("Id", new_rid)
            new_rel.set("Type", old_rel.get("Type"))
            new_rel.set("Target", old_rel.get("Target"))
            layout_rels.append(new_rel)

            parent = layout_drawing.getparent()
            parent.replace(layout_drawing, cloned)

        # Remove stale image relationships that belonged to the old chart PNGs.
        used_rids = set(layout_doc.xpath("//@r:id | //@r:embed | //@r:link", namespaces=NS))
        for rel in list(layout_rels):
            if rel.get("Id") not in used_rids and rel.get("Target", "").startswith("media/"):
                layout_rels.remove(rel)

        # Copy the native chart package parts and any chart-specific theme
        # overrides referenced by the chart relationship files.
        for name in chart_zip.namelist():
            if name.startswith("word/charts/") or name.startswith("word/theme/themeOverride"):
                replacements[name] = chart_zip.read(name)

        for override in list(layout_types.findall(f"{{{CONTENT_NS}}}Override")):
            part_name = override.get("PartName", "")
            if part_name.startswith("/word/charts/") or part_name.startswith(
                "/word/theme/themeOverride"
            ):
                layout_types.remove(override)
        for override in chart_types.findall(f"{{{CONTENT_NS}}}Override"):
            part_name = override.get("PartName", "")
            if part_name.startswith("/word/charts/") or part_name.startswith(
                "/word/theme/themeOverride"
            ):
                layout_types.append(etree.fromstring(etree.tostring(override)))

        replacements["word/document.xml"] = _write_xml(layout_doc)
        replacements["word/_rels/document.xml.rels"] = _write_xml(layout_rels)
        replacements["[Content_Types].xml"] = _write_xml(layout_types)

    _replace_zip_entries(layout_template, replacements, output)
    logger.info("Merged Huaan native charts into original Word layout: %s", output)
    return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    print(merge_layout_with_native_charts())
