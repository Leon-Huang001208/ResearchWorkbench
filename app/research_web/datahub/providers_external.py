"""Bounded, cancellable reads of named endpoints from the external-source inventory."""

import asyncio
import csv
import hashlib
import hmac
import io
import json
import math
import re
import time
from datetime import UTC, datetime
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree

import httpx

from core.observability import get_logger

from .contracts import BusinessQuery
from .external_sources import (
    EXTERNAL_SOURCES,
    credential_transport_blocked,
    inventory_rows,
    readable_endpoints,
)
from .providers import DEADLINE, MAX_RESPONSE_BYTES, MAX_ROWS, ProviderError, Result

log = get_logger(__name__)
OFFICIAL_NUMERIC_CONTRACT = "official-numeric-v2"
EXTERNAL_ENVELOPE_CONTRACT = "external-envelope-v1"
SPDR_NUMERIC_CONTRACT = "spdr-gld-trust-snapshot-v1"
SPDR_METRIC_UNITS = {
    "total_nav_usd": "USD",
    "total_tonnes": "tonnes",
    "total_ounces": "ounces",
    "shares_outstanding": "shares",
}
_SPDR_MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        start=1,
    )
}
EXTERNAL_ENVELOPES = frozenset(
    {
        ("ext_nasdaq", "history"),
        ("ext_cls", "hot-list"),
        ("ext_danjuan", "history"),
        ("ext_kapsarc", "production"),
    }
)
OFFICIAL_NUMERIC = frozenset(
    {("ext_worldbank", "inflation"), ("ext_nyfed", "rates"), ("ext_treasury", "cash")}
)
_CASH_FIELDS = ("close_today_bal", "open_today_bal", "open_month_bal", "open_fiscal_year_bal")
_RATE_PERCENT_FIELDS = frozenset(
    {
        "percentRate",
        "percentPercentile1",
        "percentPercentile25",
        "percentPercentile75",
        "percentPercentile99",
        "targetRateFrom",
        "targetRateTo",
        "intraDayLow",
        "intraDayHigh",
        "standardDeviation",
    }
)
_PRIVATE_KEYS = re.compile(
    r"(?:password|secret|token|api_?key|registration_?key|authorization|cookie|headers?|url|host|proxy|redirect|callback|path|module|sql)",
    re.IGNORECASE,
)


def arguments(value: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError):
        raise ProviderError("external_arguments_invalid") from None
    if not isinstance(parsed, dict) or set(parsed) - {"params", "query", "body"}:
        raise ProviderError("external_arguments_invalid")

    def validate(item: Any, depth: int = 0) -> None:
        if depth > 8:
            raise ProviderError("external_arguments_invalid")
        if isinstance(item, dict):
            if len(item) > 50 or any(_PRIVATE_KEYS.search(key) for key in item):
                raise ProviderError("external_arguments_forbidden")
            for child in item.values():
                validate(child, depth + 1)
        elif isinstance(item, list):
            if len(item) > 100:
                raise ProviderError("external_arguments_invalid")
            for child in item:
                validate(child, depth + 1)
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ProviderError("external_arguments_invalid")

    validate(parsed)
    for key in ("params", "query", "body"):
        if key in parsed and not isinstance(parsed[key], dict):
            raise ProviderError("external_arguments_invalid")
    return parsed


def spdr_projection(raw: bytes) -> list[dict[str, Any]]:
    """Validate four source metrics; preserve source strings and each reference date."""
    try:
        body = json.loads(raw)
        if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
            raise TypeError("invalid_envelope")
        if (
            body.get("success") is False
            or body.get("error")
            or any(
                body.get(key) not in (None, 0, "0")
                for key in ("errorcode", "error_code", "errcode")
            )
            or body.get("code") not in (None, 0, "0", 200, "200")
        ):
            raise ValueError("error_envelope")
        rows = []
        for metric, unit in SPDR_METRIC_UNITS.items():
            item = body["data"][metric]
            source_value, source_date = item["value"], item["date"]
            if (
                not isinstance(source_value, str)
                or not 1 <= len(source_value) <= 128
                or not isinstance(source_date, str)
                or not 1 <= len(source_date) <= 64
            ):
                raise ValueError("invalid_metric_text")
            number_text = source_value
            if metric == "total_nav_usd":
                match = re.fullmatch(r"US\$ ?(.+)", source_value)
                if match is None:
                    raise ValueError("invalid_currency")
                number_text = match[1]
            grammar = r"(?:0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+)"
            if metric != "shares_outstanding":
                grammar += r"(?:\.[0-9]+)?"
            if re.fullmatch(grammar, number_text) is None:
                raise ValueError("invalid_number")
            exact = number_text.replace(",", "")
            numeric = int(exact) if metric == "shares_outstanding" else float(Decimal(exact))
            if not math.isfinite(numeric):
                raise ValueError("nonfinite_number")
            match = re.fullmatch(r"([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})", source_date)
            if match is None:
                raise ValueError("invalid_reference_date")
            reference_date = (
                datetime(int(match[3]), _SPDR_MONTHS[match[1]], int(match[2])).date().isoformat()
            )
            rows.append(
                {
                    "metric": metric,
                    "value": numeric,
                    "value_decimal": exact,
                    "source_value": source_value,
                    "reference_date": reference_date,
                    "source_reference_date": source_date,
                    "unit": unit,
                    "currency": "USD" if metric == "total_nav_usd" else None,
                }
            )
        return rows
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError, RecursionError):
        log.warning("spdr_numeric_envelope_invalid", source="ext_spdr", dataset="gld")
        raise ProviderError("spdr_numeric_schema_invalid") from None


