"""Generate report charts from Excel chart caches and embed them into DOCX.

The service reads cached series data from ``xl/charts/chart*.xml`` inside an
Excel workbook, renders chart images in memory, and writes the image bytes
directly into the final ``.docx`` package. No intermediate PNG files are kept
under the report project.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from openpyxl.utils.cell import column_index_from_string
from openpyxl.utils.datetime import from_excel

from core.observability import get_logger
from reporting.projects.project_manager import ReportProject

logger = get_logger(__name__)

CHART_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
EXCEL_BLUE = "#5B9BD5"
EXCEL_ORANGE = "#ED7D31"
EXCEL_DARK_BLUE = "#2F5597"
EXCEL_LIGHT_BLUE = "#8FAADC"
EXCEL_GRID = "#D9D9D9"
EXCEL_TEXT = "#595959"
EXCEL_FIGSIZE = (7.22, 4.34)
EXCEL_DPI = 100

ET.register_namespace("w", WORD_NS)
ET.register_namespace("wp", WP_NS)
ET.register_namespace("a", DRAWING_NS)
ET.register_namespace("pic", PIC_NS)
ET.register_namespace("c", CHART_NS)
ET.register_namespace("r", REL_NS)


@dataclass(frozen=True)
class ChartSeries:
    """One chart series parsed from Excel chart cache."""

    name: str
    categories: List[Any]
    values: List[float]


@dataclass(frozen=True)
class GeneratedChartInfo:
    """Generated chart metadata for run logs."""

    chart_id: str
    title: str
    workbook: str
    source_chart: str
    replace_kind: str
    point_count: int
    warnings: List[str]


@dataclass(frozen=True)
class GeneratedChartImage:
    """In-memory chart image and its DOCX replacement target."""

    chart_id: str
    title: str
    image_bytes: bytes
    replace: Dict[str, Any]
    info: GeneratedChartInfo


def _dict_config(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_config(value: Any, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


class ReportProjectChartService:
    """Render configured report charts and embed them into a DOCX package."""

    def generate_and_embed(
        self,
        *,
        project: ReportProject,
        report_config: Dict[str, Any],
        docx_path: Path,
    ) -> List[GeneratedChartInfo]:
        """Generate configured charts and embed them into ``docx_path``."""
        chart_configs = report_config.get("charts")
        if not isinstance(chart_configs, dict) or not chart_configs:
            return []

        sync_native_chart_parts(project, chart_configs, docx_path)

        images: List[GeneratedChartImage] = []
        for chart_id, config in chart_configs.items():
            if not isinstance(config, dict) or not config.get("enabled", True):
                continue
            replace = _dict_config(config.get("replace"))
            if replace.get("kind") == "native_chart":
                images.append(
                    GeneratedChartImage(
                        chart_id=str(chart_id),
                        title=str(config.get("title") or chart_id),
                        image_bytes=b"",
                        replace=replace,
                        info=GeneratedChartInfo(
                            chart_id=str(chart_id),
                            title=str(config.get("title") or chart_id),
                            workbook=str(config.get("workbook") or ""),
                            source_chart=str(config.get("source_chart") or ""),
                            replace_kind="native_chart",
                            point_count=0,
                            warnings=[],
                        ),
                    )
                )
                continue
            try:
                images.append(self._generate_chart(project, str(chart_id), config))
            except Exception as exc:
                replace = _dict_config(config.get("replace"))
                logger.exception(
                    "Failed to generate report chart",
                    project=project.name,
                    chart_id=chart_id,
                    error=str(exc),
                )
                images.append(
                    GeneratedChartImage(
                        chart_id=str(chart_id),
                        title=str(config.get("title") or chart_id),
                        image_bytes=b"",
                        replace=replace,
                        info=GeneratedChartInfo(
                            chart_id=str(chart_id),
                            title=str(config.get("title") or chart_id),
                            workbook=str(config.get("workbook") or ""),
                            source_chart=str(config.get("source_chart") or ""),
                            replace_kind=str(replace.get("kind") or ""),
                            point_count=0,
                            warnings=[str(exc)],
                        ),
                    )
                )

        valid_images = [image for image in images if image.image_bytes]
        if valid_images:
            embed_chart_images_in_docx(docx_path, valid_images)
        return [image.info for image in images]

    def _generate_chart(
        self,
        project: ReportProject,
        chart_id: str,
        config: Dict[str, Any],
    ) -> GeneratedChartImage:
        workbook = str(config.get("workbook") or "")
        if not workbook:
            raise ValueError(f"Chart {chart_id} missing workbook")
        workbook_path = project.project_dir / "data" / workbook
        if not workbook_path.exists():
            raise FileNotFoundError(f"Chart workbook not found: {workbook_path}")

        source_data = (
            config.get("source_data") if isinstance(config.get("source_data"), dict) else {}
        )
        source_chart = str(config.get("source_chart") or "")
        if source_data:
            series = read_worksheet_chart_series(workbook_path, source_data)
            source_label = _worksheet_source_label(source_data)
        elif source_chart:
            series = read_excel_chart_series(workbook_path, source_chart)
            source_label = source_chart
        else:
            raise ValueError(f"Chart {chart_id} missing source_chart or source_data")
        chart_type = str(config.get("type") or "line")
        title = str(config.get("title") or chart_id)
        warnings = validate_chart_series(series, chart_id)
        replace = _dict_config(config.get("replace"))
        fallback = _dict_config(config.get("fallback"))
        if _all_chart_values_zero(series) and fallback:
            fallback_series = self._read_fallback_chart_series(project, fallback)
            if fallback_series and not _all_chart_values_zero(fallback_series):
                series = fallback_series
                warnings.append(f"{chart_id}: Excel 图表缓存全为 0，已临时使用 Word 模板图表缓存")
            else:
                warnings.append(f"{chart_id}: fallback 图表缓存不可用")
        if config.get("skip_if_all_zero") and _all_chart_values_zero(series):
            return GeneratedChartImage(
                chart_id=chart_id,
                title=title,
                image_bytes=b"",
                replace=replace,
                info=GeneratedChartInfo(
                    chart_id=chart_id,
                    title=title,
                    workbook=str(workbook_path),
                    source_chart=source_label,
                    replace_kind=str(replace.get("kind") or ""),
                    point_count=sum(len(item.values) for item in series),
                    warnings=warnings,
                ),
            )
        image_bytes = render_chart_image(
            chart_type=chart_type,
            title=title,
            series=series,
            config=config,
        )
        return GeneratedChartImage(
            chart_id=chart_id,
            title=title,
            image_bytes=image_bytes,
            replace=replace,
            info=GeneratedChartInfo(
                chart_id=chart_id,
                title=title,
                workbook=str(workbook_path),
                source_chart=source_label,
                replace_kind=str(replace.get("kind") or ""),
                point_count=sum(len(item.values) for item in series),
                warnings=warnings,
            ),
        )

    def _read_fallback_chart_series(
        self,
        project: ReportProject,
        fallback: Dict[str, Any],
    ) -> List[ChartSeries]:
        package = str(fallback.get("package") or "word_template")
        source_chart = str(fallback.get("source_chart") or "")
        if not source_chart:
            return []
        if package == "word_template":
            source_path = project.word_template_path
        else:
            source_path = project.project_dir / package
        if not source_path.exists():
            return []
        return read_excel_chart_series(source_path, source_chart)


def read_excel_chart_series(workbook_path: Path, chart_path: str) -> List[ChartSeries]:
    """Read chart series from an xlsx chart XML cache."""
    normalized = chart_path.lstrip("/")
    with zipfile.ZipFile(workbook_path) as archive:
        if normalized not in archive.namelist():
            raise FileNotFoundError(f"Chart XML not found in workbook: {chart_path}")
        root = ET.fromstring(archive.read(normalized))

    ns = {"c": CHART_NS}
    series: List[ChartSeries] = []
    for index, ser in enumerate(root.findall(".//c:ser", ns), start=1):
        name_values = _cache_values(ser.find("c:tx", ns))
        categories = _cache_values(ser.find("c:cat", ns))
        raw_values = _cache_values(ser.find("c:val", ns))
        values = [_to_float(value) for value in raw_values]
        clean_pairs = [
            (category, value) for category, value in zip(categories, values) if value is not None
        ]
        if not clean_pairs:
            continue
        clean_categories, clean_values = zip(*clean_pairs)
        series.append(
            ChartSeries(
                name=name_values[0] if name_values else f"series_{index}",
                categories=[str(item) for item in clean_categories],
                values=[float(item) for item in clean_values],
            )
        )
    return series


def read_worksheet_chart_series(
    workbook_path: Path, source_data: Dict[str, Any]
) -> List[ChartSeries]:
    """Read chart series from worksheet cached cell values and drop incomplete rows."""
    sheet_name = str(source_data.get("sheet") or "")
    if not sheet_name:
        raise ValueError("worksheet chart source missing sheet")
    category_column = str(source_data.get("category_column") or "A")
    start_row = int(source_data.get("start_row") or 2)
    series_configs = source_data.get("series")
    if not isinstance(series_configs, list) or not series_configs:
        raise ValueError("worksheet chart source missing series")

    category_index = column_index_from_string(category_column)
    series_indexes = [
        (
            str(item.get("name") or item.get("column") or f"series_{index}"),
            column_index_from_string(str(item.get("column") or "")),
        )
        for index, item in enumerate(series_configs, start=1)
        if isinstance(item, dict) and item.get("column")
    ]
    if not series_indexes:
        raise ValueError("worksheet chart source has no valid series columns")

    rows = _read_worksheet_cached_rows(workbook_path, sheet_name)
    categories: List[Any] = []
    values_by_series: List[List[float]] = [[] for _ in series_indexes]
    blank_run = 0
    max_blank_run = int(source_data.get("max_blank_run") or 50)
    for row_index in sorted(index for index in rows if index >= start_row):
        row_values = rows[row_index]
        category = row_values.get(category_index)
        raw_values = [row_values.get(col_index) for _, col_index in series_indexes]
        if _is_blank(category) and all(_is_blank(value) for value in raw_values):
            blank_run += 1
            if blank_run >= max_blank_run:
                break
            continue
        blank_run = 0
        numeric_values = [_to_float(value) for value in raw_values]
        clean_values: List[float] = []
        for value in numeric_values:
            if value is None:
                break
            clean_values.append(float(value))
        if _is_blank(category) or len(clean_values) != len(series_indexes):
            continue
        categories.append(category)
        for index, value in enumerate(clean_values):
            values_by_series[index].append(value)
    return [
        ChartSeries(name=name, categories=list(categories), values=values)
        for (name, _), values in zip(series_indexes, values_by_series)
    ]


def validate_chart_series(series: List[ChartSeries], chart_id: str) -> List[str]:
    """Return warnings for suspicious chart data."""
    warnings: List[str] = []
    if not series:
        return [f"{chart_id}: 未读取到图表缓存数据"]
    if _all_chart_values_zero(series):
        warnings.append(f"{chart_id}: 图表缓存数值全为 0，请确认 Excel/Wind 已刷新并保存")
    return warnings


def _all_chart_values_zero(series: List[ChartSeries]) -> bool:
    all_values = [value for item in series for value in item.values]
    return bool(all_values) and all(abs(value) < 1e-12 for value in all_values)


def _worksheet_source_label(source_data: Dict[str, Any]) -> str:
    sheet = str(source_data.get("sheet") or "")
    category_column = str(source_data.get("category_column") or "")
    series_columns = [
        str(item.get("column") or "")
        for item in source_data.get("series", [])
        if isinstance(item, dict)
    ]
    return f"worksheet:{sheet}!{category_column},{','.join(series_columns)}"


def _read_worksheet_cached_rows(workbook_path: Path, sheet_name: str) -> Dict[int, Dict[int, Any]]:
    with zipfile.ZipFile(workbook_path) as archive:
        sheet_path = _worksheet_xml_path(archive, sheet_name)
        shared_strings = _read_shared_strings(archive)
        root = ET.fromstring(archive.read(sheet_path))

    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: Dict[int, Dict[int, Any]] = {}
    for cell in root.findall(".//main:sheetData/main:row/main:c", ns):
        ref = cell.attrib.get("r", "")
        match = re.match(r"([A-Z]+)([0-9]+)", ref)
        if not match:
            continue
        col_index = column_index_from_string(match.group(1))
        row_index = int(match.group(2))
        value = _cached_cell_value(cell, shared_strings)
        rows.setdefault(row_index, {})[col_index] = value
    return rows


def _worksheet_xml_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib.get("Id"): rel.attrib.get("Target", "")
        for rel in rels_root.iter(f"{{{pkg_ns}}}Relationship")
    }
    for sheet in workbook_root.iter(f"{{{main_ns}}}sheet"):
        if sheet.attrib.get("name") != sheet_name:
            continue
        rel_id = sheet.attrib.get(f"{{{rel_ns}}}id")
        target = rel_targets.get(rel_id)
        if not target:
            break
        if target.startswith("/"):
            return target.lstrip("/")
        return f"xl/{target}"
    raise ValueError(f"worksheet not found: {sheet_name}")


def _read_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: List[str] = []
    for item in root.findall("main:si", ns):
        strings.append("".join(text.text or "" for text in item.findall(".//main:t", ns)))
    return strings


def _cached_cell_value(cell: ET.Element, shared_strings: List[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        return inline.text if inline is not None else None
    value = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
    if value is None or value.text is None:
        return None
    if cell_type == "s":
        index = _to_float(value.text)
        if index is None:
            return None
        string_index = int(index)
        return shared_strings[string_index] if 0 <= string_index < len(shared_strings) else None
    return value.text


def render_chart_image(
    *,
    chart_type: str,
    title: str,
    series: List[ChartSeries],
    config: Dict[str, Any],
) -> bytes:
    """Render chart image bytes with matplotlib."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    _configure_chinese_fonts(font_manager, plt)
    if chart_type in {"column_bar", "horizontal_bar"}:
        return _render_column_bar(title, series, config, plt)
    if chart_type == "dual_axis_line":
        return _render_dual_axis_line(title, series, config, plt, mdates)
    return _render_line(title, series, config, plt, mdates)


