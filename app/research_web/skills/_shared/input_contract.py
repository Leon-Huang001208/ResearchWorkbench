"""Strict runtime envelope validation for reviewed CPU calculators."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from typing import Any, TypeVar

ErrorT = TypeVar("ErrorT", bound=ValueError)
ErrorFactory = Callable[[str], ErrorT]

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
    if not isinstance(value, str) or not value.strip():
        raise error("invalid_field_type")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise error("invalid_date") from exc


def reject_future(value: Any, *, as_of: str, error: ErrorFactory) -> str:
    normalized = iso_day(value, error=error)
    if normalized > as_of:
        raise error("future_data")
    return normalized


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