def spdr_fields() -> dict[str, dict[str, str]]:
    """Fresh field metadata for the bounded source-native projection."""
    return {
        "metric": {"type": "string", "unit": "source_metric"},
        "value": {"type": "number", "unit": "per_row"},
        "value_decimal": {"type": "string", "unit": "per_row", "role": "exact_decimal"},
        "source_value": {"type": "string", "unit": "per_row", "role": "source_original"},
        "reference_date": {
            "type": "date",
            "unit": "date",
            "role": "reference_period_not_available_at",
        },
        "source_reference_date": {"type": "string", "unit": "date", "role": "source_original"},
        "unit": {"type": "string", "unit": "source_unit"},
        "currency": {"type": "string", "unit": "source_currency"},
    }


def endpoint_request(
    source_id: str, dataset: str, args: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    endpoint = next((ep for ep in readable_endpoints(source_id) if ep["id"] == dataset), None)
    if endpoint is None:
        raise ProviderError("external_dataset_unknown")
    params = args.get("params", {})
    names = set(re.findall(r"\{(\w+)\}", endpoint["url"]))
    if set(params) != names:
        raise ProviderError("external_parameters_mismatch")
    url = endpoint["url"]
    for name, value in params.items():
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ProviderError("external_parameters_invalid")
        text = str(value)
        if len(text) > 500 or any(ord(c) < 32 for c in text):
            raise ProviderError("external_parameters_invalid")
        if "{" + name + "}" in endpoint["url"].split("?", 1)[0] and (
            text in {".", ".."} or "/" in text or "\\" in text or "%" in text
        ):
            raise ProviderError("external_parameters_invalid")
        url = url.replace("{" + name + "}", quote(text, safe=""))
    original, rendered = urlsplit(endpoint["url"]), urlsplit(url)
    if original.netloc != rendered.netloc or rendered.username or rendered.fragment:
        raise ProviderError("external_destination_invalid")
    query = args.get("query", {})
    if any(not isinstance(value, (str, int, float, bool)) for value in query.values()):
        raise ProviderError("external_parameters_invalid")
    if endpoint["method"] == "GET" and args.get("body"):
        raise ProviderError("external_body_not_allowed")
    return endpoint, url


def _day(value):
    if (
        not isinstance(value, str)
        or datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") != value
    ):
        raise ValueError("invalid_date")
    return value


def _positive(value):
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]*", str(value)):
        raise ValueError("invalid_page")
    return int(value)


def _nonnegative(value):
    if isinstance(value, bool) or not re.fullmatch(r"0|[1-9][0-9]*", str(value)):
        raise ValueError("invalid_count")
    return int(value)


def official_numeric_request(source, dataset, args):
    """Validate only reviewed filter syntax; never fetch additional pages implicitly."""
    if (source, dataset) not in OFFICIAL_NUMERIC:
        return
    try:
        filters = args.get("query", {})
        allowed = (
            {"date", "page", "per_page", "format"}
            if source == "ext_worldbank"
            else (
                {"filter", "page[size]", "page[number]", "format"}
                if source == "ext_treasury"
                else set()
            )
        )
        if filters.keys() - allowed or args.get("body"):
            raise ValueError("unsupported_filter")
        if filters.get("format", "json") != "json":
            raise ValueError("invalid_format")
        for key in ("page", "per_page", "page[size]", "page[number]"):
            if key in filters:
                _positive(filters[key])
        if source == "ext_worldbank" and "date" in filters:
            years = str(filters["date"]).split(":")
            if (
                len(years) not in {1, 2}
                or any(re.fullmatch(r"[0-9]{4}", year) is None for year in years)
                or years[0] > years[-1]
            ):
                raise ValueError("invalid_year_range")
        if source == "ext_nyfed":
            start, end = (args["params"][key] for key in ("start", "end"))
            if _day(start) > _day(end):
                raise ValueError("invalid_date_range")
        if source == "ext_treasury" and "filter" in filters:
            lower, upper = [], []
            for clause in str(filters["filter"]).split(","):
                field, operation, value = clause.split(":")
                if field != "record_date" or operation not in {"eq", "gte", "lte"}:
                    raise ValueError("unsupported_filter")
                _day(value)
                if operation in {"eq", "gte"}:
                    lower.append(value)
                if operation in {"eq", "lte"}:
                    upper.append(value)
            if lower and upper and max(lower) > min(upper):
                raise ValueError("invalid_date_range")
    except (ValueError, TypeError, KeyError):
        log.warning("external_numeric_request_invalid", source=source, dataset=dataset)
        raise ProviderError("external_numeric_request_invalid") from None


def _number(value):
    if value is None or value == "null":
        return False
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TypeError("invalid_numeric")
    if not math.isfinite(float(value)):
        raise ValueError("invalid_numeric")
    return True