def embed_chart_images_in_docx(docx_path: Path, images: List[GeneratedChartImage]) -> None:
    """Write generated image bytes directly into a docx package."""
    with zipfile.ZipFile(docx_path, "r") as source:
        entries = {name: source.read(name) for name in source.namelist()}

    document_xml = entries.get("word/document.xml")
    rels_xml = entries.get("word/_rels/document.xml.rels")
    if not document_xml or not rels_xml:
        raise ValueError(f"Invalid docx package: {docx_path}")

    document_root = ET.fromstring(document_xml)
    rels_root = ET.fromstring(rels_xml)
    dirty_document = False
    dirty_rels = False

    for image in images:
        replace = image.replace
        kind = replace.get("kind")
        if kind == "media":
            target = str(replace.get("target") or "").lstrip("/")
            if not target:
                raise ValueError(f"Chart {image.chart_id} missing media target")
            entries[target] = image.image_bytes
            continue

        if kind == "chart_to_image":
            media_name = f"word/media/generated_{image.chart_id}.png"
            chart_rel_id = str(replace.get("chart_relationship_id") or "")
            if _find_chart_drawing(document_root, chart_rel_id) is None:
                if media_name not in entries:
                    raise ValueError(f"Chart drawing not found in docx: {chart_rel_id}")
                entries[media_name] = image.image_bytes
                continue

            entries[media_name] = image.image_bytes
            rel_id = _next_relationship_id(rels_root)
            ET.SubElement(
                rels_root,
                f"{{{PKG_REL_NS}}}Relationship",
                {
                    "Id": rel_id,
                    "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                    "Target": f"media/generated_{image.chart_id}.png",
                },
            )
            dirty_rels = True
            if not _replace_chart_drawing_with_image(
                document_root, chart_rel_id, rel_id, image.title
            ):
                raise ValueError(f"Chart drawing not found in docx: {chart_rel_id}")
            if chart_rel_id:
                _remove_relationship(rels_root, chart_rel_id)
            dirty_document = True

    if dirty_document:
        entries["word/document.xml"] = ET.tostring(
            document_root,
            encoding="utf-8",
            xml_declaration=True,
        )
    if dirty_rels:
        entries["word/_rels/document.xml.rels"] = ET.tostring(
            rels_root,
            encoding="utf-8",
            xml_declaration=True,
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        temp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for name, content in entries.items():
                target.writestr(name, content)
        shutil.copy2(temp_path, docx_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _filter_chart_xml_zero_values(chart_xml_bytes: bytes) -> bytes:
    """Remove data points whose values are zero in *any* series from native chart XML.

    Scans all ``<c:ser>`` elements, collects the ``<c:val>`` cached values per
    index, and marks every index where at least one series holds an (approximately)
    zero value.  Those indices are then removed from every cache — both the
    category cache (``numCache`` / ``strCache``) and the value cache — and the
    remaining ``<c:pt>`` elements are renumbered sequentially.  ``ptCount`` is
    updated to match.

    Returns the original bytes unchanged when no zero values are detected (so the
    common case of fully-populated data incurs no behavioural diff).
    """
    ns = {"c": CHART_NS}
    root = ET.fromstring(chart_xml_bytes)

    # ── collect {idx → value} from every series' value cache ─────────────────
    series_value_indices: list[dict[int, float]] = []
    for ser in root.findall(".//c:ser", ns):
        val_indices: dict[int, float] = {}
        for num_cache in ser.findall(".//c:val//c:numCache", ns):
            for pt in num_cache.findall("c:pt", ns):
                idx_str = pt.attrib.get("idx", "")
                if idx_str == "":
                    continue
                idx = int(idx_str)
                v_elem = pt.find("c:v", ns)
                if v_elem is not None and v_elem.text:
                    try:
                        val_indices[idx] = float(v_elem.text)
                    except (ValueError, TypeError):
                        val_indices[idx] = 1.0  # treat unparseable as non-zero
        if val_indices:
            series_value_indices.append(val_indices)

    if not series_value_indices:
        return chart_xml_bytes

    # ── identify indices where *any* series has a zero value ─────────────────
    all_indices: set[int] = set()
    for indices in series_value_indices:
        all_indices.update(indices.keys())

    zero_indices: set[int] = set()
    for idx in sorted(all_indices):
        for indices in series_value_indices:
            val = indices.get(idx)
            if val is not None and abs(val) < 1e-10:
                zero_indices.add(idx)
                break

    if not zero_indices:
        return chart_xml_bytes

    logger.info(
        "Filtering zero-value data points from native chart XML",
        total_indices=len(all_indices),
        zero_indices=len(zero_indices),
    )

    # ── purge zero-value <c:pt> elements from every series cache ─────────────
    for ser in root.findall(".//c:ser", ns):
        for cache_tag in ("c:numCache", "c:strCache"):
            for cache_elem in ser.findall(f".//{cache_tag}", ns):
                # Keep only non-zero data points
                surviving: list[ET.Element] = []
                for pt in cache_elem.findall("c:pt", ns):
                    idx_str = pt.attrib.get("idx", "")
                    if idx_str and int(idx_str) in zero_indices:
                        continue
                    surviving.append(pt)

                # Clear removed elements (avoid keeping orphans)
                for pt in cache_elem.findall("c:pt", ns):
                    cache_elem.remove(pt)

                # Re-add with sequential indices
                for new_idx, pt in enumerate(surviving):
                    pt.attrib["idx"] = str(new_idx)
                    cache_elem.append(pt)

                # Update cached point count
                pt_count = cache_elem.find("c:ptCount", ns)
                if pt_count is not None:
                    pt_count.attrib["val"] = str(len(surviving))

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _extract_filtered_series_data(chart_xml_bytes: bytes) -> list[dict]:
    """Extract series caches from chart XML, filtered of zero-value data points.

    Uses the same zero-detection logic as ``_filter_chart_xml_zero_values``,
    but returns structured data instead of modifying the XML in-place.  This
    allows the filtered caches to be injected into a *different* XML tree
    (e.g. the template chart XML in a Word document).

    Returns a list where each element corresponds to a ``<c:ser>`` and holds
    a ``"caches"`` list of ``{"tag": str, "pts": [str, ...]}`` dicts.
    """
    ns = {"c": CHART_NS}
    root = ET.fromstring(chart_xml_bytes)

    # ── collect {idx → value} from every series' value cache ─────────────────
    series_value_indices: list[dict[int, float]] = []
    for ser in root.findall(".//c:ser", ns):
        val_indices: dict[int, float] = {}
        for num_cache in ser.findall(".//c:val//c:numCache", ns):
            for pt in num_cache.findall("c:pt", ns):
                idx_str = pt.attrib.get("idx", "")
                if not idx_str:
                    continue
                idx = int(idx_str)
                v_elem = pt.find("c:v", ns)
                if v_elem is not None and v_elem.text:
                    try:
                        val_indices[idx] = float(v_elem.text)
                    except (ValueError, TypeError):
                        val_indices[idx] = 1.0
        if val_indices:
            series_value_indices.append(val_indices)

    if not series_value_indices:
        return []

    # ── identify indices where *any* series has a zero value ─────────────────
    all_indices: set[int] = set()
    for indices in series_value_indices:
        all_indices.update(indices.keys())

    zero_indices: set[int] = set()
    for idx in sorted(all_indices):
        for indices in series_value_indices:
            val = indices.get(idx)
            if val is not None and abs(val) < 1e-10:
                zero_indices.add(idx)
                break

    # ── extract filtered caches for each series ──────────────────────────────
    result: list[dict] = []
    for ser in root.findall(".//c:ser", ns):
        series_data: dict = {"caches": []}
        for cache_tag in ("c:numCache", "c:strCache"):
            for cache_elem in ser.findall(f".//{cache_tag}", ns):
                cache_data: dict = {"tag": cache_tag, "pts": []}
                for pt in cache_elem.findall("c:pt", ns):
                    idx_str = pt.attrib.get("idx", "")
                    if idx_str and int(idx_str) in zero_indices:
                        continue
                    v_elem = pt.find("c:v", ns)
                    cache_data["pts"].append(v_elem.text if v_elem is not None else "")
                if cache_data["pts"]:
                    series_data["caches"].append(cache_data)
        result.append(series_data)

    if zero_indices:
        logger.info(
            "Filtered zero-value data points from native chart XML (data extraction)",
            total_indices=len(all_indices),
            zero_indices=len(zero_indices),
        )
    return result


def _replace_series_caches_in_template(
    template_root: ET.Element,
    filtered_data: list[dict],
) -> None:
    """Replace series caches in *template_root* with filtered data from Excel.

    Series are matched by index (1:1 correspondence).  Within each series,
    cache elements are matched by position: the Nth cache in the filtered data
    replaces the Nth cache element (all tag types combined) in the template
    series.  ``ptCount`` is updated to reflect the new point count.
    """
    ns = {"c": CHART_NS}
    ser_elements = template_root.findall(".//c:ser", ns)

    for ser_idx, ser in enumerate(ser_elements):
        if ser_idx >= len(filtered_data):
            break
        fd = filtered_data[ser_idx]

        # Build a flat list of ALL cache elements in this template series
        # (numCache / strCache, including both category and value caches)
        template_caches: list[ET.Element] = []
        for cache_tag in ("c:numCache", "c:strCache"):
            template_caches.extend(ser.findall(f".//{cache_tag}", ns))

        # Apply each filtered cache to the corresponding template cache by position
        for cache_idx, cache_data in enumerate(fd.get("caches", [])):
            if cache_idx >= len(template_caches):
                break
            cache_elem = template_caches[cache_idx]
            pts_values: list[str] = cache_data["pts"]

            # Remove old <c:pt> elements
            for pt in list(cache_elem.findall("c:pt", ns)):
                cache_elem.remove(pt)

            # Add new <c:pt> elements with sequential indices
            for new_idx, value in enumerate(pts_values):
                pt = ET.Element(f"{{{CHART_NS}}}pt")
                pt.attrib["idx"] = str(new_idx)
                v = ET.SubElement(pt, f"{{{CHART_NS}}}v")
                v.text = value
                cache_elem.append(pt)

            # Update ptCount
            pt_count = cache_elem.find("c:ptCount", ns)
            if pt_count is not None:
                pt_count.attrib["val"] = str(len(pts_values))


def sync_native_chart_parts(
    project: ReportProject,
    chart_configs: Dict[str, Any],
    docx_path: Path,
) -> None:
    """Sync chart data from Excel workbooks into the Word template's chart XML.

    Instead of replacing the entire chart XML (which would pull in Excel-
    specific structure like ``<c:printSettings>`` and language codes that are
    incompatible with Word), we keep the Word template's chart XML as the base
    and only replace the series data caches (``numCache`` / ``strCache``) with
    filtered data from the Excel workbook.
    """
    # Read current docx entries upfront so we can use template chart XML as base
    with zipfile.ZipFile(docx_path, "r") as source:
        entries: Dict[str, bytes] = {name: source.read(name) for name in source.namelist()}

    updates: Dict[str, bytes] = {}
    for chart_id, config in chart_configs.items():
        if not isinstance(config, dict) or not config.get("enabled", True):
            continue
        native_chart_part = str(config.get("native_chart_part") or "").lstrip("/")
        source_chart = str(config.get("source_chart") or "").lstrip("/")
        workbook = str(config.get("workbook") or "")
        if not native_chart_part or not source_chart or not workbook:
            continue

        if native_chart_part not in entries:
            logger.warning(
                "Native chart part not found in document",
                chart_id=str(chart_id),
                chart_part=native_chart_part,
            )
            continue

        workbook_path = project.project_dir / "data" / workbook
        if not workbook_path.exists():
            logger.warning(
                "Native chart workbook missing",
                chart_id=str(chart_id),
                workbook=str(workbook_path),
            )
            continue

        try:
            # 1. Parse the template's chart XML (preserves Word-compatible structure)
            template_root = ET.fromstring(entries[native_chart_part])

            # 2. Extract filtered series caches from the Excel chart
            with zipfile.ZipFile(workbook_path) as workbook_archive:
                excel_chart_bytes = workbook_archive.read(source_chart)
            filtered_data = _extract_filtered_series_data(excel_chart_bytes)

            if filtered_data:
                # 3. Replace only the data caches in the template XML
                _replace_series_caches_in_template(template_root, filtered_data)

            # 4. Serialize back to bytes
            result = ET.tostring(template_root, encoding="utf-8", xml_declaration=True)
            updates[native_chart_part] = result
        except Exception as exc:
            logger.warning(
                "Failed to sync native chart data",
                chart_id=str(chart_id),
                workbook=str(workbook_path),
                source_chart=source_chart,
                error=str(exc),
            )

    if not updates:
        return

    entries.update(updates)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        temp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for name, content in entries.items():
                target.writestr(name, content)
        shutil.copy2(temp_path, docx_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    logger.info(
        "Synced native chart parts into Word document",
        docx=str(docx_path),
        chart_parts=sorted(updates),
    )


def _cache_values(node: ET.Element | None) -> List[str]:
    if node is None:
        return []
    ns = {"c": CHART_NS}
    for cache_name in ["strCache", "numCache"]:
        cache = node.find(f".//c:{cache_name}", ns)
        if cache is None:
            continue
        values: List[str] = []
        for point in cache.findall("c:pt", ns):
            value = point.find("c:v", ns)
            values.append(value.text if value is not None and value.text is not None else "")
        return values
    direct_value = node.find("c:v", ns)
    if direct_value is not None and direct_value.text is not None:
        return [direct_value.text]
    return []


def _is_blank(value: Any) -> bool:
    return value is None or value == ""


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            value = value.replace(",", "")
        return float(value)
    except (TypeError, ValueError):
        return None


def _configure_chinese_fonts(font_manager: Any, plt: Any) -> None:
    candidates = [
        "PingFang SC",
        "Hiragino Sans GB",
        "Songti SC",
        "STHeiti",
        "Arial Unicode MS",
        "SimHei",
    ]
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def _render_column_bar(
    title: str, series: List[ChartSeries], config: Dict[str, Any], plt: Any
) -> bytes:
    if not series:
        raise ValueError(f"{title}: no series")
    item = series[0]
    categories = item.categories
    values = item.values

    fig, ax = plt.subplots(figsize=EXCEL_FIGSIZE, dpi=EXCEL_DPI)
    ax.bar(range(len(values)), values, color=EXCEL_BLUE, width=0.72)
    if config.get("show_title"):
        ax.set_title(title, fontsize=16, color=EXCEL_TEXT, pad=12, fontweight="normal")
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=90, fontsize=7, color=EXCEL_TEXT)
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    _apply_excel_axis_style(ax, grid_axis="y")
    ax.tick_params(axis="y", labelsize=8, colors=EXCEL_TEXT, length=0)
    ax.tick_params(axis="x", colors=EXCEL_TEXT, length=0)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.92, bottom=0.34)
    return _figure_to_png_bytes(fig, plt)


def _render_dual_axis_line(
    title: str,
    series: List[ChartSeries],
    config: Dict[str, Any],
    plt: Any,
    mdates: Any,
) -> bytes:
    if len(series) < 2:
        raise ValueError(f"{title}: dual axis line chart requires at least two series")
    left, right = series[0], series[1]
    x_left = _categories_to_dates(left.categories)
    x_right = _categories_to_dates(right.categories)
    x_left, y_left = _slice_recent(x_left, left.values, config.get("recent_points"))
    x_right, y_right = _slice_recent(x_right, right.values, config.get("recent_points"))

    fig, ax_left = plt.subplots(figsize=EXCEL_FIGSIZE, dpi=EXCEL_DPI)
    ax_right = ax_left.twinx()
    line_left = ax_left.plot(x_left, y_left, color=EXCEL_BLUE, linewidth=2.25, label=left.name)
    line_right = ax_right.plot(
        x_right, y_right, color=EXCEL_ORANGE, linewidth=2.25, label=right.name
    )
    _apply_x_limits(ax_left, x_left + x_right)
    _apply_y_limits(ax_left, config.get("y_limits"))
    _apply_y_limits(ax_right, config.get("secondary_y_limits"))
    if config.get("show_title"):
        ax_left.set_title(title, fontsize=16, color=EXCEL_TEXT, pad=12, fontweight="normal")
    _format_date_axis(
        ax_left,
        mdates,
        date_format=str(config.get("date_format") or "%Y-%m-%d"),
        rotation=_int_config(config.get("x_label_rotation"), 45),
        tick_values=_date_tick_values(x_left, config),
    )
    _apply_excel_axis_style(ax_left, grid_axis="y")
    ax_right.spines["top"].set_visible(False)
    ax_right.spines["left"].set_visible(False)
    ax_right.spines["bottom"].set_color(EXCEL_GRID)
    ax_right.spines["right"].set_visible(False)
    ax_right.tick_params(axis="y", colors=EXCEL_TEXT, length=0)
    lines = line_left + line_right
    ax_left.legend(
        lines,
        [line.get_label() for line in lines],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.20),
        ncol=2,
        frameon=False,
        fontsize=11,
    )
    fig.subplots_adjust(left=0.10, right=0.92, top=0.92, bottom=0.36)
    return _figure_to_png_bytes(fig, plt)


