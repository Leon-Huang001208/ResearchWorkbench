"""Validate the fixed KAPSARC BGS mirror; metadata dates are not disclosure dates."""

import csv
import hashlib
import io
import json
import math
import re
import unicodedata
from datetime import datetime
from typing import Any

from core.observability import get_logger

from .providers import MAX_RESPONSE_BYTES, MAX_ROWS, ProviderError

log = get_logger(__name__)
KAPSARC_NUMERIC_CONTRACT = "kapsarc-bgs-gold-mine-kg-v1"
KAPSARC_METADATA_URL = (
    "https://datasource.kapsarc.org/api/v2/catalog/datasets/production-of-gold-mine"
)
KAPSARC_UNITS = {"production": "kg", "production_kg": "kg"}
_COLUMNS = ("country", "sub_commodity", "year", "production")
_TYPES = ("text", "text", "date", "double")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _text(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 512
        or value.strip() != value
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ValueError("invalid_text")
    return value


def kapsarc_metadata(metadata: bytes) -> dict[str, Any]:
    """Return validated count and immutable field-dictionary provenance, never PIT."""
    try:
        if not isinstance(metadata, bytes) or not 1 <= len(metadata) <= MAX_RESPONSE_BYTES:
            raise ValueError("metadata_size")
        body = json.loads(metadata.decode("utf-8"), object_pairs_hook=_object)
        dataset = body["dataset"]
        defaults = dataset["metas"]["default"]
        custom = dataset["metas"]["custom"]
        if (
            dataset["dataset_id"] != "production-of-gold-mine"
            or dataset["visibility"] != "domain"
            or dataset["has_records"] is not True
            or dataset["data_visible"] is not True
            or custom["data-classification"] != ["Public"]
            or custom["unit-of-measure"] != "kilograms"
            or defaults["publisher"] != "British Geological Survey"
            or defaults["title"] != "Production of Gold, Mine"
        ):
            raise ValueError("metadata_identity_or_unit")
        count = defaults["records_count"]
        if type(count) is not int or not 1 <= count <= MAX_ROWS:
            raise ValueError("metadata_count")
        fields = dataset["fields"]
        if not isinstance(fields, list) or len(fields) != len(_COLUMNS):
            raise ValueError("metadata_fields")
        if [(item["name"], item["type"]) for item in fields] != list(zip(_COLUMNS, _TYPES)):
            raise ValueError("metadata_fields")
        evidence: dict[str, Any] = {
            "source_url": KAPSARC_METADATA_URL,
            "sha256": hashlib.sha256(metadata).hexdigest(),
            "records_count": count,
            "unit": "kilograms",
        }
        for field in ("data_processed", "modified"):
            stamp = _text(defaults[field])
            if datetime.fromisoformat(stamp).tzinfo is None:
                raise ValueError("metadata_timestamp")
            evidence[field] = stamp
        return {"records_count": count, "field_dictionary_evidence": evidence}
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        log.warning("kapsarc_metadata_invalid", source="ext_kapsarc")
        raise ProviderError("kapsarc_metadata_invalid") from None


def kapsarc_projection(raw_csv: bytes, metadata: bytes) -> list[dict[str, Any]]:
    """Preserve source decimals and country labels; validate full export before slicing."""
    summary = kapsarc_metadata(metadata)
    try:
        if not isinstance(raw_csv, bytes) or not 1 <= len(raw_csv) <= MAX_RESPONSE_BYTES:
            raise ValueError("csv_size")
        text = raw_csv.decode("utf-8-sig")
        if not text.endswith("\n"):
            raise ValueError("csv_truncated_record")
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=";", strict=True)
        if next(reader) != list(_COLUMNS):
            raise ValueError("csv_header")
        rows: list[dict[str, Any]] = []
        keys: set[tuple[str, ...]] = set()
        for values in reader:
            if len(values) != 4 or len(rows) >= MAX_ROWS:
                raise ValueError("csv_shape_or_count")
            country, commodity, year, production = [_text(value) for value in values]
            if re.fullmatch(r"[0-9]{4}", year) is None or not 1 <= int(year) <= 9999:
                raise ValueError("invalid_year")
            if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", production) is None:
                raise ValueError("invalid_number")
            numeric = float(production)
            if not math.isfinite(numeric) or numeric < 0:
                raise ValueError("invalid_number")
            key = (country, commodity, year)
            if key in keys:
                raise ValueError("duplicate_observation")
            keys.add(key)
            rows.append(dict(zip(_COLUMNS, values), production_kg=numeric))
        if len(rows) != summary["records_count"]:
            raise ValueError("csv_record_count_mismatch")
        return rows
    except (ValueError, TypeError, OverflowError, csv.Error, StopIteration):
        log.warning("kapsarc_csv_invalid", source="ext_kapsarc")
        raise ProviderError("kapsarc_numeric_schema_invalid") from None


def kapsarc_fields() -> dict[str, dict[str, str]]:
    """Fresh field definitions for source originals and the sole typed projection."""
    return {
        "country": {"type": "string", "unit": "source_country", "role": "source_original"},
        "sub_commodity": {"type": "string", "unit": "source_commodity", "role": "source_original"},
        "year": {"type": "string", "unit": "year", "role": "reference_period_not_available_at"},
        "production": {"type": "string", "unit": "kg", "role": "source_original"},
        "production_kg": {"type": "number", "unit": "kg"},
    }