def _official_rows(source, body, args):
    filters = args.get("query", {})
    if source == "ext_worldbank":
        if not isinstance(body, list) or len(body) != 2 or not isinstance(body[0], dict):
            raise ValueError("invalid_worldbank")
        header, rows = body
        page = _positive(header["page"])
        pages, total = _nonnegative(header["pages"]), _nonnegative(header["total"])
        size = _positive(header["per_page"])
        if page != _positive(filters.get("page", 1)) or size != _positive(
            filters.get("per_page", 100)
        ):
            raise ValueError("pagination_identity_mismatch")
        if rows is None and total == 0:
            rows = []
        if (
            not isinstance(rows, list)
            or total < 0
            or pages != (total + size - 1) // size
            or page > max(1, pages)
            or len(rows) != max(0, min(size, total - (page - 1) * size))
        ):
            raise ValueError("pagination_inconsistent")
        seen = set()
        for row in rows:
            year = row["date"]
            if (
                row["indicator"]["id"] != "FP.CPI.TOTL.ZG"
                or row["countryiso3code"] != "WLD"
                or row["country"]["id"] != "1W"
                or not isinstance(year, str)
                or re.fullmatch(r"[0-9]{4}", year) is None
                or year in seen
            ):
                raise ValueError("observation_identity_mismatch")
            years = str(filters.get("date", year)).split(":")
            if not years[0] <= year <= years[-1]:
                raise ValueError("date_filter_mismatch")
            _number(row["value"])
            seen.add(year)
        return rows, total, pages <= 1
    if source == "ext_nyfed":
        if (
            not isinstance(body, dict)
            or set(body) != {"refRates"}
            or not isinstance(body["refRates"], list)
        ):
            raise ValueError("invalid_nyfed")
        rows, seen = body["refRates"], set()
        for row in rows:
            day, kind = _day(row["effectiveDate"]), row["type"]
            if (
                kind not in {"EFFR", "OBFR", "TGCR", "BGCR", "SOFR", "SOFRAI"}
                or not args["params"]["start"] <= day <= args["params"]["end"]
                or (day, kind) in seen
            ):
                raise ValueError("rate_identity_mismatch")
            for field in (
                ("average30day", "average90day", "average180day", "index")
                if kind == "SOFRAI"
                else ("percentRate", "volumeInBillions")
            ):
                _number(row[field])
            for field in _RATE_PERCENT_FIELDS & row.keys():
                _number(row[field])
            seen.add((day, kind))
        return rows, len(rows), True
    if (
        not isinstance(body, dict)
        or not {"data", "meta", "links"} <= body.keys()
        or not isinstance(body["data"], list)
    ):
        raise ValueError("invalid_treasury")
    rows, meta, links = body["data"], body["meta"], body["links"]
    count, total, pages = (
        _nonnegative(meta[key]) for key in ("count", "total-count", "total-pages")
    )
    size, page = _positive(filters.get("page[size]", 20)), _positive(filters.get("page[number]", 1))
    if (
        count != len(rows)
        or total < 0
        or pages != (total + size - 1) // size
        or page > max(1, pages)
        or count != max(0, min(size, total - (page - 1) * size))
        or bool(links.get("next")) != (page < pages)
        or bool(links.get("prev")) != (page > 1)
    ):
        raise ValueError("pagination_inconsistent")
    seen = set()
    for row in rows:
        day = _day(row["record_date"])
        key = (day, row["account_type"], row["src_line_nbr"])
        if (
            row["table_nbr"] != "I"
            or row["table_nm"] != "Operating Cash Balance"
            or not row["account_type"]
            or key in seen
        ):
            raise ValueError("cash_identity_mismatch")
        for clause in str(filters.get("filter", "")).split(","):
            if clause:
                _, operation, expected = clause.split(":")
                if not {"eq": day == expected, "gte": day >= expected, "lte": day <= expected}[
                    operation
                ]:
                    raise ValueError("date_filter_mismatch")
        for field in _CASH_FIELDS:
            if (
                meta["dataTypes"][field] != "CURRENCY0"
                or meta["dataFormats"][field] != "$1,000,000"
            ):
                raise ValueError("cash_unit_mismatch")
            _number(row[field])
        seen.add(key)
    return rows, total, pages <= 1