def _render_line(
    title: str, series: List[ChartSeries], config: Dict[str, Any], plt: Any, mdates: Any
) -> bytes:
    if not series:
        raise ValueError(f"{title}: no series")
    fig, ax = plt.subplots(figsize=EXCEL_FIGSIZE, dpi=EXCEL_DPI)
    colors = config.get("colors")
    if not isinstance(colors, list) or not colors:
        colors = [EXCEL_DARK_BLUE, EXCEL_LIGHT_BLUE, EXCEL_BLUE, EXCEL_ORANGE]
    all_x_values: List[Any] = []
    for index, item in enumerate(series):
        x_values, y_values = _slice_recent(
            _categories_to_dates(item.categories),
            item.values,
            config.get("recent_points"),
        )
        all_x_values.extend(x_values)
        ax.plot(
            x_values, y_values, linewidth=2.25, color=colors[index % len(colors)], label=item.name
        )
    _apply_x_limits(ax, all_x_values)
    _apply_y_limits(ax, config.get("y_limits"))
    if config.get("show_title", True):
        ax.set_title(title, fontsize=16, color=EXCEL_TEXT, pad=12, fontweight="normal")
    _format_date_axis(
        ax,
        mdates,
        date_format=str(config.get("date_format") or "%Y"),
        rotation=_int_config(config.get("x_label_rotation"), 45),
        tick_values=_date_tick_values(x_values, config),
    )
    _apply_excel_axis_style(ax, grid_axis="y")
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.20),
        ncol=max(1, len(series)),
        frameon=False,
        fontsize=11,
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.34)
    return _figure_to_png_bytes(fig, plt)


