"""Trusted Run resources for first-source comparison and reviewed API semantics."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .models import WorkflowError
from .weekly_data import MAPPING_SHA256, load_weekly_mapping

log = get_logger(__name__)
SOURCE_CONTRACT = "mappings/huaan-weekly-source-contract.json"
_HASH = re.compile(r"^[a-f0-9]{64}$")


def freeze_weekly_workbook_dates(run_root, manifest, contract) -> dict:
    """Freeze only Run-copy date inputs before an explicit Office calibration."""
    from lxml import etree

    from .weekly_workbooks import _parts, _serial, _set, _sheets

    manifest_value = (
        manifest.model_dump(mode="json") if hasattr(manifest, "model_dump") else manifest
    )
    if manifest_value.get("workflow_id") != "huaan-etf-weekly":
        raise WorkflowError("报告映射身份不符", "weekly_workflow_mismatch", 409)
    results = []
    for name in ("周报数据.xlsx", "周报图表.xlsx"):
        candidates = [
            item["path"]
            for item in manifest_value.get("resources", [])
            if PurePosixPath(item["path"]).name == name
        ]
        if len(candidates) != 1:
            raise WorkflowError("日期底稿映射缺失", "weekly_workbook_unmapped", 409)
        logical = candidates[0]
        raw = _resource(run_root, manifest, logical)
        infos, parts = _parts(raw)
        workbook, sheets = _sheets(parts)
        namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        properties = workbook.find("m:workbookPr", namespace)
        date_1904 = properties is not None and properties.get("date1904") in {"1", "true"}
        if name == "周报数据.xlsx":
            changes = {
                "日期": {
                    "A2": _serial(contract["period_end"], date_1904),
                    "B2": _serial(
                        (
                            date.fromisoformat(contract["period_start"]) - timedelta(days=3)
                        ).isoformat(),
                        date_1904,
                    ),
                }
            }
        else:
            changes = {"申万一级行业指数": {"A2": _serial(contract["period_end"], date_1904)}}
        for sheet_name, cells in changes.items():
            if sheet_name not in sheets:
                raise WorkflowError("日期工作表缺失", "weekly_workbook_sheet_missing", 409)
            for coordinate, cell_value in cells.items():
                _set(sheets[sheet_name][1], coordinate, cell_value)
            parts[sheets[sheet_name][0]] = etree.tostring(
                sheets[sheet_name][1], xml_declaration=True, encoding="UTF-8", standalone=True
            )
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as package:
            for info in infos:
                package.writestr(info, parts[info.filename])
        output = buffer.getvalue()
        target = Path(run_root).joinpath(*PurePosixPath(logical).parts)
        fd, temporary = tempfile.mkstemp(prefix="weekly-dates-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(output)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
        except OSError as exc:
            log.warning("weekly_dates_freeze_failed", error_type=type(exc).__name__)
            raise WorkflowError("日期冻结失败", "weekly_dates_freeze_failed", 409) from exc
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        results.append({"path": logical, "sha256": hashlib.sha256(output).hexdigest()})
    log.info("report_weekly_dates_frozen", workbook_count=len(results))
    return {"cutoff": contract["cutoff"], "workbooks": results}


def _resource(run_root, manifest, logical, *, immutable=False):
    root = Path(run_root)
    value = manifest.model_dump(mode="json") if hasattr(manifest, "model_dump") else manifest
    resource = next((item for item in value.get("resources", []) if item["path"] == logical), None)
    parts = PurePosixPath(logical)
    if (
        root.is_symlink()
        or resource is None
        or parts.is_absolute()
        or ".." in parts.parts
        or "\\" in logical
    ):
        raise WorkflowError("周报资源没有版本归属", "weekly_resource_invalid", 409)
    target = root.joinpath(*parts.parts)
    if not target.is_file() or any(
        root.joinpath(*parts.parts[:index]).is_symlink() for index in range(1, len(parts.parts) + 1)
    ):
        raise WorkflowError("周报资源不是安全副本", "weekly_resource_invalid", 409)
    raw = target.read_bytes()
    if (
        len(raw) > 128 * 1024 * 1024
        or immutable
        and hashlib.sha256(raw).hexdigest() != resource.get("sha256")
    ):
        raise WorkflowError("周报资源版本校验失败", "weekly_resource_changed", 409)
    return raw


def load_run_source_contract(run_root, manifest) -> tuple[dict, str]:
    """Read only a published package's exact resource, never arbitrary JSON input."""
    raw = _resource(run_root, manifest, SOURCE_CONTRACT, immutable=True)
    if len(raw) > 512 * 1024:
        raise WorkflowError("周报数据源合同过大", "weekly_source_contract_unverified", 409)
    try:
        value = json.loads(raw)
        if set(value) != {
            "schema_version",
            "mapping_sha256",
            "verification",
            "calendars",
            "economic_calendar",
        }:
            raise ValueError("contract_fields")
        if value.get("schema_version") != 1 or value.get("mapping_sha256") != MAPPING_SHA256:
            raise ValueError("identity")
        proof = value.get("verification", {})
        if proof.get("status") != "reviewed" or not _HASH.fullmatch(
            str(proof.get("evidence_sha256", ""))
        ):
            raise ValueError("review")
        markets = load_weekly_mapping()["calendars"]
        if set(value.get("calendars", {})) != set(markets):
            raise ValueError("calendar_coverage")
        for calendar in value["calendars"].values():
            if set(calendar) - {
                "semantics_verified",
                "wind_calendar",
                "timezone",
                "close_time",
                "close_day_offset",
                "session_overrides",
                "session_closes",
            }:
                raise ValueError("calendar_fields")
            if calendar.get("semantics_verified") is not True:
                raise ValueError("calendar_review")
            if not re.fullmatch(r"[A-Za-z0-9]{1,32}", calendar.get("wind_calendar", "")):
                raise ValueError("calendar_identity")
            if not isinstance(calendar.get("timezone"), str) or len(calendar["timezone"]) > 80:
                raise ValueError("calendar_timezone")
            ZoneInfo(calendar["timezone"])
            if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", calendar.get("close_time", "")):
                raise ValueError("calendar_close")
            if calendar.get("close_day_offset", 0) not in (0, 1):
                raise ValueError("calendar_close_day")
            for day, close in calendar.get("session_overrides", {}).items():
                date.fromisoformat(day)
                if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", close):
                    raise ValueError("calendar_override")
        economic = value.get("economic_calendar", {})
        if economic.get("method") != "wset" or economic.get("semantics_verified") is not True:
            raise ValueError("economic_method")
        if set(economic) - {
            "method",
            "dataset",
            "semantics_verified",
            "start_parameter",
            "end_parameter",
            "fields",
            "static_options",
            "importance_values",
        }:
            raise ValueError("economic_contract_fields")
        for key in ("dataset", "start_parameter", "end_parameter"):
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", economic.get(key, "")):
                raise ValueError("economic_query")
        if economic["start_parameter"] == economic["end_parameter"] or set(
            economic.get("static_options", {})
        ) & {economic["start_parameter"], economic["end_parameter"]}:
            raise ValueError("economic_date_parameters")
        if any(
            not isinstance(key, str)
            or not key
            or len(key) > 80
            or item not in {"重要", "较重要", "一般"}
            for key, item in economic.get("importance_values", {}).items()
        ):
            raise ValueError("economic_importance_mapping")
        if set(economic.get("fields", {})) != {"date", "country", "indicator", "importance"}:
            raise ValueError("economic_fields")
        if any(
            not isinstance(field, str) or not field.strip() or len(field) > 80
            for field in economic["fields"].values()
        ):
            raise ValueError("economic_field")
        for key, item in economic.get("static_options", {}).items():
            if (
                not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", key)
                or not isinstance(item, str)
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", item)
            ):
                raise ValueError("economic_option")
    except (ValueError, TypeError, KeyError) as exc:
        raise WorkflowError(
            "周报数据源合同未核实", "weekly_source_contract_unverified", 409
        ) from exc
    return value, hashlib.sha256(raw).hexdigest()