def _quantapi_history_body(args: dict[str, Any]) -> dict[str, Any]:
    """Wrap only the documented history contract, before reading credentials."""
    reason = "quantapi_history_contract_invalid"
    body = args.get("body", {})
    if args.get("query") or ("reqBody" in body and set(body) != {"reqBody"}):
        raise ProviderError(reason)
    payload = body.get("reqBody") if "reqBody" in body else body
    required = {"codes", "indicators", "startdate", "enddate"}
    if (
        not isinstance(payload, dict)
        or not required <= payload.keys()
        or payload.keys() - required - {"functionpara"}
    ):
        raise ProviderError(reason)
    for key in required:
        value = payload[key]
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= (10 if key.endswith("date") else 4096)
            or any(char.isspace() or ord(char) < 32 for char in value)
            or any(not part for part in value.split(","))
        ):
            raise ProviderError(reason)
        if key in {"codes", "indicators"}:
            pattern = r"[A-Za-z0-9._-]+" if key == "codes" else r"[A-Za-z0-9_]+"
            if any(re.fullmatch(pattern, part) is None for part in value.split(",")):
                raise ProviderError(reason)
    dates = []
    for key in ("startdate", "enddate"):
        value = payload[key]
        pattern = "%Y-%m-%d" if "-" in value else "%Y/%m/%d" if "/" in value else "%Y%m%d"
        try:
            day = datetime.strptime(value, pattern)
        except ValueError:
            raise ProviderError(reason) from None
        if day.strftime(pattern) != value:
            raise ProviderError(reason)
        dates.append(day)
    if dates[0] > dates[1]:
        raise ProviderError(reason)
    options = payload.get("functionpara", {})
    enums = {
        "Interval": {"D", "W", "M", "Q", "S", "Y"},
        "SampleInterval": {"D", "W", "M", "Q", "S", "Y"},
        "CPS": {"1", "2"},
        "PriceType": {"1", "2"},
        "Currency": {"RMB", "MHB", "GHB", "YSHB"},
    }
    if (
        not isinstance(options, dict)
        or options.keys() - enums.keys() - {"Fill", "BaseDate"}
        or {"Interval", "SampleInterval"} <= options.keys()
    ):
        raise ProviderError(reason)
    for key, value in options.items():
        if key in enums:
            if not isinstance(value, str) or value not in enums[key]:
                raise ProviderError(reason)
        elif key == "BaseDate":
            try:
                if (
                    not isinstance(value, str)
                    or datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") != value
                ):
                    raise ValueError
            except ValueError:
                raise ProviderError(reason) from None
        elif not isinstance(value, str) or value not in {"Previous", "Blank", "Omit"}:
            try:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (str, int, float))
                    or not math.isfinite(float(value))
                ):
                    raise ValueError
            except (ValueError, OverflowError):
                raise ProviderError(reason) from None
    # Host safety budget, not vendor/account quota or the returned-row limit.
    cells = (
        len(payload["codes"].split(","))
        * len(payload["indicators"].split(","))
        * ((dates[1] - dates[0]).days + 1)
    )
    if cells > MAX_ROWS:
        raise ProviderError("quantapi_history_workload_limit")
    return {"reqBody": payload}


_NESTED_LIST_KEYS = (
    "refRates",
    "items",
    "data",
    "results",
    "records",
    "rows",
    "entries",
    "articles",
    "events",
    "series",
    "points",
    "values",
    "tables",
    "list",
)


def _list_payload(payload: Any) -> list[Any] | None:
    """Dict payloads with a primary list become real rows so samples stay small."""

    if not isinstance(payload, dict):
        return None
    results = payload.get("Results")
    if isinstance(results, dict) and isinstance(results.get("series"), list) and results["series"]:
        return results["series"]
    for key in _NESTED_LIST_KEYS:
        value = payload.get(key)
        if isinstance(value, list) and value:
            return value
    return None


class PageText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def response_rows(raw: bytes, content_type: str, encoding: str = "utf-8") -> list[dict[str, Any]]:
    text = raw.decode(encoding, errors="replace")
    stripped = text.lstrip()
    if "json" in content_type or stripped.startswith(("{", "[")):
        try:
            payload = json.loads(text)
        except ValueError:
            raise ProviderError("external_invalid_json") from None
        if isinstance(payload, dict):
            for key in ("errorcode", "error_code", "errcode"):
                if key in payload and payload[key] not in (0, "0", None):
                    raise ProviderError("vendor_rejected")
            if payload.get("success") is False or payload.get("error"):
                raise ProviderError("vendor_rejected")
            if "code" in payload and payload["code"] not in (0, "0", 200, "200", None):
                raise ProviderError("vendor_rejected")
            if isinstance(payload.get("chart"), dict) and payload["chart"].get("error"):
                raise ProviderError("vendor_rejected")
        list_rows = _list_payload(payload)
        if list_rows is not None:
            return [row if isinstance(row, dict) else {"value": row} for row in list_rows]
        if isinstance(payload, list):
            return [row if isinstance(row, dict) else {"value": row} for row in payload]
        return [payload if isinstance(payload, dict) else {"value": payload}]
    if "csv" in content_type or stripped.startswith(("DATE,", "observation_date,")):
        return list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
    if "xml" in content_type or stripped.startswith(("<?xml", "<rss", "<feed")):
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ProviderError("external_xml_invalid")
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            raise ProviderError("external_xml_invalid") from None
        entries = [
            item
            for item in root.iter()
            if item.tag.rsplit("}", 1)[-1] in {"item", "entry", "event"}
        ]
        return [
            {
                child.tag.rsplit("}", 1)[-1]: "".join(child.itertext()).strip() or child.get("href")
                for child in entry
            }
            for entry in entries
        ] or [{"text": text}]
    if "html" in content_type or stripped.lower().startswith(("<html", "<!doctype html")):
        parser = PageText()
        parser.feed(text)
        return [{"text": "\n".join(parser.parts), "format": "page_text"}]
    return [{"text": text, "format": "source_text"}]


