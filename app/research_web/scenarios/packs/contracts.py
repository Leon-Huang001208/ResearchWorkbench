"""Strict in-memory contracts. No filesystem, network, or authority operations."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, date, datetime
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from core.observability import get_logger

from .record_contracts import RECORD_SCHEMAS

log = get_logger(__name__)
MAX_ROWS = 50_000
MAX_BYTES = 64 * 1024 * 1024


class PackError(ValueError):
    """Content-free stable failure; callers must not expose private inputs."""

    def __init__(self, code: str):
        self.code = code
        log.warning("research_pack_rejected code=%s", code)
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PackError(code)


def number(value: Any) -> float:
    require(not isinstance(value, bool) and isinstance(value, (int, float)), "number_invalid")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise PackError("number_invalid") from exc
    require(math.isfinite(result), "number_nonfinite")
    return result


def instant(value: Any) -> datetime:
    require(isinstance(value, str), "as_of_precision_required")
    require(
        bool(
            re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
                value,
            )
        ),
        "as_of_precision_required",
    )
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PackError("instant_invalid") from exc
    require(result.tzinfo is not None, "as_of_precision_required")
    return result.astimezone(UTC)


def day(value: str) -> date:
    try:
        result = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise PackError("date_invalid") from exc
    require(result.isoformat() == value, "date_invalid")
    return result


def security(value: Any) -> tuple[str, str, str, str]:
    require(
        isinstance(value, dict)
        and set(value) == {"security_id", "market", "asset_class", "currency"},
        "security_invalid",
    )
    require(
        all(isinstance(x, str) and 0 < len(x) <= 4096 for x in value.values()), "security_invalid"
    )
    require(value["asset_class"] in {"equity", "index", "fund"}, "security_invalid")
    return tuple(value[k] for k in ("security_id", "market", "asset_class", "currency"))


def encoded(value: Any, limit: int = MAX_BYTES) -> bytes:
    """Stream encoding counts before allocating a full serialized copy."""
    size = 0
    parts = []
    try:
        for chunk in json.JSONEncoder(
            allow_nan=False, ensure_ascii=False, separators=(",", ":")
        ).iterencode(value):
            part = chunk.encode("utf-8")
            size += len(part)
            require(size <= limit, "workload_too_large")
            parts.append(part)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        if isinstance(exc, PackError):
            raise
        raise PackError("json_invalid") from exc
    return b"".join(parts)


def validate_inputs(records: dict, parameters: dict) -> tuple[dict, datetime, int]:
    require(isinstance(records, dict) and isinstance(parameters, dict), "input_invalid")
    require(set(records) <= set(RECORD_SCHEMAS), "unknown_record_kind")
    require(all(isinstance(rows, list) for rows in records.values()), "records_invalid")
    for kind in ("valuation", "exchange-session"):
        require(len(records.get(kind, [])) <= 5000, "workload_too_large")
    require(len(records.get("daily-price", [])) <= 10000, "workload_too_large")
    count = sum(len(rows) for rows in records.values())
    require(count <= MAX_ROWS, "workload_too_large")
    encoded({"records": records, "parameters": parameters})
    cutoff = instant(parameters.get("as_of"))
    seen = set()
    for kind, rows in records.items():
        validator = Draft202012Validator(RECORD_SCHEMAS[kind], format_checker=FormatChecker())
        for row in rows:
            require(not any(validator.iter_errors(row)), "record_contract_invalid")
            require(row["row_id"] not in seen, "duplicate_row_id")
            seen.add(row["row_id"])
            require(instant(row["origin"]["observed_at"]) <= cutoff, "future_data")
            published = row["origin"]["published_at"]
            require(published is None or instant(published) <= cutoff, "future_data")
            if "security" in row:
                security(row["security"])
            for key in ("value", "lower", "upper", "weight", "close", "shares", "float_shares"):
                if key in row and row[key] is not None:
                    number(row[key])
    return records, cutoff, count


def result(
    method: str,
    count: int,
    rows: list,
    metrics: dict,
    missing: list | None = None,
    rejected: list | None = None,
    limitations: list | None = None,
    status: str | None = None,
    source_refs: list | None = None,
    parameters: dict | None = None,
    input_sha256: str | None = None,
) -> dict:
    encoded(rows, 16 * 1024 * 1024)
    missing = missing or []
    full_parameters = parameters or {}

    def project_parameter(value):
        if isinstance(value, list):
            return {
                "input_collection_sha256": hashlib.sha256(encoded(value)).hexdigest(),
                "item_count": len(value),
            }
        if isinstance(value, dict):
            return {key: project_parameter(item) for key, item in value.items()}
        return value

    parameter_projection = project_parameter(full_parameters)
    output = {
        "schema_version": 1,
        "method": method,
        "method_version": "1.0.0",
        "status": status or ("partial" if missing else "complete"),
        "host_qualification": "NOT_RUN",
        "research_quality": "NOT_RUN",
        "parameters": parameter_projection,
        "input_sha256": input_sha256,
        "parameter_delivery": "collections_bound_by_input_digest",
        "method_source_binding": "host_required",
        "processed_input_rows": count,
        "metrics": metrics,
        "rows": rows[:128],
        "row_delivery": {
            "mode": "inline" if len(rows) <= 128 else "summary_with_source_refs",
            "total_output_rows": len(rows),
            "inline_output_rows": min(128, len(rows)),
            "omitted_output_rows": max(0, len(rows) - 128),
        },
        "missing": missing,
        "rejected_rows": rejected or [],
        "source_refs": source_refs or [],
        "limitations": [
            "source_format_not_authority",
            "host_readback_rights_pit_required",
            "not_vendor_equivalence",
        ]
        + (limitations or []),
    }
    # Hash covers the receipt before its own digest. Not a signed execution authority.
    output["result_sha256"] = hashlib.sha256(encoded(output, 65536)).hexdigest()
    encoded(output, 65536)
    log.info(
        "research_pack_calculated method=%s rows=%d status=%s", method, count, output["status"]
    )
    return output
