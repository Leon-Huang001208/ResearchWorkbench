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
MAX_DATASET_REFS = 32
MAX_SOURCE_HASHES = 32
MAX_TEXT_CHARS = 4_096
MAX_RESULT_BYTES = 64 * 1_024


class ContractTooLarge(ValueError):
    """Stable, content-free rejection for bounded contract collections or output."""

    code = "workload_too_large"

    def __init__(self, resource: str, limit: int, actual: int) -> None:
        self.metadata = {
            "resource": resource,
            "limit": limit,
            "actual": actual,
            "reduce_scope": True,
        }
        super().__init__(self.code)


def checked_text(value: Any, *, error: ErrorFactory) -> str:
    """Normalize a required string while bounding material copied to results."""

    if not isinstance(value, str) or not value.strip():
        raise error("invalid_field_type")
    normalized = value.strip()
    if len(normalized) > MAX_TEXT_CHARS:
        raise ContractTooLarge("text_chars", MAX_TEXT_CHARS, len(normalized))
    return normalized


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
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
    except (OverflowError, ValueError) as exc:
        raise error("invalid_number") from exc
    encoded_size = len(serialized.encode("utf-8"))
    if encoded_size > MAX_RESULT_BYTES:
        raise ContractTooLarge("result_bytes", MAX_RESULT_BYTES, encoded_size)
    return serialized


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
            "dataset_refs_reused": True,
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
        "dataset_refs_reused": True,
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
    if (
        not isinstance(argument, str)
        or path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise error("unsafe_input_path")
    if os.name == "nt":
        return _load_relative_json_windows(path, error=error, budget=budget)
    return _load_relative_json_posix(path, error=error, budget=budget)


def _load_relative_json_posix(path: Path, *, error: ErrorFactory, budget: Any) -> tuple[Any, int]:
    """Open every component relative to an already-open trusted directory fd."""

    directory_flag = getattr(os, "O_DIRECTORY", 0)
    nofollow_flag = getattr(os, "O_NOFOLLOW", 0)
    if not directory_flag or not nofollow_flag:
        raise error("unsafe_input_path")
    directory_access = getattr(os, "O_SEARCH", os.O_RDONLY)
    directory_fds: list[int] = []
    descriptor: int | None = None
    try:
        current_fd = os.open(".", directory_access | directory_flag | nofollow_flag)
        directory_fds.append(current_fd)
        for component in path.parts[:-1]:
            next_fd = os.open(
                component,
                directory_access | directory_flag | nofollow_flag,
                dir_fd=current_fd,
            )
            opened_directory = os.fstat(next_fd)
            if _is_link_or_reparse(opened_directory) or not stat.S_ISDIR(opened_directory.st_mode):
                raise error("unsafe_input_path")
            directory_fds.append(next_fd)
            current_fd = next_fd
        descriptor = os.open(path.parts[-1], os.O_RDONLY | nofollow_flag, dir_fd=current_fd)
        opened = os.fstat(descriptor)
        if _is_link_or_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise error("unsafe_input_path")
        budget.add_input(rows=0, bytes_count=opened.st_size)
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read()
        named = os.stat(path.parts[-1], dir_fd=current_fd, follow_symlinks=False)
        if _is_link_or_reparse(named) or (named.st_dev, named.st_ino, named.st_size) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
        ):
            raise error("unsafe_input_path")
    except OSError as exc:
        raise error("unsafe_input_path") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for directory_fd in reversed(directory_fds):
            os.close(directory_fd)
    return _decode_json(raw, error=error)


def _load_relative_json_windows(path: Path, *, error: ErrorFactory, budget: Any) -> tuple[Any, int]:
    """Verify the opened Windows handle resolves to the requested non-reparse file."""

    descriptor: int | None = None
    try:
        root = Path.cwd().resolve(strict=True)
        candidate = root.joinpath(*path.parts)
        current = root
        for component in path.parts:
            current /= component
            if _is_link_or_reparse(os.lstat(current)):
                raise error("unsafe_input_path")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise error("unsafe_input_path")
        descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        opened = os.fstat(descriptor)
        if _is_link_or_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise error("unsafe_input_path")
        final_path = _windows_final_path(descriptor)
        if final_path is None or os.path.normcase(final_path) != os.path.normcase(str(resolved)):
            raise error("unsafe_input_path")
        budget.add_input(rows=0, bytes_count=opened.st_size)
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read()
        after = os.stat(resolved, follow_symlinks=False)
        if (after.st_dev, after.st_ino, after.st_size) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
        ):
            raise error("unsafe_input_path")
    except OSError as exc:
        raise error("unsafe_input_path") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return _decode_json(raw, error=error)


def _windows_final_path(descriptor: int) -> str | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        import msvcrt

        buffer = ctypes.create_unicode_buffer(32_768)
        length = ctypes.windll.kernel32.GetFinalPathNameByHandleW(  # type: ignore[attr-defined]
            msvcrt.get_osfhandle(descriptor), buffer, len(buffer), 0
        )
        if not length or length >= len(buffer):
            return None
        value = buffer.value
        return value.removeprefix("\\\\?\\")
    except (AttributeError, OSError, ValueError):
        return None


def _decode_json(raw: bytes, *, error: ErrorFactory) -> tuple[Any, int]:
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
    if len(value) > MAX_SOURCE_HASHES:
        raise ContractTooLarge("source_hashes", MAX_SOURCE_HASHES, len(value))
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
    if len(value) > MAX_DATASET_REFS:
        raise ContractTooLarge("dataset_refs", MAX_DATASET_REFS, len(value))
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
        normalized_id = checked_text(dataset_id, error=error)
        normalized.append(
            {
                "dataset_id": normalized_id,
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