def external_business_envelope(source, dataset, raw):
    """Only verified business envelopes; reference lines and error bodies are not rows."""
    selected = (source, dataset)
    if selected not in EXTERNAL_ENVELOPES:
        return None
    try:
        if selected == ("ext_kapsarc", "production"):
            records = csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";", strict=True)
            fields = ["country", "sub_commodity", "year", "production"]
            if next(records, None) != fields:
                raise ValueError("header_mismatch")
            rows = []
            identities = set()
            for parts in records:
                if not parts:
                    continue
                if (
                    len(parts) != 4
                    or not all(part.strip() for part in parts)
                    or re.fullmatch(r"[0-9]{4}", parts[2]) is None
                ):
                    raise ValueError("invalid_csv_row")
                year = int(parts[2])
                value = float(parts[3])
                identity = tuple(parts[:3])
                if (
                    not 1 <= year <= datetime.now(UTC).year
                    or not math.isfinite(value)
                    or value < 0
                    or identity in identities
                ):
                    raise ValueError("invalid_production")
                identities.add(identity)
                rows.append(dict(zip(fields, parts, strict=True)))
            return rows, len(rows), None
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise TypeError("envelope_required")
        if selected == ("ext_nasdaq", "history"):
            code = body["status"]["rCode"]
            if type(code) is not int:
                raise TypeError("invalid_status")
            if code != 200:
                raise ProviderError("vendor_rejected")
            if body.get("data") is None:
                raise ValueError("missing_business_data")
        elif selected == ("ext_cls", "hot-list"):
            code = body["errno"]
            if type(code) not in {int, str}:
                raise TypeError("invalid_status")
            if code not in {0, "0"}:
                raise ProviderError("vendor_rejected")
        else:
            code = body["result_code"]
            if type(code) not in {int, str}:
                raise TypeError("invalid_status")
            if code not in {0, "0"}:
                raise ProviderError("vendor_rejected")
            history = body["data"]["index_eva_pe_growths"]
            if not isinstance(history, list):
                raise TypeError("invalid_history")
            if not history:
                return [], 0, None
        # No successful Nasdaq/CLS/Danjuan business schema has been verified.
        log.warning("external_business_schema_unverified", source=source, dataset=dataset)
        raise ProviderError("external_business_schema_unverified")
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        UnicodeError,
        csv.Error,
        OverflowError,
    ):
        log.warning("external_business_envelope_invalid", source=source, dataset=dataset)
        raise ProviderError("external_numeric_schema_invalid") from None


def numeric_envelope(source, dataset, raw, fallback_rows, args=None):
    """Closed official envelopes; original bytes retain publication/revision limits."""
    selected = (source, dataset)
    if selected not in {
        ("ext_worldbank", "inflation"),
        ("ext_bls", "series"),
        ("ext_ths", "cmd_history_quotation"),
        *OFFICIAL_NUMERIC,
    }:
        return fallback_rows, None, None
    try:
        body = json.loads(raw)
        if selected in OFFICIAL_NUMERIC:
            return _official_rows(source, body, args or {})
        if selected == ("ext_bls", "series"):
            if not isinstance(body, dict) or body.get("status") != "REQUEST_SUCCEEDED":
                raise ValueError("invalid_bls_status")
            series = body["Results"]["series"]
            if not isinstance(series, list):
                raise ValueError("invalid_series")
            rows = []
            for item in series:
                if not isinstance(item.get("seriesID"), str) or not isinstance(
                    item.get("data"), list
                ):
                    raise TypeError("invalid_series")
                for row in item["data"]:
                    if (
                        not isinstance(row, dict)
                        or not {"year", "period", "value"} <= row.keys()
                        or "series_id" in row
                    ):
                        raise ValueError("invalid_observation")
                    rows.append({"series_id": item["seriesID"], **row})
            return rows, len(rows), True
        tables = body["tables"]
        if not isinstance(tables, list):
            raise TypeError("invalid_tables")
        rows = []
        for item in tables:
            times, fields, asset = item["time"], item["table"], item["thscode"]
            if (
                not isinstance(times, list)
                or not isinstance(fields, dict)
                or not fields
                or not isinstance(asset, str)
                or not asset
                or {"asset", "date"} & fields.keys()
                or any(not isinstance(t, str) or not t for t in times)
                or any(
                    not isinstance(values, list) or len(values) != len(times)
                    for values in fields.values()
                )
            ):
                raise ValueError("unaligned_history")
            for index, day in enumerate(times):
                rows.append(
                    {
                        "asset": asset,
                        "date": day,
                        **{key: values[index] for key, values in fields.items()},
                    }
                )
        return rows, len(rows), True
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        log.warning("external_numeric_envelope_invalid", source=source, dataset=dataset)
        raise ProviderError("external_numeric_schema_invalid") from None


def _rows_reflect_credentials(rows: Any, secrets: list[str]) -> bool:
    """Inspect decoded strings before publishing; never log credential contents."""
    sensitive = tuple(secret for secret in secrets if secret)
    if not sensitive:
        return False
    pending: list[Any] = [rows]
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            if any(secret in value for secret in sensitive):
                return True
        elif isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return False


async def bounded_response(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
) -> tuple[bytes, str, str]:
    async with client.stream(method, url, **kwargs) as response:
        if response.is_redirect:
            raise ProviderError("redirect_denied")
        if response.status_code != 200:
            raise ProviderError(f"http_{response.status_code}")
        chunks, size = [], 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ProviderError("response_size_limit")
            chunks.append(chunk)
        return (
            b"".join(chunks),
            response.headers.get("content-type", ""),
            response.encoding or "utf-8",
        )


