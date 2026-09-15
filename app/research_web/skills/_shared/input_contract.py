"""Strict runtime envelope validation for reviewed CPU calculators."""

from __future__ import annotations

import json
import math
import os
import stat
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Any, TypeVar

ErrorT = TypeVar("ErrorT", bound=ValueError)
ErrorFactory = Callable[[str], ErrorT]
SOURCE_KEY_LINE_SEPARATORS = frozenset("\r\n\u2028\u2029")

DATA_CONTRACT_FIELDS = frozenset(
    {
        "provider",
        "mapping_id",
        "mapping_version",
        "units",
        "date_semantics",
        "adjustment",
    }
)
DATASET_REF_FIELDS = frozenset({"dataset_id", "provider_id", "as_of", "sha256"})


def checked_number(value: Any, *, error: ErrorFactory, positive: bool = False) -> float:
    """Convert a supplied number without leaking conversion overflows."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error("invalid_field_type")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise error("invalid_number") from exc
    if not math.isfinite(result) or (positive and result <= 0):
        raise error("invalid_number")
    return result


def checked_arithmetic(value: Any, *, error: ErrorFactory) -> float:
    """Require every derived arithmetic result to remain finite."""

    try:
        return checked_number(value, error=error)
    except (ArithmeticError, OverflowError) as exc:
        raise error("invalid_number") from exc


def checked_sum(values: list[float], *, error: ErrorFactory) -> float:
    try:
        return checked_arithmetic(math.fsum(values), error=error)
    except (ArithmeticError, OverflowError) as exc:
        raise error("invalid_number") from exc


def checked_add(left: float, right: float, *, error: ErrorFactory) -> float:
    return checked_arithmetic(left + right, error=error)


def checked_subtract(left: float, right: float, *, error: ErrorFactory) -> float:
    return checked_arithmetic(left - right, error=error)


def checked_multiply(left: float, right: float, *, error: ErrorFactory) -> float:
    return checked_arithmetic(left * right, error=error)


def checked_divide(left: float, right: float, *, error: ErrorFactory) -> float:
    try:
        return checked_arithmetic(left / right, error=error)
    except (ArithmeticError, OverflowError, ZeroDivisionError) as exc:
        raise error("invalid_number") from exc


def checked_mean(values: list[float], *, error: ErrorFactory) -> float:
    if not values:
        raise error("invalid_number")
    return checked_divide(checked_sum(values, error=error), len(values), error=error)


def strict_json_dumps(value: Any, *, error: ErrorFactory) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
    except (OverflowError, ValueError) as exc:
        raise error("invalid_number") from exc


def bounded_result_rows(
    rows: Any,
    *,
    processed_input_rows: int,
    dataset_refs: list[dict[str, Any]],
    inline_limit: int = 128,
) -> tuple[Any, dict[str, Any]]:
    """Expose an explicit bounded projection after processing the full input."""

    def count(value: Any) -> int:
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return sum(len(item) for item in value.values() if isinstance(item, list))
        return 0

    total = count(rows)
    if total <= inline_limit:
        return rows, {
            "mode": "inline",
            "processed_input_rows": processed_input_rows,
            "inline_output_rows": total,
            "omitted_output_rows": 0,
            "dataset_refs": [],
        }
    if isinstance(rows, list):
        projection = rows[:inline_limit]
    elif isinstance(rows, dict):
        remaining = inline_limit
        projection = {}
        for key, value in rows.items():
            if isinstance(value, list):
                projection[key] = value[:remaining]
                remaining -= len(projection[key])
            else:
                projection[key] = value
    else:
        projection = rows
    inline_rows = count(projection)
    return projection, {
        "mode": "summary_with_dataset_refs",
        "processed_input_rows": processed_input_rows,
        "inline_output_rows": inline_rows,
        "omitted_output_rows": total - inline_rows,
        "dataset_refs": dataset_refs,
    }


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & reparse
    )


def load_relative_json(
    argument: str,
    *,
    error: ErrorFactory,
    budget: Any,
) -> tuple[Any, int]:
    """Read one contained regular JSON file without following links or replacements."""

    path = Path(argument)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        raise error("unsafe_input_path")
    try:
        root = Path.cwd().resolve(strict=True)
        current = root
        for part in path.parts:
            current /= part
            if _is_link_or_reparse(os.lstat(current)):
                raise error("unsafe_input_path")
        resolved = (root / path).resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise error("unsafe_input_path")
        before = os.stat(resolved, follow_symlinks=False)
        if _is_link_or_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise error("unsafe_input_path")
        budget.add_input(rows=0, bytes_count=before.st_size)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(resolved, flags)
        try:
            opened = os.fstat(descriptor)
            if (
                _is_link_or_reparse(opened)
                or not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino, opened.st_size)
                != (before.st_dev, before.st_ino, before.st_size)
            ):
                raise error("unsafe_input_path")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read()
            after = os.stat(resolved, follow_symlinks=False)
            if (after.st_dev, after.st_ino, after.st_size) != (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
            ):
                raise error("unsafe_input_path")
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise error("input_unavailable") from exc
    try:
        return json.loads(raw.decode("utf-8")), len(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise error("invalid_input") from exc


def strict_object(
    value: Any,
    *,
    required: frozenset[str],
    allowed: frozenset[str],
    error: ErrorFactory,
) -> dict[str, Any]:
    """Return an exact object or fail without including user content."""
    if not isinstance(value, dict):
        raise error("invalid_field_type")
    if set(value) - allowed:
        raise error("unknown_field")
    if required - set(value):
        raise error("missing_required_field")
    return value


def iso_day(value: Any, *, error: ErrorFactory) -> str:
    if not isinstance(value, str) or not value:
        raise error("invalid_field_type")
    if (
        len(value) != 10
        or value[4] != "-"
        or value[7] != "-"
        or not (value[:4] + value[5:7] + value[8:]).isdigit()
    ):
        raise error("invalid_date")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise error("invalid_date") from exc


def reject_future(value: Any, *, as_of: str, error: ErrorFactory) -> str:
    normalized = iso_day(value, error=error)
    if normalized > as_of:
        raise error("future_data")
    return normalized


def validate_source_hashes(
    payload: Mapping[str, Any],
    *,
    error: ErrorFactory,
) -> tuple[dict[str, str], list[str]]:
    """Validate canonical source digests or mark missing provenance explicitly."""
    if "source_hashes" not in payload:
        return {}, ["source_hashes_missing"]
    value = payload["source_hashes"]
    if not isinstance(value, dict):
        raise error("invalid_source_hashes")
    if not value:
        return {}, ["source_hashes_missing"]
    normalized: dict[str, str] = {}
    for source, digest in value.items():
        if (
            not isinstance(source, str)
            or not source
            or source != source.strip()
            or any(separator in source for separator in SOURCE_KEY_LINE_SEPARATORS)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest.lower())
        ):
            raise error("invalid_source_hashes")
        normalized[source] = digest.lower()
    return normalized, []


def validate_data_contract(
    value: Any,
    *,
    mapping_id: str,
    mapping_version: str,
    units: Mapping[str, str],
    date_semantics: str,
    adjustment: str,
    providers: frozenset[str],
    error: ErrorFactory,
) -> dict[str, Any]:
    """Require the exact reviewed provider mapping and measurement semantics."""
    if not isinstance(value, dict) or set(value) != DATA_CONTRACT_FIELDS:
        raise error("data_not_equivalent")
    provider = value.get("provider")
    supplied_units = value.get("units")
    if (
        not isinstance(provider, str)
        or provider not in providers
        or value.get("mapping_id") != mapping_id
        or value.get("mapping_version") != mapping_version
        or not isinstance(supplied_units, dict)
        or supplied_units != dict(units)
        or value.get("date_semantics") != date_semantics
        or value.get("adjustment") != adjustment
    ):
        raise error("data_not_equivalent")
    return value


def validate_dataset_refs(
    value: Any,
    *,
    as_of: str,
    providers: frozenset[str],
    error: ErrorFactory,
) -> list[dict[str, Any]]:
    """Validate exact provenance references and reject look-ahead data."""
    if not isinstance(value, list) or not value:
        raise error("invalid_field_type")
    normalized: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise error("invalid_dataset_ref")
        if set(raw) - DATASET_REF_FIELDS:
            raise error("unknown_field")
        if DATASET_REF_FIELDS - set(raw):
            raise error("invalid_dataset_ref")
        dataset_id = raw.get("dataset_id")
        provider_id = raw.get("provider_id")
        digest = raw.get("sha256")
        if (
            not isinstance(dataset_id, str)
            or not dataset_id.strip()
            or not isinstance(provider_id, str)
            or provider_id not in providers
        ):
            raise error("data_not_equivalent")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest.lower())
        ):
            raise error("invalid_dataset_ref")
        normalized.append(
            {
                "dataset_id": dataset_id.strip(),
                "provider_id": provider_id,
                "as_of": reject_future(raw.get("as_of"), as_of=as_of, error=error),
                "sha256": digest.lower(),
            }
        )
    return normalized


def safe_error_payload(exc: ValueError) -> dict[str, Any]:
    """Expose only stable error codes and explicitly safe budget metadata."""
    code = getattr(exc, "code", "invalid_input")
    payload: dict[str, Any] = {"code": code, "message": code}
    metadata = getattr(exc, "metadata", None)
    if isinstance(metadata, dict):
        allowed = {"resource", "limit", "actual", "reduce_scope"}
        safe = {key: metadata[key] for key in sorted(allowed & set(metadata))}
        if safe:
            payload["metadata"] = safe
    return {"error": payload}
