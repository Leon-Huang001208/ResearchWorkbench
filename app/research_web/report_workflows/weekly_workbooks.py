"""Project verified weekly data into existing Run OOXML copies without reformatting."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import TypeAlias
from zipfile import BadZipFile, ZipFile

from lxml import etree

from core.observability import get_logger

from .models import WorkflowError
from .weekly_data import (
    assess_weekly_snapshot,
    build_weekly_data_contract,
    load_weekly_mapping,
    weekly_snapshot_sha256,
)

log = get_logger(__name__)
M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS = {"m": M, "c": C}
_MAX_BYTES = 128 * 1024 * 1024
CellValue: TypeAlias = str | int | float | Decimal | None


def _xml(raw):
    if b"<!DOCTYPE" in raw.upper():
        raise WorkflowError("工作簿 XML 不允许 DTD", "weekly_workbook_invalid", 409)
    return etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True))


def _serial(day: str, date_1904: bool) -> int:
    return (
        date.fromisoformat(day) - date(1904, 1, 1)
        if date_1904
        else date.fromisoformat(day) - date(1899, 12, 30)
    ).days


def _column(ref):
    value = 0
    match = re.match(r"[A-Z]+", ref)
    if match is None:
        raise WorkflowError("单元格列引用无效", "weekly_cell_invalid", 409)
    for char in match[0]:
        value = value * 26 + ord(char) - ord("A") + 1
    return value


def _row_number(coordinate: str) -> int:
    match = re.search(r"[1-9][0-9]*$", coordinate)
    if match is None:
        raise WorkflowError("单元格行引用无效", "weekly_cell_invalid", 409)
    return int(match[0])


def _set(sheet, coordinate, value):
    data = sheet.find("m:sheetData", NS)
    if data is None:
        raise WorkflowError("工作簿缺少数据区", "weekly_workbook_invalid", 409)
    row_index = _row_number(coordinate)
    row = data.find(f"m:row[@r='{row_index}']", NS)
    if row is None:
        row = etree.Element(f"{{{M}}}row", r=str(row_index))
        following = next((item for item in data if int(item.get("r", 0)) > row_index), None)
        data.insert(data.index(following), row) if following is not None else data.append(row)
    cell = row.find(f"m:c[@r='{coordinate}']", NS)
    if cell is None:
        cell = etree.Element(f"{{{M}}}c", r=coordinate)
        following = next(
            (item for item in row if _column(item.get("r", "A1")) > _column(coordinate)), None
        )
        row.insert(row.index(following), cell) if following is not None else row.append(cell)
    for child in list(cell):
        if child.tag in {f"{{{M}}}v", f"{{{M}}}f", f"{{{M}}}is"}:
            cell.remove(child)
    cell.attrib.pop("t", None)
    if value is None:
        return
    if isinstance(value, str):
        cell.set("t", "inlineStr")
        inline = etree.SubElement(cell, f"{{{M}}}is")
        text = etree.SubElement(inline, f"{{{M}}}t")
        text.text = value
    else:
        etree.SubElement(cell, f"{{{M}}}v").text = str(value)


def _parts(raw):
    with ZipFile(io.BytesIO(raw)) as package:
        infos = package.infolist()
        if len(infos) > 4096 or sum(item.file_size for item in infos) > _MAX_BYTES:
            raise WorkflowError("工作簿超过安全大小", "weekly_workbook_too_large", 409)
        names = [item.filename for item in infos]
        if len(names) != len(set(names)) or any(
            PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name
            for name in names
        ):
            raise WorkflowError("工作簿部件无效", "weekly_workbook_invalid", 409)
        return infos, {name: package.read(name) for name in names}


def _sheets(parts):
    workbook = _xml(parts["xl/workbook.xml"])
    relationships = _xml(parts["xl/_rels/workbook.xml.rels"])
    by_id = {item.get("Id"): item.get("Target") for item in relationships}
    result = {}
    for sheet in workbook.find("m:sheets", NS):
        target = by_id[sheet.get(f"{{{R}}}id")]
        name = target.lstrip("/") if target.startswith("/") else "xl/" + target
        if ".." in PurePosixPath(name).parts or name not in parts:
            raise WorkflowError("工作表引用无效", "weekly_workbook_invalid", 409)
        result[sheet.get("name")] = (name, _xml(parts[name]))
    return workbook, result


def _cached(parts, sheets):
    strings = []
    if "xl/sharedStrings.xml" in parts:
        strings = ["".join(node.itertext()) for node in _xml(parts["xl/sharedStrings.xml"])]
    values = {}
    for name, (_, sheet) in sheets.items():
        cells = {}
        for cell in sheet.findall(".//m:sheetData/m:row/m:c", NS):
            value = cell.find("m:v", NS)
            if cell.get("t") == "s" and value is not None:
                cells[cell.get("r")] = strings[int(value.text)]
            elif cell.get("t") == "inlineStr":
                cells[cell.get("r")] = "".join(cell.find("m:is", NS).itertext())
            elif cell.get("t") in {"str", "e", "d"} and value is not None:
                # Wind name formulas cache text as t=str rather than shared
                # strings. Preserve it; attempting float() corrupts real files.
                cells[cell.get("r")] = value.text
            elif value is not None:
                cells[cell.get("r")] = float(value.text)
        values[name] = cells
    return values


def _chart_caches(parts, values, history_ends):
    pattern = re.compile(r"^'?(.*?)'?!\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?$")
    for name in list(parts):
        if not re.fullmatch(r"xl/charts/chart[0-9]+\.xml", name):
            continue
        chart = _xml(parts[name])
        for reference in chart.findall(".//c:numRef", NS) + chart.findall(".//c:strRef", NS):
            formula = reference.find("c:f", NS)
            match = pattern.fullmatch(formula.text or "") if formula is not None else None
            if match is None or match[1] not in values:
                raise WorkflowError("图表数据源未映射", "weekly_chart_source_unmapped", 409)
            sheet, column, start, end_column, end = match.groups()
            if end_column and end_column != column:
                raise WorkflowError("图表数据源不支持二维范围", "weekly_chart_source_unmapped", 409)
            first, last = int(start), int(end or start)
            if sheet in history_ends and first == 3 and end is not None:
                last = history_ends[sheet]
                formula.text = f"'{sheet}'!${column}${first}:${column}${last}"
            kind = "numCache" if reference.tag == f"{{{C}}}numRef" else "strCache"
            cache = reference.find(f"c:{kind}", NS)
            if cache is None:
                cache = etree.SubElement(reference, f"{{{C}}}{kind}")
            for child in list(cache):
                if child.tag in {f"{{{C}}}pt", f"{{{C}}}ptCount"}:
                    cache.remove(child)
            etree.SubElement(cache, f"{{{C}}}ptCount", val=str(last - first + 1))
            for index, row in enumerate(range(first, last + 1)):
                value = values[sheet].get(f"{column}{row}")
                if value is None:
                    continue  # Real holiday gaps remain gaps, never zero-filled.
                point = etree.SubElement(cache, f"{{{C}}}pt", idx=str(index))
                etree.SubElement(point, f"{{{C}}}v").text = str(value)
        parts[name] = etree.tostring(chart, xml_declaration=True, encoding="UTF-8", standalone=True)


def _project(raw, role, snapshot, assessment, contract):
    infos, parts = _parts(raw)
    workbook, sheets = _sheets(parts)
    values = _cached(parts, sheets)
    date_properties = workbook.find("m:workbookPr", NS)
    date_1904 = date_properties is not None and date_properties.get("date1904") in {"1", "true"}
    changes: dict[str, dict[str, CellValue]] = {}
    history_ends: dict[str, int] = {}
    observations = {item["id"]: item for item in assessment["observations"]}
    mapping = load_weekly_mapping()
    if role == "primary":
        changes["日期"] = {
            "A2": _serial(contract["period_end"], date_1904),
            "B2": _serial(
                max(
                    item["baseline_date"]
                    for item in observations.values()
                    if item["kind"] == "price_return" and item["id"].startswith("domestic_")
                ),
                date_1904,
            ),
        }
        for spec in mapping["series"]:
            if spec["group"] in {"domestic", "overseas"}:
                sheet, cell = spec["legacy_cell"].split("!")
                row = _row_number(cell)
                changes.setdefault(sheet, {}).update(
                    {f"A{row}": spec["asset"], f"B{row}": spec["display_name"]}
                )
                changes.setdefault(sheet, {})[cell] = Decimal(
                    observations[spec["id"]]["return_pct"]
                ) / (100 if spec["group"] == "overseas" else 1)
            elif spec["group"] in {"gold", "oil"}:
                sheet, coordinates = spec["legacy_cell"].split("!")
                row = _row_number(coordinates.split(":", 1)[0])
                observation = observations[spec["id"]]
                changes.setdefault(sheet, {})
                changes[sheet].update({f"A{row}": spec["asset"], f"B{row}": spec["display_name"]})
                if spec["group"] == "gold":
                    changes[sheet].update(
                        {
                            f"C{row}": Decimal(observation["close"]),
                            f"D{row}": Decimal(observation["return_pct"]),
                        }
                    )
                else:
                    changes[sheet].update(
                        {
                            f"C{row}": Decimal(observation["return_pct"]),
                            f"D{row}": Decimal(observation["close"]),
                            f"E{row}": Decimal(observation["baseline_close"]),
                            f"F{row}": Decimal(observation["close"])
                            - Decimal(observation["baseline_close"]),
                        }
                    )
        turnover = observations["market_turnover"]
        changes["市场成交"] = {
            "B2": Decimal(turnover["value"]) / Decimal("1e12"),
            "C2": Decimal(turnover["previous_value"]) / Decimal("1e12"),
        }
    elif role == "charts":
        changes["申万一级行业指数"] = {"A2": _serial(contract["period_end"], date_1904)}
        for spec in mapping["series"]:
            if spec["group"] == "industry":
                _, cell = spec["legacy_cell"].split("!")
                row = _row_number(cell)
                label = spec["display_name"]
                if label.endswith(("(申万)", "（申万）")):
                    label = label[:-4]
                changes["申万一级行业指数"].update(
                    {f"B{row}": spec["asset"], f"C{row}": spec["display_name"], f"D{row}": label}
                )
                changes["申万一级行业指数"][cell] = (
                    Decimal(observations[spec["id"]]["return_pct"]) / 100
                )
        for sheet, identifiers in (
            ("伦敦金_Au9999", ("history_gold_london", "history_gold_shanghai")),
            ("期货结算价(连续)_布伦特原油", ("history_oil_brent", "history_oil_wti")),
        ):
            series = [
                {
                    row["date"]: Decimal(str(row["value"]))
                    for row in snapshot["series"][identifier]["rows"]
                }
                for identifier in identifiers
            ]
            dates = sorted(series[0].keys() | series[1].keys())
            changes[sheet] = {
                coordinate: None
                for coordinate in values[sheet]
                if re.fullmatch(r"[ABC][0-9]+", coordinate) and int(coordinate[1:]) >= 3
            }
            for row, day in enumerate(dates, 3):
                changes[sheet].update(
                    {
                        f"A{row}": _serial(day, date_1904),
                        f"B{row}": series[0].get(day),
                        f"C{row}": series[1].get(day),
                    }
                )
            history_ends[sheet] = len(dates) + 2
    else:
        sheet = "经济数据"
        changes[sheet] = {
            coordinate: None
            for coordinate in values[sheet]
            if re.fullmatch(r"[A-H][0-9]+", coordinate) and int(coordinate[1:]) >= 2
        }
        for row, event in enumerate(snapshot["economic_calendar"]["events"], 2):
            content = (
                event["date"],
                event.get("time"),
                event["country"],
                event["indicator"],
                event["importance"],
                event.get("previous"),
                event.get("forecast"),
                event.get("actual"),
            )
            for column, value in zip("ABCDEFGH", content, strict=True):
                changes[sheet][f"{column}{row}"] = value
    for sheet_name, updates in changes.items():
        if sheet_name not in sheets:
            raise WorkflowError("本期底稿缺少映射工作表", "weekly_workbook_sheet_missing", 409)
        for coordinate, value in updates.items():
            _set(sheets[sheet_name][1], coordinate, value)
        values[sheet_name].update(updates)
        parts[sheets[sheet_name][0]] = etree.tostring(
            sheets[sheet_name][1], xml_declaration=True, encoding="UTF-8", standalone=True
        )
    calculation = workbook.find("m:calcPr", NS)
    if calculation is not None:
        calculation.set("calcMode", "manual")
        calculation.set("fullCalcOnLoad", "0")
        calculation.set("forceFullCalc", "0")
    parts["xl/workbook.xml"] = etree.tostring(
        workbook, xml_declaration=True, encoding="UTF-8", standalone=True
    )
    if role == "charts":
        _chart_caches(parts, values, history_ends)
    output = io.BytesIO()
    with ZipFile(output, "w") as package:
        for info in infos:
            package.writestr(info, parts[info.filename])
    return output.getvalue(), history_ends


def materialize_weekly_workbooks(
    snapshot: dict, run_root: Path, manifest, *, execution_purpose="formal"
) -> dict:
    """Modify only safe, existing Run copies, with exact snapshot/output hashes."""
    cutoff = snapshot.get("cutoff")
    if not isinstance(cutoff, str):
        raise WorkflowError("周报截止时间无效", "weekly_cutoff_invalid", 409)
    contract = build_weekly_data_contract(cutoff)
    assessment = assess_weekly_snapshot(
        snapshot,
        contract,
        run_root=run_root,
        manifest=manifest,
        execution_purpose=execution_purpose,
    )
    if assessment["status"] != "passed":
        raise WorkflowError("本期数据未通过，禁止投影工作簿", "weekly_data_not_passed", 409)
    root = Path(run_root)
    if root.is_symlink() or not root.is_dir():
        raise WorkflowError("运行目录无效", "weekly_run_root_invalid", 409)
    snapshot_path = root / "snapshots" / "report-data.json"
    if (
        snapshot_path.is_symlink()
        or snapshot_path.parent.is_symlink()
        or not snapshot_path.is_file()
    ):
        raise WorkflowError("本期数据尚未冻结", "weekly_snapshot_not_materialized", 409)
    try:
        snapshot_bytes = snapshot_path.read_bytes()
        if json.loads(snapshot_bytes) != snapshot:
            raise ValueError("snapshot_changed")
    except (OSError, ValueError) as exc:
        raise WorkflowError("本期数据版本不符", "weekly_snapshot_changed", 409) from exc
    manifest_value = (
        manifest.model_dump(mode="json") if hasattr(manifest, "model_dump") else manifest
    )
    if manifest_value.get("workflow_id") != "huaan-etf-weekly":
        raise WorkflowError("报告映射身份不符", "weekly_workflow_mismatch", 409)
    paths = [item["path"] for item in manifest_value.get("resources", [])]
    prepared = []
    ends = {}
    roles = {"primary": "周报数据.xlsx", "charts": "周报图表.xlsx", "calendar": "全球经济日历.xlsx"}
    try:
        for role, filename in roles.items():
            candidates = [value for value in paths if PurePosixPath(value).name == filename]
            if len(candidates) != 1:
                raise WorkflowError("报告工作簿映射不唯一或缺失", "weekly_workbook_unmapped", 409)
            logical = PurePosixPath(candidates[0])
            if (
                logical.is_absolute()
                or ".." in logical.parts
                or "\\" in candidates[0]
                or logical.parts[0] != "workbooks"
            ):
                raise WorkflowError("报告工作簿越界", "weekly_workbook_unsafe", 409)
            target = root.joinpath(*logical.parts)
            if not target.is_file() or any(
                root.joinpath(*logical.parts[:index]).is_symlink()
                for index in range(1, len(logical.parts) + 1)
            ):
                raise WorkflowError("报告工作簿不是安全副本", "weekly_workbook_unsafe", 409)
            source = target.read_bytes()
            if len(source) > _MAX_BYTES:
                raise WorkflowError("报告工作簿超过大小限制", "weekly_workbook_too_large", 409)
            raw, history = _project(source, role, snapshot, assessment, contract)
            ends.update(history)
            prepared.append((target, logical.as_posix(), raw))
        for target, _, raw in prepared:
            fd, temporary = tempfile.mkstemp(prefix="weekly-projection-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary, 0o600)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    except WorkflowError:
        raise
    except (OSError, BadZipFile, KeyError, ValueError, etree.XMLSyntaxError) as exc:
        log.warning("report_weekly_projection_failed", error_type=type(exc).__name__)
        raise WorkflowError("本期底稿无法投影", "weekly_projection_failed", 409) from exc
    log.info("report_weekly_workbooks_materialized", workbook_count=len(prepared))
    gold_end = ends.get("伦敦金_Au9999", 2)
    oil_end = ends.get("期货结算价(连续)_布伦特原油", 2)
    return {
        "snapshot_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "snapshot_content_sha256": weekly_snapshot_sha256(snapshot),
        "workbooks": [
            {"path": logical, "sha256": hashlib.sha256(raw).hexdigest()}
            for _, logical, raw in prepared
        ],
        "charts": {
            "industry_weekly_performance": {
                "workbook": "workbooks/周报图表.xlsx",
                "part": "xl/charts/chart1.xml",
                "sheet": "申万一级行业指数",
                "category_range": "D2:D32",
                "value_ranges": ["E2:E32"],
                "last_row": 32,
            },
            "gold_price": {
                "workbook": "workbooks/周报图表.xlsx",
                "part": "xl/charts/chart2.xml",
                "sheet": "伦敦金_Au9999",
                "category_range": f"A3:A{gold_end}",
                "value_ranges": [f"B3:B{gold_end}", f"C3:C{gold_end}"],
                "last_row": gold_end,
            },
            "oil_price": {
                "legacy_id": "crude_oil_price",
                "workbook": "workbooks/周报图表.xlsx",
                "part": "xl/charts/chart3.xml",
                "sheet": "期货结算价(连续)_布伦特原油",
                "category_range": f"A3:A{oil_end}",
                "value_ranges": [f"B3:B{oil_end}", f"C3:C{oil_end}"],
                "last_row": oil_end,
            },
        },
        "economic_calendar": {
            "workbook": "workbooks/全球经济日历.xlsx",
            "sheet": "经济数据",
            "range": f"A1:H{len(snapshot['economic_calendar']['events']) + 1}",
        },
        "overseas": {
            "workbook": "workbooks/周报数据.xlsx",
            "sheet": "海外",
            "range": "A2:C13",
            "columns": ["code", "name", "return_fraction"],
        },
    }