def capture_excel_comparison(run_root, manifest, contract) -> dict:
    """Read actual refreshed Run workbooks; callers cannot supply comparison values."""
    from .weekly_workbooks import _cached, _parts, _sheets

    value = manifest.model_dump(mode="json") if hasattr(manifest, "model_dump") else manifest
    if value.get("workflow_id") != "huaan-etf-weekly":
        raise WorkflowError("周报身份不符", "weekly_workflow_mismatch", 409)
    resources = value.get("resources", [])
    workbooks, evidence = {}, []
    for filename in ("周报数据.xlsx", "周报图表.xlsx", "全球经济日历.xlsx"):
        paths = [item["path"] for item in resources if PurePosixPath(item["path"]).name == filename]
        if len(paths) != 1:
            raise WorkflowError("Excel 比较底稿缺失", "weekly_baseline_missing", 409)
        raw = _resource(run_root, manifest, paths[0])
        _, parts = _parts(raw)
        workbook, sheets = _sheets(parts)
        workbooks[filename] = (_cached(parts, sheets), workbook)
        evidence.append({"path": paths[0], "sha256": hashlib.sha256(raw).hexdigest()})
    refresh_root = Path(run_root) / "refresh-manifests"
    if refresh_root.is_symlink() or not refresh_root.is_dir():
        raise WorkflowError("Excel 比较缺少刷新证据", "weekly_baseline_refresh_missing", 409)
    refreshes = []
    for path in sorted(refresh_root.glob("*.json")):
        if path.is_symlink() or not _HASH.fullmatch(path.stem):
            raise WorkflowError("刷新证据引用无效", "weekly_baseline_refresh_invalid", 409)
        raw = path.read_bytes()
        if len(raw) > 65536:
            raise WorkflowError("刷新证据过大", "weekly_baseline_refresh_invalid", 409)
        try:
            row = json.loads(raw)
        except ValueError as exc:
            raise WorkflowError("刷新证据无效", "weekly_baseline_refresh_invalid", 409) from exc
        if row.get("status") == "ready" and row.get("provider") == "wind_excel":
            refreshes.append(row)
    for item in evidence[:2]:
        if not any(
            row.get("workbook") == item["path"] and row.get("output_sha256") == item["sha256"]
            for row in refreshes
        ):
            raise WorkflowError("Excel 比较底稿未完整刷新", "weekly_baseline_refresh_missing", 409)
    primary, primary_book = workbooks["周报数据.xlsx"]
    graph, graph_book = workbooks["周报图表.xlsx"]
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

    def excel_day(number, workbook):
        if isinstance(number, bool) or not isinstance(number, (float, int)):
            raise TypeError("date_missing")
        prop = workbook.find("m:workbookPr", namespace)
        start = (
            date(1904, 1, 1)
            if prop is not None and prop.get("date1904") in {"1", "true"}
            else date(1899, 12, 30)
        )
        return (start + timedelta(days=int(number))).isoformat()

    def number(cells, coordinate):
        item = cells.get(coordinate)
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError("number_missing")
        return Decimal(str(item))

    try:
        if excel_day(primary["日期"].get("A2"), primary_book) != contract["period_end"]:
            raise ValueError("baseline_period_mismatch")
        observations = {}
        histories = {}
        for spec in load_weekly_mapping()["series"]:
            result = {key: spec[key] for key in ("asset", "field", "unit", "currency", "market")}
            if spec["group"] in {"domestic", "overseas", "industry"}:
                sheet, coordinate = spec["legacy_cell"].split("!")
                cells = graph[sheet] if spec["group"] == "industry" else primary[sheet]
                match = re.search(r"\d+", coordinate)
                if match is None:
                    raise ValueError("coordinate_invalid")
                row_number = int(match[0])
                if (
                    cells.get(f"{'B' if spec['group'] == 'industry' else 'A'}{row_number}")
                    != spec["asset"]
                ):
                    raise ValueError("asset_identity")
                multiplier = 100 if spec["group"] in {"industry", "overseas"} else 1
                result["return_pct"] = format(number(cells, coordinate) * multiplier, "f")
            elif spec["group"] == "turnover":
                result["current_total"] = format(
                    number(primary["市场成交"], "B2") * Decimal("5e12"), "f"
                )
                result["previous_total"] = format(
                    number(primary["市场成交"], "C2") * Decimal("5e12"), "f"
                )
            elif spec["group"] in {"gold", "oil"}:
                sheet, coordinate = spec["legacy_cell"].split("!")
                match = re.search(r"\d+", coordinate)
                if match is None:
                    raise ValueError("coordinate_invalid")
                row = int(match[0])
                if primary[sheet].get(f"A{row}") != spec["asset"]:
                    raise ValueError("asset_identity")
                result["return_pct"] = format(
                    number(primary[sheet], f"D{row}" if spec["group"] == "gold" else f"C{row}"), "f"
                )
                result["close"] = format(
                    number(primary[sheet], f"C{row}" if spec["group"] == "gold" else f"D{row}"), "f"
                )
                if spec["group"] == "oil":
                    result["baseline_close"] = format(number(primary[sheet], f"E{row}"), "f")
            else:
                sheet = "伦敦金_Au9999" if "gold" in spec["id"] else "期货结算价(连续)_布伦特原油"
                column = "B" if spec["id"].endswith(("london", "brent")) else "C"
                cells = graph[sheet]
                rows = []
                for coordinate in sorted(
                    (key for key in cells if re.fullmatch(r"A[0-9]+", key) and int(key[1:]) >= 3),
                    key=lambda key: int(key[1:]),
                ):
                    if cells.get(column + coordinate[1:]) is not None:
                        rows.append(
                            {
                                "date": excel_day(cells[coordinate], graph_book),
                                "value": format(number(cells, column + coordinate[1:]), "f"),
                            }
                        )
                histories[spec["id"]] = {
                    **result,
                    "rows": rows,
                    "source": "wind_excel",
                    "raw_sha256": evidence[1]["sha256"],
                }
            observations[spec["id"]] = result
    except (ValueError, KeyError, TypeError) as exc:
        raise WorkflowError("Excel 比较期或字段无效", "weekly_baseline_invalid", 409) from exc
    log.info("report_weekly_excel_comparison_captured", observation_count=len(observations))
    return {
        "schema_version": 1,
        "baseline_kind": "excel_workbooks",
        "workflow_id": "huaan-etf-weekly",
        "cutoff": contract["cutoff"],
        "mapping_sha256": MAPPING_SHA256,
        "source": "wind_excel",
        "comparisons": observations,
        "series": histories,
        "evidence": evidence,
        "refresh_manifests": refreshes,
    }