async def _source_secret(connections: Any, source_id: str) -> str:
    if connections is None:
        raise ProviderError("blocked_config")
    try:
        secret = await asyncio.to_thread(connections.read_source_secret, source_id)
    except Exception:  # noqa: BLE001 - credential backends must fail closed without secret details.
        raise ProviderError("blocked_config") from None
    if not isinstance(secret, str) or not secret:
        raise ProviderError("blocked_config")
    return secret


def _quantapi_configuration(secret: str) -> tuple[str | None, str | None]:
    """Accept bounded opaque tokens, without exposing configuration in errors."""
    try:
        if len(secret) > 16384:
            raise ValueError
        value = secret.strip()
        config = json.loads(value) if value.startswith(("{", "[")) else {"access_token": value}
        if not isinstance(config, dict):
            raise TypeError
        tokens = []
        for key in ("access_token", "refresh_token"):
            token = config.get(key)
            if token is not None and (
                not isinstance(token, str)
                or len(token) > 4096
                or any(ord(char) < 33 or ord(char) > 126 for char in token)
            ):
                raise ValueError
            tokens.append(token or None)
        if not any(tokens):
            raise ValueError
        return tokens[0], tokens[1]
    except (TypeError, ValueError):
        raise ProviderError("vendor_auth_failed") from None


async def _quantapi_credentials(client: httpx.AsyncClient, secret: str) -> tuple[str, list[str]]:
    token, refresh = _quantapi_configuration(secret)
    sensitive = [value for value in (secret, token, refresh) if value]
    if token:
        return token, sensitive
    try:
        raw, _, _ = await bounded_response(
            client,
            "POST",
            "https://quantapi.51ifind.com/api/v1/get_access_token",
            headers={"refresh_token": refresh},
        )
        body = json.loads(raw)
        if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
            raise TypeError
        token, _ = _quantapi_configuration(
            json.dumps({"access_token": body["data"].get("access_token")})
        )
        if body.get("errorcode", 0) != 0 or not token:
            raise ValueError
        return token, [*sensitive, token]
    except (KeyError, TypeError, ValueError):
        raise ProviderError("vendor_auth_failed") from None


async def credentials(
    client: httpx.AsyncClient, source_id: str, connections: Any
) -> tuple[str, list[str]]:
    secret = await _source_secret(connections, source_id)
    if source_id != "ext_ths":
        return secret, [secret]
    return await _quantapi_credentials(client, secret)


async def verify_quantapi_authorization(connections, *, transport=None):
    """Verify existing access via metadata, or exchange a refresh-only config."""
    try:
        async with (
            asyncio.timeout(12),
            httpx.AsyncClient(
                transport=transport, timeout=8, follow_redirects=False, trust_env=False
            ) as client,
        ):
            secret = await _source_secret(connections, "ext_ths")
            access, _refresh = _quantapi_configuration(secret)
            token, sensitive = await _quantapi_credentials(client, secret)
            if access:
                raw, _, _ = await bounded_response(
                    client,
                    "GET",
                    "https://quantapi.51ifind.com/ds_service_basic/api/v1/get_limit_policy",
                    headers={"access_token": token},
                )
                policy = json.loads(raw)
                fields = {
                    "user_type",
                    "user_type_cn",
                    "qps_limit",
                    "request_data_limit",
                    "data_volume_limit",
                    "data_range_limit",
                }
                if (
                    not isinstance(policy, dict)
                    or set(policy) != fields
                    or any(
                        not isinstance(policy[key], str) or not policy[key]
                        for key in ("user_type", "user_type_cn")
                    )
                    or any(
                        not isinstance(policy[key], dict)
                        for key in fields - {"user_type", "user_type_cn"}
                    )
                    or _rows_reflect_credentials(policy, sensitive)
                ):
                    raise ProviderError("vendor_auth_failed")
    except (ProviderError, httpx.HTTPError, TimeoutError, ValueError) as exc:
        reason = (
            str(exc)
            if isinstance(exc, ProviderError)
            and str(exc) in {"blocked_config", "redirect_denied", "response_size_limit"}
            else "vendor_auth_failed"
        )
        log.warning("quantapi_authorization_failed", reason=reason)
        raise ProviderError(reason) from None
    log.info(
        "quantapi_authorization_verified", method="limit_policy" if access else "refresh_exchange"
    )
    return {
        "status": "authenticated",
        "data_permission_verified": False,
        "data_queries": 0,
        "token_rotated": False,
        "checked_at": datetime.now(UTC).isoformat(),
    }