def _categories_to_dates(categories: List[str]) -> List[Any]:
    dates = []
    for category in categories:
        try:
            dates.append(from_excel(float(category)))
        except (TypeError, ValueError):
            dates.append(category)
    return dates


def _format_date_axis(
    ax: Any,
    mdates: Any,
    *,
    date_format: str,
    rotation: int,
    tick_values: List[Any] | None,
) -> None:
    if tick_values:
        ax.set_xticks(tick_values)
    else:
        ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
    ax.tick_params(axis="x", labelrotation=rotation, labelsize=11, colors=EXCEL_TEXT, length=0)
    ax.tick_params(axis="y", labelsize=11, colors=EXCEL_TEXT, length=0)


def _apply_excel_axis_style(ax: Any, *, grid_axis: str) -> None:
    ax.set_facecolor("white")
    ax.grid(axis=grid_axis, color=EXCEL_GRID, linewidth=1.0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(EXCEL_GRID)


def _apply_y_limits(ax: Any, limits: Any) -> None:
    if not isinstance(limits, list) or len(limits) != 2:
        return
    try:
        ax.set_ylim(float(limits[0]), float(limits[1]))
    except (TypeError, ValueError):
        return


def _apply_x_limits(ax: Any, values: List[Any]) -> None:
    comparable = [value for value in values if hasattr(value, "toordinal")]
    if comparable:
        ax.set_xlim(min(comparable), max(comparable))


def _slice_recent(
    x_values: List[Any], y_values: List[float], recent_points: Any
) -> tuple[List[Any], List[float]]:
    if recent_points in (None, "", "all"):
        return x_values, y_values
    points = _int_config(recent_points, 0)
    if points <= 0:
        return x_values, y_values
    return x_values[-points:], y_values[-points:]


def _year_start_ticks(values: List[Any]) -> List[Any]:
    ticks: List[Any] = []
    seen_years = set()
    for value in values:
        year = getattr(value, "year", None)
        if year is None or year in seen_years:
            continue
        seen_years.add(year)
        ticks.append(value)
    return ticks


def _date_tick_values(values: List[Any], config: Dict[str, Any]) -> List[Any] | None:
    if config.get("date_ticks") == "year":
        ticks = _year_start_ticks(values)
        interval = _int_config(config.get("date_tick_interval"), 1)
        if interval > 1:
            return ticks[::interval]
        return ticks
    return _year_start_ticks(values)


def _figure_to_png_bytes(fig: Any, plt: Any) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", facecolor="white")
    plt.close(fig)
    return buffer.getvalue()


def _replace_chart_drawing_with_image(
    document_root: ET.Element,
    chart_rel_id: str,
    image_rel_id: str,
    title: str,
) -> bool:
    image_template = _find_first_image_drawing(document_root)
    if image_template is None:
        return False

    for parent in document_root.iter():
        children = list(parent)
        for child_index, child in enumerate(children):
            drawing = _find_chart_drawing(child, chart_rel_id)
            if drawing is None:
                continue
            extent = drawing.find(f".//{{{WP_NS}}}extent")
            cx = extent.attrib.get("cx", "5490210") if extent is not None else "5490210"
            cy = extent.attrib.get("cy", "1798320") if extent is not None else "1798320"
            replacement = deepcopy(image_template)
            _set_picture_relationship(replacement, image_rel_id, title, cx, cy)
            if child is drawing:
                parent[child_index] = replacement
            else:
                _replace_descendant(child, drawing, replacement)
            return True
    return False


def _find_first_image_drawing(document_root: ET.Element) -> ET.Element | None:
    for drawing in document_root.iter(f"{{{WORD_NS}}}drawing"):
        if drawing.find(f".//{{{DRAWING_NS}}}blip") is not None:
            return drawing
    return None


def _find_chart_drawing(node: ET.Element, chart_rel_id: str) -> ET.Element | None:
    for drawing in node.iter(f"{{{WORD_NS}}}drawing"):
        chart = drawing.find(f".//{{{CHART_NS}}}chart")
        if chart is None:
            continue
        rel_id = chart.attrib.get(f"{{{REL_NS}}}id")
        if not chart_rel_id or rel_id == chart_rel_id:
            return drawing
    return None


def _replace_descendant(root: ET.Element, target: ET.Element, replacement: ET.Element) -> bool:
    for parent in root.iter():
        children = list(parent)
        for index, child in enumerate(children):
            if child is target:
                parent[index] = replacement
                return True
    return False


def _set_picture_relationship(
    drawing: ET.Element,
    rel_id: str,
    title: str,
    cx: str,
    cy: str,
) -> None:
    blip = drawing.find(f".//{{{DRAWING_NS}}}blip")
    if blip is not None:
        blip.attrib[f"{{{REL_NS}}}embed"] = rel_id
    doc_pr = drawing.find(f".//{{{WP_NS}}}docPr")
    if doc_pr is not None:
        doc_pr.attrib["name"] = title
        doc_pr.attrib["descr"] = title
    extent = drawing.find(f".//{{{WP_NS}}}extent")
    if extent is not None:
        extent.attrib["cx"] = cx
        extent.attrib["cy"] = cy
    for ext in drawing.iter(f"{{{DRAWING_NS}}}ext"):
        if "cx" in ext.attrib and "cy" in ext.attrib:
            ext.attrib["cx"] = cx
            ext.attrib["cy"] = cy


def _next_relationship_id(rels_root: ET.Element) -> str:
    existing = {rel.attrib.get("Id", "") for rel in rels_root}
    index = 100
    while f"rId{index}" in existing:
        index += 1
    return f"rId{index}"


def _remove_relationship(rels_root: ET.Element, rel_id: str) -> None:
    for rel in list(rels_root):
        if rel.attrib.get("Id") == rel_id:
            rels_root.remove(rel)
