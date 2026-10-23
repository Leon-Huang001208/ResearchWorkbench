"""Trusted Run resources for first-source comparison and reviewed API semantics."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .models import WorkflowError
from .weekly_data import MAPPING_SHA256, load_weekly_mapping

log = get_logger(__name__)
SOURCE_CONTRACT = "mappings/huaan-weekly-source-contract.json"
_HASH = re.compile(r"^[a-f0-9]{64}$")
_INDIA_FIELDS = {
    "calendar_source",
    "semantics_verified",
    "market",
    "asset",
    "timezone",
    "close_time",
    "evidence_path",
    "evidence_sha256",
    "completion_basis",
}


def _india_calendar_identity(spec, market):
    if (
        set(spec) != _INDIA_FIELDS
        or spec.get("calendar_source") != "exchange_calendar"
        or market != "IN"
        or spec.get("market") != "IN"
        or spec.get("asset") != "SENSEX.BO"
        or spec.get("timezone") != "Asia/Kolkata"
        or spec.get("completion_basis") != "full_session_end"
        or spec.get("semantics_verified") is not True
        or not _HASH.fullmatch(str(spec.get("evidence_sha256", "")))
        or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", spec.get("close_time", ""))
    ):
        raise ValueError("india_calendar_identity")


def _bse_native_dates(text):
    """Recognize actual BSE circular date spellings, including holiday-table rows."""
    months = {
        name.lower(): index
        for index, name in enumerate(
            ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1
        )
    }
    result = set(re.findall(r"\b20[0-9]{2}-[01][0-9]-[0-3][0-9]\b", text))
    for day, month, year in re.findall(
        r"\b([0-3]?[0-9])[- ]([A-Za-z]{3})[- ]([0-9]{2}|20[0-9]{2})\b", text
    ):
        if month.lower() in months:
            result.add(
                date(
                    int(year) + (2000 if len(year) == 2 else 0), months[month.lower()], int(day)
                ).isoformat()
            )
    for month, day, year in re.findall(r"\b([A-Za-z]+) ([0-3]?[0-9]),? (20[0-9]{2})\b", text):
        if month[:3].lower() in months:
            result.add(date(int(year), months[month[:3].lower()], int(day)).isoformat())
    return result


def read_india_exchange_calendar(run_root, manifest, spec, contract, *, acquired_at=None):
    """Host checks locked BSE bytes and every date; no caller-supplied sessions."""
    try:
        _india_calendar_identity(spec, "IN")
        raw = _resource(run_root, manifest, spec["evidence_path"], immutable=True)
        if len(raw) > 512 * 1024 or hashlib.sha256(raw).hexdigest() != spec["evidence_sha256"]:
            raise ValueError("india_calendar_hash")
        value = json.loads(raw)
        if set(value) != {
            "schema_version",
            "calendar_source",
            "market",
            "asset",
            "timezone",
            "coverage_start",
            "coverage_end",
            "observed_at",
            "native_sources",
            "days",
            "completion_basis",
        } or any(
            value.get(key) != expected
            for key, expected in (
                ("schema_version", 1),
                ("calendar_source", "exchange_calendar"),
                ("market", "IN"),
                ("asset", "SENSEX.BO"),
                ("timezone", "Asia/Kolkata"),
                ("completion_basis", "full_session_end"),
            )
        ):
            raise ValueError("india_calendar_identity")
        start, end = date.fromisoformat(value["coverage_start"]), date.fromisoformat(
            value["coverage_end"]
        )
        cutoff, observed = datetime.fromisoformat(contract["cutoff"]), datetime.fromisoformat(
            value["observed_at"]
        )
        if (
            not 0 <= (end - start).days <= 62
            or start.isoformat() > contract["window_start"]
            or end.isoformat() < contract["period_end"]
            or observed.tzinfo is None
            or not observed <= min(acquired_at or datetime.now(UTC), datetime.now(UTC))
            or start.year != end.year
            or set(value["native_sources"]) != {"holidays", "hours"}
        ):
            raise ValueError("india_calendar_coverage_or_time")
        texts = {}
        import pdfplumber

        for kind, source in value["native_sources"].items():
            fields = {"path", "sha256", "publisher", "notice", "source_url", "published_on"}
            if kind == "hours":
                fields.add("effective_from")
            if set(source) != fields:
                raise ValueError("india_native_fields")
            published = date.fromisoformat(source["published_on"])
            uri = urlsplit(source["source_url"])
            if (
                source["publisher"] != "BSE Limited"
                or not re.fullmatch(r"20[0-9]{6}-[0-9]{1,5}", source["notice"])
                or published.strftime("%Y%m%d") != source["notice"].split("-")[0]
                or published > min(observed.date(), cutoff.date())
                or uri.scheme != "https"
                or uri.username
                or uri.password
                or uri.hostname
                not in (
                    {"www.bseindia.com", "www.steelcitynettrade.com"}
                    if kind == "holidays"
                    else {"www.bseindia.com"}
                )
                or not _HASH.fullmatch(str(source["sha256"]))
            ):
                raise ValueError("india_native_identity")
            payload = _resource(run_root, manifest, source["path"], immutable=True)
            if (
                len(payload) > 8 * 1024 * 1024
                or hashlib.sha256(payload).hexdigest() != source["sha256"]
                or not payload.startswith(b"%PDF-")
            ):
                raise ValueError("india_native_hash")
            try:
                with pdfplumber.open(io.BytesIO(payload)) as pdf:
                    if not 1 <= len(pdf.pages) <= 40:
                        raise ValueError("india_native_pages")
                    pages = [
                        page.extract_text(layout=kind == "holidays") or "" for page in pdf.pages
                    ]
                    # Retain native holiday paragraph gaps; without layout text,
                    # a detached timings reference could inherit a prior date.
                    text = "\n".join(pages)
                    if kind == "holidays":
                        text = "\n".join(
                            re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()
                        )
            except Exception as exc:  # Native PDF parser errors remain an explicit failure.
                raise ValueError("india_native_pdf_invalid") from exc
            if (
                len(text) > 512 * 1024
                or not re.search(r"\bBSE\s+(?:Limited|Ltd\.?)(?:\b|,)", text)
                or not re.search(rf"(?<![0-9]){re.escape(source['notice'])}(?![0-9])", text)
                or source["published_on"] not in _bse_native_dates(text)
            ):
                raise ValueError("india_native_text_identity")
            texts[kind] = text
        if not re.search(
            rf"Trading Holidays.*(?:Calendar )?Year {start.year}.*Equity",
            texts["holidays"],
            re.IGNORECASE,
        ):
            raise ValueError("india_holiday_scope")
        holidays = _bse_native_dates(texts["holidays"])
        for special in re.finditer(
            r"\b(?:Muhurat|special\s+trading|Trading\s+(?:may|will|shall)\s+be\s+conducted)\b",
            texts["holidays"],
            re.IGNORECASE,
        ):
            # PDF line wraps may split the marker, month, day or year. Keep
            # only its bounded sentence so another table/publication date
            # cannot silently become this special session's date.
            context = texts["holidays"][special.start() : special.end() + 512].split(".", 1)[0]
            context = re.sub(r"\s+", " ", context)
            special_dates = _bse_native_dates(context)
            if not special_dates:
                # The exact pure timings reference may inherit only its
                # immediately preceding dated Muhurat announcement, in the
                # same native paragraph and within 512 characters in total.
                prefix = texts["holidays"][: special.start()]
                timings = re.search(r"Timings\s+of\s+$", prefix)
                reference = re.match(
                    r"Muhurat\s+Trading\s+shall\s+be\s+notified\s+subsequently\.",
                    texts["holidays"][special.start() :],
                )
                if timings and reference:
                    before = prefix[: timings.start()]
                    candidates = list(
                        re.finditer(
                            r"\bMuhurat\s+Trading\s+(?:may|will|shall)\s+be\s+conducted\b",
                            before,
                            re.IGNORECASE,
                        )
                    )
                    if candidates:
                        announcement = before[candidates[-1].start() :]
                        total_length = special.start() + reference.end() - candidates[-1].start()
                        stripped = announcement.rstrip()
                        if (
                            total_length <= 512
                            and stripped.endswith(".")
                            and "." not in stripped[:-1]
                            and not re.search(r"\n\s*\n", announcement)
                        ):
                            special_dates = _bse_native_dates(re.sub(r"\s+", " ", stripped))
            if not special_dates or any(
                start.isoformat() <= day <= end.isoformat() for day in special_dates
            ):
                raise ValueError("india_special_session_unverified")
        # This reviewed notice ends the full session at 16:00, independently of
        # the CAS pricing instant and Wind's unchanged SENSEX.BO close field.
        hours = value["native_sources"]["hours"]
        if (
            hours["notice"] != "20260610-41"
            or hours["source_url"]
            != "https://www.bseindia.com/downloads/UploadDocs/Notices/20260610-41/20260610-41.pdf"
            or hours["published_on"] != "2026-06-10"
            or hours["effective_from"] != "2026-08-03"
            or start < date.fromisoformat(hours["effective_from"])
            or "from Monday, August 03, 2026" not in texts["hours"]
            or not re.search(
                r"Post closing session shall be from 3:50\s*pm to 4:00\s*pm\.", texts["hours"]
            )
            or spec["close_time"] != "16:00"
        ):
            raise ValueError("india_close_unverified")
        expected = [
            (start + timedelta(days=index)).isoformat() for index in range((end - start).days + 1)
        ]
        if (
            not isinstance(value["days"], list)
            or [row["date"] for row in value["days"]] != expected
        ):
            raise ValueError("india_calendar_missing_dates")
        for row in value["days"]:
            day = date.fromisoformat(row["date"])
            reason = (
                "weekend"
                if day.weekday() >= 5
                else "holiday" if row["date"] in holidays else "regular"
            )
            close = (
                f"{day.isoformat()}T{spec['close_time']}:00+05:30" if reason == "regular" else None
            )
            if set(row) != {"date", "status", "close_at", "reason"} or row != {
                "date": day.isoformat(),
                "status": "open" if reason == "regular" else "closed",
                "close_at": close,
                "reason": reason,
            }:
                raise ValueError("india_calendar_source_disagreement")
        log.info(
            "weekly_india_exchange_calendar_verified",
            day_count=len(expected),
            native_source_count=2,
        )
        return value
    except (WorkflowError, ValueError, TypeError, KeyError, OSError) as exc:
        log.warning("weekly_india_exchange_calendar_rejected", error_type=type(exc).__name__)
        raise WorkflowError(
            "印度交易所日历来源未核实", "weekly_exchange_calendar_unverified", 409
        ) from exc


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
    from ..datahub.security import directory, read_file

    with directory(root, parts.parts[:-1]) as folder:
        raw = read_file(folder, parts.name, limit=128 * 1024 * 1024)
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
        excel_mode = (
            value.get("schema_version") in (2, 3, 4) and value.get("data_source") == "wind_excel"
        )
        expected = {
            "schema_version",
            "mapping_sha256",
            "verification",
            "calendars",
            "economic_calendar",
        }
        if excel_mode:
            expected |= {"data_source", "excel_exports"}
        if value.get("schema_version") == 4:
            expected.add("history_supplement")
        if set(value) != expected:
            raise ValueError("contract_fields")
        if (
            value.get("schema_version") not in ((2, 3, 4) if excel_mode else (1,))
            or value.get("mapping_sha256") != MAPPING_SHA256
        ):
            raise ValueError("identity")
        proof = value.get("verification", {})
        if proof.get("status") != "reviewed" or not _HASH.fullmatch(
            str(proof.get("evidence_sha256", ""))
        ):
            raise ValueError("review")
        markets = load_weekly_mapping()["calendars"]
        if set(value.get("calendars", {})) != set(markets):
            raise ValueError("calendar_coverage")
        if (
            value["schema_version"] in (3, 4)
            and value["calendars"]["IN"].get("calendar_source") != "exchange_calendar"
        ):
            raise ValueError("india_calendar_missing")
        for market, calendar in value["calendars"].items():
            if calendar.get("calendar_source") == "exchange_calendar":
                if value["schema_version"] not in (3, 4) or not excel_mode:
                    raise ValueError("india_calendar_schema")
                _india_calendar_identity(calendar, market)
                evidence = _resource(run_root, manifest, calendar["evidence_path"], immutable=True)
                if hashlib.sha256(evidence).hexdigest() != calendar["evidence_sha256"]:
                    raise ValueError("india_calendar_hash")
                continue
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
        if excel_mode:
            if value["schema_version"] == 4:
                supplement = value["history_supplement"]
                if set(supplement) != {"path", "sha256"} or not _HASH.fullmatch(
                    str(supplement["sha256"])
                ):
                    raise ValueError("gold_supplement_identity")
                payload = _resource(run_root, manifest, supplement["path"], immutable=True)
                if (
                    len(payload) > 2 * 1024 * 1024
                    or hashlib.sha256(payload).hexdigest() != supplement["sha256"]
                ):
                    raise ValueError("gold_supplement_hash")
            reviewed = _resource(run_root, manifest, proof["evidence_path"], immutable=True)
            if hashlib.sha256(reviewed).hexdigest() != proof["evidence_sha256"]:
                raise ValueError("review_resource_hash")
            economic = value.get("economic_calendar", {})
            if (
                set(economic) != {"method", "importance_values"}
                or economic.get("method") != "wind_excel_export"
            ):
                raise ValueError("economic_method")
            if economic["importance_values"] != {"重要": "重要", "中等": "较重要", "低": "一般"}:
                raise ValueError("economic_importance_mapping")
            exports = value.get("excel_exports", {})
            if set(exports) != {"edb", "economic_calendar"}:
                raise ValueError("excel_export_coverage")
            for kind, export in exports.items():
                fields = {"path", "sha256", "exported_at", "sheet"}
                if kind == "economic_calendar":
                    fields |= {
                        "coverage_start",
                        "coverage_end",
                        "coverage_evidence_path",
                        "coverage_evidence_sha256",
                        "observation_path",
                        "observation_sha256",
                    }
                if kind == "economic_calendar" and "additional_sheets" in export:
                    fields.add("additional_sheets")
                    sheets = export["additional_sheets"]
                    if (
                        not isinstance(sheets, list)
                        or len(sheets) > 4
                        or any(not isinstance(item, str) or not item for item in sheets)
                        or len(set(sheets)) != len(sheets)
                        or export.get("sheet") in sheets
                    ):
                        raise ValueError("excel_export_sheets")
                if set(export) != fields or not _HASH.fullmatch(str(export.get("sha256", ""))):
                    raise ValueError("excel_export_fields")
                moment = datetime.fromisoformat(export["exported_at"])
                if (
                    moment.tzinfo is None
                    or not isinstance(export["sheet"], str)
                    or not export["sheet"]
                ):
                    raise ValueError("excel_export_metadata")
                payload = _resource(run_root, manifest, export["path"], immutable=True)
                if hashlib.sha256(payload).hexdigest() != export["sha256"]:
                    raise ValueError("excel_export_hash")
                if kind == "economic_calendar":
                    date.fromisoformat(export["coverage_start"])
                    date.fromisoformat(export["coverage_end"])
                    proof = _resource(
                        run_root, manifest, export["coverage_evidence_path"], immutable=True
                    )
                    if hashlib.sha256(proof).hexdigest() != export["coverage_evidence_sha256"]:
                        raise ValueError("excel_coverage_hash")
                    observation = _resource(
                        run_root, manifest, export["observation_path"], immutable=True
                    )
                    if hashlib.sha256(observation).hexdigest() != export["observation_sha256"]:
                        raise ValueError("excel_observation_hash")
        else:
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


def _gold_formula(start, end):
    return f'=wsd("SPTAUUSDOZ.IDC","close","{start}","{end}","Period=D","PriceAdj=U","Days=Trading","Fill=Blank","TradingCalendar=IDC")'


def _gold_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("gold_number_type")
    number = Decimal(str(value))
    if not number.is_finite() or number <= 0:
        raise ValueError("gold_number_invalid")
    return number


def _gold_day(value):
    if isinstance(value, datetime):
        if value.time() != datetime.min.time() or value.tzinfo is not None:
            raise ValueError("gold_date_time")
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or not re.fullmatch(
        r"20[0-9]{2}-[0-9]{2}-[0-9]{2}(?: 00:00:00)?", value
    ):
        raise ValueError("gold_date_invalid")
    return date.fromisoformat(value[:10]).isoformat()


def read_gold_history_supplement(run_root, manifest, source, contract, completed):
    """Replay frozen native responses; repair exactly one empty EDB cell, read-only."""
    from ..datahub.providers_wind_excel_weekly import _sheet_rows, _workbook

    try:
        if source.get("schema_version") != 4 or source.get("data_source") != "wind_excel":
            raise ValueError("gold_schema")
        binding = source["history_supplement"]
        raw = _resource(run_root, manifest, binding["path"], immutable=True)
        if len(raw) > 2 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != binding["sha256"]:
            raise ValueError("gold_resource_hash")
        proof = json.loads(raw)
        identity = {
            "schema_version": 1,
            "source": "wind_excel",
            "series_id": "history_gold_london",
            "unit": "USD/ounce",
            "currency": "USD",
            "period_end": "2026-10-23",
            "coverage_start": "2017-01-01",
            "coverage_end": "2026-10-22",
        }
        if set(proof) != set(identity) | {
            "original_edb_sha256",
            "observed_at",
            "history_requests",
            "calendar_requests",
            "recheck",
        } or any(proof[key] != item for key, item in identity.items()):
            raise ValueError("gold_identity")
        observed = datetime.fromisoformat(proof["observed_at"])
        if (
            contract["period_end"] != proof["period_end"]
            or observed.tzinfo is None
            or observed > datetime.now(UTC)
        ):
            raise ValueError("gold_period_or_time")
        calendar = source["calendars"]["LONDON_GOLD"]
        if calendar.get("wind_calendar") != "IDC" or calendar.get("semantics_verified") is not True:
            raise ValueError("gold_calendar_identity")
        native_dates, prices = [], {}
        for kind, end in (("calendar", proof["coverage_end"]), ("history", proof["coverage_end"])):
            requests = proof[kind + "_requests"]
            if not isinstance(requests, list) or len(requests) != 10:
                raise ValueError("gold_request_count")
            cursor, last = date(2017, 1, 1), date.fromisoformat(end)
            for request in requests:
                finish = min(cursor + timedelta(days=365), last)
                start, stop = cursor.isoformat(), finish.isoformat()
                field = "raw_rows"
                formula = (
                    f'=tdays("{start}","{stop}","TradingCalendar=IDC")'
                    if kind == "calendar"
                    else _gold_formula(start, stop)
                )
                if set(request) != {"formula", field} or request["formula"] != formula:
                    raise ValueError("gold_request_identity")
                rows = request[field]
                if not isinstance(rows, list) or not rows or len(rows) > 1000:
                    raise ValueError("gold_response_shape")
                chunk = []
                for row in rows:
                    if not isinstance(row, list) or len(row) != (1 if kind == "calendar" else 2):
                        raise ValueError("gold_response_shape")
                    day = _gold_day(row[0])
                    if not start <= day <= stop:
                        raise ValueError("gold_response_range")
                    chunk.append(day)
                    if kind == "history":
                        if day in prices:
                            raise ValueError("gold_duplicate_date")
                        prices[day] = _gold_number(row[1])
                if chunk != sorted(set(chunk)):
                    raise ValueError("gold_response_order")
                if kind == "calendar":
                    native_dates.extend(chunk)
                cursor = finish + timedelta(days=1)
            if cursor != last + timedelta(days=1):
                raise ValueError("gold_request_coverage")
        cutoff = datetime.fromisoformat(contract["cutoff"])
        native_completed = []
        for day in native_dates:
            supplied = calendar.get("session_closes", {}).get(day)
            if supplied is None:
                close_time = calendar.get("session_overrides", {}).get(day, calendar["close_time"])
                supplied = datetime.combine(
                    date.fromisoformat(day) + timedelta(days=calendar.get("close_day_offset", 0)),
                    datetime.strptime(close_time, "%H:%M").time(),
                    ZoneInfo(calendar["timezone"]),
                ).isoformat()
            close = datetime.fromisoformat(supplied)
            if close.tzinfo is None:
                raise ValueError("gold_close_unknown")
            if close <= cutoff:
                native_completed.append(day)
        if (
            native_completed != completed
            or not completed
            or completed[-1] != "2026-10-22"
            or list(prices) != completed
        ):
            raise ValueError("gold_calendar_coverage")
        recheck = proof["recheck"]
        if (
            set(recheck) != {"formula", "rows"}
            or recheck["formula"] != _gold_formula("2017-01-30", "2017-01-30")
            or not isinstance(recheck["rows"], list)
            or len(recheck["rows"]) != 1
        ):
            raise ValueError("gold_recheck_identity")
        row = recheck["rows"][0]
        if (
            not isinstance(row, list)
            or len(row) != 2
            or _gold_day(row[0]) != "2017-01-30"
            or _gold_number(row[1]) != prices["2017-01-30"]
        ):
            raise ValueError("gold_recheck_value")
        export = source["excel_exports"]["edb"]
        edb = _resource(run_root, manifest, export["path"], immutable=True)
        if (
            hashlib.sha256(edb).hexdigest() != export["sha256"]
            or export["sha256"] != proof["original_edb_sha256"]
        ):
            raise ValueError("gold_edb_hash")
        book = _workbook(edb)
        try:
            with ZipFile(io.BytesIO(edb)) as package:
                for name in package.namelist():
                    if (
                        name.startswith("xl/worksheets/")
                        and name.endswith(".xml")
                        and any(
                            node.tag.rsplit("}", 1)[-1] == "f"
                            for node in ElementTree.fromstring(package.read(name)).iter()
                        )
                    ):
                        raise ValueError("gold_edb_formula")
            rows = _sheet_rows(book, export["sheet"])
        finally:
            book.close()
        if len(rows) < 9 or rows[4][0] != "指标ID" or rows[3][0] != "单位":
            raise ValueError("gold_edb_metadata")
        columns = [index for index, value in enumerate(rows[4]) if value == "S0270980"]
        if len(columns) != 1 or rows[3][columns[0]] not in {"USD/盎司", "美元/盎司"}:
            raise ValueError("gold_edb_identity")
        values, missing, seen = {}, [], set()
        for row_index, row in enumerate(rows[8:], start=8):
            if not row or row[0] is None:
                continue
            if (
                row[0] == "数据来源：Wind"
                and row_index == len(rows) - 1
                and all(cell is None for cell in row[1:])
            ):
                continue
            day = _gold_day(row[0])
            if not "2017-01-01" <= day <= contract["period_end"]:
                continue
            if day in seen:
                raise ValueError("gold_edb_duplicate")
            seen.add(day)
            value = row[columns[0]] if columns[0] < len(row) else None
            if isinstance(value, bool):
                raise TypeError("gold_edb_bool")
            if day > completed[-1]:
                if value not in (None, "", 0):
                    raise ValueError("gold_edb_unclosed_observation")
                continue
            if value in (None, "", 0):
                if day in prices:
                    missing.append(day)
                continue
            values[day] = _gold_number(value)
        if (
            missing != ["2017-01-30"]
            or any(day not in values for day in completed if day != "2017-01-30")
            or any(values[day] != prices[day] for day in values.keys() & prices.keys())
        ):
            raise ValueError("gold_edb_overlap_or_missing")
        values["2017-01-30"] = prices["2017-01-30"]
        lineage = {
            "series_id": "history_gold_london",
            "date": "2017-01-30",
            "original_edb_sha256": export["sha256"],
            "supplement_path": binding["path"],
            "supplement_sha256": binding["sha256"],
            "overlap_count": len(prices) - 1,
            "value": format(prices["2017-01-30"], "f"),
        }
        log.info(
            "weekly_gold_history_supplement_verified",
            overlap_count=lineage["overlap_count"],
            supplement_sha256=binding["sha256"],
        )
        return [(day, float(value)) for day, value in sorted(values.items())], lineage
    except Exception as exc:  # Native workbook/JSON parser failures cannot authorize a repair.
        log.warning(
            "weekly_gold_history_supplement_rejected",
            error_type=type(exc).__name__,
            reason=(
                str(exc)
                if isinstance(exc, (ValueError, TypeError))
                and re.fullmatch(r"gold_[a-z_]+", str(exc))
                else "native_resource_invalid"
            ),
        )
        raise WorkflowError(
            "黄金历史补查证据未核实", "weekly_gold_supplement_unverified", 409
        ) from exc


def verify_weekly_history_supplement(snapshot, contract, *, run_root=None, manifest=None):
    """Host replays version resources even if a forged snapshot drops its lineage."""
    declared = any("history_supplement" in item for item in snapshot.get("series", {}).values())
    if run_root is None or manifest is None:
        if declared:
            raise ValueError("weekly_gold_supplement_unverified")
        return
    manifest_value = (
        manifest.model_dump(mode="json") if hasattr(manifest, "model_dump") else manifest
    )
    if not any(item.get("path") == SOURCE_CONTRACT for item in manifest_value.get("resources", [])):
        if declared:
            raise ValueError("weekly_gold_supplement_unverified")
        return
    try:
        raw = _resource(run_root, manifest, SOURCE_CONTRACT, immutable=True)
        version = json.loads(raw).get("schema_version")
        if version != 4:
            if declared:
                raise ValueError("gold_lineage_without_schema4")
            return
        source, _ = load_run_source_contract(run_root, manifest)
    except (WorkflowError, ValueError, TypeError, AttributeError) as exc:
        log.warning("weekly_gold_source_replay_rejected", error_type=type(exc).__name__)
        raise ValueError("weekly_gold_supplement_unverified") from exc
    try:
        rows, lineage = read_gold_history_supplement(
            run_root,
            manifest,
            source,
            contract,
            snapshot["calendars"]["LONDON_GOLD"]["completed_dates"],
        )
        item = snapshot["series"]["history_gold_london"]
        expected = [{"date": day, "value": value, "published_at": None} for day, value in rows]
        if (
            snapshot.get("source") != "wind_excel"
            or item.get("source") != "wind_excel"
            or item.get("rows") != expected
            or item.get("history_supplement") != lineage
            or item.get("raw_sha256") != lineage["original_edb_sha256"]
            or item.get("raw_payload") != {"export": source["excel_exports"]["edb"], "column": 1}
            or any(
                "history_supplement" in other
                for key, other in snapshot["series"].items()
                if key != "history_gold_london"
            )
        ):
            raise ValueError("gold_snapshot_changed")
    except (WorkflowError, ValueError, TypeError, KeyError) as exc:
        log.warning("weekly_gold_snapshot_replay_rejected", error_type=type(exc).__name__)
        raise ValueError("weekly_gold_supplement_unverified") from exc


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