async def cicc_request(
    client: httpx.AsyncClient, url: str, args: dict[str, Any], secret: str
) -> tuple[tuple[bytes, str, str], list[str]]:
    if urlsplit(url).scheme != "https":
        raise ProviderError("credential_transport_blocked")
    try:
        config = json.loads(secret)
        app_id, app_secret = config["app_id"], config["app_secret"]
        if (
            not isinstance(app_id, str)
            or not isinstance(app_secret, str)
            or not app_id
            or not app_secret
        ):
            raise ProviderError("blocked_config")
    except (ValueError, KeyError, TypeError):
        raise ProviderError("blocked_config") from None
    token_raw, _, _ = await bounded_response(
        client,
        "POST",
        "https://www.research.cicc.com/api/oauth2.0/accessToken",
        data={"grant_type": "client_credentials", "client_id": app_id, "client_secret": app_secret},
    )
    token_body = json.loads(token_raw)
    if not isinstance(token_body, dict) or not isinstance(token_body.get("data"), dict):
        raise ProviderError("vendor_auth_failed")
    if token_body.get("code") != 0:
        raise ProviderError("vendor_auth_failed")
    token = token_body.get("data", {}).get("accessToken")
    if not isinstance(token, str) or not token:
        raise ProviderError("vendor_auth_failed")
    body = json.dumps(args.get("body", {}))
    params = {"timestamp": str(int(time.time() * 1000))}
    signing = "\n".join(
        [
            "POST",
            "/llm/dianjing-agent/search/integration",
            "timestamp=" + params["timestamp"],
            hashlib.sha256(body.encode()).hexdigest(),
        ]
    )
    signature = hmac.new(app_secret.encode(), signing.encode(), hashlib.sha256).hexdigest()
    response = await bounded_response(
        client,
        "POST",
        url,
        params=params,
        content=body,
        headers={
            "Authorization": "Bearer " + token,
            "X-CICC-Signature": signature,
            "Content-Type": "application/json",
        },
    )
    return response, [app_secret, token]


async def fetch(
    query: BusinessQuery,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    connections: Any = None,
) -> Result:
    source_id = query.source
    result = Result(provider_id=source_id)
    try:
        dataset = query.parameters.get("dataset", "catalog")
        if dataset == "catalog":
            result.rows = inventory_rows(source_id)
            result.status = "snapshot"
            result.limitations = ["目录信息不代表实时取数验证。"]
            return result
        if source_id not in EXTERNAL_SOURCES:
            raise ProviderError("external_source_required")
        args = arguments(query.parameters.get("arguments_json"))
        if (source_id, dataset) == ("ext_spdr", "gld"):
            if query.as_of is not None or query.purpose == "backtest" or query.required_semantics:
                log.warning("spdr_request_rejected", reason="historical_semantics_unsupported")
                raise ProviderError("spdr_historical_semantics_unsupported")
            if args:
                log.warning("spdr_request_rejected", reason="arguments_unsupported")
                raise ProviderError("spdr_arguments_unsupported")
        endpoint, url = endpoint_request(source_id, dataset, args)
        official_numeric_request(source_id, dataset, args)
        if (source_id, dataset) == ("ext_ths", "cmd_history_quotation"):
            args["body"] = _quantapi_history_body(args)
        if credential_transport_blocked(endpoint):
            raise ProviderError("credential_transport_blocked")
        limit = query.parameters.get("limit", MAX_ROWS)
        if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
            raise ProviderError("external_limit_invalid")
        reflected: list[str] = []
        async with asyncio.timeout(DEADLINE):
            async with httpx.AsyncClient(
                transport=transport,
                timeout=DEADLINE,
                trust_env=False,
                follow_redirects=False,
                headers={
                    "User-Agent": "Mozilla/5.0 ResearchWorkbench/1.0",
                    "Accept": "application/json,text/csv,application/xml,text/html",
                },
            ) as client:
                headers = dict(endpoint.get("headers", {}))
                if endpoint.get("specialAuth"):
                    secret, reflected = await credentials(client, source_id, connections)
                    (raw, content_type, encoding), exchanged = await cicc_request(
                        client, url, args, secret
                    )
                    reflected.extend(exchanged)
                else:
                    if endpoint.get("auth"):
                        secret, sensitive = await credentials(client, source_id, connections)
                        reflected.extend(sensitive)
                        auth = endpoint["auth"]
                        headers[auth["header"]] = auth.get("prefix", "") + secret
                    request = {"headers": headers}
                    if args.get("query"):
                        # Preserve fixed query parameters while applying explicit business filters.
                        combined = dict(httpx.URL(url).params)
                        combined.update(args["query"])
                        request["params"] = combined
                    if endpoint["method"] == "POST":
                        request["json"] = args.get("body", {})
                    raw, content_type, encoding = await bounded_response(
                        client, endpoint["method"], url, **request
                    )
        if any(value and value.encode() in raw for value in reflected):
            raise ProviderError("credential_reflection")
        if reflected:
            text = raw.decode(encoding, errors="replace")
            if "json" in content_type or text.lstrip().startswith(("{", "[")):
                try:
                    decoded = json.loads(text)
                except ValueError:
                    raise ProviderError("external_invalid_json") from None
                # Inspect envelope metadata and keys before selecting rows: a
                # JSON-escaped secret must never enter archived original bytes.
                if _rows_reflect_credentials(decoded, reflected):
                    raise ProviderError("credential_reflection")
        business = (
            (spdr_projection(raw), 4, True)
            if (source_id, dataset) == ("ext_spdr", "gld")
            else external_business_envelope(source_id, dataset, raw)
        )
        if business is None:
            rows = response_rows(raw, content_type, encoding)
            rows, provider_total, complete_page = numeric_envelope(
                source_id, dataset, raw, rows, args
            )
        else:
            rows, provider_total, complete_page = business
        if _rows_reflect_credentials(rows, reflected):
            raise ProviderError("credential_reflection")
        result.rows = rows[:limit]
        result.status = (
            "partial"
            if len(rows) > limit or complete_page is False
            else "snapshot" if rows else "empty"
        )
        if (
            (source_id, dataset) == ("ext_ths", "cmd_history_quotation")
            and result.rows
            and all(
                value is None
                for row in result.rows
                for key, value in row.items()
                if key not in {"asset", "date"}
            )
        ):
            result.status = "partial"
            result.missing.append("history_values_missing")
        result.provider_total = provider_total
        result.pagination_complete = len(rows) <= limit and complete_page is True
        if complete_page is False:
            result.missing.append("remaining_provider_pages")
        result.raw = [raw]
        result.raw_bytes = len(raw)
        result.pages_fetched = 1
        result.source_url = url
        if (source_id, dataset) in OFFICIAL_NUMERIC:
            result.source_url = str(httpx.URL(url).copy_merge_params(args.get("query", {})))
        result.as_of = datetime.now(UTC).isoformat()
        result.fields = {
            key: {"type": "source", "unit": "provider_defined"}
            for row in result.rows
            for key in row
        }
        if (source_id, dataset) == ("ext_spdr", "gld"):
            result.fields = spdr_fields()
            result.metadata = {
                "schema_version": SPDR_NUMERIC_CONTRACT,
                "provider_semantics_revision": SPDR_NUMERIC_CONTRACT,
                "upstream_id": "spdrgoldshares",
                "availability_basis": "first_observed",
                "revision_policy": "first_observed_not_historical_vintage",
                "historical_point_in_time": False,
                "formal_backtest_eligible": False,
                "units": dict(SPDR_METRIC_UNITS),
            }
        if (source_id, dataset) in EXTERNAL_ENVELOPES:
            result.metadata["schema_version"] = EXTERNAL_ENVELOPE_CONTRACT
            if (source_id, dataset) == ("ext_danjuan", "history") or not result.rows:
                result.status = "partial"
                result.missing.append("no_observation_rows")
        if (source_id, dataset) in OFFICIAL_NUMERIC:
            result.metadata = {
                "schema_version": OFFICIAL_NUMERIC_CONTRACT,
                "provider_semantics_revision": OFFICIAL_NUMERIC_CONTRACT,
                "revision_policy": "first_observed_not_historical_vintage",
            }
            result.fields[
                (
                    "date"
                    if source_id == "ext_worldbank"
                    else "effectiveDate" if source_id == "ext_nyfed" else "record_date"
                )
            ] = {
                "type": "date",
                "unit": "year" if source_id == "ext_worldbank" else "date",
                "role": "reference_period_not_available_at",
            }
            numeric = (
                ("value",)
                if source_id == "ext_worldbank"
                else (
                    _CASH_FIELDS
                    if source_id == "ext_treasury"
                    else (
                        "percentRate",
                        "average30day",
                        "average90day",
                        "average180day",
                        "index",
                        "volumeInBillions",
                    )
                )
            )
            for field in numeric:
                if field in result.fields:
                    unit = (
                        "percent_per_year"
                        if source_id == "ext_worldbank"
                        else "USD_million" if source_id == "ext_treasury" else "provider_defined"
                    )
                    result.fields[field] = {"type": "number", "unit": unit}
            if source_id == "ext_nyfed":
                for field in result.fields:
                    if field in _RATE_PERCENT_FIELDS:
                        result.fields[field] = {"type": "number", "unit": "percent"}
                    elif field == "volumeInBillions":
                        result.fields[field] = {"type": "number", "unit": "USD_billion"}
            if source_id == "ext_treasury":
                result.metadata["units"] = {field: "USD_million" for field in _CASH_FIELDS}
            missing_values = any(
                (
                    (not any(_number(row.get(field)) for field in numeric if field in row))
                    if source_id == "ext_treasury"
                    else any(
                        not _number(row[field])
                        for field in (
                            ("value",)
                            if source_id == "ext_worldbank"
                            else (
                                ("average30day", "average90day", "average180day", "index")
                                if row["type"] == "SOFRAI"
                                else ("percentRate", "volumeInBillions")
                            )
                        )
                    )
                )
                for row in result.rows
            )
            if missing_values:
                result.status = "partial"
                result.missing.append("numeric_values_missing")
        result.limitations = ["single_response_not_complete_history", "provider_native_fields"]
        if len(rows) > limit:
            result.limitations.append("row_limit")
    except asyncio.CancelledError:
        log.info("external_source_cancelled", source=source_id)
        raise
    except (ProviderError, httpx.HTTPError, TimeoutError, ValueError, LookupError) as exc:
        reason = (
            str(exc)
            if isinstance(exc, ProviderError)
            else (
                "deadline"
                if isinstance(exc, TimeoutError)
                else "external_transport_or_schema_error"
            )
        )
        result.status = "failed"
        result.rows = []
        result.raw = []
        result.limitations = [reason]
        log.warning("external_source_failed", source=source_id, reason=reason)
    return result
